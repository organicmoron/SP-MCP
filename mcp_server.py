#!/usr/bin/env python3
# MCP Server for Super Productivity Integration

import asyncio
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
    HABIT_FIELD_MAP = {
        "title": "title",
        "is_enabled": "isEnabled",
        "is_hide_button": "isHideButton",
        "icon": "icon",
        "type": "type",
        "is_track_streaks": "isTrackStreaks",
        "streak_min_value": "streakMinValue",
        "streak_mode": "streakMode",
        "streak_week_days": "streakWeekDays",
        "streak_weekly_frequency": "streakWeeklyFrequency",
        "countdown_duration": "countdownDuration",
    }
    HABIT_TYPES = {"ClickCounter", "StopWatch", "RepeatedCountdownReminder"}
    HABIT_STREAK_MODES = {"specific-days", "weekly-frequency"}

    def __init__(self):
        self.server = Server("super-productivity")
        self.setup_directories()
        self.setup_logging()
        self.setup_tools()
        
    def setup_directories(self):
        if os.name == 'nt':  # Windows
            data_dir = os.environ.get('APPDATA', os.path.expanduser('~/AppData/Roaming'))
        else:  # Linux/Mac
            # On macOS, Super Productivity runs in a sandbox so its plugin sees a different
            # home directory. Use the container path if it exists so paths align.
            sp_container_data = os.path.expanduser(
                '~/Library/Containers/com.super-productivity.app/Data/.local/share'
            )
            sp_container_root = os.path.expanduser(
                '~/Library/Containers/com.super-productivity.app'
            )
            if os.path.isdir(sp_container_root):
                data_dir = sp_container_data
            else:
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
                    description="Get all tasks from Super Productivity",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "include_done": {
                                "type": "boolean",
                                "description": "Include completed tasks",
                                "default": True
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
                    name="get_habits",
                    description="Get all habits from Super Productivity. Habits are represented by Super Productivity Simple Counters.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "include_disabled": {
                                "type": "boolean",
                                "description": "Include disabled habits",
                                "default": True
                            }
                        }
                    }
                ),
                types.Tool(
                    name="create_habit",
                    description="Create/register a new habit in Super Productivity.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Habit title"
                            },
                            "id": {
                                "type": "string",
                                "description": "Optional habit ID. Use only letters, numbers, hyphens, and underscores. If omitted, one is generated from the title."
                            },
                            "type": {
                                "type": "string",
                                "enum": ["ClickCounter", "StopWatch", "RepeatedCountdownReminder"],
                                "description": "Habit counter type",
                                "default": "ClickCounter"
                            },
                            "icon": {
                                "type": "string",
                                "description": "Optional Material icon name, e.g. fitness_center"
                            },
                            "is_enabled": {
                                "type": "boolean",
                                "description": "Whether the habit is enabled",
                                "default": True
                            },
                            "is_hide_button": {
                                "type": "boolean",
                                "description": "Hide the habit from quick counter buttons"
                            },
                            "is_track_streaks": {
                                "type": "boolean",
                                "description": "Whether streaks are tracked for this habit",
                                "default": True
                            },
                            "streak_min_value": {
                                "type": "number",
                                "description": "Minimum daily value required to count toward the streak"
                            },
                            "streak_mode": {
                                "type": "string",
                                "enum": ["specific-days", "weekly-frequency"],
                                "description": "Streak tracking mode",
                                "default": "specific-days"
                            },
                            "streak_week_days": {
                                "type": "object",
                                "description": "Specific active weekdays as keys 0-6 where 0 is Sunday, e.g. {\"1\": true, \"2\": true, \"3\": true, \"4\": true, \"5\": true}",
                                "additionalProperties": {"type": "boolean"}
                            },
                            "streak_weekly_frequency": {
                                "type": "integer",
                                "description": "Required completions per week for weekly-frequency streak mode"
                            },
                            "countdown_duration": {
                                "type": "integer",
                                "description": "Countdown duration in milliseconds for RepeatedCountdownReminder habits"
                            },
                            "initial_value": {
                                "type": "number",
                                "description": "Initial counter value for today",
                                "default": 0
                            }
                        },
                        "required": ["title"]
                    }
                ),
                types.Tool(
                    name="update_habit",
                    description="Edit an existing Super Productivity habit.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Habit ID"
                            },
                            "title": {
                                "type": "string",
                                "description": "New habit title"
                            },
                            "type": {
                                "type": "string",
                                "enum": ["ClickCounter", "StopWatch", "RepeatedCountdownReminder"],
                                "description": "Habit counter type"
                            },
                            "icon": {
                                "type": "string",
                                "description": "Material icon name"
                            },
                            "is_enabled": {
                                "type": "boolean",
                                "description": "Whether the habit is enabled"
                            },
                            "is_hide_button": {
                                "type": "boolean",
                                "description": "Hide the habit from quick counter buttons"
                            },
                            "is_track_streaks": {
                                "type": "boolean",
                                "description": "Whether streaks are tracked for this habit"
                            },
                            "streak_min_value": {
                                "type": "number",
                                "description": "Minimum daily value required to count toward the streak"
                            },
                            "streak_mode": {
                                "type": "string",
                                "enum": ["specific-days", "weekly-frequency"],
                                "description": "Streak tracking mode"
                            },
                            "streak_week_days": {
                                "type": "object",
                                "description": "Specific active weekdays as keys 0-6 where 0 is Sunday",
                                "additionalProperties": {"type": "boolean"}
                            },
                            "streak_weekly_frequency": {
                                "type": "integer",
                                "description": "Required completions per week for weekly-frequency streak mode"
                            },
                            "countdown_duration": {
                                "type": "integer",
                                "description": "Countdown duration in milliseconds for RepeatedCountdownReminder habits"
                            }
                        },
                        "required": ["id"]
                    }
                ),
                types.Tool(
                    name="log_habit",
                    description="Register a habit value for today or a specific YYYY-MM-DD date.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Habit ID"
                            },
                            "operation": {
                                "type": "string",
                                "enum": ["set", "increment", "decrement"],
                                "description": "How to apply the value",
                                "default": "set"
                            },
                            "value": {
                                "type": "number",
                                "description": "Value to set, increment by, or decrement by",
                                "default": 1
                            },
                            "date": {
                                "type": "string",
                                "description": "Optional date in YYYY-MM-DD format. If omitted, today is used."
                            }
                        },
                        "required": ["id"]
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
                elif name == "get_projects":
                    result = await self.get_projects(arguments)
                elif name == "create_project":
                    result = await self.create_project(arguments)
                elif name == "get_tags":
                    result = await self.get_tags(arguments)
                elif name == "create_tag":
                    result = await self.create_tag(arguments)
                elif name == "get_habits":
                    result = await self.get_habits(arguments)
                elif name == "create_habit":
                    result = await self.create_habit(arguments)
                elif name == "update_habit":
                    result = await self.update_habit(arguments)
                elif name == "log_habit":
                    result = await self.log_habit(arguments)
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
        """Get all tasks"""
        return await self.send_command("getTasks")
    
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
        
        return await self.send_command("updateTask", taskId=task_id, data=updates)
    
    async def complete_and_archive_task(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Complete a task (mark as done) - true deletion is not supported"""
        task_id = args.get("task_id")
        if not task_id:
            return {"success": False, "error": "task_id is required"}
        
        # Mark task as done instead of deleting
        return await self.send_command("setTaskDone", taskId=task_id)
    
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

    def build_habit_data(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Build SimpleCounter habit data from MCP snake_case arguments."""
        habit_data = {}
        for arg_name, habit_name in self.HABIT_FIELD_MAP.items():
            if arg_name in args and args[arg_name] is not None:
                habit_data[habit_name] = args[arg_name]

        habit_type = habit_data.get("type")
        if habit_type and habit_type not in self.HABIT_TYPES:
            return {"error": f"type must be one of {sorted(self.HABIT_TYPES)}"}

        streak_mode = habit_data.get("streakMode")
        if streak_mode and streak_mode not in self.HABIT_STREAK_MODES:
            return {"error": f"streak_mode must be one of {sorted(self.HABIT_STREAK_MODES)}"}

        return habit_data

    async def get_habits(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get all habits"""
        return await self.send_command(
            "getHabits",
            includeDisabled=args.get("include_disabled", True)
        )

    async def create_habit(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create/register a new habit"""
        title = args.get("title", "")
        if not title:
            return {"success": False, "error": "title is required"}

        habit_data = self.build_habit_data(args)
        if "error" in habit_data:
            return {"success": False, "error": habit_data["error"]}

        habit_data.setdefault("title", title)
        habit_data.setdefault("type", "ClickCounter")
        habit_data.setdefault("isEnabled", True)

        return await self.send_command(
            "createHabit",
            habitId=args.get("id"),
            data=habit_data,
            initialValue=args.get("initial_value", 0)
        )

    async def update_habit(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Edit an existing habit"""
        habit_id = args.get("id")
        if not habit_id:
            return {"success": False, "error": "id is required"}

        habit_data = self.build_habit_data(args)
        if "error" in habit_data:
            return {"success": False, "error": habit_data["error"]}
        if not habit_data:
            return {"success": False, "error": "No habit fields provided to update"}

        return await self.send_command("updateHabit", habitId=habit_id, data=habit_data)

    async def log_habit(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Register a value for a habit"""
        habit_id = args.get("id")
        if not habit_id:
            return {"success": False, "error": "id is required"}

        operation = args.get("operation", "set")
        if operation not in {"set", "increment", "decrement"}:
            return {"success": False, "error": "operation must be set, increment, or decrement"}

        habit_date = args.get("date")
        if habit_date and not re.match(r"^\d{4}-\d{2}-\d{2}$", habit_date):
            return {"success": False, "error": "date must use YYYY-MM-DD format"}

        return await self.send_command(
            "logHabit",
            habitId=habit_id,
            operation=operation,
            value=args.get("value", 1),
            date=habit_date
        )
    
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
