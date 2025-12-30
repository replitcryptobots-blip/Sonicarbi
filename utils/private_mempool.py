"""
Private Mempool Support for MEV Protection.

This module provides support for submitting transactions through private mempools
to reduce MEV extraction risk (sandwich attacks, frontrunning).

Supported Methods:
1. Flashbots Protect RPC (if available on Scroll)
2. Private RPC with direct builder access
3. Eden Network (if available)
4. Standard mempool (fallback)

Security Benefits:
- Transactions not visible in public mempool
- Reduced sandwich attack risk
- Lower frontrunning exposure
- Better execution for large trades
"""

import asyncio
from web3 import Web3
from web3.types import TxParams
from typing import Dict, Optional, Union
from eth_account.signers.local import LocalAccount
import aiohttp
import time

from config.logging_config import get_logger
from config.config import config

logger = get_logger(__name__)


class PrivateMempoolProvider:
    """
    Base class for private mempool providers.

    Subclasses implement specific provider logic (Flashbots, etc.)
    """

    def __init__(self, name: str):
        self.name = name
        self.enabled = False

    async def send_transaction(
        self,
        signed_tx: bytes,
        max_block_number: Optional[int] = None
    ) -> Optional[str]:
        """
        Send a signed transaction through the private mempool.

        Args:
            signed_tx: Signed transaction bytes
            max_block_number: Maximum block number for inclusion

        Returns:
            Transaction hash if successful, None otherwise
        """
        raise NotImplementedError("Subclasses must implement send_transaction")

    def is_available(self) -> bool:
        """Check if this provider is available/enabled."""
        return self.enabled


class FlashbotsProvider(PrivateMempoolProvider):
    """
    Flashbots Protect RPC provider.

    Note: Flashbots may not be available on Scroll yet. This provides
    the infrastructure for when it becomes available.

    Flashbots Docs: https://docs.flashbots.net/
    """

    def __init__(self, rpc_url: Optional[str] = None):
        super().__init__("Flashbots")

        # Flashbots RPC URL (if available on Scroll)
        self.rpc_url = rpc_url or getattr(config, 'FLASHBOTS_RPC_URL', None)

        if self.rpc_url:
            self.enabled = True
            logger.info(f"Flashbots provider initialized: {self.rpc_url}")
        else:
            logger.warning(
                "Flashbots RPC URL not configured. "
                "Flashbots may not be available on Scroll yet."
            )

    async def send_transaction(
        self,
        signed_tx: bytes,
        max_block_number: Optional[int] = None
    ) -> Optional[str]:
        """
        Send transaction via Flashbots Protect RPC.

        Args:
            signed_tx: Signed transaction bytes
            max_block_number: Maximum block number for inclusion

        Returns:
            Transaction hash or None
        """
        if not self.enabled:
            logger.debug("Flashbots not available, skipping")
            return None

        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_sendPrivateTransaction",
                "params": [{
                    "tx": signed_tx.hex(),
                    "maxBlockNumber": hex(max_block_number) if max_block_number else None,
                    "preferences": {
                        "fast": True  # Prioritize speed over cost
                    }
                }]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.rpc_url,
                    json=payload,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        result = await response.json()

                        if 'result' in result:
                            tx_hash = result['result']
                            logger.info(f"Transaction sent via Flashbots: {tx_hash}")
                            return tx_hash
                        elif 'error' in result:
                            logger.error(f"Flashbots error: {result['error']}")
                            return None
                    else:
                        error_text = await response.text()
                        logger.error(f"Flashbots HTTP error {response.status}: {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Failed to send via Flashbots: {e}", exc_info=True)
            return None


class PrivateRPCProvider(PrivateMempoolProvider):
    """
    Private RPC with direct builder connection.

    Some RPC providers offer private transaction submission that bypasses
    the public mempool.
    """

    def __init__(self, rpc_url: Optional[str] = None):
        super().__init__("PrivateRPC")

        # Private RPC URL
        self.rpc_url = rpc_url or getattr(config, 'PRIVATE_RPC_URL', None)

        if self.rpc_url:
            self.enabled = True
            self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
            logger.info(f"Private RPC provider initialized: {self.rpc_url}")
        else:
            logger.info("No private RPC configured")

    async def send_transaction(
        self,
        signed_tx: bytes,
        max_block_number: Optional[int] = None
    ) -> Optional[str]:
        """
        Send transaction via private RPC.

        Args:
            signed_tx: Signed transaction bytes
            max_block_number: Not used for private RPC

        Returns:
            Transaction hash or None
        """
        if not self.enabled:
            logger.debug("Private RPC not available, skipping")
            return None

        try:
            # Send transaction through private RPC
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx)
            tx_hash_hex = tx_hash.hex()

            logger.info(f"Transaction sent via Private RPC: {tx_hash_hex}")
            return tx_hash_hex

        except Exception as e:
            logger.error(f"Failed to send via Private RPC: {e}", exc_info=True)
            return None


