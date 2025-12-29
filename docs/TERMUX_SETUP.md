# Sonicarbi on Termux (Android)

Complete guide to running the Sonicarbi arbitrage bot on Android using Termux.

## Why Termux?

- ✅ Run the bot 24/7 on your Android device
- ✅ Low power consumption vs desktop/VPS
- ✅ Portable - monitor from anywhere
- ✅ Free - no VPS costs
- ✅ Full Python environment

## Prerequisites

- Android device (phone/tablet)
- At least 2GB free storage
- Stable internet connection
- Termux app from F-Droid (NOT Play Store version)

## Installation

### 1. Install Termux

**IMPORTANT**: Install from F-Droid, NOT Google Play Store!

1. Download F-Droid APK: https://f-droid.org/
2. Install F-Droid
3. Open F-Droid and search for "Termux"
4. Install Termux

### 2. Update Termux Packages

```bash
# Update package lists
pkg update && pkg upgrade -y

# Install required packages
pkg install -y python git postgresql libpq clang openssl rust binutils

# Install pip
pip install --upgrade pip
```

### 3. Install PostgreSQL (Optional)

```bash
# Install PostgreSQL
pkg install postgresql -y

# Initialize database
initdb $PREFIX/var/lib/postgresql

# Start PostgreSQL
pg_ctl -D $PREFIX/var/lib/postgresql start

# Create database
createdb mev_scroll_db
```

### 4. Clone Repository

```bash
# Navigate to home
cd ~

# Clone the repo
git clone https://github.com/replitcryptobots-blip/Sonicarbi.git
cd Sonicarbi
```

### 5. Install Python Dependencies

```bash
# Install build dependencies first
pkg install -y python-cryptography libffi

# Install Python packages
pip install -r requirements.txt

# If you get compilation errors, install pre-built wheels:
pip install --prefer-binary web3 eth-abi aiohttp psycopg2-binary
```

### 6. Configure Environment

```bash
# Copy example config
cp config/.env.example config/.env

# Edit with nano (Termux text editor)
nano config/.env
```

**Termux-specific config:**
```bash
# Use public RPC endpoints (no VPN needed)
SCROLL_RPC_URL=https://rpc.scroll.io
SCROLL_TESTNET_RPC=https://sepolia-rpc.scroll.io
NETWORK_MODE=testnet

# Your private key
PRIVATE_KEY=your_64_char_private_key_without_0x

# Database (if using PostgreSQL)
DATABASE_URL=postgresql://localhost:5432/mev_scroll_db

# Telegram alerts (recommended for mobile monitoring)
ENABLE_TELEGRAM_ALERTS=true
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Save: `Ctrl+X`, then `Y`, then `Enter`

### 7. Validate Configuration

```bash
python scripts/validate_config.py
```

### 8. Run the Bot

```bash
# Run the scanner
python src/scanner.py
```

## Running in Background

### Option 1: Using `nohup`

```bash
# Run in background
nohup python src/scanner.py > bot.log 2>&1 &

# Check if running
ps aux | grep scanner

# View logs
tail -f bot.log

# Stop the bot
pkill -f scanner.py
```

### Option 2: Using `tmux` (Recommended)

```bash
# Install tmux
pkg install tmux -y

# Start a tmux session
tmux new -s arbitrage

# Run the bot
python src/scanner.py

# Detach from session: Ctrl+B, then D

# Reattach later
tmux attach -t arbitrage

# List sessions
tmux ls
```

### Option 3: Using Termux:Boot (Auto-start on Device Boot)

```bash
# Install Termux:Boot from F-Droid
# Create boot script
mkdir -p ~/.termux/boot
nano ~/.termux/boot/start-arbitrage.sh
```

Add this content:
```bash
#!/data/data/com.termux/files/usr/bin/bash
cd ~/Sonicarbi
python src/scanner.py >> ~/arbitrage.log 2>&1
```

Make executable:
```bash
chmod +x ~/.termux/boot/start-arbitrage.sh
```

## Termux-Specific Optimizations

### 1. Prevent Termux from Sleeping

```bash
# Acquire wakelock (keeps CPU active)
termux-wake-lock

# To release later:
termux-wake-unlock
```

### 2. Enable Notifications

```bash
# Install Termux:API from F-Droid
# Then install API package
pkg install termux-api -y

# Send test notification
termux-notification --title "Arbitrage Bot" --content "Bot is running!"
```

### 3. Set Up Telegram Alerts

Since you're on mobile, Telegram alerts are ESSENTIAL:

1. Create a bot with @BotFather on Telegram
2. Get your chat ID from @userinfobot
3. Add to `.env`:
```bash
ENABLE_TELEGRAM_ALERTS=true
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHAT_ID=123456789
```

Now you'll get alerts on your phone even when the screen is off!

## Troubleshooting

### Issue: "Cannot install psycopg2"

**Solution:**
```bash
# Use binary version
pip uninstall psycopg2
pip install psycopg2-binary
```

### Issue: "Permission denied" errors

**Solution:**
```bash
# Give Termux storage access
termux-setup-storage

# This will prompt for permission - allow it
```

### Issue: "Out of memory"

**Solution:**
```bash
# Free up memory
pkg clean

# Remove unused packages
pkg autoclean

