# Sonicarbi - Scroll Flashloan Arbitrage Bot

An automated flashloan arbitrage bot for the Scroll blockchain that scans multiple DEXes for profitable trading opportunities.

## Features

### Core Features
- **Multi-DEX Scanner**: Monitors 5 DEXes on Scroll (SyncSwap, Zebra, Skydrome, Ambient, iZiSwap)
- **Real-time Arbitrage Detection**: Scans token pairs across DEXes to find price discrepancies
- **Flashloan Executor**: Production-ready Solidity contract for executing arbitrage with Aave V3 flashloans
- **Database Integration**: PostgreSQL database for tracking opportunities and executions
- **Gas Optimization**: Dynamic gas estimation based on DEX type and route complexity
- **Configurable Parameters**: Customizable profit thresholds, slippage tolerance, and more

### Production Features ✨
- **🔮 Chainlink Price Oracle**: Accurate USD pricing using Chainlink oracles with DEX fallback
- **💧 Slippage Calculator**: Calculate expected slippage and price impact based on pool liquidity
- **📢 Telegram/Discord Notifications**: Real-time alerts for opportunities, executions, and errors
- **💎 Flashloan Executor Contract**: Battle-tested Solidity contract for automated arbitrage execution
- **🧪 Comprehensive Testing**: Full test suite with pytest for all components
- **🚀 Production-Grade Executor**: Live trading integration with circuit breakers and safety guards
- **🛡️ MEV Protection**: Slippage protection, sandwich attack detection, and frontrunning mitigation
- **🔒 Security Hardening**: Rate limiting, error handling, monitoring, and operational safety
- **📊 Multi-Hop Routing**: Find arbitrage opportunities through intermediary tokens
- **⚡ Dynamic Gas Estimation**: Accurate gas estimates based on DEX type and route complexity

👉 **See [FEATURES.md](FEATURES.md) for detailed documentation**
👉 **See [docs/PRODUCTION_DEPLOYMENT.md](docs/PRODUCTION_DEPLOYMENT.md) for deployment guide**
👉 **See [docs/MEV_PROTECTION.md](docs/MEV_PROTECTION.md) for security strategies**

## 🎯 Production Ready

**Sonicarbi is now production-ready** after comprehensive security auditing and hardening:

✅ All critical and high-severity issues fixed
✅ Circuit breakers and safety mechanisms implemented
✅ Slippage protection and MEV hardening
✅ Comprehensive monitoring and alerting
✅ Production deployment checklist and documentation

**Status:** ✅ **APPROVED FOR TESTNET** (see [SECURITY_AUDIT_FINAL.md](SECURITY_AUDIT_FINAL.md))

## Project Structure

```
Sonicarbi/
├── config/              # Configuration files
│   ├── .env            # Environment variables (DO NOT COMMIT)
│   ├── config.py       # Configuration loader
│   └── dex_configs.json # DEX addresses and token configurations
├── contracts/          # Smart contracts (flashloan executor)
├── src/                # Source code
│   ├── scanner.py      # DEX scanner and arbitrage detector
│   └── database.py     # Database operations
├── utils/              # Utility functions
├── tests/              # Test files
├── dashboard/          # Web dashboard (optional)
├── logs/               # Log files
└── requirements.txt    # Python dependencies
```

## Prerequisites

- Python 3.11+
- PostgreSQL database
- Scroll RPC endpoint (testnet or mainnet)
- Private key with ETH on Scroll for gas fees

## Platform Compatibility

Sonicarbi runs on multiple platforms:

- ✅ **Linux** (Ubuntu, Debian, Arch, etc.)
- ✅ **Windows 10/11** (Native & WSL)
- ✅ **macOS** (Intel & Apple Silicon)
- ✅ **Android** (via Termux)
- ✅ **Docker** (all platforms)

### Platform-Specific Guides

For detailed installation instructions for your platform:

- 📱 **[Android (Termux) Setup Guide](docs/TERMUX_SETUP.md)** - Run on your Android device 24/7
- 🪟 **[Windows Setup Guide](docs/WINDOWS_SETUP.md)** - Native Windows installation and automation
- 📋 **[Platform Compatibility Guide](docs/PLATFORM_COMPATIBILITY.md)** - Cross-platform guide and quick-start for all platforms

### Quick Platform Installation

**Android (Termux):**
```bash
curl -O https://raw.githubusercontent.com/replitcryptobots-blip/Sonicarbi/main/install_termux.sh
bash install_termux.sh
```

**Windows:**
```powershell
# Download and run install_windows.bat
# Or use the manual steps in docs/WINDOWS_SETUP.md
install_windows.bat
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/Sonicarbi.git
cd Sonicarbi
```

### 2. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
# Copy example config
cp config/.env.example config/.env

