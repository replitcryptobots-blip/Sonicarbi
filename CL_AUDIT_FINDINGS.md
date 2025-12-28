# Audit Report: Concentrated Liquidity Implementation

**Date**: December 28, 2025
**Scope**: Concentrated Liquidity Support (commit ffb3f67)
**Auditor**: Claude
**Status**: ⚠️ **ISSUES FOUND**

---

## Executive Summary

The concentrated liquidity implementation adds Ambient Finance support to the bot. However, **one critical logic error** was identified in the price calculation that could lead to incorrect arbitrage opportunity detection. Additionally, several minor issues were found.

### Severity Breakdown
- 🔴 **Critical**: 1 issue (decimal handling)
- 🟡 **Medium**: 1 issue (error handling)
- 🟢 **Low**: 1 issue (unused import)

---

## 🔴 Critical Issues

### Issue #1: **Potential Decimal Handling Logic Error**

**File**: `src/concentrated_liquidity.py`
**Lines**: 99-101
**Severity**: 🔴 CRITICAL

**Description**:
The price calculation may not correctly handle token decimal differences, depending on how Ambient's `queryPrice` returns the price ratio.

**Current Code**:
```python
amount_in_adjusted = amount_in * (10 ** token_in['decimals'])   # Line 99
amount_out_adjusted = amount_in_adjusted * price                # Line 100
amount_out = amount_out_adjusted / (10 ** token_out['decimals']) # Line 101
```

**Problem**:
The code assumes `price` is a dimensionless ratio of wei amounts (raw balances). However, Ambient's `queryPrice` may return the price as a ratio of token amounts (already accounting for decimals).

**Two Possible Scenarios**:

1. **If Ambient price is in token terms** (e.g., "1 WETH = 3500 USDC"):
   - Current calculation: `amount_out = (1 * 10^18) * 3500 / 10^6 = 3.5e15 USDC`
   - Expected: `amount_out = 1 * 3500 = 3500 USDC`
   - **Result**: WRONG by factor of 10^12!

2. **If Ambient price is in wei terms** (raw balance ratio):
   - Current calculation would be correct
   - Need to verify with Ambient documentation

**Impact**:
- If scenario 1 is correct: **All Ambient prices will be drastically wrong**
- Could miss real opportunities or show false opportunities
- Arbitrage calculations would be completely incorrect

**Recommendation**:
```python
# PROPOSED FIX (if price is in token terms):
# Simply multiply without wei conversion
amount_out = amount_in * price

# OR (if price needs decimal adjustment):
# Adjust price for decimal differences first
decimal_adjustment = (10 ** token_out['decimals']) / (10 ** token_in['decimals'])
adjusted_price = price * decimal_adjustment
amount_out = amount_in * adjusted_price
```

**Action Required**:
1. Test with real Scroll mainnet data (e.g., WETH/USDC pair)
2. Compare Ambient price with known market rates
3. Verify actual behavior of `queryPrice` function
4. Fix calculation based on findings

---

## 🟡 Medium Issues

### Issue #2: **Silent Error Handling**

**File**: `src/concentrated_liquidity.py`
**Lines**: 105-107
**Severity**: 🟡 MEDIUM

**Description**:
Errors are silently suppressed, making debugging difficult.

**Current Code**:
```python
except Exception as e:
    # Silently fail - pool might not exist for this pair
    return None
```

**Problem**:
- No logging of errors
- Can't distinguish between "pool doesn't exist" vs "RPC error" vs "calculation error"
- Makes debugging production issues very difficult

**Recommendation**:
```python
except Exception as e:
    # Log errors for debugging (can be disabled in production)
    if config.DEBUG_MODE:
        print(f"[DEBUG] Ambient price fetch failed for {token_in['symbol']}/{token_out['symbol']}: {str(e)}")
    return None
```

---

## 🟢 Low Issues

### Issue #3: **Unused Import**

**File**: `src/concentrated_liquidity.py`
**Line**: 16
**Severity**: 🟢 LOW

**Description**:
The `config` module is imported but never used.

**Current Code**:
```python
from config.config import config  # Line 16
# ... config is never referenced in this file
```

