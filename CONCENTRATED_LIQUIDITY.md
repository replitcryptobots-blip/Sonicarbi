# Concentrated Liquidity DEX Support

This document explains the concentrated liquidity DEX integration in the Sonicarbi arbitrage bot.

## Overview

The bot now supports **concentrated liquidity DEXes** in addition to traditional Uniswap V2-style DEXes. Concentrated liquidity allows liquidity providers to concentrate their capital within specific price ranges, resulting in more capital-efficient liquidity.

## Supported DEXes

### ✅ Ambient Finance (CrocSwap) - FULLY SUPPORTED

**Network**: Scroll Mainnet
**Type**: Concentrated Liquidity AMM
**Contract Addresses**:
- CrocSwapDex: `0xaaaaAAAACB71BF2C8CaE522EA5fa455571A74106`
- CrocQuery: `0x62223e90605845Cf5CC6DAE6E0de4CDA130d6DDf`

**Implementation Details**:
- Uses the `CrocQuery` contract for price queries
- Function: `queryPrice(address base, address quote, uint256 poolIdx)`
- Default poolIdx: `420` (standard pools)
- Returns: Q64.64 fixed-point representation of sqrt(price)
- Price calculation: `price = (sqrt_price)^2`

**Documentation**: [Ambient Finance Docs](https://docs.ambient.finance/developers/query-contracts/crocquery-contract)

---

### ⚠️ iZiSwap - LIMITED SUPPORT

**Network**: Scroll Mainnet
**Type**: Discretized Concentrated Liquidity
**Status**: **NOT FULLY FUNCTIONAL** - needs correct Quoter contract address

**Current Limitation**:
The config currently has the LiquidityManager (NFT) address instead of the Quoter contract address. The Quoter contract is required for price queries.

**How to Fix**:
1. Find the iZiSwap Quoter contract address from [iZiSwap Docs](https://developer.izumi.finance/iZiSwap/deployed_contracts/mainnet)
2. Update `src/concentrated_liquidity.py` line 115 with the correct address
3. The quoter should support `quoteExactInput(bytes path, uint256 amountIn)`

**Documentation**: [iZiSwap Developer Docs](https://developer.izumi.finance/iZiSwap/SDK/examples/quoter_and_swap/quoter_and_swap)

---

## Architecture

### Module Structure

```
src/concentrated_liquidity.py
├── AmbientPriceFetcher      # Handles Ambient/CrocSwap queries
├── iZiSwapPriceFetcher      # Handles iZiSwap queries (WIP)
└── ConcentratedLiquidityManager  # Unified interface
```

### Integration with Scanner

The scanner (`src/scanner.py`) automatically detects DEX type and routes to the appropriate price fetcher:

```python
if dex['type'] == 'uniswap_v2':
    price = self.get_price(dex, token_in, token_out, amount)
elif dex['type'] == 'concentrated':
    price = self.get_concentrated_price(dex, token_in, token_out, amount)
```

---

## How Concentrated Liquidity Pricing Works

### Ambient Finance (CrocSwap)

1. **Query the sqrt price** from CrocQuery contract
2. **Convert Q64.64 fixed-point** to float: `sqrt_price = price_q64 / 2^64`
3. **Calculate actual price**: `price = sqrt_price^2`
4. **Handle token ordering**: Ambient requires `base < quote` (addresses sorted)
5. **Calculate output amount**: `amount_out = amount_in * price * (decimals_adjustment)`

### Key Differences from Uniswap V2

| Feature | Uniswap V2 | Concentrated Liquidity |
|---------|-----------|----------------------|
| Liquidity | Distributed across 0 to ∞ | Concentrated in price ranges |
| Capital Efficiency | Lower | Higher |
| Price Query | `getAmountsOut` on Router | Specialized query contracts |
| Price Format | Direct token amounts | Often sqrt or Q64.64 format |
| Slippage | Linear (constant product) | Non-linear (depends on range) |

---

## Configuration

DEX configurations are stored in `config/dex_configs.json`:

```json
{
  "name": "Ambient",
  "router": "0xaaaaAAAACB71BF2C8CaE522EA5fa455571A74106",
  "query_contract": "0x62223e90605845Cf5CC6DAE6E0de4CDA130d6DDf",
  "type": "concentrated",
  "fee": 0.002,
  "priority": 4
}
```

---

## Limitations & Considerations

### Current Limitations

1. **Simplified Price Calculation**: The current implementation uses a simplified price calculation that doesn't account for:
   - Liquidity depth at specific price points
   - Concentrated liquidity ranges
   - Real swap impact on price

2. **No Slippage Modeling**: Concentrated liquidity can have significant slippage depending on:
   - The amount being swapped
   - Available liquidity at the current price
   - How concentrated the liquidity is

3. **iZiSwap Not Functional**: Requires the correct Quoter contract address

### Recommended Improvements

1. **Add Slippage Calculation**: Query liquidity depth and calculate realistic slippage
2. **Use callStatic**: Quoter contracts often use state-changing calls that revert - use `eth_call` with `callStatic`
3. **Cache Queries**: Price queries can be expensive - implement caching
4. **Pool Discovery**: Automatically discover available pools instead of assuming all pairs exist
5. **Multi-hop Routing**: Support routing through multiple pools (e.g., TokenA → WETH → TokenB)

---

## Testing

### Manual Testing

```python
from src.concentrated_liquidity import AmbientPriceFetcher
from web3 import Web3

# Connect to Scroll
w3 = Web3(Web3.HTTPProvider('https://rpc.scroll.io'))

# Initialize price fetcher
ambient = AmbientPriceFetcher(w3)

# Test WETH → USDC swap
weth = {
    'address': '0x5300000000000000000000000000000000000004',
    'decimals': 18,
    'symbol': 'WETH'
}
usdc = {
    'address': '0x06eFdBFf2a14a7c8E15944D1F4A48F9F95F663A4',
    'decimals': 6,
    'symbol': 'USDC'
}

price = ambient.get_price(weth, usdc, 1.0)
print(f"1 WETH = {price} USDC on Ambient")
```

---

## Future DEX Support

### Candidates for Addition

1. **Uniswap V3** (if deployed on Scroll)
   - Quoter: Standard V3 quoter contract
   - Similar to iZiSwap implementation

2. **Other Concentrated Liquidity DEXes**
   - PancakeSwap V3
   - SushiSwap V3
   - Trader Joe V2

### Implementation Template

To add a new concentrated liquidity DEX:

1. Create a new class in `src/concentrated_liquidity.py`
2. Implement `get_price(token_in, token_out, amount_in)` method
3. Add to `ConcentratedLiquidityManager.get_price()` routing
4. Add configuration to `config/dex_configs.json`
5. Test thoroughly with mainnet data

---

## References

### Documentation
- [Ambient Finance CrocQuery Docs](https://docs.ambient.finance/developers/query-contracts/crocquery-contract)
- [iZiSwap Developer Docs](https://developer.izumi.finance/iZiSwap/SDK/)
- [Uniswap V3 Quoter Guide](https://docs.uniswap.org/sdk/v3/guides/swaps/quoting)

### Contract Addresses
- [Ambient on Scrollscan](https://scrollscan.com/address/0xaaaaaaaacb71bf2c8cae522ea5fa455571a74106)
- [Ambient CrocQuery on Scrollscan](https://scrollscan.com/address/0x62223e90605845Cf5CC6DAE6E0de4CDA130d6DDf)

---

## Troubleshooting

### Ambient Returns None

**Possible Causes**:
1. No liquidity pool exists for the token pair
2. RPC connection issues
3. Tokens not in base/quote order

**Solution**: Check Scrollscan to verify the pool exists

### iZiSwap Not Working

**Expected**: iZiSwap is not fully functional without the correct Quoter address.

**Solution**: Update the Quoter contract address in `src/concentrated_liquidity.py`

### Price Seems Incorrect

**Possible Causes**:
1. Token decimals mismatch
2. Price inversion needed (base vs quote)
3. Sqrt price not squared correctly

**Solution**: Add debug logging to trace price calculations

---

## Contributing

When adding support for new concentrated liquidity DEXes:
1. Research the DEX's price query mechanism
2. Identify the correct query contract and ABI
3. Implement with proper error handling
4. Test with real mainnet data
5. Document in this file
6. Update AUDIT_REPORT.md