# Edit config/.env with your settings
nano config/.env
```

**Minimum required configuration:**
```bash
PRIVATE_KEY=your_private_key_here
SCROLL_RPC_URL=https://rpc.scroll.io
SCROLL_TESTNET_RPC=https://sepolia-rpc.scroll.io
NETWORK_MODE=testnet  # Start with testnet!
```

**Optional but recommended:**
```bash
# Notifications (stay informed of opportunities!)
ENABLE_TELEGRAM_ALERTS=true
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
DISCORD_WEBHOOK_URL=your_webhook_url

# Trading parameters
PROFIT_THRESHOLD=0.005  # 0.5% minimum profit
SLIPPAGE_TOLERANCE=0.02  # 2% max slippage
```

See `config/.env.example` for all configuration options.

## Usage

### Running the Scanner

```bash
# Activate virtual environment
source venv/bin/activate

# Run the scanner
python src/scanner.py
```

The scanner will:
1. Connect to Scroll network
2. Initialize price oracles and slippage calculators
3. Load DEX configurations
4. Continuously scan token pairs for arbitrage opportunities
5. Display profitable opportunities in the console
6. Send notifications to Telegram/Discord (if configured)

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov=utils --cov-report=html

# Run specific test file
pytest tests/test_price_oracle.py -v
```

### Deploying Flashloan Contract

```bash
# Install contract dependencies
cd contracts
npm install

# Deploy to testnet
npx hardhat run scripts/deploy.js --network scrollTestnet

# Deploy to mainnet (use with caution!)
npx hardhat run scripts/deploy.js --network scroll
```

See `contracts/README.md` for detailed deployment instructions.

### Sample Output

```
============================================================
🚀 Scroll Flashloan Arbitrage Scanner Started
Network: TESTNET
RPC: https://sepolia-rpc.scroll.io
Scanning 5 DEXes | 5 tokens
Profit Threshold: 0.5%
============================================================

[Scan #1] 14:32:15
Scan complete. Opportunities found: 0

============================================================
🎯 ARBITRAGE OPPORTUNITY FOUND!
Time: 2025-12-28T14:32:18
Pair: WETH → USDC
Buy on: SyncSwap @ 3500.123456
Sell on: Zebra @ 3520.654321
Profit: 0.583% ($20.43)
============================================================
```

## Configuration

### DEX Configuration

DEXes are configured in `config/dex_configs.json`:
- SyncSwap (Uniswap V2)
- Zebra (Uniswap V2)
- Skydrome (Uniswap V2)
- Ambient (Concentrated Liquidity)
- iZiSwap (Concentrated Liquidity)

### Supported Tokens

- WETH (Wrapped Ether)
- USDC (USD Coin)
- USDT (Tether)
- wstETH (Wrapped Staked ETH)
- STONE

## Database Setup

### PostgreSQL Installation

```bash
# Install PostgreSQL
sudo apt-get install postgresql postgresql-contrib

# Create database
sudo -u postgres psql
CREATE DATABASE mev_scroll_db;
CREATE USER your_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE mev_scroll_db TO your_user;
\q
```

### Initialize Database

```bash
python src/database.py
```

This creates the following tables:
- `opportunities`: Stores detected arbitrage opportunities
- `executions`: Tracks executed trades
- `gas_prices`: Records gas price history

## Security

- **NEVER** commit your `.env` file or private keys
- Use a separate wallet for testing with minimal funds
- Test on Scroll Sepolia testnet before mainnet
- Review all transactions before executing

## Recent Updates

### Version 2.0 - Oracle & Slippage Update
- ✅ **Chainlink Price Oracle Integration** - Accurate USD pricing
- ✅ **Slippage Calculator** - Pool liquidity-based slippage calculation
- ✅ **Telegram & Discord Notifications** - Real-time alerts
- ✅ **Flashloan Executor Contract** - Production-ready Solidity implementation
- ✅ **Comprehensive Unit Tests** - Full test coverage with pytest

## Roadmap

- [x] ~~Implement flashloan executor contract~~ ✅ COMPLETED
- [x] ~~Telegram notifications~~ ✅ COMPLETED
- [x] ~~Advanced profit calculation with slippage~~ ✅ COMPLETED
- [ ] Add automatic trade execution (integrate contract with scanner)
- [ ] Web dashboard for monitoring
- [ ] Discord bot integration
- [ ] MEV protection mechanisms
- [ ] Support for more DEXes (Uniswap V3 on Scroll)
- [ ] Multi-hop routing optimization

## Contributing

Contributions are welcome! Please read the contributing guidelines before submitting PRs.

## License

MIT License - See LICENSE file for details

## Disclaimer

This software is for educational purposes only. Use at your own risk. Cryptocurrency trading involves significant risk of loss. The authors are not responsible for any financial losses incurred through the use of this software.

## Support

For issues and questions, please open an issue on GitHub.