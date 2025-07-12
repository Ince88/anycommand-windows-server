# Contributing to AnyCommand Windows Server

Thank you for your interest in contributing to AnyCommand Windows Server! This document provides guidelines and information for contributors.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Windows 10/11
- Git
- Basic knowledge of Python and Windows development

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/your-username/anycommand-windows-server.git
   cd anycommand-windows-server/server
   ```

2. **Install Dependencies**
   ```bash
   python setup.py
   # or manually:
   pip install -r requirements.txt
   ```

3. **Run the Server**
   ```bash
   python server_gui.py
   ```

## Development Guidelines

### Code Style

- Follow PEP 8 style guidelines
- Use meaningful variable and function names
- Add docstrings to all functions and classes
- Keep functions focused and single-purpose

### Testing

- Test your changes thoroughly on Windows
- Test both GUI and command-line modes
- Verify screen sharing, file transfer, and input simulation work correctly
- Test with different Python versions (3.8+)

### Security Considerations

- Never commit sensitive files (API keys, credentials)
- Use environment variables for configuration
- Validate all user inputs
- Follow secure coding practices

## Project Structure

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
├── setup.py              # Setup script
├── README.md             # Project documentation
├── LICENSE               # MIT License
├── CONTRIBUTING.md       # This file
└── assets/              # GUI assets
```

## Making Changes

### Feature Development

1. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Your Changes**
   - Follow the coding guidelines
   - Add appropriate comments and documentation
   - Test your changes thoroughly

3. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "Add feature: brief description"
   ```

4. **Push and Create Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```

### Bug Fixes

1. **Create a Bug Fix Branch**
   ```bash
   git checkout -b fix/bug-description
   ```

2. **Fix the Bug**
   - Identify the root cause
   - Implement the fix
   - Add tests if applicable

3. **Commit and Push**
   ```bash
   git commit -m "Fix: brief description of the fix"
   git push origin fix/bug-description
   ```

## Pull Request Guidelines

### Before Submitting

- [ ] Code follows PEP 8 style guidelines
- [ ] All tests pass
- [ ] Documentation is updated
- [ ] No sensitive data is included
- [ ] Changes are tested on Windows

### Pull Request Template

```markdown
## Description
Brief description of the changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Code refactoring

## Testing
- [ ] Tested on Windows 10/11
- [ ] Tested with Python 3.8+
- [ ] All functionality works correctly

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No sensitive data included
```

## Areas for Contribution

### High Priority
- Performance improvements
- Security enhancements
- Bug fixes
- Documentation improvements

### Medium Priority
- New features
- UI/UX improvements
- Code refactoring
- Test coverage

### Low Priority
- Minor optimizations
- Code style improvements
- Additional documentation

## Communication

### Issues
- Use GitHub Issues for bug reports and feature requests
- Provide detailed information about the issue
- Include system information and steps to reproduce

### Discussions
- Use GitHub Discussions for general questions
- Share ideas and suggestions
- Help other contributors

## Code of Conduct

- Be respectful and inclusive
- Help others learn and grow
- Provide constructive feedback
- Follow the project's coding standards

## License

By contributing to this project, you agree that your contributions will be licensed under the MIT License.

## Questions?

If you have questions about contributing, feel free to:
- Open a GitHub Issue
- Start a GitHub Discussion
- Contact the maintainers

Thank you for contributing to AnyCommand Windows Server! 