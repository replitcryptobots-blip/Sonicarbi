import os
import shutil
from pathlib import Path
from dotenv import load_dotenv

# Load .env from config directory relative to this file
config_dir = Path(__file__).parent
env_path = config_dir / '.env'
env_example_path = config_dir / '.env.example'

# Auto-create .env from .env.example if it doesn't exist
if not env_path.exists() and env_example_path.exists():
    print(f"[INFO] .env file not found. Creating from .env.example...")
    shutil.copy(env_example_path, env_path)
    print(f"[INFO] Created {env_path}")
    print(f"[INFO] Please edit {env_path} and configure your settings (especially PRIVATE_KEY if trading)")
elif not env_path.exists() and not env_example_path.exists():
    raise FileNotFoundError(
        f"Neither .env nor .env.example found in {config_dir}. "
        f"Please create a .env file with your configuration."
    )

load_dotenv(env_path)

class Config:
    # Network
    SCROLL_RPC_URL = os.getenv('SCROLL_RPC_URL')
    SCROLL_TESTNET_RPC = os.getenv('SCROLL_TESTNET_RPC')
    CHAIN_ID = int(os.getenv('SCROLL_CHAIN_ID', 534352))
    NETWORK_MODE = os.getenv('NETWORK_MODE', 'testnet')

    # Get active RPC based on mode
    ACTIVE_RPC = SCROLL_TESTNET_RPC if NETWORK_MODE == 'testnet' else SCROLL_RPC_URL
    ACTIVE_CHAIN_ID = 534351 if NETWORK_MODE == 'testnet' else CHAIN_ID

    # Keys
    PRIVATE_KEY = os.getenv('PRIVATE_KEY')

    # Contracts
    FLASHLOAN_CONTRACT = os.getenv('FLASHLOAN_CONTRACT')
    AAVE_V3_POOL = os.getenv('AAVE_V3_POOL')

    # Database
    DATABASE_URL = os.getenv('DATABASE_URL')

    # Trading
    PROFIT_THRESHOLD = float(os.getenv('PROFIT_THRESHOLD', 0.005))
    MAX_GAS_PRICE = float(os.getenv('MAX_GAS_PRICE', 0.1))
    MIN_LIQUIDITY_USD = float(os.getenv('MIN_LIQUIDITY_USD', 5000))
    SLIPPAGE_TOLERANCE = float(os.getenv('SLIPPAGE_TOLERANCE', 0.02))

    # Minimum profit in USD to execute trade (dust threshold)
    MIN_PROFIT_USD = float(os.getenv('MIN_PROFIT_USD', 1.0))

    # Maximum trade size in USD (safety limit)
    MAX_TRADE_SIZE_USD = float(os.getenv('MAX_TRADE_SIZE_USD', 10000.0))

    # Monitoring
    ENABLE_TELEGRAM = os.getenv('ENABLE_TELEGRAM_ALERTS', 'false').lower() == 'true'
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT = os.getenv('TELEGRAM_CHAT_ID')
    DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

    # Chainlink Price Feeds (Scroll Mainnet)
    CHAINLINK_ETH_USD = os.getenv('CHAINLINK_ETH_USD', '0x6bF14CB0A831078629D993FDeBcB182b21A8774C')

    # Price validation bounds
    MIN_ETH_PRICE_USD = float(os.getenv('MIN_ETH_PRICE_USD', 100.0))
    MAX_ETH_PRICE_USD = float(os.getenv('MAX_ETH_PRICE_USD', 20000.0))
    MAX_PRICE_AGE_SECONDS = int(os.getenv('MAX_PRICE_AGE_SECONDS', 600))  # 10 minutes

    # Debug
    DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'

    # Multi-Hop Routing
    ENABLE_MULTI_HOP_ROUTING = os.getenv('ENABLE_MULTI_HOP_ROUTING', 'true').lower() == 'true'
    MAX_ROUTING_HOPS = int(os.getenv('MAX_ROUTING_HOPS', 2))

    # Private Mempool (MEV Protection)
    USE_PRIVATE_MEMPOOL = os.getenv('USE_PRIVATE_MEMPOOL', 'false').lower() == 'true'
    FLASHBOTS_RPC_URL = os.getenv('FLASHBOTS_RPC_URL')  # e.g., https://relay.flashbots.net (if available)
    PRIVATE_RPC_URL = os.getenv('PRIVATE_RPC_URL')  # Private RPC with direct builder access

config = Config()