**Recommendation**:
Either:
1. Remove the unused import
2. Or use it for debug logging (see Issue #2)

---

## ✅ Code Quality - Good Practices

### Positive Findings:

1. **✅ Good Type Hints**: Uses `typing.Dict` and `typing.Optional`
2. **✅ Good Documentation**: Clear docstrings for all methods
3. **✅ Proper Error Handling Structure**: Try-except blocks in place
4. **✅ Clean Architecture**: Separate classes for each DEX
5. **✅ Correct Base/Quote Ordering**: Lines 73-78 properly handle Ambient's requirement
6. **✅ Price Inversion Logic**: Lines 92-94 correctly invert price when needed
7. **✅ Verified Contract Address**: CrocQuery address verified from official sources

---

## 🧪 Testing Recommendations

### Manual Test Case 1: WETH → USDC on Ambient

```python
from src.concentrated_liquidity import AmbientPriceFetcher
from web3 import Web3

w3 = Web3(Web3.HTTPProvider('https://rpc.scroll.io'))
ambient = AmbientPriceFetcher(w3)

weth = {'address': '0x5300000000000000000000000000000000000004', 'decimals': 18, 'symbol': 'WETH'}
usdc = {'address': '0x06eFdBFf2a14a7c8E15944D1F4A48F9F95F663A4', 'decimals': 6, 'symbol': 'USDC'}

price = ambient.get_price(weth, usdc, 1.0)
print(f"1 WETH = {price} USDC")

# EXPECTED: ~3000-4000 USDC (current ETH price range)
# If you get: 3.5e12 or similar huge number → CRITICAL BUG CONFIRMED
# If you get: ~3500 → Code is correct
```

### Manual Test Case 2: Reverse Direction

```python
price_reverse = ambient.get_price(usdc, weth, 3500)
print(f"3500 USDC = {price_reverse} WETH")

# EXPECTED: ~1.0 WETH
# Check if price * price_reverse ≈ 1.0 (should be reciprocals)
```

---

## 🔍 Code Review - Line by Line

### `AmbientPriceFetcher.get_price()` Analysis

| Line | Code | Status | Notes |
|------|------|--------|-------|
| 69-70 | Address conversion | ✅ OK | Proper checksumming |
| 73-78 | Base/quote ordering | ✅ OK | Correctly sorts addresses |
| 81-83 | queryPrice call | ✅ OK | Correct ABI and params |
| 87 | Q64.64 conversion | ✅ OK | Correct formula |
| 90 | Squaring sqrt_price | ✅ OK | Mathematically correct |
| 93-94 | Price inversion | ✅ OK | Handles direction properly |
| **99-101** | **Decimal handling** | ⚠️ **CRITICAL** | **Needs verification** |
| 103 | Return statement | ✅ OK | - |
| 105-107 | Error handling | 🟡 MEDIUM | Should log errors |

---

## 📋 Verification Checklist

- [x] Contract addresses verified against Scrollscan
- [x] ABI matches Ambient documentation
- [x] Base/quote ordering logic correct
- [x] Q64.64 conversion formula correct
- [ ] **Decimal handling verified with real data** ← **CRITICAL TODO**
- [ ] Error logging implemented
- [ ] Integration tested with scanner
- [ ] Tested on mainnet with real pools

---

## 🎯 Recommended Actions

### Immediate (Before Production Use):

1. **TEST WITH REAL DATA** - Critical!
   - Query known WETH/USDC pool on Scroll
   - Compare price with CEX rates
   - Verify calculation is correct

2. **Add Debug Logging**
   - Log all price queries in debug mode
   - Include input/output amounts
   - Log any errors encountered

3. **Add Price Sanity Checks**
   - Alert if price deviates >50% from expected range
   - Prevent obviously wrong arbitrage signals

### Short Term:

4. **Add Unit Tests**
   - Mock Ambient responses
   - Test decimal edge cases
   - Test price inversion logic

5. **Add Integration Tests**
   - Test with scanner
   - Verify end-to-end arbitrage detection

### Long Term:

6. **Implement Proper Slippage Calculation**
   - Query liquidity depth
   - Model real swap impact

7. **Add Monitoring**
   - Track Ambient price fetch success rate
   - Alert on consistent failures

---

## 📊 Risk Assessment

| Risk | Likelihood | Impact | Severity |
|------|-----------|--------|----------|
| Incorrect prices from Ambient | Medium | Critical | 🔴 HIGH |
| Missed arbitrage opportunities | Low | Medium | 🟡 MEDIUM |
| False arbitrage signals | Medium | High | 🔴 HIGH |
| Silent errors hiding issues | High | Medium | 🟡 MEDIUM |

---

## 🔗 References

- [Ambient Finance CrocQuery Docs](https://docs.ambient.finance/developers/query-contracts/crocquery-contract)
- [Q64.64 Fixed Point Explanation](https://en.wikipedia.org/wiki/Q_(number_format))
- [Scrollscan CrocQuery](https://scrollscan.com/address/0x62223e90605845Cf5CC6DAE6E0de4CDA130d6DDf)

---

## Conclusion

The concentrated liquidity implementation is **well-structured** and follows good practices. However, there is **one critical uncertainty** regarding decimal handling that must be resolved before production use.

**Status**: ⚠️ **REQUIRES TESTING AND POTENTIAL FIX**

**Next Steps**:
1. Test with real mainnet data immediately
2. Fix decimal handling if needed
3. Add logging for better debugging
4. Re-audit after fixes

---

**Audit Complete**: December 28, 2025
