# Sonicarbi on Windows

Complete guide to running the Sonicarbi arbitrage bot on Windows 10/11.

## Prerequisites

- Windows 10 or Windows 11
- At least 4GB free storage
- Stable internet connection
- Administrator access

## Installation Methods

### Method 1: Native Windows (Recommended)

#### 1. Install Python 3.11+

Download from: https://www.python.org/downloads/

**IMPORTANT**: During installation, check "Add Python to PATH"!

Verify installation:
```powershell
python --version
# Should show: Python 3.11.x or higher
```

#### 2. Install Git

Download from: https://git-scm.com/download/win

Use default settings during installation.

Verify:
```powershell
git --version
```

#### 3. Install PostgreSQL (Optional)

Download from: https://www.postgresql.org/download/windows/

During installation:
- Set password for postgres user
- Default port: 5432
- Remember the password!

Create database:
```powershell
# Open Command Prompt as Administrator
psql -U postgres
CREATE DATABASE mev_scroll_db;
\q
```

#### 4. Clone Repository

```powershell
# Open PowerShell or Command Prompt
cd %USERPROFILE%\Documents
git clone https://github.com/replitcryptobots-blip/Sonicarbi.git
cd Sonicarbi
```

#### 5. Create Virtual Environment

```powershell
# Create virtual environment
python -m venv venv

# Activate it
.\venv\Scripts\activate

# Your prompt should now show (venv)
```

#### 6. Install Dependencies

```powershell
# Upgrade pip first
python -m pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# If you get SSL errors:
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```

#### 7. Configure Environment

```powershell
# Copy example config
copy config\.env.example config\.env

# Edit with Notepad
notepad config\.env
```

**Windows-specific configuration:**
```bash
# Network
SCROLL_RPC_URL=https://rpc.scroll.io
SCROLL_TESTNET_RPC=https://sepolia-rpc.scroll.io
NETWORK_MODE=testnet

# Your private key (64 hex characters, no 0x prefix)
PRIVATE_KEY=your_private_key_here

# Database (if using PostgreSQL)
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/mev_scroll_db

# Notifications
ENABLE_TELEGRAM_ALERTS=true
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
DISCORD_WEBHOOK_URL=your_webhook_url

# Windows-specific: Use forward slashes or double backslashes for paths
# LOG_PATH=C:/Users/YourName/Documents/Sonicarbi/logs
```

Save and close Notepad.

#### 8. Validate Configuration

```powershell
python scripts\validate_config.py
```

#### 9. Run the Bot

```powershell
# Make sure virtual environment is activated
.\venv\Scripts\activate

# Run the scanner
python src\scanner.py
```

---

### Method 2: Windows Subsystem for Linux (WSL)

For advanced users who prefer Linux environment.

#### 1. Enable WSL

```powershell
# Open PowerShell as Administrator
wsl --install

# Restart your computer
```

#### 2. Install Ubuntu

```powershell
# After restart, install Ubuntu
wsl --install -d Ubuntu

# Set up username and password when prompted
```

#### 3. Update Ubuntu

```bash
# Inside WSL Ubuntu terminal
sudo apt update && sudo apt upgrade -y
```

#### 4. Follow Linux Installation

```bash
# Install dependencies
sudo apt install -y python3 python3-pip python3-venv git postgresql

# Clone repo
cd ~
git clone https://github.com/replitcryptobots-blip/Sonicarbi.git
cd Sonicarbi

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt

# Configure
cp config/.env.example config/.env
nano config/.env

# Run
python src/scanner.py
```

---

## Running in Background on Windows

### Option 1: Using PowerShell Background Job

```powershell
# Start bot in background
Start-Job -ScriptBlock {
    cd C:\Users\YourName\Documents\Sonicarbi
    .\venv\Scripts\activate
    python src\scanner.py
}

# List running jobs
Get-Job

# View job output
Receive-Job -Id 1

# Stop job
Stop-Job -Id 1
Remove-Job -Id 1
```

### Option 2: Using Windows Task Scheduler (Recommended)

Create a scheduled task that runs on startup:

1. Open Task Scheduler (search in Start menu)
2. Click "Create Basic Task"
3. Name: "Sonicarbi Arbitrage Bot"
4. Trigger: "When the computer starts"
5. Action: "Start a program"
6. Program: `C:\Users\YourName\Documents\Sonicarbi\venv\Scripts\python.exe`
7. Arguments: `src\scanner.py`
8. Start in: `C:\Users\YourName\Documents\Sonicarbi`
9. Check "Run whether user is logged on or not"
10. Check "Run with highest privileges"

### Option 3: Create a Batch Script

