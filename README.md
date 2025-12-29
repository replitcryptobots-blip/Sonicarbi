# Sonicarbi - Scroll Flashloan Arbitrage Bot

An automated flashloan arbitrage bot for the Scroll blockchain that scans multiple DEXes for profitable trading opportunities.

## Features

- **Multi-DEX Scanner**: Monitors 5 DEXes on Scroll (SyncSwap, Zebra, Skydrome, Ambient, iZiSwap)
- **Real-time Arbitrage Detection**: Scans token pairs across DEXes to find price discrepancies
- **Flashloan Ready**: Designed to execute arbitrage using Aave V3 flashloans
- **Database Integration**: PostgreSQL database for tracking opportunities and executions
- **Gas Optimization**: Accounts for Scroll's low gas costs in profit calculations
- **Configurable Parameters**: Customizable profit thresholds, slippage tolerance, and more

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

Edit `config/.env` and set your configuration:

```bash
# Required
PRIVATE_KEY=your_private_key_here
SCROLL_RPC_URL=https://rpc.scroll.io
NETWORK_MODE=testnet  # or mainnet

# Optional
PROFIT_THRESHOLD=0.005  # 0.5%
DATABASE_URL=postgresql://localhost:5432/mev_scroll_db
```

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
2. Load DEX configurations
3. Continuously scan token pairs for arbitrage opportunities
4. Display profitable opportunities in the console

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

## Roadmap

- [ ] Implement flashloan executor contract
- [ ] Add automatic trade execution
- [ ] Web dashboard for monitoring
- [ ] Telegram notifications
- [ ] MEV protection mechanisms
- [ ] Support for more DEXes
- [ ] Advanced profit calculation with slippage

## Contributing

Contributions are welcome! Please read the contributing guidelines before submitting PRs.

## License

MIT License - See LICENSE file for details

## Disclaimer

This software is for educational purposes only. Use at your own risk. Cryptocurrency trading involves significant risk of loss. The authors are not responsible for any financial losses incurred through the use of this software.

## Support

For issues and questions, please open an issue on GitHub.