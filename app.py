#!/usr/bin/env python3
"""
MCP SSH Server - Main application file
Provides a web interface to SSH to other computers
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_cors import CORS
import os
import json
import logging
import datetime
from dotenv import load_dotenv
from ssh_client import SSHClient
from config import Config
from mcp_loader import load_mcp_config

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load MCP config settings
mcp_settings = load_mcp_config()
logger.info(f"Loaded MCP settings: {json.dumps(mcp_settings, indent=2)}")

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev_key_please_change_in_production')

# Enable CORS
CORS(app)

# Add context processor for templates
@app.context_processor
def inject_now():
    return {'now': datetime.datetime.now()}

# Load configuration
config = Config()
ssh_connections = {}

# Auto-connect function
def auto_connect():
    """Automatically connect to SSH server if configuration is available."""
    if not mcp_settings:
        logger.warning("Auto-connect skipped: No MCP settings found")
        return None
        
    hostname = mcp_settings.get('host')
    port = int(mcp_settings.get('port', '22'))
    username = mcp_settings.get('username')
    password = mcp_settings.get('password', '')
    key_path = mcp_settings.get('key_path', '')
    
    logger.info(f"Attempting auto-connect to {username}@{hostname}:{port}")
    
    # Only attempt connection if hostname and username are provided
    if hostname and username:
        connection_id = f"{username}@{hostname}:{port}"
        
        try:
            # Create SSH client and connect
            client = SSHClient()
            client.connect(hostname, port, username, password, key_path)
            
            # Store connection
            ssh_connections[connection_id] = client
            logger.info(f"Auto-connected to {connection_id}")
            
            # Save to config
            config.add_connection({
                'hostname': hostname,
                'port': port,
                'username': username,
                'key_path': key_path
            })
            
            return connection_id
        except Exception as e:
            logger.error(f"Auto-connection error: {str(e)}")
    else:
        logger.warning("Auto-connect skipped: Missing hostname or username")
    
    return None

# Try auto-connect at startup
auto_connection_id = auto_connect()
if auto_connection_id:
    logger.info(f"Auto-connected to {auto_connection_id} at startup")

@app.route('/')
def index():
    """Render the main page."""
    saved_connections = config.get_connections()
    
    # Check if we're already auto-connected
    auto_connection_id = None
    for conn_id, client in ssh_connections.items():
        if client.is_connected():
            auto_connection_id = conn_id
            session['current_connection'] = conn_id
            logger.info(f"Active connection found: {conn_id}")
            break
    
    # If no active connection, try to auto-connect
    if not auto_connection_id:
        auto_connection_id = auto_connect()
        if auto_connection_id:
            session['current_connection'] = auto_connection_id
            return redirect(url_for('terminal', connection_id=auto_connection_id))
    
    # Get default values for the form
    default_host = mcp_settings.get('host', '')
    default_port = mcp_settings.get('port', '22')
    default_username = mcp_settings.get('username', '')
    default_key_path = mcp_settings.get('key_path', '')
    
    return render_template('index.html', 
                          connections=saved_connections,
                          auto_connection=auto_connection_id,
                          default_host=default_host,
                          default_port=default_port,
                          default_username=default_username,
                          default_key_path=default_key_path)

@app.route('/connect', methods=['POST'])
def connect():
    """Connect to a remote server via SSH."""
    hostname = request.form.get('hostname')
    port = int(request.form.get('port', 22))
    username = request.form.get('username')
    password = request.form.get('password', '')
    key_path = request.form.get('key_path', '')
    
    connection_id = f"{username}@{hostname}:{port}"
    
    try:
        # Log the connection attempt
        logger.info(f"Web interface: Connecting to {connection_id}")
        
        # Create SSH client and connect
        client = SSHClient()
        client.connect(hostname, port, username, password, key_path)
        
        # Store connection
        ssh_connections[connection_id] = client
        logger.info(f"Web interface: Successfully connected to {connection_id}")
        
        # Save to config if 'save' is checked
        if request.form.get('save'):
            config.add_connection({
                'hostname': hostname,
                'port': port,
                'username': username,
                'key_path': key_path
            })
        
        session['current_connection'] = connection_id
        return redirect(url_for('terminal', connection_id=connection_id))
    
    except Exception as e:
        logger.error(f"Connection error: {str(e)}")
        return render_template('index.html', 
                              error=f"Failed to connect: {str(e)}",
                              connections=config.get_connections(),
                              default_host=hostname,
                              default_port=port,
                              default_username=username,
                              default_key_path=key_path)

@app.route('/terminal/<connection_id>')
def terminal(connection_id):
    """Display terminal interface for an active connection."""
    if connection_id not in ssh_connections:
        return redirect(url_for('index'))
    
    return render_template('terminal.html', connection_id=connection_id)

@app.route('/execute', methods=['POST'])
def execute_command():
    """Execute a command on the remote server."""
    connection_id = request.form.get('connection_id')
    command = request.form.get('command')
    
    if not connection_id or not command or connection_id not in ssh_connections:
        return jsonify({"error": "Invalid request or connection lost"}), 400
    
    try:
        client = ssh_connections[connection_id]
        stdout, stderr = client.execute_command(command)
        return jsonify({
            "stdout": stdout,
            "stderr": stderr
        })
    except Exception as e:
        logger.error(f"Command execution error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/disconnect/<connection_id>')
def disconnect(connection_id):
    """Disconnect from a remote server."""
    if connection_id in ssh_connections:
        try:
            ssh_connections[connection_id].close()
            del ssh_connections[connection_id]
            if session.get('current_connection') == connection_id:
                session.pop('current_connection', None)
        except Exception as e:
            logger.error(f"Disconnect error: {str(e)}")
    
    return redirect(url_for('index'))

@app.route('/api/connections', methods=['GET'])
def api_connections():
    """API endpoint to get saved connections."""
    return jsonify(config.get_connections())

@app.route('/api/active_connections', methods=['GET'])
def api_active_connections():
    """API endpoint to get active connections."""
    return jsonify(list(ssh_connections.keys()))

# Enhanced MCP v1 API
@app.route('/connect', methods=['GET'])
def connect_endpoint():
    """MCP v1 API endpoint for connecting - GET method for Windsurf integration"""
    # This handles the case when Windsurf tries to hit /connect directly
    active_connections = []
    for conn_id, client in ssh_connections.items():
        if client.is_connected():
            username, hostname, port = conn_id.split('@')[0], conn_id.split('@')[1].split(':')[0], conn_id.split(':')[1]
            active_connections.append({
                "id": conn_id,
                "hostname": hostname,
                "port": int(port),
                "username": username,
                "connected": True
            })
    
    return jsonify({
        "status": "ok",
        "connections": active_connections
    })

# MCP v1 API - Disconnect endpoint
@app.route('/disconnect', methods=['POST'])
def disconnect_endpoint():
    """MCP v1 API endpoint for disconnecting"""
    data = request.json or {}
    connection_id = data.get('connection_id')
    
    if not connection_id or connection_id not in ssh_connections:
        return jsonify({"status": "error", "message": "Invalid connection ID"}), 400
    
    try:
        ssh_connections[connection_id].close()
        del ssh_connections[connection_id]
        logger.info(f"Disconnected from {connection_id}")
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Error disconnecting from {connection_id}: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# MCP v1 API - Execute command endpoint
@app.route('/execute', methods=['POST'])
def execute_endpoint():
    """MCP v1 API endpoint for executing commands"""
    data = request.json or {}
    connection_id = data.get('connection_id')
    command = data.get('command')
    
    if not connection_id or connection_id not in ssh_connections:
        return jsonify({"status": "error", "message": "Invalid connection ID"}), 400
    
    if not command:
        return jsonify({"status": "error", "message": "No command provided"}), 400
    
    try:
        client = ssh_connections[connection_id]
        output = client.execute_command(command)
        return jsonify({
            "status": "ok",
            "output": output
        })
    except Exception as e:
        logger.error(f"Error executing command on {connection_id}: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# MCP Protocol Endpoints - Updated to match Windsurf's expectations

@app.route('/alive', methods=['GET'])
def alive():
    """MCP protocol endpoint to check if the server is alive."""
    return jsonify({"status": "ok"})

@app.route('/list_sessions', methods=['GET'])
def list_sessions():
    """MCP protocol endpoint to list active SSH sessions."""
    sessions = []
    
    for conn_id, client in ssh_connections.items():
        connected = client.is_connected()
        if connected:
            parts = conn_id.split('@')
            if len(parts) == 2 and ':' in parts[1]:
                username = parts[0]
                host_parts = parts[1].split(':')
                hostname = host_parts[0]
                port = int(host_parts[1]) if len(host_parts) > 1 else 22
                
                sessions.append({
                    "id": conn_id,
                    "hostname": hostname,
                    "port": port,
                    "username": username,
                    "connected": connected
                })
    
    return jsonify({
        "status": "ok",
        "sessions": sessions
    })

@app.route('/ssh', methods=['POST'])
def ssh_command():
    """MCP protocol endpoint for SSH operations."""
    try:
        data = request.json
        operation = data.get('operation')
        
        # Handle different operations
        if operation == 'connect':
            return handle_ssh_connect(data)
        elif operation == 'execute':
            return handle_ssh_execute(data)
        elif operation == 'disconnect':
            return handle_ssh_disconnect(data)
        else:
            return jsonify({
                "status": "error", 
                "message": f"Unknown operation: {operation}"
            }), 400
    
    except Exception as e:
        logger.error(f"Error in SSH command: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

def handle_ssh_connect(data):
    """Handle SSH connect operation."""
    hostname = data.get('hostname')
    port = int(data.get('port', 22))
    username = data.get('username')
    password = data.get('password', '')
    key_path = data.get('key_path', '')
    
    if not hostname or not username:
        return jsonify({
            "status": "error", 
            "message": "Hostname and username are required"
        }), 400
    
    connection_id = f"{username}@{hostname}:{port}"
    
    # Check if already connected
    if connection_id in ssh_connections and ssh_connections[connection_id].is_connected():
        return jsonify({
            "status": "ok",
            "message": f"Already connected to {connection_id}",
            "connection_id": connection_id
        })
    
    try:
        logger.info(f"MCP API: Connecting to {connection_id}")
        client = SSHClient()
        client.connect(hostname, port, username, password, key_path)
        ssh_connections[connection_id] = client
        logger.info(f"MCP API: Successfully connected to {connection_id}")
        
        return jsonify({
            "status": "ok",
            "message": f"Connected to {connection_id}",
            "connection_id": connection_id
        })
    
    except Exception as e:
        logger.error(f"MCP API: Connection error to {connection_id}: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Failed to connect: {str(e)}"
        }), 500

def handle_ssh_execute(data):
    """Handle SSH execute operation."""
    connection_id = data.get('connection_id')
    command = data.get('command')
    
    if not connection_id:
        return jsonify({
            "status": "error", 
            "message": "Connection ID is required"
        }), 400
    
    if not command:
        return jsonify({
            "status": "error", 
            "message": "Command is required"
        }), 400
    
    if connection_id not in ssh_connections:
        return jsonify({
            "status": "error", 
            "message": f"Connection {connection_id} not found"
        }), 404
    
    client = ssh_connections[connection_id]
    
    if not client.is_connected():
        return jsonify({
            "status": "error", 
            "message": f"Connection {connection_id} is not active"
        }), 400
    
    try:
        logger.info(f"MCP API: Executing command on {connection_id}: {command}")
        output = client.execute_command(command)
        return jsonify({
            "status": "ok",
            "output": output
        })
    
    except Exception as e:
        logger.error(f"MCP API: Command execution error on {connection_id}: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Command execution failed: {str(e)}"
        }), 500

def handle_ssh_disconnect(data):
    """Handle SSH disconnect operation."""
    connection_id = data.get('connection_id')
    
    if not connection_id:
        return jsonify({
            "status": "error", 
            "message": "Connection ID is required"
        }), 400
    
    if connection_id not in ssh_connections:
        return jsonify({
            "status": "ok",
            "message": f"Connection {connection_id} not found or already disconnected"
        })
    
    try:
        logger.info(f"MCP API: Disconnecting from {connection_id}")
        ssh_connections[connection_id].close()
        del ssh_connections[connection_id]
        
        return jsonify({
            "status": "ok",
            "message": f"Disconnected from {connection_id}"
        })
    
    except Exception as e:
        logger.error(f"MCP API: Disconnect error from {connection_id}: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Failed to disconnect: {str(e)}"
        }), 500

# Additional MCP v1 Protocol Endpoints for Windsurf compatibility

@app.route('/ssh/sessions', methods=['GET'])
def ssh_sessions():
    """MCP protocol endpoint to list active SSH sessions (alternative endpoint)."""
    sessions = []
    
    for conn_id, client in ssh_connections.items():
        connected = client.is_connected()
        if connected:
            parts = conn_id.split('@')
            if len(parts) == 2 and ':' in parts[1]:
                username = parts[0]
                host_parts = parts[1].split(':')
                hostname = host_parts[0]
                port = int(host_parts[1]) if len(host_parts) > 1 else 22
                
                sessions.append({
                    "id": conn_id,
                    "hostname": hostname,
                    "port": port,
                    "username": username,
                    "connected": connected
                })
    
    return jsonify({
        "status": "ok",
        "sessions": sessions
    })

@app.route('/mcp/status', methods=['GET'])
def mcp_status():
    """MCP protocol endpoint to return server status."""
    auto_connection = None
    for conn_id, client in ssh_connections.items():
        if client.is_connected():
            auto_connection = conn_id
            break
            
    return jsonify({
        "status": "ok",
        "version": "1.0.0",
        "type": "ssh",
        "connection": auto_connection
    })

@app.route('/mcp/connect', methods=['POST'])
def mcp_connect():
    """MCP protocol endpoint for connecting to SSH servers."""
    try:
        data = request.json
        hostname = data.get('hostname')
        port = int(data.get('port', 22))
        username = data.get('username')
        password = data.get('password', '')
        key_path = data.get('key_path', '')
        
        if not hostname or not username:
            return jsonify({
                "status": "error", 
                "message": "Hostname and username are required"
            }), 400
        
        connection_id = f"{username}@{hostname}:{port}"
        
        logger.info(f"MCP: Connecting to {connection_id}")
        
        # Check if already connected
        if connection_id in ssh_connections and ssh_connections[connection_id].is_connected():
            return jsonify({
                "status": "ok",
                "message": f"Already connected to {connection_id}",
                "connection_id": connection_id
            })
        
        client = SSHClient()
        client.connect(hostname, port, username, password, key_path)
        ssh_connections[connection_id] = client
        
        logger.info(f"MCP: Successfully connected to {connection_id}")
        
        return jsonify({
            "status": "ok",
            "message": f"Connected to {connection_id}",
            "connection_id": connection_id
        })
    
    except Exception as e:
        logger.error(f"MCP Connect error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Failed to connect: {str(e)}"
        }), 500

@app.route('/mcp/execute', methods=['POST'])
def mcp_execute():
    """MCP protocol endpoint for executing SSH commands."""
    try:
        data = request.json
        connection_id = data.get('connection_id')
        command = data.get('command')
        
        if not connection_id:
            return jsonify({
                "status": "error", 
                "message": "Connection ID is required"
            }), 400
        
        if not command:
            return jsonify({
                "status": "error", 
                "message": "Command is required"
            }), 400
        
        if connection_id not in ssh_connections:
            return jsonify({
                "status": "error", 
                "message": f"Connection {connection_id} not found"
            }), 404
        
        client = ssh_connections[connection_id]
        
        if not client.is_connected():
            return jsonify({
                "status": "error", 
                "message": f"Connection {connection_id} is not active"
            }), 400
        
        logger.info(f"MCP: Executing command on {connection_id}: {command}")
        output = client.execute_command(command)
        return jsonify({
            "status": "ok",
            "output": output
        })
    
    except Exception as e:
        logger.error(f"MCP Execute error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Command execution failed: {str(e)}"
        }), 500

@app.route('/mcp/disconnect', methods=['POST'])
def mcp_disconnect():
    """MCP protocol endpoint for disconnecting from SSH servers."""
    try:
        data = request.json
        connection_id = data.get('connection_id')
        
        if not connection_id:
            return jsonify({
                "status": "error", 
                "message": "Connection ID is required"
            }), 400
        
        if connection_id not in ssh_connections:
            return jsonify({
                "status": "ok",
                "message": f"Connection {connection_id} not found or already disconnected"
            })
        
        logger.info(f"MCP: Disconnecting from {connection_id}")
        ssh_connections[connection_id].close()
        del ssh_connections[connection_id]
        
        return jsonify({
            "status": "ok",
            "message": f"Disconnected from {connection_id}"
        })
    
    except Exception as e:
        logger.error(f"MCP Disconnect error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Failed to disconnect: {str(e)}"
        }), 500

@app.route('/capabilities', methods=['GET'])
def capabilities():
    """MCP protocol endpoint to describe server capabilities."""
    return jsonify({
        "status": "ok",
        "capabilities": {
            "type": "ssh",
            "version": "1.0.0",
            "operations": ["connect", "execute", "disconnect"],
            "features": {
                "auto_connect": True,
                "key_auth": True,
                "password_auth": True
            }
        }
    })

@app.route('/sessions', methods=['GET'])
def sessions_endpoint():
    """Alternative MCP protocol endpoint for listing active sessions."""
    sessions = []
    
    for conn_id, client in ssh_connections.items():
        connected = client.is_connected()
        if connected:
            parts = conn_id.split('@')
            if len(parts) == 2 and ':' in parts[1]:
                username = parts[0]
                host_parts = parts[1].split(':')
                hostname = host_parts[0]
                port = int(host_parts[1]) if len(host_parts) > 1 else 22
                
                sessions.append({
                    "id": conn_id,
                    "hostname": hostname,
                    "port": port,
                    "username": username,
                    "connected": connected
                })
    
    return jsonify({
        "status": "ok",
        "sessions": sessions
    })

# MCP SSH-specific Protocol Endpoints

@app.route('/ssh/alive', methods=['GET'])
def ssh_alive():
    """SSH-specific MCP protocol endpoint to check if the server is alive."""
    return jsonify({"status": "ok"})

@app.route('/ssh/capabilities', methods=['GET'])
def ssh_capabilities():
    """SSH-specific MCP protocol endpoint to describe server capabilities."""
    return jsonify({
        "status": "ok",
        "type": "ssh",
        "version": "1.0.0",
        "operations": ["connect", "execute", "disconnect"],
        "features": {
            "auto_connect": True,
            "key_auth": True,
            "password_auth": True
        }
    })

@app.route('/ssh/connect', methods=['POST'])
def ssh_connect_endpoint():
    """SSH-specific MCP protocol endpoint for connecting."""
    try:
        data = request.json or {}
        hostname = data.get('hostname')
        port = int(data.get('port', 22))
        username = data.get('username')
        password = data.get('password', '')
        key_path = data.get('key_path', '')
        
        if not hostname or not username:
            return jsonify({
                "status": "error", 
                "message": "Hostname and username are required"
            }), 400
        
        connection_id = f"{username}@{hostname}:{port}"
        
        logger.info(f"SSH API: Connecting to {connection_id}")
        
        # Check if already connected
        if connection_id in ssh_connections and ssh_connections[connection_id].is_connected():
            return jsonify({
                "status": "ok",
                "message": f"Already connected to {connection_id}",
                "connection_id": connection_id
            })
        
        client = SSHClient()
        client.connect(hostname, port, username, password, key_path)
        ssh_connections[connection_id] = client
        
        logger.info(f"SSH API: Successfully connected to {connection_id}")
        
        return jsonify({
            "status": "ok",
            "message": f"Connected to {connection_id}",
            "connection_id": connection_id
        })
    
    except Exception as e:
        logger.error(f"SSH API: Connection error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Failed to connect: {str(e)}"
        }), 500

@app.route('/ssh/execute', methods=['POST'])
def ssh_execute_endpoint():
    """SSH-specific MCP protocol endpoint for executing commands."""
    try:
        data = request.json or {}
        connection_id = data.get('connection_id')
        command = data.get('command')
        
        if not connection_id or not command:
            return jsonify({
                "status": "error", 
                "message": "Connection ID and command are required"
            }), 400
        
        if connection_id not in ssh_connections:
            return jsonify({
                "status": "error", 
                "message": f"Connection {connection_id} not found"
            }), 404
        
        client = ssh_connections[connection_id]
        
        if not client.is_connected():
            return jsonify({
                "status": "error", 
                "message": f"Connection {connection_id} is not active"
            }), 400
        
        logger.info(f"SSH API: Executing command on {connection_id}: {command}")
        output = client.execute_command(command)
        
        return jsonify({
            "status": "ok",
            "output": output
        })
    
    except Exception as e:
        logger.error(f"SSH API: Command execution error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Command execution failed: {str(e)}"
        }), 500

@app.route('/ssh/disconnect', methods=['POST'])
def ssh_disconnect_endpoint():
    """SSH-specific MCP protocol endpoint for disconnecting."""
    try:
        data = request.json or {}
        connection_id = data.get('connection_id')
        
        if not connection_id:
            return jsonify({
                "status": "error", 
                "message": "Connection ID is required"
            }), 400
        
        if connection_id not in ssh_connections:
            return jsonify({
                "status": "ok",
                "message": f"Connection {connection_id} not found or already disconnected"
            })
        
        logger.info(f"SSH API: Disconnecting from {connection_id}")
        ssh_connections[connection_id].close()
        del ssh_connections[connection_id]
        
        return jsonify({
            "status": "ok",
            "message": f"Disconnected from {connection_id}"
        })
    
    except Exception as e:
        logger.error(f"SSH API: Disconnect error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Failed to disconnect: {str(e)}"
        }), 500

if __name__ == '__main__':
    # Create template directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5050, debug=True)