Create `start_bot.bat`:
```batch
@echo off
cd /d %~dp0
call venv\Scripts\activate.bat
python src\scanner.py
pause
```

Double-click to run!

### Option 4: Create a Windows Service

For advanced users - runs bot as a Windows service.

Install NSSM (Non-Sucking Service Manager):
```powershell
# Download from https://nssm.cc/download
# Extract to C:\nssm

# Install service
C:\nssm\nssm.exe install SonicarbiBot "C:\Users\YourName\Documents\Sonicarbi\venv\Scripts\python.exe" "src\scanner.py"

# Set working directory
C:\nssm\nssm.exe set SonicarbiBot AppDirectory "C:\Users\YourName\Documents\Sonicarbi"

# Start service
C:\nssm\nssm.exe start SonicarbiBot

# Stop service
C:\nssm\nssm.exe stop SonicarbiBot

# Remove service
C:\nssm\nssm.exe remove SonicarbiBot
```

---

## Windows-Specific Optimizations

### 1. Prevent Windows Sleep

```powershell
# Disable sleep while plugged in
powercfg /change standby-timeout-ac 0

# Disable hibernation
powercfg /hibernate off
```

### 2. Set Process Priority

```powershell
# Set high priority for Python process
Get-Process python | ForEach-Object { $_.PriorityClass = 'High' }
```

### 3. Windows Defender Exception

Add Sonicarbi folder to Windows Defender exclusions:

1. Open Windows Security
2. Virus & threat protection
3. Manage settings
4. Exclusions > Add exclusion
5. Folder: `C:\Users\YourName\Documents\Sonicarbi`

This prevents antivirus from slowing down the bot.

### 4. Create Desktop Shortcut

Create `Sonicarbi.vbs` (double-click to run hidden):
```vbscript
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run chr(34) & "C:\Users\YourName\Documents\Sonicarbi\start_bot.bat" & Chr(34), 0
Set WshShell = Nothing
```

---

## Troubleshooting

### Issue: "Python is not recognized"

**Solution:**
1. Reinstall Python and check "Add Python to PATH"
2. Or manually add to PATH:
   - Settings > System > About > Advanced system settings
   - Environment Variables
   - Edit PATH, add: `C:\Users\YourName\AppData\Local\Programs\Python\Python311`

### Issue: "pip install fails with SSL error"

**Solution:**
```powershell
# Option 1: Use trusted host
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

# Option 2: Upgrade pip
python -m pip install --upgrade pip
```

### Issue: "Access Denied" errors

**Solution:**
Run PowerShell or Command Prompt as Administrator:
- Right-click > Run as Administrator

### Issue: "psycopg2 installation fails"

**Solution:**
```powershell
# Use binary version (no compilation needed)
pip install psycopg2-binary
```

### Issue: "Virtual environment activation fails"

**Solution:**
```powershell
# Enable script execution
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then activate
.\venv\Scripts\activate
```

### Issue: "Port already in use" (PostgreSQL)

**Solution:**
```powershell
# Check what's using port 5432
netstat -ano | findstr :5432

# Kill the process
taskkill /PID <process_id> /F
```

### Issue: Firewall blocking connections

**Solution:**
1. Windows Firewall > Allow an app
2. Click "Change settings"
3. Allow Python through firewall

---

## Monitoring on Windows

### 1. View Logs

```powershell
# Real-time log viewing
Get-Content logs\bot.log -Wait -Tail 50

# Or use Notepad++, VS Code, etc.
notepad logs\bot.log
```

### 2. Check if Bot is Running

```powershell
# Check Python processes
Get-Process python

# Check specific bot process
Get-Process | Where-Object {$_.Path -like "*Sonicarbi*"}
```

### 3. Resource Monitoring

```powershell
# Open Task Manager
taskmgr

# Or use Resource Monitor
perfmon /res
```

### 4. Set Up Logging

Edit `config/.env`:
```bash
# Enable detailed logging
DEBUG_MODE=true

# Log to file (Windows path format)
LOG_FILE=C:/Users/YourName/Documents/Sonicarbi/logs/bot.log
```

---

## Performance Tips

### 1. Optimize Windows for Performance

1. Disable unnecessary startup programs
2. Disable Windows Search indexing for Sonicarbi folder
3. Use SSD for better I/O performance
4. Keep at least 20% disk space free

### 2. Network Optimization

```powershell
# Flush DNS cache
ipconfig /flushdns

# Reset TCP/IP stack (if connection issues)
netsh int ip reset
netsh winsock reset
```

### 3. Python Optimization

Add to `config/.env`:
```bash
# Disable Python buffering for immediate log output
PYTHONUNBUFFERED=1

# Use optimized Python
PYTHONOPTIMIZE=1
```