class StandardMempoolProvider(PrivateMempoolProvider):
    """
    Standard public mempool (fallback).

    This is the default method if no private mempool is available.
    Transactions are visible to all mempool participants (MEV risk).
    """

    def __init__(self, w3: Web3):
        super().__init__("StandardMempool")
        self.w3 = w3
        self.enabled = True
        logger.info("Standard mempool provider initialized (fallback)")

    async def send_transaction(
        self,
        signed_tx: bytes,
        max_block_number: Optional[int] = None
    ) -> Optional[str]:
        """
        Send transaction via standard mempool.

        Args:
            signed_tx: Signed transaction bytes
            max_block_number: Not used for standard mempool

        Returns:
            Transaction hash or None
        """
        try:
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx)
            tx_hash_hex = tx_hash.hex()

            logger.info(f"Transaction sent via standard mempool: {tx_hash_hex}")
            logger.warning(
                "⚠️  Transaction sent to PUBLIC mempool - MEV risk! "
                "Consider using private mempool for production."
            )
            return tx_hash_hex

        except Exception as e:
            logger.error(f"Failed to send via standard mempool: {e}", exc_info=True)
            return None


class PrivateMempoolManager:
    """
    Manages multiple private mempool providers with automatic fallback.

    Usage:
        manager = PrivateMempoolManager(w3)
        tx_hash = await manager.send_transaction(signed_tx)

    The manager tries providers in order of preference:
    1. Flashbots (if available)
    2. Private RPC (if configured)
    3. Standard mempool (fallback)
    """

    def __init__(
        self,
        w3: Web3,
        prefer_private: bool = True
    ):
        """
        Initialize private mempool manager.

        Args:
            w3: Web3 instance
            prefer_private: Whether to prefer private mempools over public
        """
        self.w3 = w3
        self.prefer_private = prefer_private

        # Initialize providers (in order of preference)
        self.providers: list[PrivateMempoolProvider] = []

        # Try Flashbots first (if available)
        flashbots = FlashbotsProvider()
        if flashbots.is_available():
            self.providers.append(flashbots)

        # Try Private RPC
        private_rpc = PrivateRPCProvider()
        if private_rpc.is_available():
            self.providers.append(private_rpc)

        # Always have standard mempool as fallback
        self.providers.append(StandardMempoolProvider(w3))

        # Log available providers
        available = [p.name for p in self.providers if p.is_available()]
        logger.info(f"Private mempool manager initialized. Available providers: {available}")

        if not any(p.name in ['Flashbots', 'PrivateRPC'] for p in self.providers):
            logger.warning(
                "⚠️  No private mempool configured! Using public mempool (MEV risk). "
                "Configure FLASHBOTS_RPC_URL or PRIVATE_RPC_URL for MEV protection."
            )

    async def send_transaction(
        self,
        signed_tx: bytes,
        max_block_number: Optional[int] = None,
        retry_on_failure: bool = True
    ) -> Optional[str]:
        """
        Send transaction through the best available provider.

        Tries providers in order until one succeeds.

        Args:
            signed_tx: Signed transaction bytes
            max_block_number: Maximum block number for inclusion (Flashbots)
            retry_on_failure: Whether to try fallback providers on failure

        Returns:
            Transaction hash if successful, None otherwise
        """
        # If not preferring private, just use standard mempool
        if not self.prefer_private:
            standard_provider = next(
                (p for p in self.providers if p.name == 'StandardMempool'),
                None
            )
            if standard_provider:
                return await standard_provider.send_transaction(signed_tx)

        # Try each provider in order
        for provider in self.providers:
            if not provider.is_available():
                continue

            logger.debug(f"Attempting to send via {provider.name}...")

            tx_hash = await provider.send_transaction(signed_tx, max_block_number)

            if tx_hash:
                logger.info(f"✅ Transaction sent successfully via {provider.name}")
                return tx_hash

            if not retry_on_failure:
                logger.error(f"Transaction failed via {provider.name}, not retrying")
                return None

            logger.warning(f"Failed to send via {provider.name}, trying next provider...")

        logger.error("All providers failed to send transaction")
        return None

    def get_active_provider(self) -> str:
        """Get the name of the currently active (first available) provider."""
        for provider in self.providers:
            if provider.is_available():
                return provider.name
        return "None"

    def has_private_mempool(self) -> bool:
        """Check if any private mempool provider is available."""
        return any(
            p.is_available() and p.name in ['Flashbots', 'PrivateRPC']
            for p in self.providers
        )

    def get_stats(self) -> Dict:
        """Get statistics about available providers."""
        return {
            'prefer_private': self.prefer_private,
            'active_provider': self.get_active_provider(),
            'has_private_mempool': self.has_private_mempool(),
            'available_providers': [
                p.name for p in self.providers if p.is_available()
            ]
        }
