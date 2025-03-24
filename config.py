#!/usr/bin/env python3
"""
Configuration module for MCP Server
Handles configuration and saved connections
"""
import os
import yaml
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class Config:
    """Configuration handler for the MCP SSH Server."""
    
    def __init__(self, config_dir=None):
        """
        Initialize the configuration handler.
        
        Args:
            config_dir (str, optional): Directory to store config files
        """
        self.config_dir = config_dir or os.path.join(os.path.expanduser('~'), '.mcp')
        self.connections_file = os.path.join(self.config_dir, 'connections.yaml')
        
        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Create connections file if it doesn't exist
        if not os.path.exists(self.connections_file):
            with open(self.connections_file, 'w') as f:
                yaml.dump([], f)
    
    def get_connections(self):
        """
        Get saved SSH connections.
        
        Returns:
            list: List of saved connection dictionaries
        """
        try:
            with open(self.connections_file, 'r') as f:
                connections = yaml.safe_load(f) or []
            return connections
        except Exception as e:
            logger.error(f"Failed to load connections: {str(e)}")
            return []
    
    def add_connection(self, connection):
        """
        Add a new SSH connection to saved connections.
        
        Args:
            connection (dict): Connection details
        """
        try:
            connections = self.get_connections()
            
            # Check if connection already exists
            for i, conn in enumerate(connections):
                if (conn.get('hostname') == connection.get('hostname') and
                    conn.get('username') == connection.get('username') and
                    conn.get('port') == connection.get('port')):
                    # Update existing connection
                    connections[i] = connection
                    break
            else:
                # Add new connection
                connections.append(connection)
            
            with open(self.connections_file, 'w') as f:
                yaml.dump(connections, f)
                
            logger.info(f"Saved connection to {connection.get('username')}@{connection.get('hostname')}")
            
        except Exception as e:
            logger.error(f"Failed to save connection: {str(e)}")
    
    def remove_connection(self, hostname, username, port=22):
        """
        Remove a saved SSH connection.
        
        Args:
            hostname (str): The hostname or IP address
            username (str): The username
            port (int, optional): The SSH port (default 22)
        
        Returns:
            bool: True if connection was removed, False otherwise
        """
        try:
            connections = self.get_connections()
            initial_count = len(connections)
            
            connections = [conn for conn in connections if not (
                conn.get('hostname') == hostname and
                conn.get('username') == username and
                conn.get('port') == port
            )]
            
            if len(connections) < initial_count:
                with open(self.connections_file, 'w') as f:
                    yaml.dump(connections, f)
                logger.info(f"Removed connection for {username}@{hostname}:{port}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to remove connection: {str(e)}")
            return False
