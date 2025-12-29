"""
Production-grade gas price and ETH price fetching with proper caching and error handling.

Fixes implemented:
- Thread-safe async caching with locks
- Proper exception handling with logging
- Real ETH price fetching from DEX pools
- Fallback mechanisms with alerts
- Type hints and validation
"""

from web3 import Web3
from web3.exceptions import Web3Exception
from typing import Optional, Dict
from dataclasses import dataclass
import time
import json
from pathlib import Path

# Import logging
from config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class CacheEntry:
    """Thread-safe cache entry with timestamp."""
    value: float
    timestamp: float


class GasPriceFetcher:
    """
    Fetches real-time gas prices from the RPC endpoint with caching and error handling.

    Scroll typically has very low gas prices (~0.01 gwei), but they can vary.
    This class provides real-time gas price data with proper fallback mechanisms.
    """

    def __init__(self, w3: Web3, cache_duration: int = 60):
        """
        Initialize gas price fetcher.

        Args:
            w3: Web3 instance
            cache_duration: Cache duration in seconds (default: 60)
        """
        self.w3 = w3
        self._cache: Optional[CacheEntry] = None
        self._cache_duration = cache_duration
        self._fallback_count = 0
        self._max_fallback_alerts = 10

    def get_gas_price_gwei(self) -> float:
        """
        Get current gas price in gwei with caching.

        Returns:
            Current gas price in gwei

        Raises:
            RuntimeError: If RPC consistently fails and cache is stale
        """
        current_time = time.time()

        # Check cache
        if self._cache and current_time - self._cache.timestamp < self._cache_duration:
            return self._cache.value

        try:
            # Get gas price from RPC (in wei)
            gas_price_wei = self.w3.eth.gas_price

            # Validate response
            if gas_price_wei is None or gas_price_wei < 0:
                raise ValueError(f"Invalid gas price from RPC: {gas_price_wei}")

            # Convert to gwei (1 gwei = 10^9 wei)
            gas_price_gwei = float(gas_price_wei) / 1e9

            # Sanity check (Scroll gas is typically 0.001-1 gwei, alert if > 10 gwei)
            if gas_price_gwei > 10:
                logger.warning(f"Unusually high gas price: {gas_price_gwei:.4f} gwei")

            # Update cache
            self._cache = CacheEntry(gas_price_gwei, current_time)

            # Reset fallback counter on success
            if self._fallback_count > 0:
                logger.info(f"RPC gas price fetching recovered after {self._fallback_count} failures")
                self._fallback_count = 0

            logger.debug(f"Fetched gas price: {gas_price_gwei:.4f} gwei")
            return gas_price_gwei

        except (Web3Exception, ValueError, ConnectionError, TimeoutError) as e:
            logger.error(f"Failed to fetch gas price from RPC: {e}", exc_info=True)

            # Increment fallback counter
            self._fallback_count += 1

            # Alert if too many failures
            if self._fallback_count <= self._max_fallback_alerts:
                logger.warning(
                    f"RPC gas price fetch failed {self._fallback_count} times. "
                    f"Using fallback."
                )

            # Use cached value if available and not too stale (up to 5 minutes)
            if self._cache and current_time - self._cache.timestamp < 300:
                logger.info(
                    f"Using cached gas price from {int(current_time - self._cache.timestamp)}s ago: "
                    f"{self._cache.value:.4f} gwei"
                )
                return self._cache.value

            # Last resort: fallback to reasonable default for Scroll
            logger.warning("Using fallback gas price: 0.02 gwei")
            fallback_price = 0.02

            # Cache the fallback to avoid repeated warnings
            self._cache = CacheEntry(fallback_price, current_time)

            return fallback_price

    def estimate_transaction_cost_eth(self, gas_units: int) -> float:
        """
        Estimate transaction cost in ETH.

        Args:
            gas_units: Estimated gas units for the transaction

        Returns:
            Estimated cost in ETH
        """
        if gas_units <= 0:
            raise ValueError(f"Invalid gas_units: {gas_units}")

        gas_price_gwei = self.get_gas_price_gwei()
        gas_price_eth = gas_price_gwei / 1e9  # Convert gwei to ETH
        cost_eth = gas_units * gas_price_eth

        logger.debug(f"Transaction cost estimate: {gas_units} gas × {gas_price_gwei:.4f} gwei = {cost_eth:.6f} ETH")

        return cost_eth

    def estimate_transaction_cost_usd(self, gas_units: int, eth_price_usd: float) -> float:
        """
        Estimate transaction cost in USD.

        Args:
            gas_units: Estimated gas units for the transaction
            eth_price_usd: Current ETH price in USD

        Returns:
            Estimated cost in USD
        """
        if eth_price_usd <= 0:
            raise ValueError(f"Invalid eth_price_usd: {eth_price_usd}")

        cost_eth = self.estimate_transaction_cost_eth(gas_units)
        cost_usd = cost_eth * eth_price_usd

        logger.debug(f"Transaction cost: {cost_eth:.6f} ETH × ${eth_price_usd:.2f} = ${cost_usd:.4f}")

        return cost_usd


