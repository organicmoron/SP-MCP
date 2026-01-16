// MCP Bridge Plugin for Super Productivity

class MCPBridgePlugin {
  constructor() {
    this.mcpServerPath = null;
    this.commandWatchInterval = null;
    this.lastProcessedCommand = 0;
    this.isInitialized = false;
    this.commandQueue = [];
    this.lastNoCommandsLog = 0;
    
    // Configuration
    this.config = {
      commandCheckIntervalMs: 2000, // Check for commands every 2 seconds (configurable)
      mcpCommandDir: null,          // Will be set during initialization  
      mcpResponseDir: null,         // Will be set during initialization
      debugMode: true,
      maxConcurrentCommands: 5,
      configFile: null              // Will be set to store settings
    };

    // Statistics
    this.stats = {
      commandsProcessed: 0,
      lastCommandTime: null,
      errors: 0,
      startTime: Date.now()
    };
  }

  async loadConfig() {
    try {
      const result = await PluginAPI.executeNodeScript({
        script: `
          const fs = require('fs');
          const path = require('path');
          
          const configFile = args[0];
          
          try {
            if (fs.existsSync(configFile)) {
              const configData = fs.readFileSync(configFile, 'utf8');
              return { success: true, config: JSON.parse(configData) };
            } else {
              // Return default config
              return { 
                success: true, 
                config: { 
                  commandCheckIntervalMs: 2000 
                } 
              };
            }
          } catch (error) {
            return { success: false, error: error.message };
          }
        `,
        args: [this.config.configFile],
        timeout: 5000
      });
      
      if (result && result.success && result.result && result.result.success) {
        const savedConfig = result.result.config;
        this.config.commandCheckIntervalMs = savedConfig.commandCheckIntervalMs || 2000;
        return true;
      }
    } catch (error) {
      await this.log(`Failed to load config: ${error.message}`);
    }
    return false;
  }

  async saveConfig() {
    try {
      const configData = {
        commandCheckIntervalMs: this.config.commandCheckIntervalMs
      };
      
      const result = await PluginAPI.executeNodeScript({
        script: `
          const fs = require('fs');
          
          const configFile = args[0];
          const configData = args[1];
          
          try {
            fs.writeFileSync(configFile, JSON.stringify(configData, null, 2));
            return { success: true };
          } catch (error) {
            return { success: false, error: error.message };
          }
        `,
        args: [this.config.configFile, configData],
        timeout: 5000
      });
      
      if (result && result.success && result.result && result.result.success) {
        return true;
      }
    } catch (error) {
      await this.log(`Failed to save config: ${error.message}`);
    }
    return false;
  }

  async updatePollingFrequency(frequencySeconds) {
    const newIntervalMs = frequencySeconds * 1000;
    if (newIntervalMs >= 1000 && newIntervalMs <= 60000) {
      this.config.commandCheckIntervalMs = newIntervalMs;
      await this.saveConfig();
      
      // Restart command processing with new interval
      this.startCommandProcessing();
      
      this.updateUI({
        config: { pollingFrequency: frequencySeconds },
        log: { message: `Polling updated to ${frequencySeconds}s`, type: 'info' }
      });
      return true;
    }
    return false;
  }

  async init() {
    await this.log('MCP Bridge Plugin initializing...');
    
    try {
      // Find the MCP server and set up communication directories
      await this.setupMCPCommunication();
      
      // Set config file path and load configuration (non-blocking)
      this.config.configFile = this.mcpServerPath + '/mcp_bridge_config.json';
      this.loadConfig().catch(e => this.log(`Config loading failed: ${e.message}`));
      
      // Start the command processing loop
      this.startCommandProcessing();
      
      // Register event hooks for Super Productivity changes
      this.registerHooks();
      
      // Register UI elements
      this.registerUI();
      
      this.isInitialized = true;
      await this.log('MCP Bridge Plugin initialized successfully!');
      
      // Log success (skip notifications for now)
      console.log('🔗 MCP Bridge connected! Ready for commands.');
      
      // Send initialization status to UI
      this.updateUI({
        status: { type: 'connected', message: '✅ Connected and ready' },
        mcpPath: this.mcpServerPath,
        commandDir: this.config.mcpCommandDir,
        responseDir: this.config.mcpResponseDir,
        config: {
          pollingFrequency: Math.floor(this.config.commandCheckIntervalMs / 1000)
        }
      });
      
    } catch (error) {
      await this.log(`Failed to initialize: ${error.message}`);
      console.error('MCP Bridge failed:', error.message);
      this.updateUI({
        status: { type: 'disconnected', message: `❌ ${error.message}` }
      });
    }
  }

