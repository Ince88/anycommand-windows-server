# AnyCommand Windows Companion Server

A powerful Windows companion server that enables remote control of your Windows PC from mobile devices. This server provides screen sharing, file transfer, clipboard synchronization, and gamepad emulation capabilities.

## Features

- **Remote Control**: Full mouse and keyboard control from mobile devices
- **Screen Sharing**: Real-time screen capture and sharing
- **File Transfer**: Secure file transfer between devices
- **Clipboard Sync**: Synchronize clipboard content across devices
- **Gamepad Emulation**: Use mobile device as a gamepad for PC games
- **PIN Authentication**: Secure connection with customizable PIN codes
- **System Tray Integration**: Runs in background with system tray support
- **Auto-start Support**: Configure to start with Windows

## Requirements

- Windows 10/11
- Python 3.8 or higher
- Administrator privileges (for some features)

## Installation

### Option 1: Using the Installer (Recommended)

1. Download the latest release from the [Releases](https://github.com/your-repo/releases) page
2. Run the installer as Administrator
3. Follow the installation wizard

### Option 2: Manual Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/your-repo/anycommand-windows-server.git
   cd anycommand-windows-server/server
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the server:
   ```bash
   python server_gui.py
   ```

## Usage

1. **Start the Server**: Run `server_gui.py` or use the installer
2. **Get Connection Info**: The GUI displays your IP address and PIN code
3. **Connect from Mobile**: Use the AnyCommand mobile app to connect
4. **Remote Control**: Control your PC remotely with full mouse/keyboard support

## Configuration

### PIN Configuration

The server supports two PIN modes:
- **Auto-generated PIN**: Server generates a random 6-digit PIN
- **Custom PIN**: Set your own PIN code

### Auto-start

Enable auto-start to have the server start automatically with Windows:
1. Open the server GUI
2. Go to Settings → Auto-start
3. Toggle the auto-start option

### File Transfer Directory

Configure the file transfer directory in Settings:
1. Open the server GUI
2. Go to Settings → File Transfer
3. Set your preferred directory

## Development

### Project Structure

```
server/
├── remote_server.py          # Main server implementation
├── server_gui.py            # GUI application
├── screen_share_service.py  # Screen sharing functionality
├── file_transfer_service.py # File transfer service
├── clipboard_service.py     # Clipboard synchronization
├── window_thumbnails_service.py # Window thumbnails
├── websocket_server.py     # WebSocket server for text input
├── shortcuts_handler.py    # Keyboard shortcuts handling
├── requirements.txt        # Python dependencies
└── assets/               # GUI assets
```

### Building from Source

1. Install build dependencies:
   ```bash
   pip install pyinstaller
   ```

2. Build the executable:
   ```bash
   pyinstaller server_gui.spec
   ```

3. The executable will be created in `dist/server_gui/`

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Security

- **PIN Authentication**: All connections require a PIN code
- **Local Network Only**: Server only accepts connections from local network
- **No Internet Communication**: Server doesn't communicate with external services
- **Secure File Transfer**: File transfers use encrypted channels

## Troubleshooting

### Common Issues

1. **Server won't start**
   - Ensure you're running as Administrator
   - Check if another instance is already running
   - Verify Python and dependencies are installed

2. **Connection issues**
   - Check firewall settings
   - Ensure both devices are on the same network
   - Verify the correct IP address and PIN

3. **Screen sharing not working**
   - Ensure you have the latest graphics drivers
   - Check Windows display settings

### Logs

Server logs are saved to:
- `remote_server.log` - Main server logs
- `server.log` - GUI application logs

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: Report bugs and feature requests on GitHub
- **Discussions**: Join community discussions
- **Documentation**: Check the wiki for detailed guides

## Acknowledgments

- Built with Python and CustomTkinter
- Uses PyAutoGUI for input simulation
- Screen sharing powered by Windows GDI
- File transfer uses secure WebSocket connections 