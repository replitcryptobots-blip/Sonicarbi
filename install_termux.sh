#!/bin/bash
# Termux installation script for Sonicarbi
# Run this after installing Termux from F-Droid

set -e  # Exit on error

echo "🤖 Sonicarbi Termux Installer"
echo "=============================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running in Termux
if [ ! -d "$PREFIX" ]; then
    echo -e "${RED}❌ This script must be run in Termux!${NC}"
    echo "Download Termux from F-Droid: https://f-droid.org/"
    exit 1
fi

echo -e "${GREEN}✓${NC} Running in Termux"

# Update packages
echo ""
echo "📦 Updating Termux packages..."
pkg update -y && pkg upgrade -y

# Install required packages
echo ""
echo "📦 Installing required packages..."
pkg install -y python git clang openssl rust binutils libffi

# Install optional packages
echo ""
read -p "Install PostgreSQL? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    pkg install -y postgresql

    echo "🗄️  Initializing PostgreSQL..."
    if [ ! -d "$PREFIX/var/lib/postgresql" ]; then
        initdb $PREFIX/var/lib/postgresql
    fi

    echo "Starting PostgreSQL..."
    pg_ctl -D $PREFIX/var/lib/postgresql start

    echo "Creating database..."
    createdb mev_scroll_db || echo "Database may already exist"

    echo -e "${GREEN}✓${NC} PostgreSQL installed and configured"
fi

# Install pip packages
echo ""
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Clone repository if not already cloned
echo ""
if [ -d "$HOME/Sonicarbi" ]; then
    echo -e "${YELLOW}⚠${NC}  Sonicarbi directory already exists"
    read -p "Pull latest changes? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cd $HOME/Sonicarbi
        git pull
    fi
else
    echo "📥 Cloning Sonicarbi repository..."
    cd $HOME
    git clone https://github.com/replitcryptobots-blip/Sonicarbi.git
    cd Sonicarbi
fi

cd $HOME/Sonicarbi

# Install Python dependencies
echo ""
echo "📦 Installing Python packages (this may take a while)..."
pip install --prefer-binary -r requirements.txt

# Create .env if doesn't exist
echo ""
if [ ! -f "config/.env" ]; then
    echo "⚙️  Creating configuration file..."
    cp config/.env.example config/.env
    echo -e "${GREEN}✓${NC} Created config/.env"
    echo ""
    echo -e "${YELLOW}⚠${NC}  IMPORTANT: Edit config/.env with your settings!"
    echo "Run: nano config/.env"
else
    echo -e "${GREEN}✓${NC} config/.env already exists"
fi

# Request storage permission
echo ""
echo "📁 Requesting storage access..."
termux-setup-storage

# Install termux-api if available
echo ""
read -p "Install Termux:API for notifications? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    pkg install -y termux-api
    echo -e "${GREEN}✓${NC} Termux:API installed"
    echo "Make sure to install Termux:API app from F-Droid!"
fi

# Create helper scripts
echo ""
echo "📝 Creating helper scripts..."

# Start bot script
cat > $HOME/Sonicarbi/start_bot.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd ~/Sonicarbi
python src/scanner.py
EOF
chmod +x $HOME/Sonicarbi/start_bot.sh

# Start in background script
cat > $HOME/Sonicarbi/start_background.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd ~/Sonicarbi
nohup python src/scanner.py > bot.log 2>&1 &
echo "Bot started in background. Check logs with: tail -f ~/Sonicarbi/bot.log"
echo "Stop with: pkill -f scanner.py"
EOF
chmod +x $HOME/Sonicarbi/start_background.sh

# Stop bot script
cat > $HOME/Sonicarbi/stop_bot.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
pkill -f scanner.py
echo "Bot stopped"
EOF
chmod +x $HOME/Sonicarbi/stop_bot.sh

echo -e "${GREEN}✓${NC} Helper scripts created"

# Create boot script directory
mkdir -p $HOME/.termux/boot

# Ask about auto-start
echo ""
read -p "Auto-start bot on device boot? (requires Termux:Boot) (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    cat > $HOME/.termux/boot/start-arbitrage.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
cd ~/Sonicarbi
nohup python src/scanner.py >> ~/arbitrage.log 2>&1 &
EOF
    chmod +x $HOME/.termux/boot/start-arbitrage.sh
    echo -e "${GREEN}✓${NC} Boot script created"
    echo "Install Termux:Boot from F-Droid to enable auto-start"
fi

# Installation complete
echo ""
echo "=============================="
echo -e "${GREEN}✅ Installation Complete!${NC}"
echo "=============================="
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Edit configuration:"
echo "   nano config/.env"
echo ""
echo "2. Add your private key and RPC URLs"
echo ""
echo "3. Validate configuration:"
echo "   python scripts/validate_config.py"
echo ""
echo "4. Run the bot:"
echo "   ./start_bot.sh"
echo "   or"
echo "   ./start_background.sh"
echo ""
echo "📚 Helper commands:"
echo "   ./start_bot.sh         - Start bot (foreground)"
echo "   ./start_background.sh  - Start bot (background)"
echo "   ./stop_bot.sh          - Stop bot"
echo "   tail -f bot.log        - View logs"
echo ""
echo "⚡ Performance tips:"
echo "   termux-wake-lock       - Prevent device sleep"
echo "   termux-wake-unlock     - Allow device sleep"
echo ""
echo "📖 Full guide: docs/TERMUX_SETUP.md"
echo ""
echo -e "${YELLOW}⚠️  REMEMBER:${NC}"
echo "- Keep device plugged in"
echo "- Disable battery optimization for Termux"
echo "- Test on testnet first!"
echo "- Set up Telegram alerts for monitoring"
echo ""

# Open config file if user wants
read -p "Open config file now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    nano config/.env
fi