  async setupMCPCommunication() {
    // First try to use AppData directory
    try {
      const result = await PluginAPI.executeNodeScript({
        script: `
          try {
            const fs = require('fs');
            const path = require('path');
            const os = require('os');
            
            let dataDir;
            if (os.platform() === 'win32') {
              dataDir = process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming');
            } else {
              dataDir = process.env.XDG_DATA_HOME || path.join(os.homedir(), '.local', 'share');
            }
            
            const mcpDir = path.join(dataDir, 'super-productivity-mcp');
            const commandDir = path.join(mcpDir, 'plugin_commands');
            const responseDir = path.join(mcpDir, 'plugin_responses');
            
            if (!fs.existsSync(mcpDir)) {
              fs.mkdirSync(mcpDir, { recursive: true });
            }
            if (!fs.existsSync(commandDir)) {
              fs.mkdirSync(commandDir, { recursive: true });
            }
            if (!fs.existsSync(responseDir)) {
              fs.mkdirSync(responseDir, { recursive: true });
            }
            
            return {
              success: true,
              mcpServerPath: mcpDir,
              commandDir: commandDir,
              responseDir: responseDir,
              platform: os.platform()
            };
            
          } catch (error) {
            return {
              success: false,
              error: error.message
            };
          }
        `,
        args: [],
        timeout: 10000
      });
      
      let scriptResult = result;
      if (result && result.success && result.result) {
        scriptResult = result.result;
      }
      
      if (scriptResult && scriptResult.success) {
        this.mcpServerPath = scriptResult.mcpServerPath;
        this.config.mcpCommandDir = scriptResult.commandDir;
        this.config.mcpResponseDir = scriptResult.responseDir;
        return;
      } else {
        await this.log('AppData setup failed, trying fallback method');
      }
    } catch (e) {
      await this.log(`AppData setup failed: ${e.message}`);
    }
    
    try {
      const fallbackResult = await PluginAPI.executeNodeScript({
        script: `
          const os = require('os');
          const path = require('path');
          
          let baseDir;
          if (os.platform() === 'win32') {
            baseDir = path.join(os.homedir(), 'AppData', 'Roaming', 'super-productivity-mcp');
          } else {
            baseDir = path.join(os.homedir(), '.local', 'share', 'super-productivity-mcp');
          }
          
          return {
            success: true,
            mcpServerPath: baseDir,
            commandDir: path.join(baseDir, 'plugin_commands'),
            responseDir: path.join(baseDir, 'plugin_responses')
          };
        `,
        args: [],
        timeout: 5000
      });
      
      if (fallbackResult && fallbackResult.success && fallbackResult.result) {
        this.mcpServerPath = fallbackResult.result.mcpServerPath;
        this.config.mcpCommandDir = fallbackResult.result.commandDir;
        this.config.mcpResponseDir = fallbackResult.result.responseDir;
        return;
      }
    } catch (fallbackError) {
      await this.log(`Fallback setup failed: ${fallbackError.message}`);
    }
    
    // If we get here, everything failed
    throw new Error('Could not set up MCP communication directories');
  }


  /**
   * Start the command processing loop
   */
  startCommandProcessing() {
    if (this.commandWatchInterval) {
      clearInterval(this.commandWatchInterval);
    }

    this.commandWatchInterval = setInterval(async () => {
      try {
        await this.processNewCommands();
      } catch (error) {
        await this.log(`Command processing error: ${error.message}`);
        this.stats.errors++;
      }
    }, this.config.commandCheckIntervalMs);

    console.log(`Command processing started with ${this.config.commandCheckIntervalMs}ms interval`);
  }

