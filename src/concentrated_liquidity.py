"""
Concentrated Liquidity DEX Support Module

Handles price queries for concentrated liquidity DEXes like Ambient (CrocSwap) and iZiSwap.
These DEXes use different pricing models than Uniswap V2.
"""

import json
import sys
from pathlib import Path
from web3 import Web3
from typing import Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config import config


class AmbientPriceFetcher:
    """
    Fetches prices from Ambient Finance (CrocSwap) on Scroll.

    Ambient uses a concentrated liquidity model with a CrocQuery contract
    for querying prices.
    """

    def __init__(self, w3: Web3):
        self.w3 = w3

        # CrocQuery contract address on Scroll
        self.croc_query_address = "0x62223e90605845Cf5CC6DAE6E0de4CDA130d6DDf"

        # CrocQuery ABI - minimal for queryPrice
        self.croc_query_abi = json.loads('''[
            {
                "inputs": [
                    {"internalType": "address", "name": "base", "type": "address"},
                    {"internalType": "address", "name": "quote", "type": "address"},
                    {"internalType": "uint256", "name": "poolIdx", "type": "uint256"}
                ],
                "name": "queryPrice",
                "outputs": [{"internalType": "uint128", "name": "", "type": "uint128"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]''')

        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.croc_query_address),
            abi=self.croc_query_abi
        )

        # Default pool index for standard pools
        self.default_pool_idx = 420

    def get_price(self, token_in: Dict, token_out: Dict, amount_in: float) -> Optional[float]:
        """
        Get price from Ambient Finance.

        Args:
            token_in: Token being sold (dict with 'address' and 'decimals')
            token_out: Token being bought (dict with 'address' and 'decimals')
            amount_in: Amount of token_in to swap

        Returns:
            Amount of token_out received, or None if query fails
        """
        try:
            addr_in = Web3.to_checksum_address(token_in['address'])
            addr_out = Web3.to_checksum_address(token_out['address'])

            # Ambient requires base < quote (smaller address first)
            if addr_in.lower() < addr_out.lower():
                base, quote = addr_in, addr_out
                is_buy = False  # Selling base for quote
            else:
                base, quote = addr_out, addr_in
                is_buy = True  # Buying base with quote

            # Query the current price (sqrt price in Q64.64 format)
            sqrt_price_q64 = self.contract.functions.queryPrice(
                base, quote, self.default_pool_idx
            ).call()

            # Convert Q64.64 fixed point to float
            # Q64.64 means 64 bits for integer part, 64 bits for fractional part
            sqrt_price = float(sqrt_price_q64) / (2 ** 64)

            # Price is the square of sqrt_price
            price = sqrt_price ** 2

            # If we're buying base with quote, invert the price
            if is_buy:
                price = 1.0 / price if price > 0 else 0

            # Calculate output amount
            # WARNING: This calculation assumes the price from queryPrice is a ratio of wei amounts.
            # If Ambient returns price as a ratio of token amounts (accounting for decimals),
            # this calculation will be incorrect by a factor of 10^(decimals_in - decimals_out).
            # TODO: Verify with real mainnet data and adjust if needed.
            # See CL_AUDIT_FINDINGS.md for details.
            amount_in_adjusted = amount_in * (10 ** token_in['decimals'])
            amount_out_adjusted = amount_in_adjusted * price
            amount_out = amount_out_adjusted / (10 ** token_out['decimals'])

            return amount_out

        except Exception as e:
            # Log errors if debug mode is enabled
            # Silently fail otherwise - pool might not exist for this pair
            if hasattr(config, 'DEBUG_MODE') and config.DEBUG_MODE:
                print(f"[DEBUG] Ambient price fetch failed for {token_in.get('symbol', '?')}/{token_out.get('symbol', '?')}: {str(e)}")
            return None


class iZiSwapPriceFetcher:
    """
    Fetches prices from iZiSwap on Scroll.

    iZiSwap uses concentrated liquidity with a Quoter contract pattern
    similar to Uniswap V3.

    Note: Requires the Quoter contract address which may vary.
    """

    def __init__(self, w3: Web3):
        self.w3 = w3

        # iZiSwap Quoter contract address on Scroll
        # Note: This is the LiquidityManager address from config
        # The actual Quoter address needs to be verified
        self.quoter_address = "0x1502d025BfA624469892289D45C0352997251728"

        # Uniswap V3 style Quoter ABI (minimal)
        # iZiSwap follows similar patterns
        self.quoter_abi = json.loads('''[
            {
                "inputs": [
                    {"internalType": "bytes", "name": "path", "type": "bytes"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"}
                ],
                "name": "quoteExactInput",
                "outputs": [
                    {"internalType": "uint256", "name": "amountOut", "type": "uint256"}
                ],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]''')

        # Note: This may not work without the correct Quoter contract address
        try:
            self.contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(self.quoter_address),
                abi=self.quoter_abi
            )
        except Exception:
            self.contract = None

    def get_price(self, token_in: Dict, token_out: Dict, amount_in: float) -> Optional[float]:
        """
        Get price from iZiSwap.

        Note: This implementation is limited without the correct Quoter contract address.
        Returns None for now until proper contract addresses are configured.

        Args:
            token_in: Token being sold (dict with 'address' and 'decimals')
            token_out: Token being bought (dict with 'address' and 'decimals')
            amount_in: Amount of token_in to swap

        Returns:
            Amount of token_out received, or None if query fails
        """
        # Return None - needs proper Quoter contract address
        # TODO: Update with correct Quoter address from iZiSwap docs
        return None


class ConcentratedLiquidityManager:
    """
    Manager for all concentrated liquidity DEX price queries.
    """

    def __init__(self, w3: Web3):
        self.w3 = w3
        self.ambient = AmbientPriceFetcher(w3)
        self.iziswap = iZiSwapPriceFetcher(w3)

    def get_price(self, dex_name: str, token_in: Dict, token_out: Dict,
                  amount_in: float) -> Optional[float]:
        """
        Get price from a concentrated liquidity DEX.

        Args:
            dex_name: Name of the DEX ('Ambient', 'iZiSwap', etc.)
            token_in: Token being sold
            token_out: Token being bought
            amount_in: Amount to swap

        Returns:
            Output amount or None if unsupported/failed
        """
        if dex_name == "Ambient":
            return self.ambient.get_price(token_in, token_out, amount_in)
        elif dex_name == "iZiSwap":
            return self.iziswap.get_price(token_in, token_out, amount_in)
        else:
            return None
