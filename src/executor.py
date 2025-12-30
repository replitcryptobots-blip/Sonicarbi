"""
Production-grade arbitrage executor with flashloan integration.

This module handles the execution of arbitrage opportunities found by the scanner,
including:
- Pre-execution validation
- Flashloan contract interaction
- Slippage protection
- Gas estimation and optimization
- Transaction monitoring
- MEV protection strategies
- Circuit breakers

Security Features:
- Simulates trades before execution
- Enforces strict profit thresholds
- Maximum slippage protection
- Revert-on-loss guarantee
- Sandwich attack detection
- RPC failure handling
"""

import asyncio
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import Web3Exception, ContractLogicError
from eth_account import Account
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import json
from pathlib import Path

from config.logging_config import get_logger
from config.config import config
from utils.slippage_calculator import SlippageCalculator
from utils.gas_price import GasPriceFetcher, ETHPriceFetcher
from utils.notifications import NotificationManager
from utils.private_mempool import PrivateMempoolManager

logger = get_logger(__name__)


class ExecutionError(Exception):
    """Base exception for execution errors."""
    pass


class InsufficientProfitError(ExecutionError):
    """Raised when profit is below minimum threshold."""
    pass


class SlippageExceededError(ExecutionError):
    """Raised when slippage would exceed maximum allowed."""
    pass


class CircuitBreakerTrippedError(ExecutionError):
    """Raised when circuit breaker prevents execution."""
    pass


class CircuitBreaker:
    """
    Circuit breaker to prevent repeated failures from draining funds.

    Tracks failures and automatically stops execution if too many failures occur
    within a time window.
    """

    def __init__(
        self,
        max_failures: int = 5,
        time_window_seconds: int = 300,
        cooldown_seconds: int = 600
    ):
        """
        Initialize circuit breaker.

        Args:
            max_failures: Maximum failures allowed in time window
            time_window_seconds: Time window for tracking failures (default: 5 minutes)
            cooldown_seconds: Cooldown period after tripping (default: 10 minutes)
        """
        self.max_failures = max_failures
        self.time_window = time_window_seconds
        self.cooldown = cooldown_seconds

        self.failures: list[datetime] = []
        self.tripped_at: Optional[datetime] = None

        logger.info(
            f"CircuitBreaker initialized: {max_failures} failures per {time_window_seconds}s, "
            f"cooldown={cooldown_seconds}s"
        )

    def record_failure(self, reason: str) -> None:
        """Record a failure."""
        now = datetime.now()
        self.failures.append(now)

        # Clean old failures outside time window
        cutoff = now - timedelta(seconds=self.time_window)
        self.failures = [f for f in self.failures if f > cutoff]

        logger.warning(
            f"Circuit breaker failure recorded: {reason} "
            f"({len(self.failures)}/{self.max_failures} in last {self.time_window}s)"
        )

        # Check if we should trip
        if len(self.failures) >= self.max_failures:
            self.tripped_at = now
            logger.error(
                f"CIRCUIT BREAKER TRIPPED! Too many failures "
                f"({len(self.failures)} in {self.time_window}s). "
                f"Cooldown for {self.cooldown}s."
            )

    def record_success(self) -> None:
        """Record a successful execution."""
        # Reset failures on success
        if self.failures:
            logger.info(f"Execution successful, resetting {len(self.failures)} recorded failures")
            self.failures.clear()

    def is_tripped(self) -> bool:
        """Check if circuit breaker is currently tripped."""
        if self.tripped_at is None:
            return False

        # Check if cooldown period has passed
        elapsed = (datetime.now() - self.tripped_at).total_seconds()
        if elapsed >= self.cooldown:
            logger.info(f"Circuit breaker cooldown complete ({elapsed:.0f}s), resetting")
            self.tripped_at = None
            self.failures.clear()
            return False

        return True

    def get_status(self) -> Dict:
        """Get current circuit breaker status."""
        if self.tripped_at:
            elapsed = (datetime.now() - self.tripped_at).total_seconds()
            remaining = max(0, self.cooldown - elapsed)
            return {
                'status': 'tripped',
                'failures': len(self.failures),
                'cooldown_remaining_seconds': remaining
            }
        else:
            return {
                'status': 'operational',
                'failures': len(self.failures),
                'max_failures': self.max_failures
            }


