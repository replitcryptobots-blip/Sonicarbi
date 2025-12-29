"""
Chainlink Price Oracle integration for accurate USD pricing.

This module provides price feeds for various tokens using Chainlink oracles
on Scroll network, with fallback to DEX-based pricing.
"""

from web3 import Web3
from web3.exceptions import Web3Exception
from typing import Optional, Dict
from dataclasses import dataclass
import time
import json
from pathlib import Path
from decimal import Decimal

from config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PriceFeed:
    """Price feed data structure."""
    price: float
    decimals: int
    timestamp: float
    source: str  # 'chainlink' or 'dex'


class ChainlinkPriceOracle:
    """
    Chainlink Price Oracle for getting accurate USD prices.

    Chainlink Price Feed addresses on Scroll Mainnet:
    - ETH/USD: 0x6bF14CB0A831078629D993FDeBcB182b21A8774C
    - More feeds can be added as they become available

    For testnet, we fall back to DEX-based pricing.
    """

    # Chainlink Aggregator ABI (minimal - just what we need)
    AGGREGATOR_ABI = json.loads('''[
        {
            "inputs": [],
            "name": "decimals",
            "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "latestRoundData",
            "outputs": [
                {"internalType": "uint80", "name": "roundId", "type": "uint80"},
                {"internalType": "int256", "name": "answer", "type": "int256"},
                {"internalType": "uint256", "name": "startedAt", "type": "uint256"},
                {"internalType": "uint256", "name": "updatedAt", "type": "uint256"},
                {"internalType": "uint80", "name": "answeredInRound", "type": "uint80"}
            ],
            "stateMutability": "view",
            "type": "function"
        }
    ]''')

    # Chainlink price feed addresses on Scroll Mainnet
    SCROLL_MAINNET_FEEDS = {
        'ETH': '0x6bF14CB0A831078629D993FDeBcB182b21A8774C',  # ETH/USD
        # Add more as they become available on Scroll
    }

    # Cache duration for price feeds (5 minutes)
    CACHE_DURATION = 300

    def __init__(self, w3: Web3, network_mode: str = 'mainnet'):
        """
        Initialize Chainlink Price Oracle.

        Args:
            w3: Web3 instance
            network_mode: 'mainnet' or 'testnet'
        """
        self.w3 = w3
        self.network_mode = network_mode
        self._cache: Dict[str, PriceFeed] = {}

        # Load DEX-based fallback pricing
        from utils.gas_price import ETHPriceFetcher
        self.dex_eth_fetcher = ETHPriceFetcher(w3)

        logger.info(f"Chainlink Price Oracle initialized (network: {network_mode})")

    def get_eth_price_usd(self) -> PriceFeed:
        """
        Get ETH price in USD from Chainlink oracle with DEX fallback.

        Returns:
            PriceFeed with ETH price in USD
        """
        # Check cache
        if 'ETH' in self._cache:
            cached = self._cache['ETH']
            if time.time() - cached.timestamp < self.CACHE_DURATION:
                logger.debug(f"Using cached ETH price: ${cached.price:.2f} (source: {cached.source})")
                return cached

        # Try Chainlink first (mainnet only)
        if self.network_mode == 'mainnet':
            try:
                price = self._fetch_chainlink_price('ETH')
                if price:
                    feed = PriceFeed(
                        price=price,
                        decimals=8,  # Chainlink USD feeds typically use 8 decimals
                        timestamp=time.time(),
                        source='chainlink'
                    )
                    self._cache['ETH'] = feed
                    logger.info(f"ETH price from Chainlink: ${price:.2f}")
                    return feed
            except Exception as e:
                logger.warning(f"Chainlink ETH price fetch failed: {e}, falling back to DEX")

        # Fallback to DEX-based pricing
        try:
            price = self.dex_eth_fetcher.get_eth_price_usd()
            feed = PriceFeed(
                price=price,
                decimals=18,
                timestamp=time.time(),
                source='dex'
            )
            self._cache['ETH'] = feed
            logger.info(f"ETH price from DEX: ${price:.2f}")
            return feed
        except Exception as e:
            logger.error(f"Failed to fetch ETH price from DEX: {e}")
            # Return cached value if available (even if stale)
            if 'ETH' in self._cache:
                logger.warning("Using stale cached ETH price")
                return self._cache['ETH']
            raise RuntimeError("Cannot fetch ETH price from any source")

    def _fetch_chainlink_price(self, symbol: str) -> Optional[float]:
        """
        Fetch price from Chainlink oracle.

        Args:
            symbol: Token symbol (e.g., 'ETH')

        Returns:
            Price in USD, or None if not available
        """
        if symbol not in self.SCROLL_MAINNET_FEEDS:
            logger.debug(f"No Chainlink feed available for {symbol}")
            return None

        feed_address = self.SCROLL_MAINNET_FEEDS[symbol]

        try:
            # Create contract instance
            aggregator = self.w3.eth.contract(
                address=Web3.to_checksum_address(feed_address),
                abi=self.AGGREGATOR_ABI
            )

            # Get decimals
            decimals = aggregator.functions.decimals().call()

            # Get latest price data
            round_data = aggregator.functions.latestRoundData().call()

            # Extract price (answer is in the format with decimals)
            # round_data = (roundId, answer, startedAt, updatedAt, answeredInRound)
            answer = round_data[1]
            updated_at = round_data[3]

            # Validate price data
            if answer <= 0:
                raise ValueError(f"Invalid price from Chainlink: {answer}")

            # Check if data is recent (within last hour)
            age = time.time() - updated_at
            if age > 3600:
                logger.warning(f"Chainlink price data is {age:.0f}s old")

            # Convert to float
            price = float(answer) / (10 ** decimals)

            logger.debug(f"Chainlink {symbol}/USD: ${price:.2f} (updated {age:.0f}s ago)")

            return price

        except Exception as e:
            logger.error(f"Error fetching Chainlink price for {symbol}: {e}", exc_info=True)
            return None

    def get_token_price_usd(self, token_symbol: str) -> Optional[float]:
        """
        Get token price in USD.

        Currently supports:
        - ETH/WETH: Direct Chainlink feed
        - USDC/USDT: Stablecoin (1.0)
        - Other tokens: Would need additional price feeds or DEX routing

        Args:
            token_symbol: Token symbol (e.g., 'ETH', 'WETH', 'USDC')

        Returns:
            Price in USD, or None if not available
        """
        # Normalize symbol
        symbol = token_symbol.upper()

        # Stablecoins
        if symbol in ['USDC', 'USDT', 'DAI']:
            return 1.0

        # ETH/WETH
        if symbol in ['ETH', 'WETH']:
            feed = self.get_eth_price_usd()
            return feed.price

        # For other tokens, we'd need:
        # 1. Direct Chainlink feed (if available)
        # 2. Calculate via DEX pool (token/USDC or token/ETH)
        logger.warning(f"No price feed available for {symbol}")
        return None

    def calculate_profit_usd(
        self,
        profit_amount: float,
        token_symbol: str
    ) -> Optional[float]:
        """
        Calculate profit in USD.

        Args:
            profit_amount: Profit amount in token units
            token_symbol: Token symbol

        Returns:
            Profit in USD, or None if price not available
        """
        price = self.get_token_price_usd(token_symbol)
        if price is None:
            return None

        profit_usd = profit_amount * price
        logger.debug(f"Profit: {profit_amount} {token_symbol} = ${profit_usd:.2f}")

        return profit_usd