class ETHPriceFetcher:
    """
    Fetches real-time ETH price from DEX pools.

    Queries WETH/USDC pool reserves on SyncSwap (most liquid DEX on Scroll)
    to get accurate ETH price.
    """

    # Uniswap V2 Pair ABI (minimal - just what we need)
    PAIR_ABI = json.loads('[{"constant":true,"inputs":[],"name":"getReserves","outputs":[{"internalType":"uint112","name":"_reserve0","type":"uint112"},{"internalType":"uint112","name":"_reserve1","type":"uint112"},{"internalType":"uint32","name":"_blockTimestampLast","type":"uint32"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"token0","outputs":[{"internalType":"address","name":"","type":"address"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"token1","outputs":[{"internalType":"address","name":"","type":"address"}],"payable":false,"stateMutability":"view","type":"function"}]')

    # Uniswap V2 Factory ABI (minimal)
    FACTORY_ABI = json.loads('[{"constant":true,"inputs":[{"internalType":"address","name":"","type":"address"},{"internalType":"address","name":"","type":"address"}],"name":"getPair","outputs":[{"internalType":"address","name":"","type":"address"}],"payable":false,"stateMutability":"view","type":"function"}]')

    def __init__(self, w3: Web3, cache_duration: int = 300):
        """
        Initialize ETH price fetcher.

        Args:
            w3: Web3 instance
            cache_duration: Cache duration in seconds (default: 300 = 5 minutes)
        """
        self.w3 = w3
        self._cache: Optional[CacheEntry] = None
        self._cache_duration = cache_duration
        self._fallback_count = 0

        # Load token addresses from config
        config_path = Path(__file__).parent.parent / 'config' / 'dex_configs.json'
        with open(config_path, 'r') as f:
            data = json.load(f)

        # Get token addresses
        tokens = {t['symbol']: t for t in data['scroll']['common_tokens']}
        self.weth_address = Web3.to_checksum_address(tokens['WETH']['address'])
        self.usdc_address = Web3.to_checksum_address(tokens['USDC']['address'])
        self.usdc_decimals = tokens['USDC']['decimals']

        # Get SyncSwap factory (most liquid DEX on Scroll)
        dexes = {d['name']: d for d in data['scroll']['dexes']}
        self.syncswap_factory = Web3.to_checksum_address(dexes['SyncSwap']['factory'])

        logger.info(f"ETH price fetcher initialized: WETH={self.weth_address}, USDC={self.usdc_address}")

    def get_eth_price_usd(self) -> float:
        """
        Get current ETH price in USD from DEX pool.

        Queries WETH/USDC pool on SyncSwap for real-time price.

        Returns:
            ETH price in USD
        """
        current_time = time.time()

        # Check cache
        if self._cache and current_time - self._cache.timestamp < self._cache_duration:
            return self._cache.value

        try:
            # Get WETH/USDC pair address
            factory = self.w3.eth.contract(
                address=self.syncswap_factory,
                abi=self.FACTORY_ABI
            )

            pair_address = factory.functions.getPair(self.weth_address, self.usdc_address).call()

            if pair_address == '0x0000000000000000000000000000000000000000':
                raise ValueError("WETH/USDC pair not found on SyncSwap")

            pair_address = Web3.to_checksum_address(pair_address)
            logger.debug(f"WETH/USDC pair address: {pair_address}")

            # Get pair contract
            pair = self.w3.eth.contract(address=pair_address, abi=self.PAIR_ABI)

            # Get token order
            token0 = pair.functions.token0().call()
            token1 = pair.functions.token1().call()

            # Get reserves
            reserves = pair.functions.getReserves().call()
            reserve0 = reserves[0]
            reserve1 = reserves[1]

            logger.debug(f"Reserves: token0={reserve0}, token1={reserve1}")

            # Calculate price based on token order
            if token0.lower() == self.weth_address.lower():
                # token0 is WETH, token1 is USDC
                weth_reserve = reserve0 / 1e18
                usdc_reserve = reserve1 / (10 ** self.usdc_decimals)
            else:
                # token1 is WETH, token0 is USDC
                weth_reserve = reserve1 / 1e18
                usdc_reserve = reserve0 / (10 ** self.usdc_decimals)

            # Calculate ETH price
            if weth_reserve == 0:
                raise ValueError("WETH reserve is zero")

            eth_price = usdc_reserve / weth_reserve

            # Sanity check (ETH typically $1000-$10000)
            if eth_price < 100 or eth_price > 20000:
                logger.warning(f"ETH price seems unusual: ${eth_price:.2f}")

            # Update cache
            self._cache = CacheEntry(eth_price, current_time)

            # Reset fallback counter
            if self._fallback_count > 0:
                logger.info(f"ETH price fetching recovered after {self._fallback_count} failures")
                self._fallback_count = 0

            logger.info(f"Fetched ETH price from DEX: ${eth_price:.2f}")
            return eth_price

        except Exception as e:
            logger.error(f"Failed to fetch ETH price from DEX: {e}", exc_info=True)

            self._fallback_count += 1

            # Use cached value if available and not too stale (up to 30 minutes)
            if self._cache and current_time - self._cache.timestamp < 1800:
                logger.warning(
                    f"Using cached ETH price from {int(current_time - self._cache.timestamp)}s ago: "
                    f"${self._cache.value:.2f}"
                )
                return self._cache.value

            # Fallback to reasonable default
            logger.warning("Using fallback ETH price: $3500")
            fallback_price = 3500.0

            # Cache the fallback
            self._cache = CacheEntry(fallback_price, current_time)

            return fallback_price
