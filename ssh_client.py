#!/usr/bin/env python3
"""
SSH Client module for MCP Server
Handles SSH connections to remote servers
"""
import paramiko
import os
import logging

logger = logging.getLogger(__name__)

class SSHClient:
    """Class to handle SSH connections and commands."""
    
    def __init__(self):
        """Initialize a new SSH client."""
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.connected = False
    
    def connect(self, hostname, port, username, password=None, key_path=None):
        """
        Connect to a remote server via SSH.
        
        Args:
            hostname (str): The hostname or IP address of the server
            port (int): The SSH port (default 22)
            username (str): The username to authenticate with
            password (str, optional): The password for authentication
            key_path (str, optional): Path to private key file
            
        Raises:
            Exception: If connection fails
        """
        try:
            # Authentication options
            auth_args = {}
            
            if password:
                auth_args['password'] = password
                logger.info(f"Using password authentication for {username}@{hostname}")
                
            elif key_path and os.path.isfile(key_path):
                try:
                    private_key = paramiko.RSAKey.from_private_key_file(key_path)
                    auth_args['pkey'] = private_key
                    logger.info(f"Using key authentication for {username}@{hostname}")
                except Exception as e:
                    logger.error(f"Failed to load private key: {str(e)}")
                    raise Exception(f"Failed to load private key: {str(e)}")
            
            # Connect to the server
            self.client.connect(
                hostname=hostname,
                port=port,
                username=username,
                **auth_args,
                timeout=10
            )
            
            self.connected = True
            self.hostname = hostname
            self.username = username
            
            logger.info(f"Successfully connected to {username}@{hostname}:{port}")
            
        except Exception as e:
            logger.error(f"SSH connection error: {str(e)}")
            raise Exception(f"Connection failed: {str(e)}")
    
    def execute_command(self, command):
        """
        Execute a command on the remote server.
        
        Args:
            command (str): The command to execute
            
        Returns:
            tuple: (stdout, stderr) strings
            
        Raises:
            Exception: If command execution fails
        """
        if not self.connected:
            raise Exception("Not connected to any server")
        
        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            stdout_str = stdout.read().decode('utf-8')
            stderr_str = stderr.read().decode('utf-8')
            
            return stdout_str, stderr_str
            
        except Exception as e:
            logger.error(f"Command execution error: {str(e)}")
            raise Exception(f"Command execution failed: {str(e)}")
    
    def get_sftp(self):
        """
        Get an SFTP client for file transfers.
        
        Returns:
            paramiko.SFTPClient: SFTP client object
        
        Raises:
            Exception: If connection fails
        """
        if not self.connected:
            raise Exception("Not connected to any server")
            
        try:
            return self.client.open_sftp()
        except Exception as e:
            logger.error(f"SFTP error: {str(e)}")
            raise Exception(f"SFTP connection failed: {str(e)}")
    
    def is_connected(self):
        """
        Check if the client is connected.
        
        Returns:
            bool: True if connected, False otherwise
        """
        if not self.connected:
            return False
            
        try:
            # Try to execute a simple command to check connection
            transport = self.client.get_transport()
            return transport is not None and transport.is_active()
        except Exception:
            self.connected = False
            return False
            
    def close(self):
        """Close the SSH connection."""
        if self.connected:
            self.client.close()
            self.connected = False
            logger.info(f"Disconnected from {self.username}@{self.hostname}")