class MultiTokenPriceOracle:
    """
    Extended price oracle supporting multiple tokens via DEX routing.

    For tokens without direct Chainlink feeds, calculates price via:
    1. Token/USDC pool (if exists)
    2. Token/ETH pool -> ETH/USD
    """

    def __init__(self, w3: Web3, chainlink_oracle: ChainlinkPriceOracle):
        """
        Initialize multi-token price oracle.

        Args:
            w3: Web3 instance
            chainlink_oracle: ChainlinkPriceOracle instance
        """
        self.w3 = w3
        self.chainlink_oracle = chainlink_oracle
        self._cache: Dict[str, PriceFeed] = {}

        # Load DEX configs for pool lookups
        config_path = Path(__file__).parent.parent / 'config' / 'dex_configs.json'
        with open(config_path, 'r') as f:
            data = json.load(f)

        self.tokens = {t['symbol']: t for t in data['scroll']['common_tokens']}
        self.dexes = data['scroll']['dexes']

        logger.info("Multi-token price oracle initialized")

    def get_token_price_usd(
        self,
        token_symbol: str,
        use_cache: bool = True
    ) -> Optional[float]:
        """
        Get token price in USD using multiple methods.

        Priority:
        1. Chainlink oracle (most accurate)
        2. DEX pool with USDC
        3. DEX pool with ETH -> ETH/USD from Chainlink

        Args:
            token_symbol: Token symbol
            use_cache: Whether to use cached prices

        Returns:
            Price in USD, or None if not available
        """
        # Check cache
        if use_cache and token_symbol in self._cache:
            cached = self._cache[token_symbol]
            if time.time() - cached.timestamp < ChainlinkPriceOracle.CACHE_DURATION:
                logger.debug(f"Using cached {token_symbol} price: ${cached.price:.2f}")
                return cached.price

        # Try Chainlink first
        price = self.chainlink_oracle.get_token_price_usd(token_symbol)
        if price is not None:
            self._cache[token_symbol] = PriceFeed(
                price=price,
                decimals=8,
                timestamp=time.time(),
                source='chainlink'
            )
            return price

        # Try DEX-based pricing
        # TODO: Implement DEX pool price calculation
        # This would query token/USDC or token/ETH pools

        logger.warning(f"Could not determine USD price for {token_symbol}")
        return None
