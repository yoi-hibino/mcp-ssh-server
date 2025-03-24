#!/usr/bin/env python3
"""
MCP Config Loader
Loads connection settings from MCP config file
"""
import os
import json
import logging

logger = logging.getLogger(__name__)

def load_mcp_config():
    """
    Load SSH connection details from MCP config file
    
    Returns:
        dict: Connection details or empty dict if config can't be found
    """
    try:
        mcp_config_path = os.path.expanduser("~/.codeium/windsurf/mcp_config.json")
        
        if not os.path.exists(mcp_config_path):
            logger.warning(f"MCP config file not found at {mcp_config_path}")
            return {}
            
        with open(mcp_config_path, 'r') as f:
            config = json.load(f)
            
        # Extract SSH server config
        if 'mcpServers' in config and 'ssh' in config['mcpServers']:
            ssh_config = config['mcpServers']['ssh']
            
            # Get environment variables section if it exists
            if 'env' in ssh_config:
                env = ssh_config['env']
                
                # Return connection details
                connection = {
                    'host': env.get('SSH_DEFAULT_HOST', ''),
                    'port': env.get('SSH_DEFAULT_PORT', '22'),
                    'username': env.get('SSH_DEFAULT_USERNAME', ''),
                    'password': env.get('SSH_DEFAULT_PASSWORD', ''),
                    'key_path': env.get('SSH_DEFAULT_KEY_PATH', '')
                }
                
                return connection
                
        logger.warning("No SSH configuration found in MCP config")
        return {}
        
    except Exception as e:
        logger.error(f"Error loading MCP config: {str(e)}")
        return {}
