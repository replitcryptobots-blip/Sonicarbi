"""
Multi-hop routing for DEX arbitrage.

Finds optimal paths through intermediary tokens when direct pairs don't exist.
Example: STONE → WETH → USDC instead of direct STONE → USDC
"""

from typing import List, Dict, Optional, Tuple
from itertools import permutations


class MultiHopRouter:
    """
    Finds optimal multi-hop routes for token swaps.

    Most DEXes don't have direct pairs for all token combinations.
    This router finds paths through intermediary tokens (typically WETH).
    """

    def __init__(self, common_base_tokens: List[str] = None):
        """
        Initialize the router.

        Args:
            common_base_tokens: List of token symbols commonly used as intermediaries
                              (default: ['WETH'])
        """
        if common_base_tokens is None:
            common_base_tokens = ['WETH']

        self.base_tokens = common_base_tokens

    def find_routes(self, token_in_symbol: str, token_out_symbol: str,
                   max_hops: int = 2) -> List[List[str]]:
        """
        Find all possible routes between two tokens.

        Args:
            token_in_symbol: Starting token symbol
            token_out_symbol: Ending token symbol
            max_hops: Maximum number of hops (default: 2, meaning at most 1 intermediary)

        Returns:
            List of routes, where each route is a list of token symbols
            Example: [['STONE', 'WETH', 'USDC'], ['STONE', 'USDC']]
        """
        routes = []

        # Direct route (1 hop)
        routes.append([token_in_symbol, token_out_symbol])

        # If max_hops allows, add routes through base tokens
        if max_hops >= 2:
            for base_token in self.base_tokens:
                # Skip if either token IS the base token
                if base_token == token_in_symbol or base_token == token_out_symbol:
                    continue

                # Route: token_in → base_token → token_out
                routes.append([token_in_symbol, base_token, token_out_symbol])

        return routes

    def estimate_route_cost(self, route: List[str], gas_per_swap: int = 150000,
                           fee_per_swap: float = 0.003) -> Dict:
        """
        Estimate the cost of a multi-hop route.

        Args:
            route: List of token symbols in the route
            gas_per_swap: Estimated gas units per swap (default: 150k)
            fee_per_swap: Trading fee per swap (default: 0.3%)

        Returns:
            Dict with cost estimates:
            - num_swaps: Number of swaps in route
            - total_gas: Total gas units
            - total_fee_pct: Total fee percentage
        """
        num_swaps = len(route) - 1

        return {
            'num_swaps': num_swaps,
            'total_gas': num_swaps * gas_per_swap,
            'total_fee_pct': num_swaps * fee_per_swap * 100  # Convert to percentage
        }


class RouteOptimizer:
    """
    Optimizes route selection based on actual prices and costs.

    Given multiple possible routes, selects the most profitable one
    accounting for gas costs and trading fees.
    """

    def __init__(self):
        self.router = MultiHopRouter()

    def find_best_route(self, token_in: Dict, token_out: Dict,
                       available_pairs: List[Tuple[str, str]]) -> Optional[List[str]]:
        """
        Find the best route given available trading pairs.

        Args:
            token_in: Token dict with 'symbol'
            token_out: Token dict with 'symbol'
            available_pairs: List of available pairs as tuples of (symbol1, symbol2)

        Returns:
            Best route as list of symbols, or None if no route exists
        """
        token_in_symbol = token_in['symbol']
        token_out_symbol = token_out['symbol']

        # Get all possible routes
        possible_routes = self.router.find_routes(token_in_symbol, token_out_symbol)

        # Filter routes to only those with available pairs
        valid_routes = []
        for route in possible_routes:
            if self._route_is_valid(route, available_pairs):
                valid_routes.append(route)

        if not valid_routes:
            return None

        # For now, prefer direct routes (fewer hops = lower fees)
        # Sort by number of hops (ascending)
        valid_routes.sort(key=lambda r: len(r))

        return valid_routes[0]

    def _route_is_valid(self, route: List[str], available_pairs: List[Tuple[str, str]]) -> bool:
        """
        Check if a route can be executed with available pairs.

        Args:
            route: List of token symbols
            available_pairs: List of available pairs

        Returns:
            True if all necessary pairs exist
        """
        # Check each consecutive pair in the route
        for i in range(len(route) - 1):
            token_a = route[i]
            token_b = route[i + 1]

            # Check if pair exists (in either direction)
            pair_exists = (
                (token_a, token_b) in available_pairs or
                (token_b, token_a) in available_pairs
            )

            if not pair_exists:
                return False

        return True


class PathFinder:
    """
    Advanced pathfinding for optimal arbitrage routes.

    Can find complex paths including:
    - Multi-hop routes through intermediaries
    - Circular arbitrage routes
    - Cross-DEX routing
    """

    def __init__(self, tokens: List[Dict], dexes: List[Dict]):
        """
        Initialize pathfinder.

        Args:
            tokens: List of token dicts with 'symbol', 'address', 'decimals'
            dexes: List of DEX dicts with 'name', 'router', 'type', 'fee'
        """
        self.tokens = {t['symbol']: t for t in tokens}
        self.dexes = dexes
        self.router = MultiHopRouter()

    def find_arbitrage_paths(self, start_token_symbol: str,
                            max_hops: int = 3) -> List[List[str]]:
        """
        Find circular arbitrage paths starting and ending with the same token.

        Args:
            start_token_symbol: Token to start and end with (e.g., 'WETH')
            max_hops: Maximum number of hops in the path

        Returns:
            List of circular paths
            Example: [['WETH', 'USDC', 'WETH'], ['WETH', 'USDC', 'USDT', 'WETH']]
        """
        paths = []

        # Get all other tokens
        other_tokens = [s for s in self.tokens.keys() if s != start_token_symbol]

        # 2-hop arbitrage: start → token → start
        for token in other_tokens:
            paths.append([start_token_symbol, token, start_token_symbol])

        # 3-hop arbitrage: start → token1 → token2 → start
        if max_hops >= 3:
            for token1 in other_tokens:
                for token2 in other_tokens:
                    if token1 != token2:
                        paths.append([start_token_symbol, token1, token2, start_token_symbol])

        return paths
