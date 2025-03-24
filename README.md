# MCP SSH Server

A web-based SSH client that allows you to connect to remote servers through a browser interface.

## Features

- Connect to remote servers via SSH using password or key-based authentication
- Save and manage connection details for quick access
- Web-based terminal interface
- Secure connection handling

## Prerequisites

- Python 3.7+
- Flask for the web server
- Paramiko for SSH connections
- PyYAML for configuration management

## Installation

1. Clone the repository:
```
git clone <repository-url>
cd MCP
```

2. Install the required dependencies:
```
pip install -r requirements.txt
```

3. Set up environment variables (optional):
```
# Create .env file
echo "SECRET_KEY=your_secret_key_here" > .env
```

## Usage

1. Start the server:
```
python app.py
```

2. Open your web browser and navigate to:
```
http://localhost:5000
```

3. Enter your SSH connection details and connect to a remote server.

## Configuration

The application stores saved connections in `~/.mcp/connections.yaml`. This file is automatically created on first run.

## Security Notes

- For production use, make sure to set a strong SECRET_KEY in the .env file
- SSH passwords are not stored in the configuration file, only connection details
- Consider using key-based authentication instead of passwords for better security

## License

MIT