---

## Security Best Practices

1. **Use Windows Firewall** - Block unnecessary inbound connections
2. **Enable BitLocker** - Encrypt drive containing bot files
3. **Regular Windows Updates** - Keep system patched
4. **Strong Windows Password** - Protect your account
5. **Backup .env file** - Use Windows Backup or OneDrive (encrypted)
6. **Antivirus Exception** - Add Sonicarbi folder to exclusions
7. **Limited Funds** - Only keep necessary funds in bot wallet

---

## Automation Scripts

### Auto-Restart on Crash

Create `watch_bot.ps1`:
```powershell
while ($true) {
    $process = Get-Process python -ErrorAction SilentlyContinue | Where-Object {$_.Path -like "*Sonicarbi*"}

    if (-not $process) {
        Write-Host "Bot crashed! Restarting..."
        Set-Location "C:\Users\YourName\Documents\Sonicarbi"
        & .\venv\Scripts\python.exe src\scanner.py
    }

    Start-Sleep -Seconds 60
}
```

Run in background:
```powershell
Start-Job -FilePath .\watch_bot.ps1
```

### Daily Backup Script

Create `backup.ps1`:
```powershell
$source = "C:\Users\YourName\Documents\Sonicarbi\config\.env"
$destination = "C:\Users\YourName\OneDrive\Backups\sonicarbi_$(Get-Date -Format 'yyyy-MM-dd').env"

Copy-Item $source $destination
Write-Host "Backup completed: $destination"
```

Schedule with Task Scheduler to run daily.

---

## Alternative: Docker on Windows

For consistent environment across platforms:

### 1. Install Docker Desktop

Download from: https://www.docker.com/products/docker-desktop/

### 2. Create Dockerfile

Already included in the repo (if not, create it):
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "src/scanner.py"]
```

### 3. Build and Run

```powershell
# Build image
docker build -t sonicarbi .

# Run container
docker run -d --name arbitrage-bot `
  --env-file config/.env `
  --restart unless-stopped `
  sonicarbi

# View logs
docker logs -f arbitrage-bot

# Stop
docker stop arbitrage-bot

# Restart
docker restart arbitrage-bot
```

---

## Remote Access

### Access bot from phone/laptop:

#### Option 1: Windows Remote Desktop

1. Enable Remote Desktop in Windows Settings
2. Use Microsoft Remote Desktop app on phone
3. Connect to your Windows PC

#### Option 2: TeamViewer / AnyDesk

1. Install TeamViewer or AnyDesk
2. Access from mobile app
3. View bot logs remotely

#### Option 3: Telegram Bot

Best option - get alerts on your phone:
```bash
ENABLE_TELEGRAM_ALERTS=true
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

---

## Useful Windows Commands

```powershell
# Navigate to bot directory
cd C:\Users\YourName\Documents\Sonicarbi

# Activate virtual environment
.\venv\Scripts\activate

# Run bot
python src\scanner.py

# Run tests
pytest

# Validate config
python scripts\validate_config.py

# View recent logs
Get-Content logs\bot.log -Tail 50

# Check Python processes
Get-Process python

# Kill Python processes
Stop-Process -Name python

# Update bot
git pull
pip install -r requirements.txt
```

---

## FAQ

**Q: Will this work on Windows 11?**
A: Yes! Works on both Windows 10 and 11.

**Q: Can I close the command window?**
A: No, closing will stop the bot. Use background methods above or minimize window.

**Q: Does it work with Windows Defender?**
A: Yes, but add exclusion for better performance.

**Q: Can I run on laptop?**
A: Yes, but keep it plugged in and disable sleep.

**Q: What if Windows Updates restart my PC?**
A: Use Task Scheduler to auto-start bot on boot.

**Q: How much RAM does it use?**
A: Usually 100-300MB. Should work on any modern PC.

**Q: Can I run multiple bots?**
A: Yes, clone to different folders with different configs.

---

## Getting Help

- Check logs in `logs\` folder
- Run: `python scripts\validate_config.py`
- GitHub Issues: https://github.com/replitcryptobots-blip/Sonicarbi/issues
- Discord: (if available)

## Next Steps

1. ✅ Install Python 3.11+
2. ✅ Clone repository
3. ✅ Create virtual environment
4. ✅ Install dependencies
5. ✅ Configure `.env` file
6. ✅ Validate configuration
7. ✅ Run on testnet first!
8. ✅ Set up Task Scheduler for auto-start
9. ✅ Configure Telegram alerts
10. ✅ Monitor and profit! 🚀

---

**Made with ❤️ for Windows traders**
