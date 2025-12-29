"""
Utility functions for the Sonicarbi arbitrage bot.
"""

from web3 import Web3
from typing import Optional
import time

class GasPriceFetcher:
    """
    Fetches real-time gas prices from the RPC endpoint.

    Scroll typically has very low gas prices (~0.01 gwei), but they can vary.
    This class provides real-time gas price data instead of hardcoded estimates.
    """

    def __init__(self, w3: Web3):
        self.w3 = w3
        self._cache = {}
        self._cache_duration = 60  # Cache for 60 seconds

    def get_gas_price_gwei(self) -> float:
        """
        Get current gas price in gwei.

        Returns:
            Current gas price in gwei, with caching to avoid excessive RPC calls
        """
        current_time = time.time()

        # Check cache
        if 'price' in self._cache and 'timestamp' in self._cache:
            if current_time - self._cache['timestamp'] < self._cache_duration:
                return self._cache['price']

        try:
            # Get gas price from RPC (in wei)
            gas_price_wei = self.w3.eth.gas_price

            # Convert to gwei (1 gwei = 10^9 wei)
            gas_price_gwei = float(gas_price_wei) / 1e9

            # Update cache
            self._cache = {
                'price': gas_price_gwei,
                'timestamp': current_time
            }

            return gas_price_gwei

        except Exception as e:
            # Fallback to a reasonable estimate if RPC call fails
            # Scroll average is ~0.01-0.02 gwei
            return 0.02

    def estimate_transaction_cost_eth(self, gas_units: int) -> float:
        """
        Estimate transaction cost in ETH.

        Args:
            gas_units: Estimated gas units for the transaction

        Returns:
            Estimated cost in ETH
        """
        gas_price_gwei = self.get_gas_price_gwei()
        gas_price_eth = gas_price_gwei / 1e9  # Convert gwei to ETH
        cost_eth = gas_units * gas_price_eth
        return cost_eth

    def estimate_transaction_cost_usd(self, gas_units: int, eth_price_usd: float = 3500) -> float:
        """
        Estimate transaction cost in USD.

        Args:
            gas_units: Estimated gas units for the transaction
            eth_price_usd: Current ETH price in USD (default: $3500)

        Returns:
            Estimated cost in USD
        """
        cost_eth = self.estimate_transaction_cost_eth(gas_units)
        return cost_eth * eth_price_usd


class ETHPriceFetcher:
    """
    Fetches real-time ETH price for better USD calculations.

    For now, uses a simple fallback. Could be extended to use price oracles
    or DEX WETH/USDC prices.
    """

    def __init__(self, w3: Web3):
        self.w3 = w3
        self._cache = {}
        self._cache_duration = 300  # Cache for 5 minutes

    def get_eth_price_usd(self) -> float:
        """
        Get current ETH price in USD.

        For now, returns a reasonable default. Can be extended to:
        - Query WETH/USDC pool on DEXes
        - Use Chainlink price feeds
        - Call external price APIs

        Returns:
            ETH price in USD
        """
        current_time = time.time()

        # Check cache
        if 'price' in self._cache and 'timestamp' in self._cache:
            if current_time - self._cache['timestamp'] < self._cache_duration:
                return self._cache['price']

        # TODO: Implement actual price fetching from DEX or oracle
        # For now, use a reasonable default
        default_price = 3500.0

        # Update cache
        self._cache = {
            'price': default_price,
            'timestamp': current_time
        }

        return default_price
