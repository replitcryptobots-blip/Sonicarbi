# New Features Documentation

This document describes the new features added to Sonicarbi arbitrage bot.

## 📊 1. Chainlink Price Oracle Integration

### Overview
Integrates Chainlink price feeds for accurate USD pricing of tokens, with automatic fallback to DEX-based pricing.

### Location
- `utils/price_oracle.py`

### Features
- **Chainlink Integration**: Uses Chainlink price feeds on Scroll mainnet for accurate USD prices
- **DEX Fallback**: Automatically falls back to DEX pool prices when Chainlink feeds unavailable
- **Caching**: Implements 5-minute caching to reduce RPC calls
- **Multi-Token Support**: Supports ETH/WETH, stablecoins (USDC/USDT), and extensible to other tokens
- **Source Tracking**: Tracks whether price came from Chainlink or DEX

### Usage

```python
from web3 import Web3
from utils.price_oracle import ChainlinkPriceOracle, MultiTokenPriceOracle

# Initialize
w3 = Web3(Web3.HTTPProvider(RPC_URL))
oracle = ChainlinkPriceOracle(w3, network_mode='mainnet')

# Get ETH price
eth_feed = oracle.get_eth_price_usd()
print(f"ETH: ${eth_feed.price} (source: {eth_feed.source})")

# Get token price
weth_price = oracle.get_token_price_usd('WETH')
usdc_price = oracle.get_token_price_usd('USDC')  # Returns 1.0 for stablecoins

# Calculate profit in USD
profit_usd = oracle.calculate_profit_usd(1.5, 'WETH')  # 1.5 WETH profit
```

### Chainlink Addresses on Scroll
- **ETH/USD Mainnet**: `0x6bF14CB0A831078629D993FDeBcB182b21A8774C`
- **Testnet**: Falls back to DEX pricing

### Benefits
- More accurate USD profit calculations
- Reduced dependency on DEX pool prices
- Better price discovery for less liquid tokens
- Real-time price updates from industry-standard oracles

---

## 💧 2. Slippage Calculator

### Overview
Calculates expected slippage and price impact for trades based on pool liquidity using the Uniswap V2 constant product formula.

### Location
- `utils/slippage_calculator.py`

### Features
- **V2 Slippage Calculation**: Accurate slippage calculation for Uniswap V2 style DEXes
- **Price Impact Analysis**: Calculates price impact percentage
- **Optimal Trade Size**: Determines optimal trade size for target price impact
- **Arbitrage Validation**: Validates entire arbitrage route for acceptable slippage
- **Liquidity Analysis**: Calculates pool liquidity in USD
- **High Impact Detection**: Flags trades with >1% or >5% price impact

### Usage

```python
from web3 import Web3
from utils.slippage_calculator import SlippageCalculator

# Initialize
w3 = Web3(Web3.HTTPProvider(RPC_URL))
calc = SlippageCalculator(w3)

# Calculate slippage for a trade
token_in = {'symbol': 'WETH', 'address': '0x...', 'decimals': 18}
token_out = {'symbol': 'USDC', 'address': '0x...', 'decimals': 6}

slippage_info = calc.calculate_v2_slippage(
    'SyncSwap',
    token_in,
    token_out,
    amount_in=1.0  # 1 WETH
)

print(f"Price impact: {slippage_info['price_impact_pct']:.3f}%")
print(f"Slippage: {slippage_info['slippage_pct']:.3f}%")
print(f"Reserves: {slippage_info['reserve_in']}/{slippage_info['reserve_out']}")
print(f"High impact: {slippage_info['is_high_impact']}")

# Calculate optimal trade size for 1% max impact
optimal_size = calc.calculate_optimal_trade_size(
    'SyncSwap',
    token_in,
    token_out,
    max_price_impact_pct=1.0
)
print(f"Optimal trade size: {optimal_size} WETH")

# Validate arbitrage slippage
is_valid, results = calc.validate_arbitrage_slippage(
    buy_dex='SyncSwap',
    sell_dex='Zebra',
    token_in=token_in,
    token_out=token_out,
    amount=1.0,
    max_slippage_pct=2.0
)

if is_valid:
    print(f"Arbitrage valid! Total slippage: {results['total_slippage_pct']:.3f}%")
else:
    print(f"Arbitrage invalid - too much slippage: {results['total_slippage_pct']:.3f}%")

# Get pool liquidity in USD
token_prices = {'WETH': 3500.0, 'USDC': 1.0}
liquidity_usd = calc.get_pool_liquidity_usd(
    'SyncSwap',
    token_in,
    token_out,
    token_prices
)
print(f"Pool liquidity: ${liquidity_usd:,.2f}")
```

