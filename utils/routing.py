"""
Production-grade multi-hop routing for DEX arbitrage.

Finds optimal paths through intermediary tokens when direct pairs don't exist.
Example: STONE → WETH → USDC instead of direct STONE → USDC

Fixes implemented:
- Input validation with proper error messages
- Correct fee compounding calculation
- Path generation limits to prevent combinatorial explosion
- Duplicate path removal
- Proper function naming
- Comprehensive logging
"""

from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from config.logging_config import get_logger

logger = get_logger(__name__)

# Safety limits
MAX_TOKENS_FOR_PATHFINDING = 20
MAX_PATHS_TO_GENERATE = 1000


@dataclass
class RouteInfo:
    """Information about a routing path."""
    path: List[str]
    num_swaps: int
    estimated_gas: int
    estimated_fee_pct: float


class MultiHopRouter:
    """
    Finds multi-hop routes for token swaps.

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
        logger.info(f"MultiHopRouter initialized with base tokens: {common_base_tokens}")

    def find_routes(
        self,
        token_in_symbol: str,
        token_out_symbol: str,
        available_pairs: Optional[Set[Tuple[str, str]]] = None,
        max_hops: int = 2
    ) -> List[List[str]]:
        """
        Find all possible routes between two tokens.

        Args:
            token_in_symbol: Starting token symbol
            token_out_symbol: Ending token symbol
            available_pairs: Optional set of available pairs (for filtering)
            max_hops: Maximum number of hops (default: 2, meaning at most 1 intermediary)

        Returns:
            List of routes, where each route is a list of token symbols
            Example: [['STONE', 'USDC'], ['STONE', 'WETH', 'USDC']]

        Raises:
            ValueError: If inputs are invalid
        """
        # Input validation
        if not token_in_symbol or not isinstance(token_in_symbol, str):
            raise ValueError(f"Invalid token_in_symbol: {token_in_symbol}")
        if not token_out_symbol or not isinstance(token_out_symbol, str):
            raise ValueError(f"Invalid token_out_symbol: {token_out_symbol}")
        if token_in_symbol == token_out_symbol:
            raise ValueError(f"token_in and token_out cannot be the same: {token_in_symbol}")
        if max_hops < 1 or max_hops > 3:
            raise ValueError(f"max_hops must be between 1 and 3, got: {max_hops}")

        routes = []
        seen_routes = set()  # Deduplicate routes

        # Direct route (1 hop) - only add if pair exists
        direct_route = [token_in_symbol, token_out_symbol]
        if available_pairs is None or self._pair_exists(token_in_symbol, token_out_symbol, available_pairs):
            route_tuple = tuple(direct_route)
            if route_tuple not in seen_routes:
                routes.append(direct_route)
                seen_routes.add(route_tuple)
                logger.debug(f"Added direct route: {direct_route}")

        # Multi-hop routes through base tokens
        if max_hops >= 2:
            for base_token in self.base_tokens:
                # Skip if either token IS the base token
                if base_token == token_in_symbol or base_token == token_out_symbol:
                    continue

                # Route: token_in → base_token → token_out
                route = [token_in_symbol, base_token, token_out_symbol]

                # Only add if all pairs exist (if available_pairs provided)
                if available_pairs is None or self._route_is_valid(route, available_pairs):
                    route_tuple = tuple(route)
                    if route_tuple not in seen_routes:
                        routes.append(route)
                        seen_routes.add(route_tuple)
                        logger.debug(f"Added 2-hop route: {route}")

        # 3-hop routes (if needed) - token_in → base1 → base2 → token_out
        if max_hops >= 3 and len(self.base_tokens) >= 2:
            for base1 in self.base_tokens:
                for base2 in self.base_tokens:
                    if base1 == base2:
                        continue
                    if base1 in [token_in_symbol, token_out_symbol]:
                        continue
                    if base2 in [token_in_symbol, token_out_symbol]:
                        continue

                    route = [token_in_symbol, base1, base2, token_out_symbol]

                    if available_pairs is None or self._route_is_valid(route, available_pairs):
                        route_tuple = tuple(route)
                        if route_tuple not in seen_routes:
                            routes.append(route)
                            seen_routes.add(route_tuple)
                            logger.debug(f"Added 3-hop route: {route}")

        logger.info(f"Found {len(routes)} valid routes from {token_in_symbol} to {token_out_symbol}")
        return routes

    def _pair_exists(self, token_a: str, token_b: str, available_pairs: Set[Tuple[str, str]]) -> bool:
        """Check if a pair exists in available pairs."""
        return (token_a, token_b) in available_pairs or (token_b, token_a) in available_pairs

    def _route_is_valid(self, route: List[str], available_pairs: Set[Tuple[str, str]]) -> bool:
        """
        Check if a route can be executed with available pairs.

        Args:
            route: List of token symbols
            available_pairs: Set of available pairs

        Returns:
            True if all necessary pairs exist
        """
        for i in range(len(route) - 1):
            if not self._pair_exists(route[i], route[i + 1], available_pairs):
                return False
        return True

    def estimate_route_cost(
        self,
        route: List[str],
        gas_per_swap: int = 150000,
        fee_per_swap: float = 0.003
    ) -> RouteInfo:
        """
        Estimate the cost of a multi-hop route.

        Args:
            route: List of token symbols in the route
            gas_per_swap: Estimated gas units per swap (default: 150k)
            fee_per_swap: Trading fee per swap as decimal (default: 0.003 = 0.3%)

        Returns:
            RouteInfo with cost estimates

        Raises:
            ValueError: If inputs are invalid
        """
        if not route or len(route) < 2:
            raise ValueError(f"Invalid route: {route}")
        if gas_per_swap <= 0:
            raise ValueError(f"Invalid gas_per_swap: {gas_per_swap}")
        if fee_per_swap < 0 or fee_per_swap >= 1:
            raise ValueError(f"Invalid fee_per_swap: {fee_per_swap}")

        num_swaps = len(route) - 1

        # Correct fee compounding calculation
        # After N swaps with fee f, you retain (1-f)^N of your value
        # So total fee is: 1 - (1-f)^N
        total_fee_decimal = 1 - ((1 - fee_per_swap) ** num_swaps)
        total_fee_pct = total_fee_decimal * 100

        return RouteInfo(
            path=route,
            num_swaps=num_swaps,
            estimated_gas=num_swaps * gas_per_swap,
            estimated_fee_pct=total_fee_pct
        )


class RouteOptimizer:
    """
    Selects shortest valid route based on available pairs.

    Note: This finds the route with fewest hops, not necessarily the most
    profitable route (which would require price simulation).
    """

    def __init__(self):
        self.router = MultiHopRouter()
        logger.info("RouteOptimizer initialized")

    def find_shortest_route(
        self,
        token_in: Dict,
        token_out: Dict,
        available_pairs: List[Tuple[str, str]]
    ) -> Optional[List[str]]:
        """
        Find the shortest route given available trading pairs.

        Args:
            token_in: Token dict with 'symbol' key
            token_out: Token dict with 'symbol' key
            available_pairs: List of available pairs as tuples of (symbol1, symbol2)

        Returns:
            Shortest route as list of symbols, or None if no route exists

        Raises:
            ValueError: If inputs are invalid
        """
        # Input validation
        if not isinstance(token_in, dict) or 'symbol' not in token_in:
            raise ValueError(f"Invalid token_in (must be dict with 'symbol' key): {token_in}")
        if not isinstance(token_out, dict) or 'symbol' not in token_out:
            raise ValueError(f"Invalid token_out (must be dict with 'symbol' key): {token_out}")
        if not isinstance(available_pairs, (list, set)):
            raise ValueError(f"Invalid available_pairs (must be list or set): {type(available_pairs)}")

        token_in_symbol = token_in['symbol']
        token_out_symbol = token_out['symbol']

        # Convert to set for O(1) lookup
        pairs_set = set(available_pairs)

        # Get all possible routes
        possible_routes = self.router.find_routes(
            token_in_symbol,
            token_out_symbol,
            available_pairs=pairs_set
        )

        if not possible_routes:
            logger.warning(f"No valid routes found from {token_in_symbol} to {token_out_symbol}")
            return None

        # Sort by number of hops (ascending) - prefer fewer hops
        possible_routes.sort(key=lambda r: len(r))

        shortest_route = possible_routes[0]
        logger.info(
            f"Selected shortest route from {token_in_symbol} to {token_out_symbol}: "
            f"{' → '.join(shortest_route)} ({len(shortest_route) - 1} hops)"
        )

        return shortest_route


class PathFinder:
    """
    Advanced pathfinding for circular arbitrage routes.

    Can find complex paths including:
    - Multi-hop routes through intermediaries
    - Circular arbitrage routes (start and end with same token)
    """

    def __init__(self, tokens: List[Dict], dexes: List[Dict]):
        """
        Initialize pathfinder.

        Args:
            tokens: List of token dicts with 'symbol', 'address', 'decimals'
            dexes: List of DEX dicts with 'name', 'router', 'type', 'fee'

        Raises:
            ValueError: If too many tokens or invalid inputs
        """
        # Validate inputs
        if not isinstance(tokens, list) or not all(isinstance(t, dict) for t in tokens):
            raise ValueError("tokens must be a list of dicts")
        if not isinstance(dexes, list) or not all(isinstance(d, dict) for d in dexes):
            raise ValueError("dexes must be a list of dicts")

        # Safety limit
        if len(tokens) > MAX_TOKENS_FOR_PATHFINDING:
            raise ValueError(
                f"Too many tokens for pathfinding (max {MAX_TOKENS_FOR_PATHFINDING}, got {len(tokens)}). "
                f"This prevents combinatorial explosion."
            )

        self.tokens = {t['symbol']: t for t in tokens}
        self.dexes = dexes
        self.router = MultiHopRouter()

        logger.info(f"PathFinder initialized with {len(tokens)} tokens and {len(dexes)} DEXes")

    def find_arbitrage_paths(
        self,
        start_token_symbol: str,
        max_hops: int = 3,
        max_paths: int = MAX_PATHS_TO_GENERATE
    ) -> List[List[str]]:
        """
        Find circular arbitrage paths starting and ending with the same token.

        Args:
            start_token_symbol: Token to start and end with (e.g., 'WETH')
            max_hops: Maximum number of hops in the path (default: 3)
            max_paths: Maximum number of paths to generate (safety limit)

        Returns:
            List of circular paths
            Example: [['WETH', 'USDC', 'WETH'], ['WETH', 'USDC', 'USDT', 'WETH']]

        Raises:
            ValueError: If inputs are invalid
        """
        # Validation
        if start_token_symbol not in self.tokens:
            raise ValueError(f"Unknown token: {start_token_symbol}")
        if max_hops < 2 or max_hops > 4:
            raise ValueError(f"max_hops must be between 2 and 4, got: {max_hops}")

        paths = []
        seen_paths = set()  # Deduplicate

        # Get all other tokens
        other_tokens = [s for s in self.tokens.keys() if s != start_token_symbol]

        logger.info(
            f"Finding arbitrage paths from {start_token_symbol} with {len(other_tokens)} "
            f"other tokens, max_hops={max_hops}"
        )

        # 2-hop arbitrage: start → token → start
        for token in other_tokens:
            path = [start_token_symbol, token, start_token_symbol]
            path_tuple = tuple(path)

            if path_tuple not in seen_paths:
                paths.append(path)
                seen_paths.add(path_tuple)

                # Safety check
                if len(paths) >= max_paths:
                    logger.warning(f"Reached max_paths limit: {max_paths}")
                    return paths

        # 3-hop arbitrage: start → token1 → token2 → start
        if max_hops >= 3:
            for token1 in other_tokens:
                for token2 in other_tokens:
                    if token1 == token2:
                        continue

                    path = [start_token_symbol, token1, token2, start_token_symbol]
                    path_tuple = tuple(path)

                    if path_tuple not in seen_paths:
                        paths.append(path)
                        seen_paths.add(path_tuple)

                        # Safety check
                        if len(paths) >= max_paths:
                            logger.warning(f"Reached max_paths limit: {max_paths}")
                            return paths

        # 4-hop arbitrage: start → token1 → token2 → token3 → start
        if max_hops >= 4:
            # Limit to prevent explosion
            limited_tokens = other_tokens[:10]  # Only use top 10 tokens
            if len(other_tokens) > 10:
                logger.warning(
                    f"Limited 4-hop pathfinding to top 10 tokens "
                    f"(out of {len(other_tokens)} available)"
                )

            for token1 in limited_tokens:
                for token2 in limited_tokens:
                    if token2 == token1:
                        continue
                    for token3 in limited_tokens:
                        if token3 in [token1, token2]:
                            continue

                        path = [start_token_symbol, token1, token2, token3, start_token_symbol]
                        path_tuple = tuple(path)

                        if path_tuple not in seen_paths:
                            paths.append(path)
                            seen_paths.add(path_tuple)

                            # Safety check
                            if len(paths) >= max_paths:
                                logger.warning(f"Reached max_paths limit: {max_paths}")
                                return paths

        logger.info(f"Found {len(paths)} unique arbitrage paths for {start_token_symbol}")
        return paths
