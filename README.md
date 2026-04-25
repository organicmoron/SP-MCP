# SP-MCP

Bridge between the amazing [Super Productivity](https://github.com/johannesjo/super-productivity/) app and MCP (Model Context Protocol) servers for Claude Desktop integration.

This MCP and plugin allows Claude Desktop to directly interact with Super Productivity through the MCP protocol. Create update,tasks, manage projects and tags, and get information from Super Productivity.

Make sure to backup your Super Productivity before using in case of data loss. I've provided a plugin.zip for convenience but feel free to make your own from the files.

(Can't delete tasks right now (but it can mark them as done))

## Demo

https://github.com/user-attachments/assets/cc118173-023f-48cb-8213-427027e475af


## Requirements

- Super Productivity 14.0.0 or higher
- Claude Desktop
- Python 3.8 or higher

## Installation

### Automatic Setup

**Windows:**
1. Clone this repo
2. Run `setup.bat`
3. Follow the prompts

**Linux/Mac UNTESTED:**
1. Clone this repo
2. Run `chmod +x setup.sh && ./setup.sh`
3. Follow the prompts

The setup scripts will preserve any existing MCP servers in your Claude Desktop configuration.

You'll still have to install the plugin.zip manually in Super Productivity in settings->plugins.

Once that's done, restart claude (and Super Prod for good measure) and you should be able to access your files

### Manual Setup

1. **Install Python dependencies:**
   ```bash
   pip install mcp
   ```

2. **Set up MCP server:**
   Copy `mcp_server.py` to your data directory:
   - Windows: `%APPDATA%\super-productivity-mcp\`
   - Linux: `~/.local/share/super-productivity-mcp/`
   - macOS: `~/Library/Application Support/super-productivity-mcp/`

3. **Configure Claude Desktop:**
   Edit Claude's config file and add to `mcpServers`:
   ```json
   "super-productivity": {
     "command": "python3",
     "args": ["/path/to/mcp_server.py"]
   }
   ```

4. **Install the plugin:**
   - Open Super Productivity → Settings → Plugins
   - Click "Upload Plugin"
   - Select `plugin.zip`

5. **Restart Claude Desktop**

## Usage

### Creating Tasks
```
"Create a task to review the quarterly budget #finance +work"
```

### Task Management
```
"Show me all my tasks"
"Mark the budget review task as complete"
"Update the task 'Meeting prep' with notes about the agenda"
```

### Project and Tag Management
```
"Create a new project called 'Website Redesign'"
"Show me all projects"
"Get all tags"
```

### Habit Management
```
"Show me all my habits"
"Create a habit called 'Drink water' with a daily goal of 8"
"Mark the 'Drink water' habit as done for today"
"Set the 'Meditation' habit value to 1 for 2026-04-25"
"Rename the 'Exercise' habit to 'Morning workout'"
```


## Dashboard

Access the SP-MCP dashboard from the menu. The dashboard shows:
- Real-time statistics
- Connection status
- Activity logs
- Settings (polling frequency: default 2 seconds)

## Communication

The plugin uses file-based communication through:
- Windows: `%APPDATA%\super-productivity-mcp\`
- Linux: `~/.local/share/super-productivity-mcp/`
- macOS: `~/Library/Containers/com.super-productivity.app/Data/.local/share/super-productivity-mcp/`

Commands are exchanged through `plugin_commands/` and `plugin_responses/` directories.

## Troubleshooting

### Plugin Not Loading
- Check Super Productivity version (14.0.0+ required)
- Verify plugin permissions include `nodeExecution`

### Commands Not Working
- Verify both plugin and MCP server are running
- Check file permissions on communication directories
- Check `mcp_server.log` in the communication directory (see the file-based communication paths above; on macOS this is inside the container path, not `Library/Application Support`)