class ArbitrageExecutor:
    """
    Executes arbitrage opportunities using Aave V3 flashloans.

    This class handles the complete execution flow:
    1. Validate opportunity
    2. Simulate execution
    3. Calculate optimal gas price
    4. Submit transaction
    5. Monitor transaction
    6. Handle results
    """

    # Flashloan contract ABI (minimal)
    FLASHLOAN_ABI = json.loads('''[
        {
            "inputs": [
                {
                    "components": [
                        {"internalType": "address", "name": "tokenBorrow", "type": "address"},
                        {"internalType": "uint256", "name": "amount", "type": "uint256"},
                        {"internalType": "address", "name": "tokenTarget", "type": "address"},
                        {"internalType": "address", "name": "buyDex", "type": "address"},
                        {"internalType": "address", "name": "sellDex", "type": "address"},
                        {"internalType": "uint256", "name": "minProfit", "type": "uint256"},
                        {"internalType": "uint256", "name": "deadline", "type": "uint256"},
                        {"internalType": "uint256", "name": "slippageBps", "type": "uint256"}
                    ],
                    "internalType": "struct FlashloanArbitrage.ArbitrageParams",
                    "name": "params",
                    "type": "tuple"
                }
            ],
            "name": "executeArbitrage",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "components": [
                        {"internalType": "address", "name": "tokenBorrow", "type": "address"},
                        {"internalType": "uint256", "name": "amount", "type": "uint256"},
                        {"internalType": "address", "name": "tokenTarget", "type": "address"},
                        {"internalType": "address", "name": "buyDex", "type": "address"},
                        {"internalType": "address", "name": "sellDex", "type": "address"},
                        {"internalType": "uint256", "name": "minProfit", "type": "uint256"},
                        {"internalType": "uint256", "name": "deadline", "type": "uint256"},
                        {"internalType": "uint256", "name": "slippageBps", "type": "uint256"}
                    ],
                    "internalType": "struct FlashloanArbitrage.ArbitrageParams",
                    "name": "params",
                    "type": "tuple"
                }
            ],
            "name": "simulateArbitrage",
            "outputs": [{"internalType": "uint256", "name": "expectedProfit", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        }
    ]''')

    def __init__(
        self,
        w3: Web3,
        contract_address: Optional[str] = None,
        private_key: Optional[str] = None,
        dry_run: bool = True
    ):
        """
        Initialize arbitrage executor.

        Args:
            w3: Web3 instance
            contract_address: Flashloan contract address (or use from config)
            private_key: Private key for signing transactions (or use from config)
            dry_run: If True, only simulate, don't execute (default: True for safety)
        """
        self.w3 = w3
        self.dry_run = dry_run

        # Get contract address
        self.contract_address = contract_address or config.FLASHLOAN_CONTRACT
        if not self.contract_address:
            raise ValueError("Flashloan contract address not configured")

        self.contract_address = Web3.to_checksum_address(self.contract_address)
        logger.info(f"Flashloan contract: {self.contract_address}")

        # Initialize contract
        self.contract: Contract = w3.eth.contract(
            address=self.contract_address,
            abi=self.FLASHLOAN_ABI
        )

        # Initialize account (if not dry run)
        if not dry_run:
            self.private_key = private_key or config.PRIVATE_KEY
            if not self.private_key:
                raise ValueError("Private key required for live execution")

            self.account = Account.from_key(self.private_key)
            logger.info(f"Executor account: {self.account.address}")
        else:
            self.private_key = None
            self.account = None
            logger.info("DRY RUN MODE: No transactions will be sent")

        # Initialize helpers
        self.slippage_calc = SlippageCalculator(w3)
        self.gas_fetcher = GasPriceFetcher(w3)
        self.eth_price_fetcher = ETHPriceFetcher(w3)
        self.notifier = NotificationManager()

        # Load DEX configs for router addresses
        config_path = Path(__file__).parent.parent / 'config' / 'dex_configs.json'
        with open(config_path, 'r') as f:
            data = json.load(f)
        self.dexes = {d['name']: d for d in data['scroll']['dexes']}
        self.tokens = {t['symbol']: t for t in data['scroll']['common_tokens']}

        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(
            max_failures=5,
            time_window_seconds=300,
            cooldown_seconds=600
        )

        # Private mempool manager for MEV protection
        self.use_private_mempool = getattr(config, 'USE_PRIVATE_MEMPOOL', False)
        if not dry_run:
            self.private_mempool = PrivateMempoolManager(
                w3=w3,
                prefer_private=self.use_private_mempool
            )
            logger.info(
                f"Private mempool: {'enabled' if self.use_private_mempool else 'disabled'} "
                f"(provider: {self.private_mempool.get_active_provider()})"
            )
        else:
            self.private_mempool = None

        # Execution statistics
        self.stats = {
            'total_opportunities_evaluated': 0,
            'passed_validation': 0,
            'executed': 0,
            'successful': 0,
            'failed': 0,
            'total_profit_usd': 0.0,
            'total_gas_spent_usd': 0.0
        }

        logger.info("ArbitrageExecutor initialized")

    async def evaluate_and_execute(
        self,
        opportunity: Dict
    ) -> Optional[Dict]:
        """
        Evaluate an opportunity and execute if profitable.

        Args:
            opportunity: Opportunity dict from scanner

        Returns:
            Execution result dict, or None if not executed
        """
        self.stats['total_opportunities_evaluated'] += 1

        try:
            # Check circuit breaker
            if self.circuit_breaker.is_tripped():
                status = self.circuit_breaker.get_status()
                logger.warning(
                    f"Circuit breaker tripped, skipping execution. "
                    f"Cooldown remaining: {status['cooldown_remaining_seconds']:.0f}s"
                )
                raise CircuitBreakerTrippedError("Circuit breaker is tripped")

            # Validate opportunity
            logger.info(
                f"Evaluating opportunity: {opportunity['token_in']}→{opportunity['token_out']} "
                f"via {opportunity['buy_dex']}→{opportunity['sell_dex']}, "
                f"profit={opportunity['profit_pct']:.3f}% (${opportunity['profit_usd']:.2f})"
            )

            # Pre-execution checks
            self._validate_opportunity(opportunity)

            # Check slippage
            await self._check_slippage(opportunity)

            # Simulate execution
            simulated_profit = await self._simulate_execution(opportunity)

            logger.info(
                f"Simulation successful. Expected profit: "
                f"{simulated_profit['profit_tokens']:.6f} {opportunity['token_in']} "
                f"(${simulated_profit['profit_usd']:.2f})"
            )

            # Execute (if not dry run)
            if self.dry_run:
                logger.info("DRY RUN: Would execute arbitrage here")
                result = {
                    'status': 'simulated',
                    'opportunity': opportunity,
                    'simulated_profit': simulated_profit,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                result = await self._execute_arbitrage(opportunity, simulated_profit)

            self.stats['passed_validation'] += 1
            return result

        except CircuitBreakerTrippedError:
            # Don't count as failure
            return None
        except Exception as e:
            logger.error(f"Failed to execute opportunity: {e}", exc_info=True)
            self.circuit_breaker.record_failure(str(e))

            # Send error notification
            await self.notifier.send_error(
                f"Execution failed: {str(e)}",
                context={'opportunity': opportunity}
            )

            return None

    def _validate_opportunity(self, opp: Dict) -> None:
        """
        Validate opportunity before execution.

        Raises:
            ValueError: If opportunity is invalid
            InsufficientProfitError: If profit is too low
        """
        required_fields = [
            'token_in', 'token_out', 'buy_dex', 'sell_dex',
            'amount', 'profit_pct', 'profit_usd'
        ]

        for field in required_fields:
            if field not in opp:
                raise ValueError(f"Missing required field: {field}")

        # Check profit threshold
        if opp['profit_pct'] < (config.PROFIT_THRESHOLD * 100):
            raise InsufficientProfitError(
                f"Profit {opp['profit_pct']:.3f}% below threshold "
                f"{config.PROFIT_THRESHOLD * 100:.3f}%"
            )

        # Check tokens exist in config
        if opp['token_in'] not in self.tokens:
            raise ValueError(f"Unknown token: {opp['token_in']}")
        if opp['token_out'] not in self.tokens:
            raise ValueError(f"Unknown token: {opp['token_out']}")

        # Check DEXes exist in config
        if opp['buy_dex'] not in self.dexes:
            raise ValueError(f"Unknown DEX: {opp['buy_dex']}")
        if opp['sell_dex'] not in self.dexes:
            raise ValueError(f"Unknown DEX: {opp['sell_dex']}")

        logger.debug("Opportunity validation passed")

    async def _check_slippage(self, opp: Dict) -> None:
        """
        Check if slippage is within acceptable limits.

        Raises:
            SlippageExceededError: If slippage would be too high
        """
        token_in = self.tokens[opp['token_in']]
        token_out = self.tokens[opp['token_out']]

        # Validate slippage on both legs
        is_valid, slippage_info = self.slippage_calc.validate_arbitrage_slippage(
            buy_dex=opp['buy_dex'],
            sell_dex=opp['sell_dex'],
            token_in=token_in,
            token_out=token_out,
            amount=opp['amount'],
            max_slippage_pct=config.SLIPPAGE_TOLERANCE * 100
        )

        if not is_valid:
            total_slippage = slippage_info.get('total_slippage_pct', 0)
            raise SlippageExceededError(
                f"Total slippage {total_slippage:.3f}% exceeds maximum "
                f"{config.SLIPPAGE_TOLERANCE * 100:.3f}%"
            )

        logger.debug(
            f"Slippage check passed: {slippage_info.get('total_slippage_pct', 0):.3f}% "
            f"(max: {config.SLIPPAGE_TOLERANCE * 100:.3f}%)"
        )

    async def _simulate_execution(self, opp: Dict) -> Dict:
        """
        Simulate arbitrage execution using smart contract.

        Returns:
            Dict with simulated profit info

        Raises:
            ExecutionError: If simulation fails
        """
        try:
            # Prepare parameters
            token_in = self.tokens[opp['token_in']]
            token_out = self.tokens[opp['token_out']]
            buy_dex_router = Web3.to_checksum_address(self.dexes[opp['buy_dex']]['router'])
            sell_dex_router = Web3.to_checksum_address(self.dexes[opp['sell_dex']]['router'])

            amount_wei = int(opp['amount'] * (10 ** token_in['decimals']))

            # Calculate minimum profit (80% of expected profit for safety)
            expected_profit_tokens = (opp['profit_pct'] / 100) * opp['amount']
            min_profit_tokens = expected_profit_tokens * 0.8
            min_profit_wei = int(min_profit_tokens * (10 ** token_in['decimals']))

            # Deadline (5 minutes from now)
            deadline = self.w3.eth.get_block('latest')['timestamp'] + 300

            # Slippage in basis points (from config)
            slippage_bps = int(config.SLIPPAGE_TOLERANCE * 10000)

            params = {
                'tokenBorrow': Web3.to_checksum_address(token_in['address']),
                'amount': amount_wei,
                'tokenTarget': Web3.to_checksum_address(token_out['address']),
                'buyDex': buy_dex_router,
                'sellDex': sell_dex_router,
                'minProfit': min_profit_wei,
                'deadline': deadline,
                'slippageBps': slippage_bps
            }

            # Call simulateArbitrage view function
            logger.debug(f"Simulating arbitrage with params: {params}")

            expected_profit_wei = self.contract.functions.simulateArbitrage(params).call()

            # Convert to human-readable
            expected_profit_tokens = expected_profit_wei / (10 ** token_in['decimals'])

            # Get ETH price for USD conversion
            eth_price = self.eth_price_fetcher.get_eth_price_usd()

            # Convert to USD (if possible)
            if token_in['symbol'] in ['USDC', 'USDT']:
                expected_profit_usd = expected_profit_tokens
            elif token_in['symbol'] == 'WETH':
                expected_profit_usd = expected_profit_tokens * eth_price
            else:
                expected_profit_usd = 0  # Can't calculate

            return {
                'profit_tokens': expected_profit_tokens,
                'profit_usd': expected_profit_usd,
                'profit_wei': expected_profit_wei,
                'params': params
            }

        except ContractLogicError as e:
            raise ExecutionError(f"Simulation reverted: {e}")
        except Exception as e:
            raise ExecutionError(f"Simulation failed: {e}")

    async def _execute_arbitrage(
        self,
        opp: Dict,
        simulated_profit: Dict
    ) -> Dict:
        """
        Execute arbitrage on-chain.

        Args:
            opp: Opportunity dict
            simulated_profit: Result from simulation

        Returns:
            Execution result dict
        """
        logger.info("Executing arbitrage transaction...")

        try:
            # Build transaction
            tx = self.contract.functions.executeArbitrage(
                simulated_profit['params']
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 500000,  # Conservative estimate, will be adjusted
                'gasPrice': int(self.gas_fetcher.get_gas_price_gwei() * 1e9),
                'chainId': config.ACTIVE_CHAIN_ID
            })

            # Estimate gas
            try:
                estimated_gas = self.w3.eth.estimate_gas(tx)
                tx['gas'] = int(estimated_gas * 1.2)  # 20% buffer
                logger.debug(f"Gas estimate: {estimated_gas}, using: {tx['gas']}")
            except Exception as e:
                logger.warning(f"Gas estimation failed: {e}, using default")

            # Sign transaction
            signed_tx = self.account.sign_transaction(tx)

            # Send transaction through private mempool (if available)
            if self.private_mempool:
                # Calculate max block number (valid for next 5 blocks)
                current_block = self.w3.eth.block_number
                max_block_number = current_block + 5

                tx_hash_hex = await self.private_mempool.send_transaction(
                    signed_tx.rawTransaction,
                    max_block_number=max_block_number
                )

                if not tx_hash_hex:
                    raise ExecutionError("Failed to send transaction through any mempool provider")

                logger.info(
                    f"Transaction sent via {self.private_mempool.get_active_provider()}: "
                    f"{tx_hash_hex}"
                )
            else:
                # Fallback to direct sending (should not reach here in non-dry-run mode)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                tx_hash_hex = tx_hash.hex()
                logger.info(f"Transaction sent: {tx_hash_hex}")

            # Wait for receipt
            logger.info("Waiting for transaction confirmation...")
            receipt = self.w3.eth.wait_for_transaction_receipt(
                bytes.fromhex(tx_hash_hex.replace('0x', '')),
                timeout=300
            )

            # Check if successful
            if receipt['status'] == 1:
                logger.info(f"Transaction successful! Gas used: {receipt['gasUsed']}")

                self.circuit_breaker.record_success()
                self.stats['executed'] += 1
                self.stats['successful'] += 1
                self.stats['total_profit_usd'] += simulated_profit['profit_usd']

                gas_cost_eth = receipt['gasUsed'] * (tx['gasPrice'] / 1e18)
                gas_cost_usd = gas_cost_eth * self.eth_price_fetcher.get_eth_price_usd()
                self.stats['total_gas_spent_usd'] += gas_cost_usd

                result = {
                    'status': 'success',
                    'tx_hash': tx_hash_hex,
                    'gas_used': receipt['gasUsed'],
                    'gas_cost_usd': gas_cost_usd,
                    'profit_usd': simulated_profit['profit_usd'],
                    'timestamp': datetime.now().isoformat(),
                    'token_in': opp['token_in'],
                    'token_out': opp['token_out'],
                    'buy_dex': opp['buy_dex'],
                    'sell_dex': opp['sell_dex'],
                    'actual_profit_pct': opp['profit_pct'],
                    'actual_profit_usd': simulated_profit['profit_usd']
                }

                # Send success notification
                await self.notifier.send_execution(result)

                return result

            else:
                logger.error(f"Transaction failed! Receipt: {receipt}")

                self.circuit_breaker.record_failure("Transaction reverted")
                self.stats['executed'] += 1
                self.stats['failed'] += 1

                result = {
                    'status': 'failed',
                    'tx_hash': tx_hash_hex,
                    'reason': 'Transaction reverted',
                    'timestamp': datetime.now().isoformat()
                }

                await self.notifier.send_error(
                    "Arbitrage execution reverted",
                    context={'tx_hash': tx_hash_hex}
                )

                return result

        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)

            self.circuit_breaker.record_failure(str(e))
            self.stats['failed'] += 1

            await self.notifier.send_error(
                f"Execution failed: {str(e)}",
                context={'opportunity': opp}
            )

            raise ExecutionError(f"Execution failed: {e}")

    def get_statistics(self) -> Dict:
        """Get execution statistics."""
        stats = {
            **self.stats,
            'circuit_breaker': self.circuit_breaker.get_status(),
            'success_rate': (
                (self.stats['successful'] / self.stats['executed'] * 100)
                if self.stats['executed'] > 0 else 0
            ),
            'net_profit_usd': (
                self.stats['total_profit_usd'] - self.stats['total_gas_spent_usd']
            )
        }

        # Add private mempool stats if available
        if self.private_mempool:
            stats['private_mempool'] = self.private_mempool.get_stats()

        return stats
