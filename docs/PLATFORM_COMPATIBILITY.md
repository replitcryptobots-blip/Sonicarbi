# Platform Compatibility Guide

Sonicarbi is designed to run on multiple platforms. This guide helps ensure smooth operation across different environments.

## Supported Platforms

- ✅ **Linux** (Ubuntu, Debian, Arch, etc.)
- ✅ **Windows 10/11** (Native & WSL)
- ✅ **macOS** (Intel & Apple Silicon)
- ✅ **Android** (via Termux)
- ✅ **Docker** (all platforms)

## Quick Start by Platform

### 🐧 Linux
```bash
git clone https://github.com/replitcryptobots-blip/Sonicarbi.git
cd Sonicarbi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config/.env.example config/.env
# Edit config/.env
python src/scanner.py
```

### 🪟 Windows
```powershell
git clone https://github.com/replitcryptobots-blip/Sonicarbi.git
cd Sonicarbi
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy config\.env.example config\.env
REM Edit config\.env
python src\scanner.py
```

Or use automated installer:
```powershell
install_windows.bat
```

### 📱 Android (Termux)
```bash
curl -O https://raw.githubusercontent.com/replitcryptobots-blip/Sonicarbi/main/install_termux.sh
bash install_termux.sh
```

See [TERMUX_SETUP.md](TERMUX_SETUP.md) for complete guide.

### 🍎 macOS
```bash
# Install Homebrew if needed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install python@3.11 postgresql

# Clone and setup
git clone https://github.com/replitcryptobots-blip/Sonicarbi.git
cd Sonicarbi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config/.env.example config/.env
# Edit config/.env
python src/scanner.py
```

### 🐳 Docker (All Platforms)
```bash
git clone https://github.com/replitcryptobots-blip/Sonicarbi.git
cd Sonicarbi
docker build -t sonicarbi .
docker run -d --name arbitrage-bot --env-file config/.env sonicarbi
```

## Path Handling

The bot automatically handles platform-specific paths:

```python
# Works on all platforms
from pathlib import Path

config_dir = Path(__file__).parent / 'config'
config_file = config_dir / '.env'
```

## Platform-Specific Features

### Windows
- Task Scheduler integration
- Windows Service support
- PowerShell scripts included
- Native and WSL support

### Linux
- systemd service files
- cron job support
- Full PostgreSQL support
- Best performance

### macOS
- launchd integration
- Native M1/M2 support
- Homebrew package management

### Android (Termux)
- Termux:Boot auto-start
- Termux:API notifications
- Wake lock support
- Low power consumption mode

## Resource Requirements

| Platform | RAM | CPU | Storage | Network |
|----------|-----|-----|---------|---------|
| Linux | 256MB | 1 core | 500MB | Broadband |
| Windows | 512MB | 1 core | 1GB | Broadband |
| macOS | 512MB | 1 core | 1GB | Broadband |
| Android | 512MB | 1 core | 1GB | WiFi/4G |

## Troubleshooting by Platform

### All Platforms
```bash
# Validate configuration
python scripts/validate_config.py

# Run tests
pytest -v

# Check logs
tail -f logs/bot.log  # Linux/macOS
Get-Content logs\bot.log -Wait  # Windows (PowerShell)
```

### Platform-Specific Issues

See platform-specific guides:
- [TERMUX_SETUP.md](TERMUX_SETUP.md) - Android/Termux
- [WINDOWS_SETUP.md](WINDOWS_SETUP.md) - Windows

## Best Platform for 24/7 Operation

1. **Linux VPS** - Most reliable, best performance
2. **Android (Termux)** - Portable, low cost
3. **Windows PC** - Easy setup, familiar
4. **macOS** - Reliable but power hungry

## Security Considerations

### All Platforms
- Never commit `.env` file
- Use dedicated wallet
- Enable firewall
- Regular updates

### Windows
- Enable BitLocker
- Windows Defender exclusions
- Disable remote desktop if not needed

### Android
- Screen lock required
- App encryption
- Disable USB debugging in production
- Keep device in secure location

### Linux
- UFW firewall
- Regular `apt update && apt upgrade`
- SSH key authentication only
- fail2ban recommended

## Performance Optimization

### Linux
```bash
# Increase file descriptors
ulimit -n 4096

# Disable swap if SSD
sudo swapoff -a
```

### Windows
```powershell
# Set high priority
Get-Process python | ForEach-Object { $_.PriorityClass = 'High' }
```

### Android
```bash
# Acquire wakelock
termux-wake-lock

# Free memory
pkg clean
```

## Database Support

| Platform | PostgreSQL | SQLite | No DB |
|----------|------------|--------|-------|
| Linux | ✅ Full | ✅ | ✅ |
| Windows | ✅ Full | ✅ | ✅ |
| macOS | ✅ Full | ✅ | ✅ |
| Android | ✅ Limited | ✅ | ✅ |

**Recommendation**:
- Production: PostgreSQL
- Testing: SQLite or No DB
- Mobile: No DB (logs only)

## Notification Support

| Platform | Telegram | Discord | Console | Email |
|----------|----------|---------|---------|-------|
| All | ✅ | ✅ | ✅ | ✅ |

Telegram recommended for mobile monitoring.

## Deployment Checklist

### Pre-Deployment (All Platforms)
- [ ] Python 3.11+ installed
- [ ] Git installed
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] `.env` configured
- [ ] Configuration validated
- [ ] Tests passing
- [ ] Testnet tested

### Linux
- [ ] systemd service configured
- [ ] Firewall rules set
- [ ] Auto-start enabled
- [ ] Monitoring setup

### Windows
- [ ] Task Scheduler configured
- [ ] Firewall exception added
- [ ] Auto-start enabled
- [ ] Antivirus exclusion set

### Android
- [ ] Termux:Boot installed
- [ ] Wake lock enabled
- [ ] Battery optimization disabled
- [ ] Storage permission granted

## Getting Help

- Platform issues: Check platform-specific guides
- General issues: GitHub Issues
- Quick questions: Discord (if available)

## Contributing

When contributing, ensure changes work across all platforms:
1. Use `pathlib.Path` for file paths
2. Avoid platform-specific commands
3. Test on multiple platforms if possible
4. Document platform-specific behavior