  /**
   * Process new commands from MCP server
   */
  async processNewCommands() {
    if (!this.config.mcpCommandDir) {
      return;
    }

    try {

      const result = await PluginAPI.executeNodeScript({
        script: `
          const fs = require('fs');
          const path = require('path');
          
          const commandDir = args[0];
          const lastProcessed = args[1];
          
          // Always return a result with the expected structure
          try {
            // Log what we're working with
            console.log('Processing commands in:', commandDir);
            console.log('Last processed timestamp:', lastProcessed);
            
            if (!fs.existsSync(commandDir)) {
              console.log('Command directory does not exist');
              return { success: true, commands: [], message: 'Directory not found' };
            }
            
            const files = fs.readdirSync(commandDir);
            console.log('Found files:', files);
            
            const commandFiles = files.filter(f => f.endsWith('.json'));
            console.log('JSON files:', commandFiles);
            
            // Find new command files
            const newCommands = [];
            for (const file of commandFiles) {
              const filePath = path.join(commandDir, file);
              console.log('Checking file:', filePath);
              
              try {
                const stats = fs.statSync(filePath);
                console.log('File mtime:', stats.mtime.getTime(), 'vs lastProcessed:', lastProcessed);
                
                if (stats.mtime.getTime() > lastProcessed) {
                  console.log('Processing new file:', file);
                  
                  try {
                    const content = fs.readFileSync(filePath, 'utf8');
                    const command = JSON.parse(content);
                    
                    newCommands.push({
                      filename: file,
                      path: filePath,
                      command: command,
                      timestamp: stats.mtime.getTime()
                    });
                  } catch (parseError) {
                    console.log('Parse error for file', file, ':', parseError.message);
                  }
                } else {
                  console.log('File', file, 'is not newer than last processed');
                }
              } catch (statError) {
                console.log('Stat error for file', file, ':', statError.message);
              }
            }
            
            // Sort by timestamp
            newCommands.sort((a, b) => a.timestamp - b.timestamp);
            
            console.log('Returning', newCommands.length, 'new commands');
            
            const finalResult = {
              success: true,
              commands: newCommands,
              totalFiles: files.length,
              jsonFiles: commandFiles.length,
              processedFiles: newCommands.length
            };
            
            console.log('Final result:', JSON.stringify(finalResult, null, 2));
            return finalResult;
            
          } catch (error) {
            console.log('Error in command processing:', error.message);
            return { 
              success: false, 
              error: error.message,
              commands: [] // Always include commands array
            };
          }
        `,
        args: [this.config.mcpCommandDir, this.lastProcessedCommand],
        timeout: 10000
      });

      // Add comprehensive null checking
      if (!result) {
        await this.log('executeNodeScript returned null/undefined result');
        return;
      }
      
      if (!result.hasOwnProperty('success')) {
        await this.log('executeNodeScript result missing success property');
        return;
      }
      
      if (!result.success) {
        await this.log(`Command processing failed: ${result.error || 'Unknown error'}`);
        return;
      }
      
      // The result from executeNodeScript is wrapped in a 'result' property
      const commandResult = result.result;
      
      if (!commandResult || !commandResult.hasOwnProperty('commands')) {
        await this.log('executeNodeScript result.result missing commands property');
        return;
      }
      
      if (!Array.isArray(commandResult.commands)) {
        await this.log('executeNodeScript result.result.commands is not an array');
        return;
      }
      
      if (commandResult.commands.length > 0) {
        for (const commandInfo of commandResult.commands) {
          try {
            await this.executeCommand(commandInfo);
            this.lastProcessedCommand = Math.max(this.lastProcessedCommand, commandInfo.timestamp);
          } catch (error) {
            await this.log(`Command execution failed: ${error.message}`);
          }
        }
      }
      
    } catch (error) {
      await this.log(`Error in processNewCommands: ${error.message}`);
      this.stats.errors++;
    }
  }
  