# Restart Termux
exit
# Then reopen Termux app
```

### Issue: Web3 compilation errors

**Solution:**
```bash
# Install rust for cryptography compilation
pkg install rust -y

# Or use pre-built wheels
pip install --only-binary :all: web3
```

### Issue: "Connection refused" to PostgreSQL

**Solution:**
```bash
# Start PostgreSQL
pg_ctl -D $PREFIX/var/lib/postgresql start

# Check if running
pg_ctl -D $PREFIX/var/lib/postgresql status
```

### Issue: Bot stops when screen turns off

**Solution:**
```bash
# Method 1: Use wakelock
termux-wake-lock

# Method 2: Disable battery optimization for Termux
# Settings > Apps > Termux > Battery > Unrestricted

# Method 3: Use tmux to keep session alive
tmux new -s bot
python src/scanner.py
# Ctrl+B, D to detach
```

## Performance Tips

### 1. Reduce Memory Usage

Edit `config/.env`:
```bash
# Scan less frequently
SCAN_INTERVAL=5  # seconds between scans

# Monitor fewer token pairs
# Edit config/dex_configs.json to remove unused tokens
```

### 2. Use Swap File (if low RAM)

```bash
# Create 1GB swap file
dd if=/dev/zero of=$PREFIX/var/swapfile bs=1M count=1024
chmod 600 $PREFIX/var/swapfile
mkswap $PREFIX/var/swapfile
swapon $PREFIX/var/swapfile
```

### 3. Monitor Resource Usage

```bash
# Check memory usage
free -h

# Check CPU usage
top

# Check disk usage
df -h
```

## Security Best Practices

1. **Never store large amounts** in the bot wallet
2. **Use a dedicated phone** if possible
3. **Enable screen lock** on your device
4. **Regular backups** of your `.env` file (encrypted)
5. **Monitor logs** regularly via Telegram

## Monitoring & Maintenance

### Daily Checks

```bash
# Check if bot is running
ps aux | grep scanner

# Check logs
tail -n 50 bot.log

# Check for updates
cd ~/Sonicarbi
git pull
```

### Weekly Maintenance

```bash
# Update Termux packages
pkg update && pkg upgrade

# Update Python packages
pip install --upgrade -r requirements.txt

# Clear old logs
truncate -s 0 bot.log
```

## Alternative: Running Without PostgreSQL

If you want to skip PostgreSQL setup:

Edit `config/.env`:
```bash
# Comment out or remove DATABASE_URL
# DATABASE_URL=

# The bot will run without database (logs to console only)
```

## Useful Termux Commands

```bash
# Exit Termux
exit

# Clear screen
clear

# Show current directory
pwd

# List files
ls -la

# Edit files
nano filename.txt

# View file contents
cat filename.txt

# Search in file
grep "search term" filename.txt

# Monitor file in real-time
tail -f filename.txt
```

## Advanced: Set Up Wake-on-LAN

Keep your device awake remotely:

```bash
# Install Termux:API
pkg install termux-api

# Create monitoring script
nano ~/check-bot.sh
```

Add:
```bash
#!/data/data/com.termux/files/usr/bin/bash

# Check if bot is running
if ! pgrep -f "scanner.py" > /dev/null; then
    # Send notification
    termux-notification --title "⚠️ Arbitrage Bot Down" --content "Bot has stopped!"

    # Restart bot
    cd ~/Sonicarbi
    nohup python src/scanner.py > bot.log 2>&1 &

    termux-notification --title "✅ Bot Restarted" --content "Arbitrage bot is back online"
fi
```

Make executable and add to cron:
```bash
chmod +x ~/check-bot.sh

# Install cronie
pkg install cronie -y

# Add to crontab (check every 5 minutes)
crontab -e
```

Add this line:
```
*/5 * * * * ~/check-bot.sh
```

## FAQ

**Q: Will this drain my battery?**
A: Yes, expect 10-20% battery drain per hour. Keep device plugged in.

**Q: Can I use my phone normally while bot runs?**
A: Yes! The bot runs in the background. Use tmux to keep it alive.

**Q: What if my internet disconnects?**
A: The bot will try to reconnect. Consider using a stability script.

**Q: Is it safe to leave running overnight?**
A: Yes, but ensure:
- Device is plugged in and charging
- Battery optimization is disabled for Termux
- Wakelock is enabled
- Device is in a cool place (avoid overheating)

**Q: How do I update the bot?**
```bash
cd ~/Sonicarbi
git pull
pip install -r requirements.txt
```

**Q: Can I run multiple bots?**
A: Yes, clone to different directories and use different configs.

## Getting Help

- Check logs: `tail -f bot.log`
- Validate config: `python scripts/validate_config.py`
- Test connection: `python -c "from web3 import Web3; w3 = Web3(Web3.HTTPProvider('https://rpc.scroll.io')); print(w3.is_connected())"`
- GitHub Issues: https://github.com/replitcryptobots-blip/Sonicarbi/issues

## Next Steps

1. ✅ Install Termux from F-Droid
2. ✅ Follow installation steps above
3. ✅ Set up Telegram notifications
4. ✅ Run bot in tmux session
5. ✅ Enable wakelock
6. ✅ Monitor via Telegram
7. ✅ Test on testnet first!

---

**Made with ❤️ for mobile arbitrage traders**