### Return Values

**calculate_v2_slippage()** returns:
```python
{
    'dex': 'SyncSwap',
    'pair': 'WETH/USDC',
    'pair_address': '0x...',
    'reserve_in': 100.0,          # Reserve of input token
    'reserve_out': 350000.0,      # Reserve of output token
    'amount_in': 1.0,             # Input amount
    'amount_out': 3465.23,        # Expected output amount
    'spot_price': 3500.0,         # Price before trade
    'effective_price': 3465.23,   # Price after trade (with impact)
    'price_impact_pct': 1.0,      # Price impact percentage
    'slippage_pct': 0.994,        # Slippage percentage
    'liquidity_ratio': 0.01,      # What % of pool you're using
    'is_high_impact': True,       # True if >1% impact
    'is_very_high_impact': False  # True if >5% impact
}
```

### Benefits
- Prevents failed transactions due to insufficient liquidity
- Optimizes trade sizes for minimal slippage
- Better risk assessment for arbitrage opportunities
- Identifies high-impact trades before execution

---

## 📢 3. Telegram & Discord Notifications

### Overview
Real-time notification system supporting both Telegram and Discord for monitoring arbitrage opportunities, executions, errors, and system status.

### Location
- `utils/notifications.py`

### Features
- **Multi-Platform Support**: Telegram and Discord notifications
- **Rich Formatting**: HTML formatting for Telegram, embeds for Discord
- **Multiple Alert Types**: Opportunities, executions, errors, status updates
- **Async Implementation**: Non-blocking notifications
- **Error Handling**: Graceful degradation if notifications fail
- **Rate Limiting**: Timeout protection

### Configuration

#### Telegram Setup