  async executeCommand(commandInfo) {
    const { command, filename, path: commandPath } = commandInfo;
    
    try {
      let result;
      const startTime = Date.now();
      
      // Execute the appropriate API call based on command.action
      switch (command.action) {
        // Task operations
        case 'getTasks':
          result = await PluginAPI.getTasks();
          break;
          
        case 'getArchivedTasks':
          result = await PluginAPI.getArchivedTasks();
          break;
          
        case 'getCurrentContextTasks':
          result = await PluginAPI.getCurrentContextTasks();
          break;
          
        case 'addTask':
          // Check if this is a subtask with SP syntax (@, #, +)
          if (command.data.parentId && (command.data.title.includes('@') || command.data.title.includes('#') || command.data.title.includes('+'))) {
            await this.log(`Subtask with syntax detected: ${command.data.title}`);
            
            // Step 1: Create subtask without SP syntax
            const titleWithoutSyntax = command.data.title
              .replace(/@\w+/g, '')
              .replace(/#\w+/g, '')
              .replace(/\+\w+/g, '')
              .trim();
            const taskData = { ...command.data, title: titleWithoutSyntax };
            
            await this.log(`Creating subtask without syntax: ${titleWithoutSyntax}`);
            const taskId = await PluginAPI.addTask(taskData);
            
            // Step 2: Update with original title to trigger syntax parsing
            await this.log(`Updating subtask with original title: ${command.data.title}`);
            await PluginAPI.updateTask(taskId, { title: command.data.title });
            
            result = taskId;
          } else {
            // Regular task creation
            result = await PluginAPI.addTask(command.data);
          }
          break;
          
        case 'updateTask':
          result = await PluginAPI.updateTask(command.taskId, command.data);
          break;
          
        case 'deleteTask':
        case 'removeTask':
          // Task deletion is not supported via Plugin API
          // We can only archive tasks by marking them as done and moving to archive
          result = { 
            success: false, 
            error: 'Task deletion not supported. Use updateTask to mark as done instead.',
            suggestion: 'Use updateTask with {isDone: true} to complete the task'
          };
          break;

        case 'setTaskDone':
        case 'markTaskDone':
        case 'completeTask':
          result = await PluginAPI.updateTask(command.taskId, { isDone: true, doneOn: Date.now() });
          break;

        case 'setTaskUndone':
        case 'markTaskUndone':
        case 'uncompleteTask':
          result = await PluginAPI.updateTask(command.taskId, { isDone: false, doneOn: null });
          break;

        case 'addTimeToTask':
        case 'addTimeSpent':
          // Get current task to add time to existing timeSpent
          const tasks = await PluginAPI.getTasks();
          const task = tasks.find(t => t.id === command.taskId);
          if (task) {
            const newTimeSpent = task.timeSpent + (command.timeMs || 0);
            result = await PluginAPI.updateTask(command.taskId, { timeSpent: newTimeSpent });
          } else {
            result = { error: 'Task not found' };
          }
          break;

        case 'setTimeEstimate':
          result = await PluginAPI.updateTask(command.taskId, { timeEstimate: command.timeMs || 0 });
          break;

        case 'moveTaskToProject':
          result = await PluginAPI.updateTask(command.taskId, { projectId: command.projectId });
          break;

        case 'addTagToTask':
          // Get current task to add tag to existing tagIds
          const tasksForTag = await PluginAPI.getTasks();
          const taskForTag = tasksForTag.find(t => t.id === command.taskId);
          if (taskForTag) {
            const newTagIds = [...taskForTag.tagIds];
            if (!newTagIds.includes(command.tagId)) {
              newTagIds.push(command.tagId);
            }
            result = await PluginAPI.updateTask(command.taskId, { tagIds: newTagIds });
          } else {
            result = { error: 'Task not found' };
          }
          break;

        case 'removeTagFromTask':
          // Get current task to remove tag from existing tagIds
          const tasksForTagRemoval = await PluginAPI.getTasks();
          const taskForTagRemoval = tasksForTagRemoval.find(t => t.id === command.taskId);
          if (taskForTagRemoval) {
            const newTagIds = taskForTagRemoval.tagIds.filter(id => id !== command.tagId);
            result = await PluginAPI.updateTask(command.taskId, { tagIds: newTagIds });
          } else {
            result = { error: 'Task not found' };
          }
          break;
          
        case 'reorderTasks':
          result = await PluginAPI.reorderTasks ? await PluginAPI.reorderTasks(command.taskIds, command.contextId, command.contextType) : 'reorderTasks not available';
          break;

        // Project operations
        case 'getAllProjects':
          result = await PluginAPI.getAllProjects();
          break;
          
        case 'addProject':
          result = await PluginAPI.addProject(command.data);
          break;
          
        case 'updateProject':
          result = await PluginAPI.updateProject(command.projectId, command.data);
          break;
          
        case 'deleteProject':
          result = { error: 'Project deletion not supported via Plugin API. Use updateProject to archive instead.' };
          break;

        // Tag operations
        case 'getAllTags':
          result = await PluginAPI.getAllTags();
          break;
          
        case 'addTag':
          result = await PluginAPI.addTag(command.data);
          break;
          
        case 'updateTag':
          result = await PluginAPI.updateTag(command.tagId, command.data);
          break;
          
        case 'deleteTag':
          result = { error: 'Tag deletion not supported via Plugin API.' };
          break;

        // UI operations
        case 'showSnack':
          try {
            result = await PluginAPI.showSnack({
              message: command.message,
              type: 'SUCCESS'
            });
          } catch (e) {
            // Fallback - just log the message
            console.log('Snack message:', command.message);
            result = { success: true, fallback: true };
          }
          break;
          
        case 'notify':
          try {
            result = await PluginAPI.notify(command.message);
          } catch (e) {
            // Fallback - just log the message
            console.log('Notification:', command.message);
            result = { success: true, fallback: true };
          }
          break;
          
        case 'openDialog':
          result = await PluginAPI.openDialog(command.dialogConfig);
          break;

        // Data persistence
        case 'persistDataSynced':
          result = await PluginAPI.persistDataSynced(command.key, command.data);
          break;
          
        case 'loadSyncedData':
          result = await PluginAPI.loadSyncedData(command.key);
          break;

        // Custom batch operations
        case 'batchOperation':
          result = await this.executeBatchOperation(command.operations);
          break;
          
        default:
          throw new Error(`Unknown command action: ${command.action}`);
      }
      
      const executionTime = Date.now() - startTime;
      
      // Write response back to MCP server
      await this.writeCommandResponse(command.id || filename, {
        success: true,
        result: result,
        executionTime: executionTime,
        timestamp: Date.now()
      });
      
      // Clean up command file
      await this.deleteCommandFile(commandPath);
      
      this.stats.commandsProcessed++;
      this.stats.lastCommandTime = Date.now();
      
      
    } catch (error) {
      await this.log(`Command failed: ${command.action} - ${error.message}`);
      
      // Write error response
      await this.writeCommandResponse(command.id || filename, {
        success: false,
        error: error.message,
        timestamp: Date.now()
      });
      
      // Clean up command file even on error
      await this.deleteCommandFile(commandPath);
      
      this.stats.errors++;
    }
  }

  async executeBatchOperation(operations) {
    const results = [];
    
    for (const op of operations) {
      try {
        let result;
        
        switch (op.action) {
          case 'addTask':
            result = await PluginAPI.addTask(op.data);
            break;
          case 'updateTask':
            result = await PluginAPI.updateTask(op.taskId, op.data);
            break;
          case 'addProject':
            result = await PluginAPI.addProject(op.data);
            break;
          // Add more batch operations as needed
          default:
            throw new Error(`Unsupported batch operation: ${op.action}`);
        }
        
        results.push({ success: true, result: result });
        
      } catch (error) {
        results.push({ success: false, error: error.message });
      }
    }
    
    return results;
  }

  async writeCommandResponse(commandId, response) {
    if (!this.config.mcpResponseDir) {
      return;
    }

    try {
      const result = await PluginAPI.executeNodeScript({
      script: `
        const fs = require('fs');
        const path = require('path');
        
        const responseDir = args[0];
        const commandId = args[1];
        const response = args[2];
        
        try {
          const responseFile = path.join(responseDir, \`\${commandId}_response.json\`);
          fs.writeFileSync(responseFile, JSON.stringify(response, null, 2));
          return { success: true, file: responseFile };
        } catch (error) {
          return { success: false, error: error.message };
        }
      `,
        args: [this.config.mcpResponseDir, commandId, response],
        timeout: 5000
      });
      
      
    } catch (error) {
      await this.log(`Error writing command response: ${error.message}`);
    }
  }

  async deleteCommandFile(commandPath) {
    try {
      const result = await PluginAPI.executeNodeScript({
      script: `
        const fs = require('fs');
        
        try {
          fs.unlinkSync(args[0]);
          return { success: true };
        } catch (error) {
          return { success: false, error: error.message };
        }
      `,
        args: [commandPath],
        timeout: 5000
      });
      
      
    } catch (error) {
      await this.log(`Error deleting command file: ${error.message}`);
    }
  }

  registerHooks() {
    // Task events
    PluginAPI.registerHook('taskUpdate', async (taskData) => {
      await this.sendEventToMCP('taskUpdate', taskData);
    });

    PluginAPI.registerHook('taskComplete', async (taskData) => {
      await this.sendEventToMCP('taskComplete', taskData);
    });

    PluginAPI.registerHook('taskDelete', async (taskData) => {
      await this.sendEventToMCP('taskDelete', taskData);
    });

    PluginAPI.registerHook('currentTaskChange', async (taskData) => {
      await this.sendEventToMCP('currentTaskChange', taskData);
      // Store current task for O(1) retrieval
      await PluginAPI.persistDataSynced('currentTask', taskData);
    });

  }

  registerUI() {
    // Register menu entry only (no header button to avoid duplicates)
    PluginAPI.registerMenuEntry({
      label: 'MCP Bridge Dashboard',
      icon: 'dashboard',
      onClick: () => {
        PluginAPI.showIndexHtmlAsView();
      }
    });

  }

  async sendEventToMCP(eventType, eventData) {
    if (!this.isInitialized || !this.config.mcpResponseDir) return;
    
    try {
      const timestamp = Date.now();
      const eventFile = `${timestamp}_${eventType}_event.json`;
      
      const result = await PluginAPI.executeNodeScript({
        script: `
          const fs = require('fs');
          const path = require('path');
          
          const responseDir = args[0];
          const eventFile = args[1];
          const eventData = args[2];
          
          try {
            const filePath = path.join(responseDir, eventFile);
            fs.writeFileSync(filePath, JSON.stringify(eventData, null, 2));
            return { success: true, file: filePath };
          } catch (error) {
            return { success: false, error: error.message };
          }
        `,
        args: [this.config.mcpResponseDir, eventFile, {
          eventType: eventType,
          eventData: eventData,
          timestamp: timestamp,
          source: 'super-productivity'
        }],
        timeout: 5000
      });
      
      
    } catch (error) {
      await this.log(`Failed to send event to MCP: ${error.message}`);
    }
  }

  updateUI(data) {
    // Send message to iframe UI
    if (typeof window !== 'undefined' && window.postMessage) {
      try {
        window.postMessage({
          type: 'mcp-bridge-update',
          data: {
            ...data,
            stats: this.stats,
            timestamp: Date.now()
          }
        }, '*');
      } catch (e) {
        // Ignore postMessage errors
      }
    }
  }

  getStatus() {
    return {
      isInitialized: this.isInitialized,
      mcpServerPath: this.mcpServerPath,
      commandDir: this.config.mcpCommandDir,
      responseDir: this.config.mcpResponseDir,
      stats: this.stats,
      config: {
        pollingFrequency: Math.floor(this.config.commandCheckIntervalMs / 1000),
        debugMode: this.config.debugMode
      }
    };
  }

  async forceCommandCheck() {
    await this.processNewCommands();
    this.updateUI({
      log: { message: 'Force command check completed', type: 'success' }
    });
  }

  async cleanup() {
    if (this.commandWatchInterval) {
      clearInterval(this.commandWatchInterval);
      this.commandWatchInterval = null;
    }
    
    await this.log('MCP Bridge Plugin cleaned up');
  }

  async log(message) {
    if (this.config.debugMode) {
      const timestamp = new Date().toISOString();
      console.log(`[${timestamp}] MCP Bridge: ${message}`);
      
      // Send to UI
      this.updateUI({
        log: { message: message, type: 'info' }
      });
    }
  }
}

// Initialize the plugin
const mcpBridge = new MCPBridgePlugin();
mcpBridge.init().catch(console.error);

// Export for cleanup and UI access
window.mcpBridge = mcpBridge;