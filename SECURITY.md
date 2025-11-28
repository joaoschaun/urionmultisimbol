# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.0.x   | :white_check_mark: |
| 1.x.x   | :x:                |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please follow these steps:

### 1. DO NOT Create a Public Issue

Please **do not** create a public GitHub issue for security vulnerabilities.

### 2. Report Privately

Send a detailed report to: **security@exemplo.com**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if you have one)

### 3. Wait for Response

We will respond within **48 hours** and work with you to:
- Validate the issue
- Determine severity
- Develop a fix
- Coordinate disclosure

### 4. Responsible Disclosure

Please give us reasonable time to fix the vulnerability before public disclosure.

## Security Best Practices for Users

### 🔐 Credentials

- **NEVER** commit `.env` files
- **NEVER** share your MT5 password
- **NEVER** share your Telegram bot token
- Use strong, unique passwords
- Rotate credentials regularly

### 💰 Trading Security

- **ALWAYS** test in demo account first
- Start with small amounts
- Use stop losses
- Monitor the bot regularly
- Keep backups of your database

### 🖥️ System Security

- Keep Python and dependencies updated
- Use antivirus software
- Don't run as administrator/root
- Keep your OS updated
- Use firewall

### 🔒 API Keys

- Use read-only API keys when possible
- Limit API key permissions
- Monitor API usage
- Rotate keys periodically

### 📦 Dependencies

We regularly update dependencies to patch security vulnerabilities. 

To update:
```bash
pip install -r requirements.txt --upgrade
```

### 🔍 Security Audits

We perform security audits:
- Before major releases
- When critical vulnerabilities are reported
- Quarterly reviews of dependencies

## Known Security Considerations

### MetaTrader 5 Connection

- Connection uses local MT5 terminal
- No credentials are sent over network
- All trading goes through official MT5 API

### Database

- SQLite database stores trade history
- No sensitive credentials in database
- Consider encrypting database for production

### Telegram Bot

- Webhook mode recommended for production
- Polling mode safe for development
- Bot token must be kept secret

## Security Updates

Security updates are released as soon as possible and tagged with `security` label.

Update immediately if you see:
```bash
git pull origin main
pip install -r requirements.txt --upgrade
```

## Contact

For security concerns: security@exemplo.com

For general questions: Use [GitHub Issues](https://github.com/joaoschaun/urionmultisimbol/issues)

---

**Remember**: Trading bots with real money require extra security caution. When in doubt, ask!