1. Create a bot with [@BotFather](https://t.me/BotFather):
   - Send `/newbot` to @BotFather
   - Choose a name and username
   - Save the bot token

2. Get your chat ID:
   - Send a message to [@userinfobot](https://t.me/userinfobot)
   - Copy your user ID

3. Add to `.env`:
   ```bash
   ENABLE_TELEGRAM_ALERTS=true
   TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
   TELEGRAM_CHAT_ID=123456789
   ```

#### Discord Setup

1. Create a webhook:
   - Go to Server Settings → Integrations → Webhooks
   - Click "New Webhook"
   - Choose a channel and copy the webhook URL

2. Add to `.env`:
   ```bash
   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/123456/abcdef
   ```

### Usage

```python
import asyncio
from utils.notifications import NotificationManager

# Initialize manager (reads from config automatically)
notifier = NotificationManager()

# Send opportunity alert
opportunity = {
    'timestamp': '2025-12-29T10:30:00',
    'token_in': 'WETH',
    'token_out': 'USDC',
    'buy_dex': 'SyncSwap',
    'sell_dex': 'Zebra',
    'buy_price': 3500.12,
    'sell_price': 3520.65,
    'profit_pct': 0.583,
    'profit_usd': 20.43,
    'gas_cost_usd': 0.05,
    'gas_estimate': 350000,
    'amount': 1.0
}

await notifier.send_opportunity(opportunity)

# Send execution alert
execution = {
    'timestamp': '2025-12-29T10:35:00',
    'token_in': 'WETH',
    'token_out': 'USDC',
    'buy_dex': 'SyncSwap',
    'sell_dex': 'Zebra',
    'status': 'success',
    'tx_hash': '0x1234...',
    'actual_profit_pct': 0.58,
    'actual_profit_usd': 20.30
}

await notifier.send_execution(execution)

# Send error alert
await notifier.send_error(
    "Failed to execute trade",
    context={'error_code': 500, 'dex': 'SyncSwap'}
)

# Send status update
await notifier.send_status(
    "Scanner started successfully",
    details={'dexes': 5, 'tokens': 5, 'uptime': '2h'}
)
```

### Message Examples

**Telegram Opportunity Alert:**
```
🎯 ARBITRAGE OPPORTUNITY

📊 Pair: WETH → USDC
💰 Profit: 0.583% ($20.43)

🔄 Route:
  • Buy: SyncSwap @ 3500.123456
  • Sell: Zebra @ 3520.654321

⛽ Gas Cost: $0.0500 (350000 gas)
💵 Trade Size: 1.0 WETH

🕐 Time: 2025-12-29T10:30:00
```

**Discord Opportunity Alert:**
- Formatted as a rich embed with green color
- Contains all key information in structured fields
- Includes timestamp

### Benefits
- Real-time monitoring from anywhere
- Never miss profitable opportunities
- Quick error notifications for debugging
- System health monitoring
- Mobile notifications support

---

## 💎 4. Flashloan Executor Smart Contract

### Overview
Solidity smart contract for executing arbitrage opportunities using Aave V3 flashloans on Scroll network.

### Location
- `contracts/FlashloanArbitrage.sol`

### Features
- **Aave V3 Integration**: Uses Aave V3 flashloans (0.09% fee)
- **Uniswap V2 Compatible**: Works with all V2-style DEXes
- **Profit Verification**: Ensures minimum profit before completing flashloan
- **Security**: Reentrancy protection, owner-only execution
- **Simulation**: Can simulate profit before executing
- **Profit Withdrawal**: Easy withdrawal of accumulated profits
- **Emergency Functions**: Token rescue capabilities

### Contract Interface

```solidity
struct ArbitrageParams {
    address tokenBorrow;      // Token to flashloan
    uint256 amount;           // Amount to borrow
    address tokenTarget;      // Token to swap to
    address buyDex;           // DEX to buy on (router address)
    address sellDex;          // DEX to sell on (router address)
    uint256 minProfit;        // Minimum profit in tokenBorrow
    uint256 deadline;         // Transaction deadline
}

// Execute arbitrage
function executeArbitrage(ArbitrageParams calldata params) external onlyOwner

// Simulate profit (view function)
function simulateArbitrage(ArbitrageParams calldata params)
    external view returns (uint256 expectedProfit)

// Withdraw profits
function withdrawProfit(address token) external onlyOwner
function withdrawETH() external onlyOwner
```

### Deployment

#### Install Dependencies

```bash
cd contracts
npm install
```

#### Deploy to Scroll Testnet

```bash
npx hardhat run scripts/deploy.js --network scrollTestnet
```

#### Deploy to Scroll Mainnet

```bash
npx hardhat run scripts/deploy.js --network scroll
```

### Python Integration

```python
from web3 import Web3
import json
import time

w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Load contract
with open('contracts/artifacts/FlashloanArbitrage.json', 'r') as f:
    contract_data = json.load(f)
    abi = contract_data['abi']

contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=abi)

# Prepare parameters
params = {
    'tokenBorrow': WETH_ADDRESS,
    'amount': w3.to_wei(1, 'ether'),
    'tokenTarget': USDC_ADDRESS,
    'buyDex': SYNCSWAP_ROUTER,
    'sellDex': ZEBRA_ROUTER,
    'minProfit': w3.to_wei(0.01, 'ether'),  # 0.01 ETH min profit
    'deadline': int(time.time()) + 300  # 5 minutes
}

# Simulate first
try:
    expected_profit = contract.functions.simulateArbitrage(params).call()
    print(f"Expected profit: {w3.from_wei(expected_profit, 'ether')} ETH")

    if expected_profit >= params['minProfit']:
        # Execute
        tx = contract.functions.executeArbitrage(params).build_transaction({
            'from': account.address,
            'nonce': w3.eth.get_transaction_count(account.address),
            'gas': 500000,
            'gasPrice': w3.eth.gas_price
        })

        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        print(f"Success! Tx: {receipt['transactionHash'].hex()}")
    else:
        print("Profit below minimum threshold")

except Exception as e:
    print(f"Error: {e}")

# Withdraw profits later
contract.functions.withdrawProfit(WETH_ADDRESS).transact({'from': account.address})
```

### Aave V3 Pool Addresses

- **Scroll Mainnet**: `0x11fCfe756c05AD438e312a7fd934381537D3cFfe`
- **Scroll Sepolia Testnet**: `0x48914C788295b5db23aF2b5F0B3BE775C4eA9440`

### Gas Costs

Estimated gas usage:
- Flashloan overhead: ~50,000 gas
- V2 swap: ~130,000 gas per swap
- Concentrated swap: ~180,000 gas per swap
- **Total for V2-V2 arbitrage**: ~330,000 gas
- **Total for CL-CL arbitrage**: ~410,000 gas

On Scroll (gas ~0.02 gwei, ETH ~$3500):
- V2-V2 arbitrage: ~$0.023
- CL-CL arbitrage: ~$0.029

### Security Considerations

1. **Owner-only execution**: Only deployer can execute trades
2. **Reentrancy protection**: Uses OpenZeppelin's ReentrancyGuard
3. **Profit verification**: Transaction reverts if profit below minimum
4. **Deadline protection**: Prevents stale transactions
5. **Flashloan fee**: 0.09% on Aave V3

### Benefits
- Automated flashloan execution
- No upfront capital required
- Atomic transactions (all-or-nothing)
- Gas-optimized implementation
- Production-ready security

---

## 🧪 5. Comprehensive Unit Tests

### Overview
Complete test suite for all new features using pytest and pytest-asyncio.

### Location
- `tests/test_price_oracle.py` - Price oracle tests
- `tests/test_slippage_calculator.py` - Slippage calculator tests
- `tests/test_notifications.py` - Notification system tests

### Running Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run specific test file
pytest tests/test_price_oracle.py -v

# Run with coverage
pytest --cov=src --cov=utils --cov-report=html

# Run only unit tests
pytest -m unit

# Run async tests
pytest -k async
```

### Test Coverage

#### Price Oracle Tests (test_price_oracle.py)
- ✅ Oracle initialization
- ✅ ETH price fetching (Chainlink + DEX fallback)
- ✅ Price caching mechanism
- ✅ Stablecoin pricing
- ✅ WETH/ETH price consistency
- ✅ Unknown token handling
- ✅ USD profit calculation
- ✅ Cache expiration
- ✅ Multi-token oracle integration

#### Slippage Calculator Tests (test_slippage_calculator.py)
- ✅ Calculator initialization
- ✅ V2 slippage calculation
- ✅ Pair existence checking
- ✅ High impact trade detection
- ✅ Optimal trade size calculation
- ✅ Arbitrage route validation
- ✅ Pool liquidity calculation in USD
- ✅ Error handling

#### Notification Tests (test_notifications.py)
- ✅ Telegram notifier initialization
- ✅ Discord notifier initialization
- ✅ Message sending (success/failure/timeout)
- ✅ Opportunity alerts
- ✅ Execution alerts
- ✅ Error alerts
- ✅ Status updates
- ✅ Multi-platform notification manager
- ✅ Async notification handling

### Test Configuration

See `pytest.ini` for test configuration:
- Test discovery patterns
- Async mode settings
- Output formatting
- Logging configuration

### Continuous Integration

Tests are designed to work with CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest -v --cov
```

### Benefits
- Ensures code quality
- Prevents regressions
- Documents expected behavior
- Facilitates refactoring
- Increases confidence in deployments

---

## 📝 Summary

All new features are production-ready and include:
- ✅ Full implementation
- ✅ Comprehensive documentation
- ✅ Unit tests with high coverage
- ✅ Error handling and logging
- ✅ Configuration examples
- ✅ Usage examples

### Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp config/.env.example config/.env
   # Edit config/.env with your settings
   ```

3. **Run tests**:
   ```bash
   pytest -v
   ```

4. **Deploy flashloan contract** (optional):
   ```bash
   cd contracts
   npm install
   npx hardhat run scripts/deploy.js --network scrollTestnet
   ```

5. **Start scanner**:
   ```bash
   python src/scanner.py
   ```

For detailed information on each feature, see the sections above.
