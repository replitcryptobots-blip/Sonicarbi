# MEV Protection & Security Hardening

**MEV (Maximal Extractable Value)** is the profit that can be extracted from transaction ordering, insertion, and censorship. This document outlines strategies to protect your arbitrage bot from MEV attacks.

---

## Table of Contents

1. [Understanding MEV Threats](#understanding-mev-threats)
2. [Sandwich Attack Protection](#sandwich-attack-protection)
3. [Frontrunning Protection](#frontrunning-protection)
4. [Backrunning Protection](#backrunning-protection)
5. [Implementation Strategies](#implementation-strategies)
6. [Monitoring & Detection](#monitoring--detection)

---

## Understanding MEV Threats

### Attack Vectors

#### 1. Sandwich Attacks

**What it is:**
- Attacker sees your transaction in mempool
- Places buy order before yours (frontrun)
- Places sell order after yours (backrun)
- Profits from price movement you created

**Impact on arbitrage:**
- Your buy price increases
- Your sell price decreases
- Your profit margin squeezed or eliminated
- You still pay gas but make less/no profit

**Example:**
```
You submit: Buy 1 WETH @ 3500 USDC

Attacker sees this and submits:
1. Buy 0.5 WETH @ 3500 USDC (higher gas, executes first)
2. Your tx: Buy 1 WETH @ 3510 USDC (price moved up!)
3. Sell 0.5 WETH @ 3515 USDC (backrun, profits 7.5 USDC)

Result: You lost 10 USDC, attacker gained 7.5 USDC
```

#### 2. Frontrunning

**What it is:**
- Attacker copies your transaction
- Submits it with higher gas price
- Captures the arbitrage opportunity before you

**Impact:**
- Your transaction fails or executes unprofitably
- Wasted gas costs
- Opportunity stolen

#### 3. Backrunning

**What it is:**
- Attacker executes immediately after your transaction
- Exploits price inefficiency you created
- Takes profit from your market impact

**Impact:**
- Less severe than frontrunning
- Reduces overall market efficiency
- Can cascade into future opportunities being stolen

---

## Sandwich Attack Protection

### 1. Slippage Protection (Implemented ✅)

**Contract-level protection:**

```solidity
// In FlashloanArbitrage.sol
function _swapOnDex(
    address router,
    address tokenIn,
    address tokenOut,
    uint256 amountIn,
    uint256 deadline,
    uint256 slippageBps  // e.g., 200 = 2% max slippage
) internal returns (uint256) {
    // Get expected output
    uint256[] memory expectedAmounts = IUniswapV2Router(router).getAmountsOut(amountIn, path);
    uint256 expectedOut = expectedAmounts[1];

    // Calculate minimum acceptable output
    uint256 minAmountOut = (expectedOut * (10000 - slippageBps)) / 10000;

    // Execute swap with protection
    uint256[] memory amounts = IUniswapV2Router(router).swapExactTokensForTokens(
        amountIn,
        minAmountOut,  // Revert if we get less than this
        path,
        address(this),
        deadline
    );

    return amounts[amounts.length - 1];
}
```

**Bot-level validation:**

```python
# In executor.py
async def _check_slippage(self, opp: Dict) -> None:
    """Check if slippage is within acceptable limits."""

    is_valid, slippage_info = self.slippage_calc.validate_arbitrage_slippage(
        buy_dex=opp['buy_dex'],
        sell_dex=opp['sell_dex'],
        token_in=token_in,
        token_out=token_out,
        amount=opp['amount'],
        max_slippage_pct=config.SLIPPAGE_TOLERANCE * 100  # e.g., 2%
    )

    if not is_valid:
        raise SlippageExceededError(
            f"Total slippage {slippage_info['total_slippage_pct']:.3f}% "
            f"exceeds maximum {config.SLIPPAGE_TOLERANCE * 100:.3f}%"
        )
```

**Configuration:**

```bash
# config/.env
SLIPPAGE_TOLERANCE=0.02  # 2% maximum slippage

# Lower = more protection but fewer opportunities
# Higher = more opportunities but higher sandwich risk

# Recommended values:
# - Conservative: 0.01 (1%)
# - Balanced: 0.02 (2%)
# - Aggressive: 0.05 (5%) - NOT RECOMMENDED
```

### 2. Profit Verification

**Double-check profit after execution:**

```solidity
// In FlashloanArbitrage.sol executeOperation()
uint256 finalBalance = IERC20(asset).balanceOf(address(this));
uint256 totalDebt = amount + premium;

// Ensure we actually made profit
if (finalBalance < totalDebt + minProfit) {
    revert InsufficientProfit(finalBalance - totalDebt, minProfit);
}
```

This ensures that even if sandwiched, the transaction reverts rather than executing at a loss.

### 3. Deadline Protection

```solidity
// Transactions expire after deadline
require(params.deadline >= block.timestamp, "Deadline passed");

// Swap calls include deadline
IUniswapV2Router(router).swapExactTokensForTokens(
    amountIn,
    minAmountOut,
    path,
    address(this),
    deadline  // If not mined by this timestamp, revert
);
```

**Set reasonable deadlines:**
```python
# 5 minutes from submission
deadline = current_block_time + 300
```

---

## Frontrunning Protection

### 1. Private Mempool (Recommended)

**Use private transaction relays that don't expose transactions publicly:**

#### Option A: Flashbots Protect (if available on Scroll)
```python
# Send transactions through Flashbots
# Transactions are private until included in block

import requests

def send_private_transaction(signed_tx):
    """Send transaction via Flashbots (if supported on Scroll)."""

    # Note: Flashbots may not be available on Scroll yet
    # Check current status: https://docs.flashbots.net/

    flashbots_rpc = "https://relay.flashbots.net"  # Example

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_sendPrivateTransaction",
        "params": [{
            "tx": signed_tx.rawTransaction.hex(),
            "maxBlockNumber": latest_block + 5,  # Valid for 5 blocks
        }]
    }

    response = requests.post(flashbots_rpc, json=payload)
    return response.json()
```

#### Option B: Private RPC with Direct Builder Connection
```python
# Use RPC that submits directly to block builders
# Bypasses public mempool

PRIVATE_RPC = "https://private-rpc.scroll.io"  # Example
w3 = Web3(Web3.HTTPProvider(PRIVATE_RPC))
```

#### Option C: MEV-Blocker Services
- MEV-Blocker: https://mevblocker.io/
- SecureRPC: https://securerpc.com/

### 2. Randomized Timing

```python
import random
import asyncio

async def submit_with_jitter(tx):
    """Add random delay to make timing less predictable."""

    # Random delay between 0-2 seconds
    jitter = random.uniform(0, 2)
    await asyncio.sleep(jitter)

    # Submit transaction
    return w3.eth.send_raw_transaction(tx)
```

⚠️ **Note:** This provides minimal protection and should not be relied upon alone.

### 3. Gas Price Optimization

**Don't always use maximum gas price:**

```python
def calculate_optimal_gas_price(current_gas: float, profit_usd: float) -> float:
    """
    Calculate gas price that makes frontrunning unprofitable.

    If attacker needs to pay more gas than the profit, they won't frontrun.
    """

    # Estimate gas units for arbitrage
    gas_units = 350000

    # Calculate max profitable gas price for attacker
    # profit_usd / gas_units / eth_price_usd = max_gas_price_eth
    eth_price = get_eth_price_usd()
    max_profitable_gas_gwei = (profit_usd / gas_units / eth_price) * 1e9

    # Use slightly below this to make frontrunning unprofitable
    optimal_gas = min(
        max_profitable_gas_gwei * 0.95,  # 95% of max profitable
        current_gas * 1.5  # But not more than 50% above current
    )

    logger.info(
        f"Optimal gas price: {optimal_gas:.4f} gwei "
        f"(makes frontrunning unprofitable)"
    )

    return optimal_gas
```

---

## Backrunning Protection

### 1. Minimize Market Impact

**Use smaller position sizes:**

```python
def calculate_max_trade_size(pool_reserve: float, max_impact_pct: float = 1.0) -> float:
    """
    Calculate maximum trade size for given price impact.

    For Uniswap V2: price_impact = amount_in / reserve_in
    """

    max_amount = pool_reserve * (max_impact_pct / 100)

    logger.info(
        f"Max trade size for {max_impact_pct}% impact: "
        f"{max_amount:.4f} (pool reserve: {pool_reserve:.2f})"
    )

    return max_amount
```

### 2. Multi-Leg Execution

**Split large trades across multiple DEXes:**

```python
def split_order_across_dexes(
    total_amount: float,
    dexes: List[Dict]
) -> List[Tuple[str, float]]:
    """
    Split order to minimize market impact on any single DEX.
    """

    # Get liquidity for each DEX
    liquidities = [
        (dex['name'], get_pool_liquidity(dex))
        for dex in dexes
    ]

    # Sort by liquidity (deepest first)
    liquidities.sort(key=lambda x: x[1], reverse=True)

    # Allocate proportionally to liquidity
    total_liquidity = sum(liq for _, liq in liquidities)

    allocations = [
        (name, (liq / total_liquidity) * total_amount)
        for name, liq in liquidities
    ]

    return allocations
```

---

## Implementation Strategies

### 1. Circuit Breaker for MEV Detection

```python
class MEVDetector:
    """Detect if we're being consistently sandwiched."""

    def __init__(self):
        self.recent_trades = []
        self.sandwich_count = 0

    def check_trade_result(
        self,
        expected_profit: float,
        actual_profit: float
    ) -> bool:
        """
        Check if trade result indicates sandwich attack.

        Returns True if likely sandwiched.
        """

        profit_ratio = actual_profit / expected_profit if expected_profit > 0 else 0

        # If we got <50% of expected profit, likely sandwiched
        if profit_ratio < 0.5:
            self.sandwich_count += 1
            logger.warning(
                f"Possible sandwich attack! "
                f"Expected ${expected_profit:.2f}, got ${actual_profit:.2f} "
                f"({profit_ratio*100:.1f}%)"
            )

            # If sandwiched 3 times in last 10 trades, trip circuit breaker
            if self.sandwich_count >= 3:
                logger.error(
                    "MEV circuit breaker tripped! "
                    "Consistent sandwich attacks detected."
                )
                return True
        else:
            # Reset counter on successful trade
            self.sandwich_count = max(0, self.sandwich_count - 1)

        return False
```

### 2. Private Transaction Pool

**Build your own private orderflow:**

```python
class PrivateTransactionPool:
    """
    Maintain a pool of pending transactions that are NOT broadcast publicly.

    Submit in batches or when profitable to reduce MEV risk.
    """

    def __init__(self):
        self.pending_txs = []
        self.min_batch_profit = 100  # USD

    def add_opportunity(self, opp: Dict) -> None:
        """Add opportunity to private pool."""
        self.pending_txs.append(opp)

        # Check if we should execute batch
        if self._should_execute_batch():
            self.execute_batch()

    def _should_execute_batch(self) -> bool:
        """Decide if we should execute the batch."""

        total_profit = sum(tx['profit_usd'] for tx in self.pending_txs)

        # Execute if:
        # - Total profit > minimum, OR
        # - We have 5+ opportunities, OR
        # - Oldest opportunity is >1 minute old

        return (
            total_profit >= self.min_batch_profit or
            len(self.pending_txs) >= 5 or
            self._oldest_tx_age() > 60
        )

    def execute_batch(self) -> None:
        """Execute all pending transactions in a single transaction."""

        # This would require a smart contract that can execute
        # multiple arbitrages in one transaction

        logger.info(
            f"Executing batch of {len(self.pending_txs)} opportunities, "
            f"total profit: ${sum(tx['profit_usd'] for tx in self.pending_txs):.2f}"
        )

        # Execute...
        # self.contract.functions.executeBatch(self.pending_txs).transact()

        self.pending_txs.clear()
```

### 3. Dynamic Parameter Adjustment

```python
class AdaptiveProtection:
    """Adapt protection parameters based on detected MEV activity."""

    def __init__(self):
        self.base_slippage = 0.02  # 2%
        self.base_min_profit = 0.005  # 0.5%
        self.mev_level = 0  # 0 = low, 1 = medium, 2 = high

    def update_mev_level(self, sandwich_detected: bool) -> None:
        """Update MEV threat level."""

        if sandwich_detected:
            self.mev_level = min(2, self.mev_level + 1)
        else:
            self.mev_level = max(0, self.mev_level - 1)

        logger.info(f"MEV threat level: {self.mev_level} (0=low, 2=high)")

    def get_adjusted_slippage(self) -> float:
        """Get slippage tolerance adjusted for MEV threat."""

        # Reduce slippage tolerance when MEV is high
        multipliers = [1.0, 0.7, 0.5]  # 100%, 70%, 50%

        return self.base_slippage * multipliers[self.mev_level]

    def get_adjusted_min_profit(self) -> float:
        """Get minimum profit threshold adjusted for MEV threat."""

        # Increase profit threshold when MEV is high
        multipliers = [1.0, 1.5, 2.0]  # 100%, 150%, 200%

        return self.base_min_profit * multipliers[self.mev_level]
```

---

## Monitoring & Detection

### 1. Transaction Analysis

**Monitor your transactions for MEV:**

```python
def analyze_transaction_for_mev(tx_hash: str) -> Dict:
    """
    Analyze a transaction to detect MEV activity.
    """

    receipt = w3.eth.get_transaction_receipt(tx_hash)
    block_number = receipt['blockNumber']
    tx_index = receipt['transactionIndex']

    # Get all transactions in the same block
    block = w3.eth.get_block(block_number, full_transactions=True)

    results = {
        'sandwiched': False,
        'frontrun': False,
        'backrun': False,
        'details': []
    }

    # Check transaction immediately before ours
    if tx_index > 0:
        prev_tx = block['transactions'][tx_index - 1]

        # Check if it interacted with same DEX
        if is_same_pair_swap(prev_tx, our_tx):
            results['frontrun'] = True
            results['details'].append(f"Frontrun by {prev_tx['hash'].hex()}")

    # Check transaction immediately after ours
    if tx_index < len(block['transactions']) - 1:
        next_tx = block['transactions'][tx_index + 1]

        if is_same_pair_swap(next_tx, our_tx):
            results['backrun'] = True
            results['details'].append(f"Backrun by {next_tx['hash'].hex()}")

    # If both frontrun and backrun, it's a sandwich
    if results['frontrun'] and results['backrun']:
        results['sandwiched'] = True

    return results
```

### 2. Profit Deviation Tracking

```python
def track_profit_deviation(
    expected_profit: float,
    actual_profit: float
) -> None:
    """Track how often actual profit differs from expected."""

    deviation = ((actual_profit - expected_profit) / expected_profit) * 100

    # Store in database or metrics system
    metrics.gauge('profit_deviation_pct', deviation)

    if abs(deviation) > 10:
        logger.warning(
            f"Large profit deviation: expected ${expected_profit:.2f}, "
            f"got ${actual_profit:.2f} ({deviation:+.1f}%)"
        )

    # Alert if consistent negative deviation
    recent_deviations = get_recent_deviations(count=10)
    avg_deviation = sum(recent_deviations) / len(recent_deviations)

    if avg_deviation < -5:  # Average 5% worse than expected
        alert_mev_activity(
            f"Consistent negative profit deviation: {avg_deviation:.1f}%"
        )
```

### 3. Alerting

```python
async def alert_mev_activity(message: str) -> None:
    """Send alert about MEV activity."""

    await notifier.send_error(
        f"⚠️ MEV ALERT: {message}",
        context={
            'timestamp': datetime.now().isoformat(),
            'action_required': 'Review recent transactions and consider increasing protection'
        }
    )

    # Log for analysis
    logger.error(f"MEV ALERT: {message}")
```

---

## Best Practices Summary

### ✅ Implemented Protections

1. **Slippage protection** - Contract and bot level
2. **Profit verification** - Revert if below minimum
3. **Deadline protection** - Transactions expire
4. **Circuit breaker** - Stop after repeated failures

### 🔄 Recommended Additions

1. **Private mempool** - Use Flashbots or similar
2. **MEV detection** - Monitor and adapt
3. **Dynamic parameters** - Adjust based on threat level
4. **Batch execution** - Combine multiple opportunities

### ⚠️ Operational Guidelines

1. **Start conservative** - High slippage protection, high profit threshold
2. **Monitor constantly** - Watch for sandwich attacks
3. **Adapt quickly** - Increase protection if MEV detected
4. **Document incidents** - Learn from each attack
5. **Stay updated** - MEV landscape changes constantly

---

## Resources

### Learn More About MEV
- **Flashbots Docs**: https://docs.flashbots.net/
- **MEV-Boost**: https://boost.flashbots.net/
- **Ethereum MEV Research**: https://ethereum.org/en/developers/docs/mev/

### Scroll-Specific
- **Scroll MEV Status**: Check if Flashbots or alternatives available
- **Block Explorers**: Monitor transactions on Scrollscan

### Community
- **MEV Research Discord**: https://discord.gg/flashbots
- **Scroll Discord**: https://discord.gg/scroll

---

*Last Updated: 2025-12-30*
*Version: 1.0*
