# Re-enabling Disabled MCP Servers in Claude Code

## Overview
This document provides instructions for re-enabling MCP servers that have been temporarily disabled in Claude Code by moving them to a special `_disabled_mcpServers` section.

## Location of Configuration File
The MCP server configuration is stored in:
```
/home/recon222/.claude.json
```

## How Servers Are Disabled
When MCP servers are temporarily disabled (to save context or for other reasons), they are moved from the `mcpServers` section to a special `_disabled_mcpServers` section in the configuration file. Each disabled server entry includes metadata tracking its original location.

## Re-enabling Disabled Servers

### Step 1: Find the Disabled Servers Section
Look for the `_disabled_mcpServers` section in the configuration file:
```bash
grep -n '"_disabled_mcpServers"' /home/recon222/.claude.json
```

### Step 2: Identify Servers to Re-enable
Each server in the `_disabled_mcpServers` section includes metadata fields:
- `_originalPath`: The file it came from
- `_originalStartLine`: Original starting line number
- `_originalEndLine`: Original ending line number

### Step 3: Move Server Back to Active Section
For each server you want to re-enable:

1. **Copy the server configuration** from `_disabled_mcpServers` (excluding the metadata fields starting with `_`)
2. **Remove the server** from the `_disabled_mcpServers` section
3. **Add the server** back to the `mcpServers` section
4. **Remove metadata fields** (`_originalPath`, `_originalStartLine`, `_originalEndLine`)

### Example Structure

#### Disabled Server (in _disabled_mcpServers):
```json
"_disabled_mcpServers": {
  "servername": {
    "command": "...",
    "args": [...],
    "env": {...},
    "_originalPath": "/home/recon222/.claude.json",
    "_originalStartLine": 1234,
    "_originalEndLine": 1245
  }
}
```

#### Re-enabled Server (moved back to mcpServers):
```json
"mcpServers": {
  "servername": {
    "command": "...",
    "args": [...],
    "env": {...}
  }
}
```

### Step 4: Clean Up Empty Section
If you've re-enabled all servers and the `_disabled_mcpServers` section is empty, you can remove the entire section to keep the config clean.

### Step 5: Restart Claude Code
After making changes, you must restart Claude Code for the changes to take effect.

## Important Notes

1. **JSON Syntax**: Ensure proper JSON syntax when editing:
   - Commas between server entries
   - No trailing comma on the last entry in a section
   - Proper closing braces

2. **Backup**: Consider backing up the configuration file before making changes:
   ```bash
   cp /home/recon222/.claude.json /home/recon222/.claude.json.backup
   ```

3. **Validation**: You can validate the JSON syntax after editing:
   ```bash
   jq '.' /home/recon222/.claude.json > /dev/null && echo "Valid JSON" || echo "Invalid JSON"
   ```

## Quick Commands

### List all disabled servers:
```bash
jq '._disabled_mcpServers | keys' /home/recon222/.claude.json
```

### List all active servers:
```bash
jq '.mcpServers | keys' /home/recon222/.claude.json
```

## Troubleshooting

- **Claude Code doesn't start**: Check JSON syntax is valid
- **Server still not loading**: Ensure it's in `mcpServers` not `_disabled_mcpServers`
- **Server errors**: Check that all required fields (command, args, env) are present

## Context Management
Remember that re-enabling MCP servers will increase the context usage in Claude Code. Each server's tool definitions contribute to the token count, so only enable the servers you actively need for your current work.