# Security Policy

## Supported Versions

Use this section to tell people about which versions of your project are currently being supported with security updates.

| Version | Supported          |
| ------- | ------------------ |
| 1.2.4   | :white_check_mark: |
| 1.2.0   | :white_check_mark: |
| 1.1.0   | :x:                |
| 1.0.0   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security vulnerability, please follow these steps:

### 1. **DO NOT** create a public GitHub issue
Security vulnerabilities should be reported privately to avoid potential exploitation.

### 2. Email us directly
Send an email to [security@anycommand.com](mailto:security@anycommand.com) with:
- A detailed description of the vulnerability
- Steps to reproduce the issue
- Potential impact assessment
- Suggested fix (if available)

### 3. What to expect
- You will receive an acknowledgment within 48 hours
- We will investigate the report thoroughly
- We will keep you updated on the progress
- Once fixed, we will credit you in the security advisory (unless you prefer to remain anonymous)

## Security Best Practices

### For Users
- Keep the server updated to the latest version
- Use strong PIN codes for authentication
- Only run the server on trusted networks
- Regularly check for updates
- Monitor server logs for suspicious activity

### For Developers
- Never commit sensitive files (API keys, credentials)
- Use environment variables for configuration
- Validate all user inputs
- Follow secure coding practices
- Keep dependencies updated

## Security Features

### Authentication
- PIN-based authentication system
- Secure PIN generation and validation
- Session management with timeouts

### Network Security
- Local network only (no internet communication)
- Encrypted file transfers
- Secure WebSocket connections

### Input Validation
- All user inputs are validated
- Protection against injection attacks
- Secure file handling

## Known Security Considerations

### Windows-Specific
- The server requires administrator privileges for some features
- Screen sharing uses Windows GDI APIs
- Input simulation uses Windows API calls

### Network
- Server only accepts local network connections
- No external communication by default
- Firewall rules may need adjustment

## Disclosure Policy

When a security vulnerability is discovered and fixed:

1. **Immediate Response**: Critical vulnerabilities will be addressed immediately
2. **Public Disclosure**: Security advisories will be published on GitHub
3. **Version Updates**: Patched versions will be released promptly
4. **Documentation**: Security fixes will be documented in the changelog

## Security Contacts

- **Security Team**: [security@anycommand.com](mailto:security@anycommand.com)
- **GitHub Security**: Use GitHub's security advisory feature
- **Responsible Disclosure**: We follow responsible disclosure practices

## Bug Bounty

Currently, we do not offer a formal bug bounty program. However, security researchers who responsibly disclose vulnerabilities will be:

- Credited in security advisories
- Listed in our acknowledgments
- Given early access to security patches

## Security Checklist

Before releasing any version, we ensure:

- [ ] No hardcoded credentials
- [ ] All dependencies are up to date
- [ ] Input validation is implemented
- [ ] Error messages don't leak sensitive information
- [ ] Logs don't contain sensitive data
- [ ] Network communication is secure
- [ ] Authentication is properly implemented

## Reporting Security Issues

If you find a security vulnerability, please report it to us at [security@anycommand.com](mailto:security@anycommand.com) rather than creating a public issue.

Thank you for helping keep AnyCommand Windows Server secure! 