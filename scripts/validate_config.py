#!/usr/bin/env python3
"""
Configuration validation script for Sonicarbi.

Validates that all required configuration is present and correctly formatted.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from web3 import Web3


def validate_config():
    """Validate configuration settings."""
    print("🔍 Validating Sonicarbi Configuration...")
    print("=" * 60)

    # Load .env file
    env_path = Path(__file__).parent.parent / 'config' / '.env'
    if not env_path.exists():
        print("❌ No .env file found!")
        print(f"   Expected at: {env_path}")
        print("   Copy config/.env.example to config/.env and configure it")
        return False

    load_dotenv(env_path)
    all_valid = True

    # Required settings
    print("\n📋 Required Settings:")
    required = {
        'PRIVATE_KEY': 'Private key for transactions',
        'SCROLL_RPC_URL': 'Scroll mainnet RPC endpoint',
        'SCROLL_TESTNET_RPC': 'Scroll testnet RPC endpoint',
        'NETWORK_MODE': 'Network mode (mainnet/testnet)'
    }

    for key, description in required.items():
        value = os.getenv(key)
        if not value:
            print(f"   ❌ {key}: MISSING ({description})")
            all_valid = False
        else:
            print(f"   ✅ {key}: Configured")

    # Validate private key format
    print("\n🔐 Private Key Validation:")
    private_key = os.getenv('PRIVATE_KEY', '')
    if private_key:
        if len(private_key) == 64 and all(c in '0123456789abcdefABCDEF' for c in private_key):
            print("   ✅ Private key format valid (64 hex characters)")
        elif len(private_key) == 66 and private_key.startswith('0x'):
            print("   ⚠️  Private key starts with '0x' - remove it!")
            all_valid = False
        else:
            print(f"   ❌ Private key invalid format (length: {len(private_key)})")
            print("      Should be 64 hex characters without '0x' prefix")
            all_valid = False
    else:
        print("   ❌ Private key not configured")
        all_valid = False

    # Validate network mode
    print("\n🌐 Network Configuration:")
    network_mode = os.getenv('NETWORK_MODE', '').lower()
    if network_mode in ['mainnet', 'testnet']:
        print(f"   ✅ Network mode: {network_mode}")
    else:
        print(f"   ❌ Invalid network mode: {network_mode}")
        print("      Must be 'mainnet' or 'testnet'")
        all_valid = False

    # Test RPC connectivity
    print("\n🔌 RPC Connectivity:")
    if network_mode == 'testnet':
        rpc_url = os.getenv('SCROLL_TESTNET_RPC')
        print(f"   Testing testnet RPC: {rpc_url}")
    else:
        rpc_url = os.getenv('SCROLL_RPC_URL')
        print(f"   Testing mainnet RPC: {rpc_url}")

    if rpc_url:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            if w3.is_connected():
                block = w3.eth.block_number
                print(f"   ✅ RPC connected (latest block: {block})")
            else:
                print("   ❌ RPC connection failed")
                all_valid = False
        except Exception as e:
            print(f"   ❌ RPC connection error: {e}")
            all_valid = False
    else:
        print("   ❌ RPC URL not configured")
        all_valid = False

    # Optional settings
    print("\n⚙️  Optional Settings:")
    optional = {
        'PROFIT_THRESHOLD': ('Minimum profit threshold', float, 0.005),
        'SLIPPAGE_TOLERANCE': ('Maximum slippage tolerance', float, 0.02),
        'MAX_GAS_PRICE': ('Maximum gas price (gwei)', float, 0.1),
        'MIN_LIQUIDITY_USD': ('Minimum pool liquidity (USD)', float, 5000),
    }

    for key, (description, type_func, default) in optional.items():
        value = os.getenv(key)
        if value:
            try:
                parsed = type_func(value)
                print(f"   ✅ {key}: {parsed} ({description})")
            except ValueError:
                print(f"   ⚠️  {key}: Invalid format - using default {default}")
        else:
            print(f"   ℹ️  {key}: Not set - using default {default}")

    # Notification settings
    print("\n📢 Notification Settings:")
    telegram_enabled = os.getenv('ENABLE_TELEGRAM_ALERTS', 'false').lower() == 'true'
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    telegram_chat = os.getenv('TELEGRAM_CHAT_ID')
    discord_webhook = os.getenv('DISCORD_WEBHOOK_URL')

    if telegram_enabled:
        if telegram_token and telegram_chat:
            print(f"   ✅ Telegram: Enabled")
        else:
            print(f"   ⚠️  Telegram: Enabled but missing credentials")
    else:
        print(f"   ℹ️  Telegram: Disabled")

    if discord_webhook:
        if discord_webhook.startswith('https://discord.com/api/webhooks/'):
            print(f"   ✅ Discord: Configured")
        else:
            print(f"   ⚠️  Discord: Invalid webhook URL")
    else:
        print(f"   ℹ️  Discord: Not configured")

    # Chainlink settings
    print("\n🔮 Price Oracle Settings:")
    chainlink_eth = os.getenv('CHAINLINK_ETH_USD')
    if chainlink_eth:
        if Web3.is_address(chainlink_eth):
            print(f"   ✅ Chainlink ETH/USD feed: {chainlink_eth}")
        else:
            print(f"   ❌ Invalid Chainlink address: {chainlink_eth}")
            all_valid = False
    else:
        print(f"   ℹ️  Using default Chainlink feed")

    # Summary
    print("\n" + "=" * 60)
    if all_valid:
        print("✅ Configuration is VALID - Ready to run!")
        print("\n🚀 Next steps:")
        print("   1. Run tests: pytest -v")
        print("   2. Start scanner: python src/scanner.py")
        return True
    else:
        print("❌ Configuration has ERRORS - Please fix them")
        print("\n📖 See config/.env.example for reference")
        return False


if __name__ == '__main__':
    success = validate_config()
    sys.exit(0 if success else 1)
