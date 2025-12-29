"""
Integration tests for Price Oracle (requires network access).

These tests connect to real RPC endpoints to verify oracle functionality.
Run with: pytest -m integration tests/integration/
"""

import pytest
from web3 import Web3
from utils.price_oracle import ChainlinkPriceOracle
from config.config import config


@pytest.mark.integration
@pytest.mark.network
class TestPriceOracleIntegration:
    """Integration tests for Chainlink Price Oracle."""

    @pytest.fixture
    def scroll_testnet_w3(self):
        """Connect to Scroll Sepolia testnet."""
        rpc_url = config.SCROLL_TESTNET_RPC or "https://sepolia-rpc.scroll.io"
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        assert w3.is_connected(), "Failed to connect to Scroll testnet"
        return w3

    @pytest.fixture
    def scroll_mainnet_w3(self):
        """Connect to Scroll mainnet."""
        rpc_url = config.SCROLL_RPC_URL or "https://rpc.scroll.io"
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        assert w3.is_connected(), "Failed to connect to Scroll mainnet"
        return w3

    def test_testnet_dex_fallback(self, scroll_testnet_w3):
        """Test that testnet falls back to DEX pricing."""
        oracle = ChainlinkPriceOracle(scroll_testnet_w3, network_mode='testnet')

        feed = oracle.get_eth_price_usd()

        assert feed is not None
        assert feed.price > 0
        assert feed.source == 'dex'  # Should use DEX on testnet
        assert 100 < feed.price < 20000  # Sanity check

    @pytest.mark.skipif(
        config.NETWORK_MODE == 'testnet',
        reason="Requires mainnet connection"
    )
    def test_mainnet_chainlink_or_dex(self, scroll_mainnet_w3):
        """Test ETH price fetch on mainnet (Chainlink or DEX fallback)."""
        oracle = ChainlinkPriceOracle(scroll_mainnet_w3, network_mode='mainnet')

        feed = oracle.get_eth_price_usd()

        assert feed is not None
        assert feed.price > 0
        assert feed.source in ['chainlink', 'dex']
        assert 100 < feed.price < 20000  # Reasonable bounds

    def test_stablecoin_pricing(self, scroll_testnet_w3):
        """Test stablecoin pricing."""
        oracle = ChainlinkPriceOracle(scroll_testnet_w3, network_mode='testnet')

        usdc_price = oracle.get_token_price_usd('USDC')
        usdt_price = oracle.get_token_price_usd('USDT')

        assert usdc_price == 1.0
        assert usdt_price == 1.0

    def test_weth_pricing_consistency(self, scroll_testnet_w3):
        """Test that WETH and ETH prices are consistent."""
        oracle = ChainlinkPriceOracle(scroll_testnet_w3, network_mode='testnet')

        eth_feed = oracle.get_eth_price_usd()
        weth_price = oracle.get_token_price_usd('WETH')

        assert eth_feed.price == weth_price

    def test_price_caching(self, scroll_testnet_w3):
        """Test that prices are properly cached."""
        oracle = ChainlinkPriceOracle(scroll_testnet_w3, network_mode='testnet')

        # First call
        feed1 = oracle.get_eth_price_usd()
        timestamp1 = feed1.timestamp

        # Second call should return cached value
        feed2 = oracle.get_eth_price_usd()
        timestamp2 = feed2.timestamp

        assert timestamp1 == timestamp2  # Same cached value
        assert feed1.price == feed2.price


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'integration'])
