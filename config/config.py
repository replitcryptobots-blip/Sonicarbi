import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from config directory relative to this file
config_dir = Path(__file__).parent
env_path = config_dir / '.env'
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

    # Monitoring
    ENABLE_TELEGRAM = os.getenv('ENABLE_TELEGRAM_ALERTS', 'false').lower() == 'true'
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT = os.getenv('TELEGRAM_CHAT_ID')

config = Config()
