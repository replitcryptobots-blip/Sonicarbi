"""
Slippage calculator based on pool liquidity.

This module calculates expected slippage for trades based on:
1. Pool reserves (Uniswap V2 constant product formula)
2. Concentrated liquidity (for CL DEXes like Ambient, iZiSwap)
3. Price impact calculations
"""

from web3 import Web3
from typing import Dict, Optional, Tuple
import json
from pathlib import Path
from decimal import Decimal, getcontext
import math

from config.logging_config import get_logger

logger = get_logger(__name__)

# Set high precision for Decimal calculations
getcontext().prec = 50


class SlippageCalculator:
    """
    Calculate slippage and price impact for DEX trades.

    For Uniswap V2 style DEXes:
    - Uses constant product formula (x * y = k)
    - Calculates exact output including price impact

    For Concentrated Liquidity DEXes:
    - More complex, depends on liquidity distribution
    - Simplified model for now
    """

    # Uniswap V2 Pair ABI (minimal)
    PAIR_ABI = json.loads('''[
        {
            "constant": true,
            "inputs": [],
            "name": "getReserves",
            "outputs": [
                {"internalType": "uint112", "name": "_reserve0", "type": "uint112"},
                {"internalType": "uint112", "name": "_reserve1", "type": "uint112"},
                {"internalType": "uint32", "name": "_blockTimestampLast", "type": "uint32"}
            ],
            "payable": false,
            "stateMutability": "view",
            "type": "function"
        },
        {
            "constant": true,
            "inputs": [],
            "name": "token0",
            "outputs": [{"internalType": "address", "name": "", "type": "address"}],
            "payable": false,
            "stateMutability": "view",
            "type": "function"
        },
        {
            "constant": true,
            "inputs": [],
            "name": "token1",
            "outputs": [{"internalType": "address", "name": "", "type": "address"}],
            "payable": false,
            "stateMutability": "view",
            "type": "function"
        }
    ]''')

    # Uniswap V2 Factory ABI (minimal)
    FACTORY_ABI = json.loads('''[
        {
            "constant": true,
            "inputs": [
                {"internalType": "address", "name": "", "type": "address"},
                {"internalType": "address", "name": "", "type": "address"}
            ],
            "name": "getPair",
            "outputs": [{"internalType": "address", "name": "", "type": "address"}],
            "payable": false,
            "stateMutability": "view",
            "type": "function"
        }
    ]''')

    def __init__(self, w3: Web3):
        """
        Initialize slippage calculator.

        Args:
            w3: Web3 instance
        """
        self.w3 = w3

        # Load DEX configs
        config_path = Path(__file__).parent.parent / 'config' / 'dex_configs.json'
        with open(config_path, 'r') as f:
            data = json.load(f)

        self.dexes = {d['name']: d for d in data['scroll']['dexes']}
        self.tokens = {t['symbol']: t for t in data['scroll']['common_tokens']}

        logger.info("Slippage calculator initialized")

    def calculate_v2_slippage(
        self,
        dex_name: str,
        token_in: Dict,
        token_out: Dict,
        amount_in: float
    ) -> Optional[Dict]:
        """
        Calculate slippage for Uniswap V2 style DEX.

        Uses the constant product formula:
        - x * y = k (where x and y are reserves)
        - Price impact = (amount_in / reserve_in) * 100

        Args:
            dex_name: DEX name (e.g., 'SyncSwap')
            token_in: Input token dict
            token_out: Output token dict
            amount_in: Amount of input token

        Returns:
            Dict with slippage info, or None if error
        """
        try:
            dex = self.dexes[dex_name]

            # Get pair address
            factory = self.w3.eth.contract(
                address=Web3.to_checksum_address(dex['factory']),
                abi=self.FACTORY_ABI
            )

            token_in_addr = Web3.to_checksum_address(token_in['address'])
            token_out_addr = Web3.to_checksum_address(token_out['address'])

            pair_address = factory.functions.getPair(token_in_addr, token_out_addr).call()

            if pair_address == '0x0000000000000000000000000000000000000000':
                logger.debug(f"Pair not found: {token_in['symbol']}/{token_out['symbol']} on {dex_name}")
                return None

            pair_address = Web3.to_checksum_address(pair_address)

            # Get pair contract
            pair = self.w3.eth.contract(address=pair_address, abi=self.PAIR_ABI)

            # Get token order
            token0 = pair.functions.token0().call()
            token1 = pair.functions.token1().call()

            # Get reserves
            reserves = pair.functions.getReserves().call()
            reserve0 = reserves[0]
            reserve1 = reserves[1]

            # Determine which reserve is which token
            if token0.lower() == token_in_addr.lower():
                reserve_in = reserve0
                reserve_out = reserve1
                decimals_in = token_in['decimals']
                decimals_out = token_out['decimals']
            else:
                reserve_in = reserve1
                reserve_out = reserve0
                decimals_in = token_in['decimals']
                decimals_out = token_out['decimals']

            # Convert to human-readable using Decimal for high precision
            reserve_in_decimal = Decimal(str(reserve_in)) / Decimal(10 ** decimals_in)
            reserve_out_decimal = Decimal(str(reserve_out)) / Decimal(10 ** decimals_out)
            amount_in_decimal = Decimal(str(amount_in))

            # Convert to float for backwards compatibility
            reserve_in_float = float(reserve_in_decimal)
            reserve_out_float = float(reserve_out_decimal)

            # Calculate price impact
            # Price impact = (amount_in / reserve_in) * 100
            if reserve_in_decimal == 0:
                logger.error("Reserve in is zero, cannot calculate price impact")
                return None

            price_impact_pct = float((amount_in_decimal / reserve_in_decimal) * 100)

            # Calculate expected output using constant product formula with Decimal
            # Including fee
            fee = dex.get('fee', 0.003)  # Default 0.3% if not specified
            fee_decimal = Decimal(str(fee))
            amount_in_with_fee_decimal = amount_in_decimal * (Decimal('1') - fee_decimal)

            # Convert to wei for calculation
            amount_in_with_fee_wei_decimal = amount_in_with_fee_decimal * Decimal(10 ** decimals_in)
            reserve_in_wei_decimal = Decimal(str(reserve_in))
            reserve_out_wei_decimal = Decimal(str(reserve_out))

            # Constant product formula
            numerator = amount_in_with_fee_wei_decimal * reserve_out_wei_decimal
            denominator = reserve_in_wei_decimal + amount_in_with_fee_wei_decimal
            amount_out_wei_decimal = numerator / denominator
            amount_out = float(amount_out_wei_decimal / Decimal(10 ** decimals_out))

            # Calculate spot price (before trade)
            if reserve_in_float == 0:
                logger.error("Reserve in is zero, cannot calculate price")
                return None

            spot_price = reserve_out_float / reserve_in_float

            # Calculate effective price (after trade)
            if amount_in == 0:
                logger.error("Amount in is zero, cannot calculate price")
                return None

            effective_price = amount_out / amount_in

            # Slippage = (spot_price - effective_price) / spot_price * 100
            if spot_price == 0:
                logger.error("Spot price is zero, cannot calculate slippage")
                return None

            slippage_pct = ((spot_price - effective_price) / spot_price) * 100

            # Liquidity metrics
            liquidity_ratio = amount_in / reserve_in_float  # How much of the pool we're using

            result = {
                'dex': dex_name,
                'pair': f"{token_in['symbol']}/{token_out['symbol']}",
                'pair_address': pair_address,
                'reserve_in': reserve_in_float,
                'reserve_out': reserve_out_float,
                'amount_in': amount_in,
                'amount_out': amount_out,
                'spot_price': spot_price,
                'effective_price': effective_price,
                'price_impact_pct': price_impact_pct,
                'slippage_pct': slippage_pct,
                'liquidity_ratio': liquidity_ratio,
                'is_high_impact': price_impact_pct > 1.0,  # Flag if >1% impact
                'is_very_high_impact': price_impact_pct > 5.0  # Flag if >5% impact
            }

            logger.debug(
                f"Slippage calc for {dex_name} {token_in['symbol']}/{token_out['symbol']}: "
                f"price_impact={price_impact_pct:.3f}%, slippage={slippage_pct:.3f}%, "
                f"reserves={reserve_in_float:.2f}/{reserve_out_float:.2f}"
            )

            return result

        except Exception as e:
            logger.error(f"Error calculating slippage for {dex_name}: {e}", exc_info=True)
            return None

    def calculate_optimal_trade_size(
        self,
        dex_name: str,
        token_in: Dict,
        token_out: Dict,
        max_price_impact_pct: float = 1.0
    ) -> Optional[float]:
        """
        Calculate optimal trade size to stay within price impact limit.

        For Uniswap V2:
        - Price impact = (amount_in / reserve_in) * 100
        - Solving for amount_in: amount_in = reserve_in * (max_price_impact / 100)

        Args:
            dex_name: DEX name
            token_in: Input token
            token_out: Output token
            max_price_impact_pct: Maximum acceptable price impact (%)

        Returns:
            Optimal amount_in, or None if error
        """
        try:
            # Get pool info
            slippage_info = self.calculate_v2_slippage(
                dex_name, token_in, token_out, amount_in=1.0  # Use 1.0 to get reserves
            )

            if not slippage_info:
                return None

            reserve_in = slippage_info['reserve_in']

            # Calculate max amount for given price impact
            optimal_amount = reserve_in * (max_price_impact_pct / 100)

            logger.info(
                f"Optimal trade size for {token_in['symbol']}/{token_out['symbol']} on {dex_name}: "
                f"{optimal_amount:.4f} {token_in['symbol']} "
                f"(max impact: {max_price_impact_pct}%)"
            )

            return optimal_amount

        except Exception as e:
            logger.error(f"Error calculating optimal trade size: {e}", exc_info=True)
            return None

    def validate_arbitrage_slippage(
        self,
        buy_dex: str,
        sell_dex: str,
        token_in: Dict,
        token_out: Dict,
        amount: float,
        max_slippage_pct: float = 2.0
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Validate that arbitrage trade won't have excessive slippage.

        Args:
            buy_dex: DEX to buy on
            sell_dex: DEX to sell on
            token_in: Input token
            token_out: Output token
            amount: Trade amount
            max_slippage_pct: Maximum acceptable slippage (%)

        Returns:
            Tuple of (is_valid, slippage_info_dict)
        """
        try:
            # Check if DEXes are V2 type
            buy_dex_type = self.dexes[buy_dex]['type']
            sell_dex_type = self.dexes[sell_dex]['type']

            results = {}

            # Calculate slippage for buy leg
            if buy_dex_type == 'uniswap_v2':
                buy_slippage = self.calculate_v2_slippage(buy_dex, token_in, token_out, amount)
                if buy_slippage:
                    results['buy'] = buy_slippage
                else:
                    logger.warning(f"Could not calculate slippage for buy leg on {buy_dex}")
                    return False, None

            # Calculate slippage for sell leg
            if sell_dex_type == 'uniswap_v2':
                # For sell leg, we're selling token_out for token_in
                sell_amount = buy_slippage['amount_out'] if buy_slippage else amount
                sell_slippage = self.calculate_v2_slippage(sell_dex, token_out, token_in, sell_amount)
                if sell_slippage:
                    results['sell'] = sell_slippage
                else:
                    logger.warning(f"Could not calculate slippage for sell leg on {sell_dex}")
                    return False, None

            # Check if slippage is acceptable
            total_slippage = 0
            if 'buy' in results:
                total_slippage += results['buy']['slippage_pct']
            if 'sell' in results:
                total_slippage += results['sell']['slippage_pct']

            results['total_slippage_pct'] = total_slippage
            results['is_valid'] = total_slippage <= max_slippage_pct

            logger.info(
                f"Arbitrage slippage validation: {token_in['symbol']}/{token_out['symbol']} "
                f"{buy_dex}→{sell_dex}, total_slippage={total_slippage:.3f}%, "
                f"valid={results['is_valid']}"
            )

            return results['is_valid'], results

        except Exception as e:
            logger.error(f"Error validating arbitrage slippage: {e}", exc_info=True)
            return False, None

    def get_pool_liquidity_usd(
        self,
        dex_name: str,
        token_in: Dict,
        token_out: Dict,
        token_prices: Dict[str, float]
    ) -> Optional[float]:
        """
        Calculate total pool liquidity in USD.

        Args:
            dex_name: DEX name
            token_in: Input token
            token_out: Output token
            token_prices: Dict of token prices in USD (symbol -> price)

        Returns:
            Total pool liquidity in USD, or None if error
        """
        try:
            slippage_info = self.calculate_v2_slippage(
                dex_name, token_in, token_out, amount_in=1.0
            )

            if not slippage_info:
                return None

            reserve_in = slippage_info['reserve_in']
            reserve_out = slippage_info['reserve_out']

            # Get USD prices
            price_in = token_prices.get(token_in['symbol'], 0)
            price_out = token_prices.get(token_out['symbol'], 0)

            # Calculate liquidity
            liquidity_usd = (reserve_in * price_in) + (reserve_out * price_out)

            logger.info(
                f"Pool liquidity for {token_in['symbol']}/{token_out['symbol']} on {dex_name}: "
                f"${liquidity_usd:,.2f}"
            )

            return liquidity_usd

        except Exception as e:
            logger.error(f"Error calculating pool liquidity: {e}", exc_info=True)
            return None
