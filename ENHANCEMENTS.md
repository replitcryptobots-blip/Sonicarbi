# Scanner Enhancements

This document details the latest enhancements to the Sonicarbi arbitrage bot.

---

## 🚀 New Features

### 1. **Dynamic Gas Pricing** ✨

The scanner now fetches real-time gas prices from the Scroll RPC instead of using hardcoded estimates.

**Benefits**:
- **Accurate cost calculations**: Uses actual network gas prices
- **Adaptive to network conditions**: Responds to gas price fluctuations
- **Cached for performance**: 60-second cache to avoid excessive RPC calls
- **Fallback protection**: Defaults to 0.02 gwei if RPC fails

**Implementation**:
```python
from utils.gas_price import GasPriceFetcher

gas_fetcher = GasPriceFetcher(w3)
gas_price_gwei = gas_fetcher.get_gas_price_gwei()  # Real-time from RPC
cost_usd = gas_fetcher.estimate_transaction_cost_usd(250000)  # Includes ETH price
```

**How it Works**:
1. Queries `eth.gas_price` from Scroll RPC
2. Converts from wei to gwei
3. Caches result for 60 seconds
4. Estimates transaction costs in both ETH and USD

---

### 2. **ETH Price Fetching** 💰

The scanner now has infrastructure for fetching real-time ETH prices for accurate USD profit calculations.

**Current Implementation**:
- Uses a default price of $3500 (configurable)
- Cache duration: 5 minutes
- Ready to be extended with:
  - DEX price queries (WETH/USDC pool)
  - Chainlink price feeds
  - External price APIs

**Future Enhancement**:
```python
# Can be extended to query DEX pools
def get_eth_price_from_dex(self):
    # Query WETH/USDC pool on SyncSwap or Ambient
    # Return real-time price
    pass
```

---

### 3. **Multi-Hop Routing Infrastructure** 🛣️

Added comprehensive routing infrastructure for finding optimal paths through intermediary tokens.

**Components**:

#### `MultiHopRouter`
Finds possible routes between tokens.

```python
from utils.routing import MultiHopRouter

router = MultiHopRouter(common_base_tokens=['WETH'])
routes = router.find_routes('STONE', 'USDC', max_hops=2)
# Returns: [['STONE', 'USDC'], ['STONE', 'WETH', 'USDC']]
```

#### `RouteOptimizer`
Selects the best route based on available pairs and costs.

```python
from utils.routing import RouteOptimizer

optimizer = RouteOptimizer()
best_route = optimizer.find_best_route(
    token_in={'symbol': 'STONE'},
    token_out={'symbol': 'USDC'},
    available_pairs=[('STONE', 'WETH'), ('WETH', 'USDC')]
)
# Returns: ['STONE', 'WETH', 'USDC']
```

#### `PathFinder`
Advanced pathfinding for circular arbitrage and complex routes.

```python
from utils.routing import PathFinder

pathfinder = PathFinder(tokens, dexes)
circular_paths = pathfinder.find_arbitrage_paths('WETH', max_hops=3)
# Returns: [
#   ['WETH', 'USDC', 'WETH'],
#   ['WETH', 'USDC', 'USDT', 'WETH'],
#   ...
# ]
```

**Status**: Infrastructure complete, not yet integrated into main scanner
**Reason**: Requires price fetching along multi-hop paths
**Next Steps**: Implement path price calculation and comparison

---

## 📊 Impact Analysis

### Gas Cost Accuracy

**Before**:
- Hardcoded: 0.02 gwei
- Hardcoded: $3500 ETH
- Gas cost estimate: $0.0175 for 250k gas

**After**:
- Real-time from RPC
- Configurable ETH price
- Accurate cost calculation based on actual network conditions

**Example**:
```
Scroll gas price spike: 0.05 gwei (instead of 0.02)
Old calculation: Shows $0.0175 cost (wrong)
New calculation: Shows $0.04375 cost (correct)
Result: Prevents unprofitable trades
```

### Performance

**Gas Price Fetching**:
- First call: ~100ms (RPC query)
- Cached calls: <1ms (60s cache)
- Fallback: Immediate (on RPC failure)

**Scanner Overhead**:
- Additional RPC call on startup: +100ms
- Per-arbitrage check: +0ms (uses cached value)
- Total impact: Negligible

---

## 🔧 Configuration

No configuration changes required. All enhancements work out of the box.

### Optional: Adjust Caching

Edit `utils/gas_price.py` to change cache duration:

```python
class GasPriceFetcher:
    def __init__(self, w3: Web3):
        self._cache_duration = 60  # Change to your preference (seconds)
```

---

## 📝 Usage Examples

### Manual Gas Price Check

