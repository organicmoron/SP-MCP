#!/bin/bash

echo "============================================"
echo "Super Productivity MCP Bridge Setup"
echo "============================================"
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo "ERROR: pip3 is not installed or not in PATH"
    echo "Please ensure pip3 is installed with Python"
    exit 1
fi

echo "Installing MCP dependencies..."
pip3 install mcp

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install MCP dependencies"
    exit 1
fi

# Create data directory
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    MCP_DIR="$HOME/Library/Application Support/super-productivity-mcp"
    CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
else
    # Linux
    MCP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/super-productivity-mcp"
    CLAUDE_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/Claude/claude_desktop_config.json"
fi

echo "Creating MCP directory: $MCP_DIR"
mkdir -p "$MCP_DIR"
mkdir -p "$MCP_DIR/plugin_commands"
mkdir -p "$MCP_DIR/plugin_responses"

# Copy MCP server to data directory
echo "Copying MCP server..."
cp mcp_server.py "$MCP_DIR/mcp_server.py"
cp merge_config_unix.py "$MCP_DIR/merge_config_unix.py"
chmod +x "$MCP_DIR/mcp_server.py"

# Create start script
echo "Creating start script..."
cat > "$MCP_DIR/start_mcp_server.sh" << EOF
#!/bin/bash
echo "Starting Super Productivity MCP Server..."
cd "$MCP_DIR"
python3 mcp_server.py
read -p "Press Enter to exit..."
EOF
chmod +x "$MCP_DIR/start_mcp_server.sh"

# Configure Claude Desktop
echo "Configuring Claude Desktop..."

# Create Claude config directory if it doesn't exist
mkdir -p "$(dirname "$CLAUDE_CONFIG")"

# Check if config file exists and merge
if [ -f "$CLAUDE_CONFIG" ]; then
    echo "Backing up existing Claude config..."
    cp "$CLAUDE_CONFIG" "$CLAUDE_CONFIG.backup"
    
    echo "Adding super-productivity to existing MCP servers..."
    echo "Merging with existing Claude Desktop configuration..."
    
    python3 "$MCP_DIR/merge_config_unix.py" "$CLAUDE_CONFIG" "$MCP_DIR"
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to merge configuration. Your backup is at $CLAUDE_CONFIG.backup"
        echo "Please manually add this to your Claude Desktop config:"
        echo
        echo '  "super-productivity": {'
        echo '    "command": "python3",'
        echo '    "args": ["'$MCP_DIR'/mcp_server.py"]'
        echo '  }'
        echo
        echo "Press Enter to continue..."
        read
        exit 1
    fi
else
    echo "Creating new Claude Desktop configuration..."
    cat > "$CLAUDE_CONFIG" << EOF
{
  "mcpServers": {
    "super-productivity": {
      "command": "python3",
      "args": ["$MCP_DIR/mcp_server.py"]
    }
  }
}
EOF
fi

echo
echo "============================================"
echo "Setup Complete!"
echo "============================================"
echo
echo "Next steps:"
echo "1. Install the plugin in Super Productivity:"
echo "   - Open Super Productivity"
echo "   - Go to Settings > Plugins"
echo "   - Click \"Upload Plugin\""
echo "   - Select the plugin.js file from this folder"
echo
echo "2. Restart Claude Desktop to load the MCP server"
echo
echo "3. Test the integration by asking Claude to:"
echo "   \"Create a task in Super Productivity\""
echo
echo "MCP Server installed at: $MCP_DIR"
echo "Claude config updated at: $CLAUDE_CONFIG"
echo
echo "Press Enter to exit..."
read