#!/usr/bin/env python3
# MCP Server for Super Productivity Integration

import asyncio
from datetime import date
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions


class SuperProductivityMCPServer:
    def __init__(self):
        self.server = Server("super-productivity")
        self.setup_directories()
        self.setup_logging()
        self.setup_tools()
        
    def setup_directories(self):
        if os.name == 'nt':  # Windows
            data_dir = os.environ.get('APPDATA', os.path.expanduser('~/AppData/Roaming'))
        else:  # Linux/Mac
            data_dir = os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))
        
        self.base_dir = Path(data_dir) / 'super-productivity-mcp'
        self.command_dir = self.base_dir / 'plugin_commands'
        self.response_dir = self.base_dir / 'plugin_responses'
        
        # Create directories
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.command_dir.mkdir(parents=True, exist_ok=True)
        self.response_dir.mkdir(parents=True, exist_ok=True)
        
        logging.info(f"MCP Server using directory: {self.base_dir}")
        logging.info(f"Command directory: {self.command_dir}")
        logging.info(f"Response directory: {self.response_dir}")
        
        
    def setup_logging(self):
        log_file = self.base_dir / 'mcp_server.log'
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stderr)
            ]
        )
        
    def setup_tools(self):
        """Set up MCP tools"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            """List available tools"""
            return [
                types.Tool(
                    name="create_task",
                    description="Create a new task in Super Productivity. When users provide natural language with time/date references, convert them to Super Productivity syntax in the title field.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Task title with Super Productivity syntax. Convert natural language time/date references to @syntax using days/weeks/months from TODAY (e.g., 'tomorrow' -> '@1days', 'Friday at 3pm' -> '@fri 3pm', 'next week' -> '@7days', 'push back a week' -> '@14days' if task was already a week out). Use @Xdays, @Yweeks, or @Zmonths where X/Y/Z is the number from today. Add #tags for urgency/priority and +projects as needed."
                            },
                            "notes": {
                                "type": "string",
                                "description": "Task notes/description"
                            },
                            "project_id": {
                                "type": "string",
                                "description": "Project ID to assign task to"
                            },
                            "parent_id": {
                                "type": "string",
                                "description": "Parent task ID for subtasks"
                            }
                        },
                        "required": ["title"]
                    }
                ),
                types.Tool(
                    name="get_tasks",
                    description="Get tasks from Super Productivity with optional filtering. Note: Filtering happens server-side after fetching all tasks (SP has no database indexes, so this is same O(n) complexity as filtering in SP itself).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "include_done": {
                                "type": "boolean",
                                "description": "Include completed tasks",
                                "default": True
                            },
                            "tag_id": {
                                "type": "string",
                                "description": "Filter tasks by tag ID (only returns tasks with this tag)"
                            },
                            "project_id": {
                                "type": "string",
                                "description": "Filter tasks by project ID"
                            },
                            "parents_only": {
                                "type": "boolean",
                                "description": "Only return parent tasks (exclude subtasks). Useful for triage.",
                                "default": False
                            },
                            "overdue": {
                                "type": "boolean",
                                "description": "Only return tasks with dueDay before today. These are failed schedules needing re-triage.",
                                "default": False
                            },
                            "unscheduled": {
                                "type": "boolean",
                                "description": "Only return tasks with no dueDay AND no dueWithTime set. These have never been scheduled.",
                                "default": False
                            }
                        }
                    }
                ),
                types.Tool(
                    name="update_task",
                    description="Update an existing task. When users provide natural language with time/date references, convert them to Super Productivity syntax in the title field.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "task_id": {
                                "type": "string",
                                "description": "Task ID to update"
                            },
                            "title": {
                                "type": "string",
                                "description": "New task title with Super Productivity syntax. Convert natural language time/date references to @syntax using days/weeks/months from TODAY (e.g., 'push back a week' -> '@14days' if task was already a week out, 'move to next Friday' -> '@5days' if next Friday is 5 days from today, 'reschedule for tomorrow' -> '@1days'). Use @Xdays, @Yweeks, or @Zmonths where X/Y/Z is the number from today. Add #tags for urgency/priority and +projects as needed."
                            },
                            "notes": {
                                "type": "string",
                                "description": "New task notes"
                            },
                            "is_done": {
                                "type": "boolean",
                                "description": "Mark task as done/undone"
                            },
                            "time_estimate": {
                                "type": "integer",
                                "description": "Time estimate in milliseconds"
                            },
                            "time_spent": {
                                "type": "integer",
                                "description": "Time spent in milliseconds"
                            },
                            "tag_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Replace all tags on the task with this list of tag IDs. Use add_tag_to_task/remove_tag_from_task for incremental changes."
                            },
                            "due_day": {
                                "type": ["string", "null"],
                                "description": "Due date in YYYY-MM-DD format, or null/empty string to clear the date and make task unscheduled."
                            }
                        },
                        "required": ["task_id"]
                    }
                ),
                types.Tool(
                    name="complete_and_archive_task",
                    description="Complete a task (mark as done) in Super Productivity - NOTE: True deletion is not supported",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "task_id": {
                                "type": "string",
                                "description": "Task ID to complete"
                            }
                        },
                        "required": ["task_id"]
                    }
                ),
                types.Tool(
                    name="add_tag_to_task",
                    description="Add a tag to a task. This appends to existing tags without removing them.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "task_id": {
                                "type": "string",
                                "description": "Task ID to add tag to"
                            },
                            "tag_id": {
                                "type": "string",
                                "description": "Tag ID to add"
                            }
                        },
                        "required": ["task_id", "tag_id"]
                    }
                ),
                types.Tool(
                    name="remove_tag_from_task",
                    description="Remove a tag from a task. Other tags remain unchanged.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "task_id": {
                                "type": "string",
                                "description": "Task ID to remove tag from"
                            },
                            "tag_id": {
                                "type": "string",
                                "description": "Tag ID to remove"
                            }
                        },
                        "required": ["task_id", "tag_id"]
                    }
                ),
                types.Tool(
                    name="reorder_tasks",
                    description="Reorder tasks within a project or subtasks within a parent task. Uses SP's native PluginAPI.reorderTasks() - task order is determined by array position. Perfect for LLM-assisted prioritization via binary comparisons.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "task_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Array of task IDs in the desired order (first = highest priority)"
                            },
                            "context_id": {
                                "type": "string",
                                "description": "The project ID (for reordering project tasks) or parent task ID (for reordering subtasks)"
                            },
                            "context_type": {
                                "type": "string",
                                "enum": ["project", "task"],
                                "description": "Whether reordering tasks in a project or subtasks of a parent task"
                            }
                        },
                        "required": ["task_ids", "context_id", "context_type"]
                    }
                ),
                types.Tool(
                    name="get_projects",
                    description="Get all projects from Super Productivity",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                types.Tool(
                    name="create_project",
                    description="Create a new project",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Project title"
                            },
                            "description": {
                                "type": "string",
                                "description": "Project description"
                            },
                            "color": {
                                "type": "string",
                                "description": "Project color (hex code)"
                            }
                        },
                        "required": ["title"]
                    }
                ),
                types.Tool(
                    name="update_project",
                    description="Update an existing project (title, description, color)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "Project ID to update"
                            },
                            "title": {
                                "type": "string",
                                "description": "New project title"
                            },
                            "description": {
                                "type": "string",
                                "description": "New project description"
                            },
                            "color": {
                                "type": "string",
                                "description": "New project color (hex code)"
                            }
                        },
                        "required": ["project_id"]
                    }
                ),
                types.Tool(
                    name="move_task_to_project",
                    description="Move a task to a different project",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "task_id": {
                                "type": "string",
                                "description": "Task ID to move"
                            },
                            "project_id": {
                                "type": "string",
                                "description": "Target project ID"
                            }
                        },
                        "required": ["task_id", "project_id"]
                    }
                ),
                types.Tool(
                    name="get_tags",
                    description="Get all tags from Super Productivity",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                types.Tool(
                    name="create_tag",
                    description="Create a new tag",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Tag title"
                            },
                            "color": {
                                "type": "string",
                                "description": "Tag color (hex code)"
                            }
                        },
                        "required": ["title"]
                    }
                ),
                types.Tool(
                    name="update_tag",
                    description="Update an existing tag (title, color, icon)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tag_id": {
                                "type": "string",
                                "description": "Tag ID to update"
                            },
                            "title": {
                                "type": "string",
                                "description": "New tag title"
                            },
                            "color": {
                                "type": "string",
                                "description": "New tag color (hex code)"
                            },
                            "icon": {
                                "type": "string",
                                "description": "New tag icon (emoji or material icon name)"
                            }
                        },
                        "required": ["tag_id"]
                    }
                ),
                types.Tool(
                    name="show_notification",
                    description="Show a notification in Super Productivity",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "message": {
                                "type": "string",
                                "description": "Notification message"
                            },
                            "type": {
                                "type": "string",
                                "enum": ["success", "info", "warning", "error"],
                                "description": "Notification type",
                                "default": "info"
                            }
                        },
                        "required": ["message"]
                    }
                ),
                types.Tool(
                    name="debug_directories",
                    description="Debug the communication directories and show their status",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(
            name: str, arguments: Dict[str, Any]
        ) -> List[types.TextContent]:
            """Handle tool calls"""
            try:
                if name == "create_task":
                    result = await self.create_task(arguments)
                elif name == "get_tasks":
                    result = await self.get_tasks(arguments)
                elif name == "update_task":
                    result = await self.update_task(arguments)
                elif name == "complete_and_archive_task":
                    result = await self.complete_and_archive_task(arguments)
                elif name == "add_tag_to_task":
                    result = await self.add_tag_to_task(arguments)
                elif name == "remove_tag_from_task":
                    result = await self.remove_tag_from_task(arguments)
                elif name == "reorder_tasks":
                    result = await self.reorder_tasks(arguments)
                elif name == "get_projects":
                    result = await self.get_projects(arguments)
                elif name == "create_project":
                    result = await self.create_project(arguments)
                elif name == "update_project":
                    result = await self.update_project(arguments)
                elif name == "move_task_to_project":
                    result = await self.move_task_to_project(arguments)
                elif name == "get_tags":
                    result = await self.get_tags(arguments)
                elif name == "create_tag":
                    result = await self.create_tag(arguments)
                elif name == "update_tag":
                    result = await self.update_tag(arguments)
                elif name == "show_notification":
                    result = await self.show_notification(arguments)
                elif name == "debug_directories":
                    result = await self.debug_directories(arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
                
                return [types.TextContent(type="text", text=str(result))]
                
            except Exception as e:
                logging.error(f"Error in tool {name}: {str(e)}")
                return [types.TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def send_command(self, action: str, **kwargs) -> Dict[str, Any]:
        """Send a command to Super Productivity plugin"""
        command = {
            "action": action,
            "id": f"{action}_{asyncio.get_event_loop().time()}",
            "timestamp": asyncio.get_event_loop().time(),
            **kwargs
        }
        
        # Write command file
        command_file = self.command_dir / f"{command['id']}.json"
        with open(command_file, 'w') as f:
            json.dump(command, f, indent=2)
        
        logging.info(f"Sent command: {action} -> {command_file}")
        
        # Wait for response (with timeout)
        response_file = self.response_dir / f"{command['id']}_response.json"
        
        for _ in range(30):  # Wait up to 30 seconds
            if response_file.exists():
                try:
                    with open(response_file, 'r') as f:
                        response = json.load(f)
                    
                    # Clean up response file
                    response_file.unlink()
                    
                    logging.info(f"Received response for {action}: {response.get('success', 'unknown')}")
                    return response
                    
                except Exception as e:
                    logging.error(f"Error reading response file: {e}")
                    break
                    
            await asyncio.sleep(1)
        
        # Timeout
        logging.warning(f"Timeout waiting for response to {action}")
        return {"success": False, "error": "Timeout waiting for response"}
    
    def parse_task_syntax(self, title: str) -> tuple:
        """Parse Super Productivity task syntax from title"""
        title_clean = title
        
        # Extract tags from title (format: #tagname)
        tag_matches = re.findall(r'#(\w+)', title_clean)
        title_clean = re.sub(r'\s*#\w+', '', title_clean).strip()
        
        # Extract projects from title (format: +projectname)
        project_matches = re.findall(r'\+(\w+)', title_clean)
        title_clean = re.sub(r'\s*\+\w+', '', title_clean).strip()
        
        # Extract scheduling syntax (format: @fri 4pm, @tomorrow, @2024-01-15, etc.)
        schedule_matches = re.findall(r'@(\w+(?:\s+\d+[ap]m)?)', title_clean, re.IGNORECASE)
        title_clean = re.sub(r'\s*@\w+(?:\s+\d+[ap]m)?', '', title_clean, flags=re.IGNORECASE).strip()
        
        # Extract time estimate/spent syntax (format: 10m/3h, 2h, 30m, etc.)
        time_matches = re.findall(r'(\d+[mh](?:/\d+[mh])?)', title_clean)
        title_clean = re.sub(r'\s*\d+[mh](?:/\d+[mh])?', '', title_clean).strip()
        
        return title_clean, tag_matches, project_matches, schedule_matches, time_matches
    
    async def create_task(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new task"""
        title = args.get("title", "")
        
        # Create the task data - Claude should have already converted natural language to SP syntax
        task_data = {
            "title": title,  # Use title as provided by Claude (should already have @syntax)
            "notes": args.get("notes", ""),
            "timeEstimate": args.get("time_estimate", 0),
            "projectId": args.get("project_id"),
            "parentId": args.get("parent_id"),
            "tagIds": []
        }
        
        return await self.send_command("addTask", data=task_data)
    
    async def get_tasks(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get tasks with optional server-side filtering.

        Note: SP uses IndexedDB without indexes on tagIds/projectId, so filtering
        is always O(n) whether done in SP or here. We filter server-side to reduce
        context usage when working with large task lists.

        TODO: Migrate filtering to plugin-side when SP PluginAPI supports filtered queries.
        See: https://github.com/organicmoron/SP-MCP/issues/5
        """
        result = await self.send_command("getTasks")

        if not result.get("success"):
            return result

        tasks = result.get("data", result.get("result", []))
        if not isinstance(tasks, list):
            return result

        # Filter by tag
        tag_id = args.get("tag_id")
        if tag_id:
            tasks = [t for t in tasks if tag_id in t.get("tagIds", [])]

        # Filter by project
        project_id = args.get("project_id")
        if project_id:
            tasks = [t for t in tasks if t.get("projectId") == project_id]

        # Filter out done tasks if requested
        if not args.get("include_done", True):
            tasks = [t for t in tasks if not t.get("isDone")]

        # Triage filters
        # Parents only - exclude subtasks (tasks with parentId)
        if args.get("parents_only", False):
            tasks = [t for t in tasks if not t.get("parentId")]

        # Overdue - tasks with dueDay before today (failed schedules)
        if args.get("overdue", False):
            today = date.today().isoformat()  # YYYY-MM-DD format
            tasks = [t for t in tasks if t.get("dueDay") and t.get("dueDay") < today]

        # Unscheduled - tasks with no dueDay AND no dueWithTime set
        if args.get("unscheduled", False):
            tasks = [t for t in tasks if not t.get("dueDay") and not t.get("dueWithTime")]

        # Update result with filtered tasks
        if "data" in result:
            result["data"] = tasks
        else:
            result["result"] = tasks

        return result
    
    async def update_task(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Update a task"""
        task_id = args.get("task_id")
        if not task_id:
            return {"success": False, "error": "task_id is required"}
        
        updates = {}
        
        # Handle title - Claude should have already converted natural language to SP syntax
        if "title" in args:
            updates["title"] = args["title"]
        
        if "notes" in args:
            updates["notes"] = args["notes"]
        if "is_done" in args:
            updates["isDone"] = args["is_done"]
            if args["is_done"]:
                updates["doneOn"] = asyncio.get_event_loop().time() * 1000
            else:
                updates["doneOn"] = None
        if "time_estimate" in args:
            updates["timeEstimate"] = args["time_estimate"]
        if "time_spent" in args:
            updates["timeSpent"] = args["time_spent"]
        if "tag_ids" in args:
            updates["tagIds"] = args["tag_ids"]

        # Handle due_day - can set to a date string or clear with null/empty
        if "due_day" in args:
            due_day = args["due_day"]
            if due_day is None or due_day == "" or due_day == "null":
                updates["dueDay"] = None  # Clear the date
            else:
                updates["dueDay"] = due_day  # Set to provided date

        return await self.send_command("updateTask", taskId=task_id, data=updates)
    
    async def complete_and_archive_task(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Complete a task (mark as done) - true deletion is not supported"""
        task_id = args.get("task_id")
        if not task_id:
            return {"success": False, "error": "task_id is required"}

        # Mark task as done instead of deleting
        return await self.send_command("setTaskDone", taskId=task_id)

    async def add_tag_to_task(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Add a tag to a task (appends to existing tags)"""
        task_id = args.get("task_id")
        tag_id = args.get("tag_id")

        if not task_id:
            return {"success": False, "error": "task_id is required"}
        if not tag_id:
            return {"success": False, "error": "tag_id is required"}

        return await self.send_command("addTagToTask", taskId=task_id, tagId=tag_id)

    async def remove_tag_from_task(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Remove a tag from a task"""
        task_id = args.get("task_id")
        tag_id = args.get("tag_id")

        if not task_id:
            return {"success": False, "error": "task_id is required"}
        if not tag_id:
            return {"success": False, "error": "tag_id is required"}

        return await self.send_command("removeTagFromTask", taskId=task_id, tagId=tag_id)

    async def reorder_tasks(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Reorder tasks using SP's native PluginAPI.reorderTasks().

        This uses SP's proper API - task order is stored in the project's taskIds[]
        array or parent task's subTaskIds[] array. Array position = priority.

        Perfect for LLM-assisted prioritization via binary comparisons.
        """
        task_ids = args.get("task_ids")
        context_id = args.get("context_id")
        context_type = args.get("context_type")

        if not task_ids:
            return {"success": False, "error": "task_ids array is required"}
        if not context_id:
            return {"success": False, "error": "context_id is required"}
        if context_type not in ["project", "task"]:
            return {"success": False, "error": "context_type must be 'project' or 'task'"}

        return await self.send_command(
            "reorderTasks",
            taskIds=task_ids,
            contextId=context_id,
            contextType=context_type
        )

    async def get_projects(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get all projects"""
        return await self.send_command("getAllProjects")
    
    async def create_project(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new project"""
        project_data = {
            "title": args.get("title", ""),
            "description": args.get("description", ""),
            "color": args.get("color", "#2196F3")
        }
        
        return await self.send_command("addProject", data=project_data)
    
    async def update_project(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing project"""
        project_id = args.get("project_id")
        if not project_id:
            return {"success": False, "error": "project_id is required"}

        updates = {}
        if "title" in args:
            updates["title"] = args["title"]
        if "description" in args:
            updates["description"] = args["description"]
        if "color" in args:
            updates["color"] = args["color"]

        if not updates:
            return {"success": False, "error": "No updates provided"}

        return await self.send_command("updateProject", projectId=project_id, data=updates)

    async def move_task_to_project(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Move a task to a different project"""
        task_id = args.get("task_id")
        project_id = args.get("project_id")

        if not task_id:
            return {"success": False, "error": "task_id is required"}
        if not project_id:
            return {"success": False, "error": "project_id is required"}

        return await self.send_command("moveTaskToProject", taskId=task_id, projectId=project_id)

    async def get_tags(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get all tags"""
        return await self.send_command("getAllTags")
    
    async def create_tag(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new tag"""
        tag_data = {
            "title": args.get("title", ""),
            "color": args.get("color", "#FF9800")
        }

        return await self.send_command("addTag", data=tag_data)

    async def update_tag(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing tag"""
        tag_id = args.get("tag_id")
        if not tag_id:
            return {"success": False, "error": "tag_id is required"}

        updates = {}
        if "title" in args:
            updates["title"] = args["title"]
        if "color" in args:
            updates["color"] = args["color"]
        if "icon" in args:
            updates["icon"] = args["icon"]

        return await self.send_command("updateTag", tagId=tag_id, data=updates)

    async def show_notification(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Show a notification"""
        return await self.send_command("showSnack", message=args.get("message", ""))
    
    async def debug_directories(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": True,
            "base_directory": str(self.base_dir),
            "command_directory": str(self.command_dir),
            "response_directory": str(self.response_dir),
            "directories_exist": {
                "base": self.base_dir.exists(),
                "commands": self.command_dir.exists(),
                "responses": self.response_dir.exists()
            }
        }
    
    async def run(self):
        """Run the MCP server"""
        logging.info("Starting Super Productivity MCP Server...")
        
        # Initialize server
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="super-productivity",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )


async def main():
    """Main entry point"""
    server = SuperProductivityMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())