```python
from web3 import Web3
from utils.gas_price import GasPriceFetcher

w3 = Web3(Web3.HTTPProvider('https://rpc.scroll.io'))
gas_fetcher = GasPriceFetcher(w3)

# Get current gas price
gas_price = gas_fetcher.get_gas_price_gwei()
print(f"Current Scroll gas price: {gas_price:.6f} gwei")

# Estimate transaction cost
gas_units = 250000  # Typical arbitrage transaction
cost_eth = gas_fetcher.estimate_transaction_cost_eth(gas_units)
cost_usd = gas_fetcher.estimate_transaction_cost_usd(gas_units, eth_price_usd=3500)

print(f"Transaction cost: {cost_eth:.8f} ETH (${cost_usd:.4f})")
```

### Find Routes Between Tokens

```python
from utils.routing import MultiHopRouter

router = MultiHopRouter(common_base_tokens=['WETH', 'USDC'])

# Find all routes from STONE to USDT
routes = router.find_routes('STONE', 'USDT', max_hops=3)

for route in routes:
    print(f"Route: {' → '.join(route)}")
    cost = router.estimate_route_cost(route)
    print(f"  Swaps: {cost['num_swaps']}, Gas: {cost['total_gas']}, Fees: {cost['total_fee_pct']:.2f}%")
```

---

## 🎯 Future Enhancements

### Short Term
1. **Implement Multi-Hop Price Calculation**
   - Calculate prices along multi-hop routes
   - Compare direct vs multi-hop arbitrage
   - Select most profitable path

2. **DEX-Based ETH Price**
   - Query WETH/USDC pools for real-time ETH price
   - Replace hardcoded default
   - Update every 5 minutes

3. **Route Caching**
   - Cache discovered routes
   - Avoid re-calculating on every scan
   - Invalidate when new DEXes/tokens added

### Long Term
4. **Intelligent Path Selection**
   - Machine learning for route optimization
   - Historical profitability analysis
   - Adaptive routing based on liquidity

5. **Cross-DEX Routing**
   - Route through different DEXes for each hop
   - Example: STONE→WETH on SyncSwap, WETH→USDC on Ambient
   - Maximize arbitrage opportunities

6. **Circular Arbitrage**
   - Implement circular path execution
   - Example: WETH → USDC → USDT → WETH
   - Profit from price inefficiencies across multiple pairs

---

## 📚 Technical Details

### Gas Price Fetching

**RPC Method**: `eth_gasPrice`
**Format**: Returns gas price in wei
**Conversion**: wei → gwei (÷ 10^9) → ETH (÷ 10^9)

**Cache Structure**:
```python
{
    'price': 0.025,      # gwei
    'timestamp': 1703..  # unix timestamp
}
```

**Fallback Behavior**:
- RPC failure → Returns 0.02 gwei (Scroll average)
- Network down → Uses last cached value if available
- First call fail → Immediate fallback

### Multi-Hop Routing

**Algorithm**: Breadth-first search with depth limit

**Complexity**:
- Direct routes: O(1)
- 2-hop routes: O(n) where n = number of base tokens
- 3-hop routes: O(n²)

**Optimization**:
- Prioritizes shorter routes (lower fees)
- Filters invalid routes early
- Caches route validation results

---

## ⚠️ Known Limitations

1. **Multi-Hop Not Active**: Infrastructure is built but not integrated into scanner
2. **ETH Price Static**: Uses default $3500, not querying DEX pools yet
3. **No Route Liquidity Check**: Doesn't verify sufficient liquidity in multi-hop paths
4. **Single Base Token**: Currently only considers WETH as intermediary

---

## 🧪 Testing

### Test Gas Price Fetching

```bash
# Enable debug mode
# Edit config/.env: DEBUG_MODE=true

# Run scanner
python run.py

# Check startup output shows:
# "Gas Price: X.XXXX gwei (dynamic)"
# "ETH Price: $XXXX.XX"
```

### Test Multi-Hop Routing

```python
from utils.routing import MultiHopRouter

router = MultiHopRouter()

# Test direct route
routes = router.find_routes('WETH', 'USDC', max_hops=1)
assert routes == [['WETH', 'USDC']]

# Test 2-hop route
routes = router.find_routes('STONE', 'USDC', max_hops=2)
assert ['STONE', 'WETH', 'USDC'] in routes

print("✅ All routing tests passed")
```

---

## 📖 References

- **Scroll Gas Prices**: https://scrollscan.com/gastracker
- **ETH Price Feeds**: https://data.chain.link/
- **Uniswap V2 Routing**: https://docs.uniswap.org/contracts/v2/concepts/protocol-overview/smart-contracts#router

---

## 🤝 Contributing

To add new routing algorithms or gas estimation methods:

1. Create new module in `utils/`
2. Follow existing patterns (caching, error handling)
3. Add tests in `tests/`
4. Update this documentation
5. Submit PR

---

**Last Updated**: December 28, 2025
**Version**: 1.1.0
