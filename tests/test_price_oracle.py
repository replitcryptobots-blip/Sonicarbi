"""
Unit tests for Chainlink Price Oracle integration.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from web3 import Web3
from utils.price_oracle import ChainlinkPriceOracle, MultiTokenPriceOracle, PriceFeed
import time


@pytest.fixture
def mock_w3():
    """Create a mock Web3 instance."""
    w3 = Mock(spec=Web3)
    w3.eth = Mock()
    w3.eth.contract = Mock()
    return w3


@pytest.fixture
def chainlink_oracle(mock_w3):
    """Create a ChainlinkPriceOracle instance for testing."""
    with patch('utils.price_oracle.ETHPriceFetcher'):
        oracle = ChainlinkPriceOracle(mock_w3, network_mode='testnet')
    return oracle


class TestChainlinkPriceOracle:
    """Test ChainlinkPriceOracle functionality."""

    def test_initialization(self, chainlink_oracle):
        """Test oracle initialization."""
        assert chainlink_oracle is not None
        assert chainlink_oracle.network_mode == 'testnet'
        assert isinstance(chainlink_oracle._cache, dict)

    def test_get_eth_price_usd_testnet_fallback(self, chainlink_oracle):
        """Test ETH price fetching on testnet falls back to DEX."""
        # Mock DEX fetcher
        chainlink_oracle.dex_eth_fetcher.get_eth_price_usd = Mock(return_value=3500.0)

        feed = chainlink_oracle.get_eth_price_usd()

        assert isinstance(feed, PriceFeed)
        assert feed.price == 3500.0
        assert feed.source == 'dex'
        chainlink_oracle.dex_eth_fetcher.get_eth_price_usd.assert_called_once()

    def test_get_eth_price_usd_caching(self, chainlink_oracle):
        """Test that ETH price is cached properly."""
        # Mock DEX fetcher
        chainlink_oracle.dex_eth_fetcher.get_eth_price_usd = Mock(return_value=3500.0)

        # First call
        feed1 = chainlink_oracle.get_eth_price_usd()
        assert feed1.price == 3500.0

        # Second call should use cache
        feed2 = chainlink_oracle.get_eth_price_usd()
        assert feed2.price == 3500.0

        # Should only call DEX fetcher once due to caching
        assert chainlink_oracle.dex_eth_fetcher.get_eth_price_usd.call_count == 1

    def test_fetch_chainlink_price_mainnet(self):
        """Test fetching price from Chainlink on mainnet."""
        mock_w3 = Mock(spec=Web3)
        mock_contract = Mock()

        # Mock Chainlink response
        mock_contract.functions.decimals.return_value.call.return_value = 8
        mock_contract.functions.latestRoundData.return_value.call.return_value = (
            12345,  # roundId
            350000000000,  # answer (3500.00 with 8 decimals)
            int(time.time()),  # startedAt
            int(time.time()),  # updatedAt
            12345  # answeredInRound
        )

        mock_w3.eth.contract.return_value = mock_contract
        mock_w3.to_checksum_address = Web3.to_checksum_address

        with patch('utils.price_oracle.ETHPriceFetcher'):
            oracle = ChainlinkPriceOracle(mock_w3, network_mode='mainnet')

        price = oracle._fetch_chainlink_price('ETH')

        assert price == 3500.0

    def test_get_token_price_usd_stablecoins(self, chainlink_oracle):
        """Test that stablecoins return 1.0."""
        assert chainlink_oracle.get_token_price_usd('USDC') == 1.0
        assert chainlink_oracle.get_token_price_usd('USDT') == 1.0
        assert chainlink_oracle.get_token_price_usd('DAI') == 1.0

    def test_get_token_price_usd_weth(self, chainlink_oracle):
        """Test WETH price fetching."""
        chainlink_oracle.dex_eth_fetcher.get_eth_price_usd = Mock(return_value=3500.0)

        price = chainlink_oracle.get_token_price_usd('WETH')

        assert price == 3500.0

    def test_get_token_price_usd_unknown_token(self, chainlink_oracle):
        """Test that unknown tokens return None."""
        price = chainlink_oracle.get_token_price_usd('UNKNOWN')

        assert price is None

    def test_calculate_profit_usd(self, chainlink_oracle):
        """Test USD profit calculation."""
        chainlink_oracle.dex_eth_fetcher.get_eth_price_usd = Mock(return_value=3500.0)

        # Test with WETH
        profit_usd = chainlink_oracle.calculate_profit_usd(1.5, 'WETH')
        assert profit_usd == 5250.0  # 1.5 * 3500

        # Test with USDC
        profit_usd = chainlink_oracle.calculate_profit_usd(100.0, 'USDC')
        assert profit_usd == 100.0  # 100 * 1.0

        # Test with unknown token
        profit_usd = chainlink_oracle.calculate_profit_usd(100.0, 'UNKNOWN')
        assert profit_usd is None

    def test_cache_expiration(self, chainlink_oracle):
        """Test that cache expires after cache duration."""
        chainlink_oracle.dex_eth_fetcher.get_eth_price_usd = Mock(return_value=3500.0)

        # Set very short cache duration for testing
        original_duration = ChainlinkPriceOracle.CACHE_DURATION
        ChainlinkPriceOracle.CACHE_DURATION = 1

        # First call
        feed1 = chainlink_oracle.get_eth_price_usd()
        assert chainlink_oracle.dex_eth_fetcher.get_eth_price_usd.call_count == 1

        # Wait for cache to expire
        time.sleep(1.1)

        # Second call should fetch fresh data
        chainlink_oracle.dex_eth_fetcher.get_eth_price_usd = Mock(return_value=3600.0)
        feed2 = chainlink_oracle.get_eth_price_usd()
        assert feed2.price == 3600.0

        # Restore original cache duration
        ChainlinkPriceOracle.CACHE_DURATION = original_duration


class TestMultiTokenPriceOracle:
    """Test MultiTokenPriceOracle functionality."""

    def test_initialization(self, mock_w3):
        """Test multi-token oracle initialization."""
        mock_chainlink = Mock(spec=ChainlinkPriceOracle)

        oracle = MultiTokenPriceOracle(mock_w3, mock_chainlink)

        assert oracle is not None
        assert oracle.chainlink_oracle == mock_chainlink
        assert isinstance(oracle._cache, dict)
        assert len(oracle.tokens) > 0

    def test_get_token_price_usd_from_chainlink(self, mock_w3):
        """Test getting price from Chainlink oracle."""
        mock_chainlink = Mock(spec=ChainlinkPriceOracle)
        mock_chainlink.get_token_price_usd.return_value = 3500.0

        oracle = MultiTokenPriceOracle(mock_w3, mock_chainlink)
        price = oracle.get_token_price_usd('WETH')

        assert price == 3500.0
        mock_chainlink.get_token_price_usd.assert_called_once_with('WETH')

    def test_get_token_price_usd_caching(self, mock_w3):
        """Test that prices are cached."""
        mock_chainlink = Mock(spec=ChainlinkPriceOracle)
        mock_chainlink.get_token_price_usd.return_value = 3500.0

        oracle = MultiTokenPriceOracle(mock_w3, mock_chainlink)

        # First call
        price1 = oracle.get_token_price_usd('WETH', use_cache=True)
        assert price1 == 3500.0

        # Second call should use cache
        price2 = oracle.get_token_price_usd('WETH', use_cache=True)
        assert price2 == 3500.0

        # Should only call Chainlink once
        assert mock_chainlink.get_token_price_usd.call_count == 1

    def test_get_token_price_usd_no_cache(self, mock_w3):
        """Test getting price without cache."""
        mock_chainlink = Mock(spec=ChainlinkPriceOracle)
        mock_chainlink.get_token_price_usd.return_value = 3500.0

        oracle = MultiTokenPriceOracle(mock_w3, mock_chainlink)

        # First call
        price1 = oracle.get_token_price_usd('WETH', use_cache=False)
        assert price1 == 3500.0

        # Second call should not use cache
        mock_chainlink.get_token_price_usd.return_value = 3600.0
        price2 = oracle.get_token_price_usd('WETH', use_cache=False)
        assert price2 == 3600.0

        # Should call Chainlink twice
        assert mock_chainlink.get_token_price_usd.call_count == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
