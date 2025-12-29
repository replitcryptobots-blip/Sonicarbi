"""
Unit tests for Slippage Calculator.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from web3 import Web3
from utils.slippage_calculator import SlippageCalculator


@pytest.fixture
def mock_w3():
    """Create a mock Web3 instance."""
    w3 = Mock(spec=Web3)
    w3.eth = Mock()
    w3.eth.contract = Mock()
    w3.to_checksum_address = Web3.to_checksum_address
    return w3


@pytest.fixture
def slippage_calc(mock_w3):
    """Create a SlippageCalculator instance for testing."""
    calc = SlippageCalculator(mock_w3)
    return calc


@pytest.fixture
def mock_token_in():
    """Mock input token."""
    return {
        'symbol': 'WETH',
        'address': '0x5300000000000000000000000000000000000004',
        'decimals': 18
    }


@pytest.fixture
def mock_token_out():
    """Mock output token."""
    return {
        'symbol': 'USDC',
        'address': '0x06eFdBFf2a14a7c8E15944D1F4A48F9F95F663A4',
        'decimals': 6
    }


class TestSlippageCalculator:
    """Test SlippageCalculator functionality."""

    def test_initialization(self, slippage_calc):
        """Test calculator initialization."""
        assert slippage_calc is not None
        assert len(slippage_calc.dexes) > 0
        assert len(slippage_calc.tokens) > 0

    def test_calculate_v2_slippage_success(self, slippage_calc, mock_token_in, mock_token_out):
        """Test successful slippage calculation for V2 DEX."""
        # Mock factory contract
        mock_factory = Mock()
        mock_factory.functions.getPair.return_value.call.return_value = '0x1234567890123456789012345678901234567890'

        # Mock pair contract
        mock_pair = Mock()
        mock_pair.functions.token0.return_value.call.return_value = mock_token_in['address']
        mock_pair.functions.token1.return_value.call.return_value = mock_token_out['address']

        # Mock reserves: 100 WETH, 350,000 USDC (price ~3500 USDC per WETH)
        reserve_weth = 100 * 10**18  # 100 WETH
        reserve_usdc = 350000 * 10**6  # 350,000 USDC
        mock_pair.functions.getReserves.return_value.call.return_value = (
            reserve_weth,
            reserve_usdc,
            1234567890  # timestamp
        )

        # Setup contract mocking
        def contract_side_effect(address, abi):
            if 'getPair' in str(abi):
                return mock_factory
            else:
                return mock_pair

        slippage_calc.w3.eth.contract.side_effect = contract_side_effect

        # Calculate slippage for 1 WETH trade
        result = slippage_calc.calculate_v2_slippage(
            'SyncSwap',
            mock_token_in,
            mock_token_out,
            1.0
        )

        assert result is not None
        assert result['dex'] == 'SyncSwap'
        assert result['pair'] == 'WETH/USDC'
        assert result['reserve_in'] == 100.0
        assert result['reserve_out'] == 350000.0
        assert result['amount_in'] == 1.0
        assert 'amount_out' in result
        assert 'price_impact_pct' in result
        assert 'slippage_pct' in result
        assert result['price_impact_pct'] < 2.0  # 1 WETH out of 100 = 1% impact

    def test_calculate_v2_slippage_no_pair(self, slippage_calc, mock_token_in, mock_token_out):
        """Test slippage calculation when pair doesn't exist."""
        # Mock factory returning zero address
        mock_factory = Mock()
        mock_factory.functions.getPair.return_value.call.return_value = '0x0000000000000000000000000000000000000000'

        slippage_calc.w3.eth.contract.return_value = mock_factory

        result = slippage_calc.calculate_v2_slippage(
            'SyncSwap',
            mock_token_in,
            mock_token_out,
            1.0
        )

        assert result is None

    def test_calculate_v2_slippage_high_impact(self, slippage_calc, mock_token_in, mock_token_out):
        """Test slippage calculation for high impact trade."""
        # Mock factory contract
        mock_factory = Mock()
        mock_factory.functions.getPair.return_value.call.return_value = '0x1234567890123456789012345678901234567890'

        # Mock pair contract with low liquidity
        mock_pair = Mock()
        mock_pair.functions.token0.return_value.call.return_value = mock_token_in['address']
        mock_pair.functions.token1.return_value.call.return_value = mock_token_out['address']

        # Low reserves: 10 WETH, 35,000 USDC
        reserve_weth = 10 * 10**18
        reserve_usdc = 35000 * 10**6
        mock_pair.functions.getReserves.return_value.call.return_value = (
            reserve_weth,
            reserve_usdc,
            1234567890
        )

        def contract_side_effect(address, abi):
            if 'getPair' in str(abi):
                return mock_factory
            else:
                return mock_pair

        slippage_calc.w3.eth.contract.side_effect = contract_side_effect

        # Calculate slippage for 1 WETH trade (10% of pool)
        result = slippage_calc.calculate_v2_slippage(
            'SyncSwap',
            mock_token_in,
            mock_token_out,
            1.0
        )

        assert result is not None
        assert result['price_impact_pct'] == 10.0  # 1 out of 10
        assert result['is_high_impact'] is True
        assert result['is_very_high_impact'] is True

    def test_calculate_optimal_trade_size(self, slippage_calc, mock_token_in, mock_token_out):
        """Test calculation of optimal trade size."""
        # Mock slippage calculation
        with patch.object(slippage_calc, 'calculate_v2_slippage') as mock_calc:
            mock_calc.return_value = {
                'reserve_in': 100.0,
                'reserve_out': 350000.0
            }

            optimal_amount = slippage_calc.calculate_optimal_trade_size(
                'SyncSwap',
                mock_token_in,
                mock_token_out,
                max_price_impact_pct=1.0
            )

            assert optimal_amount is not None
            assert optimal_amount == 1.0  # 1% of 100 WETH

    def test_calculate_optimal_trade_size_no_pool(self, slippage_calc, mock_token_in, mock_token_out):
        """Test optimal trade size when pool doesn't exist."""
        with patch.object(slippage_calc, 'calculate_v2_slippage') as mock_calc:
            mock_calc.return_value = None

            optimal_amount = slippage_calc.calculate_optimal_trade_size(
                'SyncSwap',
                mock_token_in,
                mock_token_out,
                max_price_impact_pct=1.0
            )

            assert optimal_amount is None

    def test_validate_arbitrage_slippage_valid(self, slippage_calc, mock_token_in, mock_token_out):
        """Test arbitrage slippage validation for valid trade."""
        # Mock slippage calculations for both legs
        buy_slippage = {
            'slippage_pct': 0.5,
            'amount_out': 3500.0,
            'price_impact_pct': 0.5
        }

        sell_slippage = {
            'slippage_pct': 0.5,
            'amount_out': 1.0,
            'price_impact_pct': 0.5
        }

        with patch.object(slippage_calc, 'calculate_v2_slippage') as mock_calc:
            mock_calc.side_effect = [buy_slippage, sell_slippage]

            is_valid, results = slippage_calc.validate_arbitrage_slippage(
                'SyncSwap',
                'Zebra',
                mock_token_in,
                mock_token_out,
                1.0,
                max_slippage_pct=2.0
            )

            assert is_valid is True
            assert results is not None
            assert results['total_slippage_pct'] == 1.0  # 0.5 + 0.5
            assert results['buy'] == buy_slippage
            assert results['sell'] == sell_slippage

    def test_validate_arbitrage_slippage_invalid(self, slippage_calc, mock_token_in, mock_token_out):
        """Test arbitrage slippage validation for invalid trade."""
        # Mock high slippage
        buy_slippage = {
            'slippage_pct': 2.0,
            'amount_out': 3500.0,
            'price_impact_pct': 2.0
        }

        sell_slippage = {
            'slippage_pct': 2.0,
            'amount_out': 1.0,
            'price_impact_pct': 2.0
        }

        with patch.object(slippage_calc, 'calculate_v2_slippage') as mock_calc:
            mock_calc.side_effect = [buy_slippage, sell_slippage]

            is_valid, results = slippage_calc.validate_arbitrage_slippage(
                'SyncSwap',
                'Zebra',
                mock_token_in,
                mock_token_out,
                1.0,
                max_slippage_pct=2.0
            )

            assert is_valid is False
            assert results is not None
            assert results['total_slippage_pct'] == 4.0  # 2.0 + 2.0

    def test_get_pool_liquidity_usd(self, slippage_calc, mock_token_in, mock_token_out):
        """Test pool liquidity calculation in USD."""
        slippage_info = {
            'reserve_in': 100.0,   # 100 WETH
            'reserve_out': 350000.0  # 350,000 USDC
        }

        token_prices = {
            'WETH': 3500.0,
            'USDC': 1.0
        }

        with patch.object(slippage_calc, 'calculate_v2_slippage') as mock_calc:
            mock_calc.return_value = slippage_info

            liquidity_usd = slippage_calc.get_pool_liquidity_usd(
                'SyncSwap',
                mock_token_in,
                mock_token_out,
                token_prices
            )

            # 100 WETH * $3500 + 350,000 USDC * $1 = $700,000
            assert liquidity_usd == 700000.0

    def test_get_pool_liquidity_usd_no_pool(self, slippage_calc, mock_token_in, mock_token_out):
        """Test pool liquidity when pool doesn't exist."""
        with patch.object(slippage_calc, 'calculate_v2_slippage') as mock_calc:
            mock_calc.return_value = None

            liquidity_usd = slippage_calc.get_pool_liquidity_usd(
                'SyncSwap',
                mock_token_in,
                mock_token_out,
                {'WETH': 3500.0, 'USDC': 1.0}
            )

            assert liquidity_usd is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
