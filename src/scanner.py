import asyncio
import json
import os
import sys
from pathlib import Path
from web3 import Web3
from datetime import datetime
from colorama import Fore, Style, init

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config import config

init(autoreset=True)

class ScrollDEXScanner:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(config.ACTIVE_RPC))
        self.load_dex_configs()
        self.opportunities = []

        # Uniswap V2 Router ABI (minimal)
        self.router_abi = json.loads('[{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"}],"name":"getAmountsOut","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"view","type":"function"}]')

    def load_dex_configs(self):
        """Load DEX configurations from JSON file"""
        config_path = Path(__file__).parent.parent / 'config' / 'dex_configs.json'
        with open(config_path, 'r') as f:
            data = json.load(f)
        self.dexes = data['scroll']['dexes']
        self.tokens = data['scroll']['common_tokens']

    def get_price(self, dex, token_in, token_out, amount_in):
        """Get price from DEX"""
        try:
            router = self.w3.eth.contract(
                address=Web3.to_checksum_address(dex['router']),
                abi=self.router_abi
            )

            path = [
                Web3.to_checksum_address(token_in['address']),
                Web3.to_checksum_address(token_out['address'])
            ]

            # Convert amount to Wei based on token decimals
            amount_in_wei = int(amount_in * (10 ** token_in['decimals']))

            amounts = router.functions.getAmountsOut(amount_in_wei, path).call()
            amount_out_wei = amounts[-1]

            # Convert back from Wei
            amount_out = amount_out_wei / (10 ** token_out['decimals'])

            return amount_out

        except Exception as e:
            # print(f"{Fore.RED}Error getting price from {dex['name']}: {str(e)}")
            return None

    async def scan_pair(self, token_in, token_out, amount=1.0):
        """Scan a token pair across all DEXes"""
        prices = {}

        for dex in self.dexes:
            if dex['type'] == 'uniswap_v2':  # Skip concentrated liquidity for now
                price = self.get_price(dex, token_in, token_out, amount)
                if price:
                    prices[dex['name']] = {
                        'price': price,
                        'router': dex['router'],
                        'fee': dex['fee']
                    }

        # Find arbitrage opportunities
        if len(prices) >= 2:
            await self.find_arbitrage(token_in, token_out, prices, amount)

    async def find_arbitrage(self, token_in, token_out, prices, amount):
        """Find profitable arbitrage opportunities"""
        dex_names = list(prices.keys())

        for i, dex1 in enumerate(dex_names):
            for dex2 in dex_names[i+1:]:
                price1 = prices[dex1]['price']
                price2 = prices[dex2]['price']

                # Check both directions for arbitrage
                # Direction 1: Buy on dex1, sell on dex2
                if price1 < price2:
                    self._check_arbitrage_direction(
                        token_in, token_out, dex1, dex2,
                        price1, price2, prices[dex1]['fee'],
                        prices[dex2]['fee'], amount
                    )

                # Direction 2: Buy on dex2, sell on dex1
                elif price2 < price1:
                    self._check_arbitrage_direction(
                        token_in, token_out, dex2, dex1,
                        price2, price1, prices[dex2]['fee'],
                        prices[dex1]['fee'], amount
                    )

    def _check_arbitrage_direction(self, token_in, token_out, buy_dex, sell_dex,
                                   buy_price, sell_price, buy_fee, sell_fee, amount):
        """Check if arbitrage is profitable in a specific direction"""
        # Calculate profit
        profit = sell_price - buy_price
        profit_pct = (profit / buy_price) * 100

        # Account for fees
        total_fees = buy_fee + sell_fee
        net_profit_pct = profit_pct - (total_fees * 100)

        # Estimate gas cost (Scroll is cheap: ~0.01 gwei avg)
        gas_estimate = 250000  # Conservative estimate
        gas_price_gwei = 0.02  # Scroll average
        gas_cost_eth = (gas_estimate * gas_price_gwei) / 1e9
        gas_cost_usd = gas_cost_eth * 3500  # Assume ETH = $3500

        # Calculate net profit in USD
        gross_profit_usd = (net_profit_pct / 100) * amount * buy_price
        net_profit_usd = gross_profit_usd - gas_cost_usd
        net_profit_pct_after_gas = (net_profit_usd / (amount * buy_price)) * 100

        if net_profit_pct_after_gas >= (config.PROFIT_THRESHOLD * 100):
            opportunity = {
                'timestamp': datetime.now().isoformat(),
                'token_in': token_in['symbol'],
                'token_out': token_out['symbol'],
                'buy_dex': buy_dex,
                'sell_dex': sell_dex,
                'buy_price': buy_price,
                'sell_price': sell_price,
                'profit_pct': round(net_profit_pct_after_gas, 4),
                'profit_usd': round(net_profit_usd, 2),
                'amount': amount
            }

            self.opportunities.append(opportunity)
            self.log_opportunity(opportunity)

    def log_opportunity(self, opp):
        """Log opportunity to console"""
        print(f"\n{Fore.GREEN}{'='*60}")
        print(f"{Fore.YELLOW}🎯 ARBITRAGE OPPORTUNITY FOUND!")
        print(f"{Fore.CYAN}Time: {opp['timestamp']}")
        print(f"{Fore.WHITE}Pair: {opp['token_in']} → {opp['token_out']}")
        print(f"{Fore.WHITE}Buy on: {opp['buy_dex']} @ {opp['buy_price']:.6f}")
        print(f"{Fore.WHITE}Sell on: {opp['sell_dex']} @ {opp['sell_price']:.6f}")
        print(f"{Fore.GREEN}Profit: {opp['profit_pct']:.3f}% (${opp['profit_usd']})")
        print(f"{Fore.GREEN}{'='*60}\n")

    async def run_continuous_scan(self):
        """Continuously scan for opportunities"""
        print(f"{Fore.MAGENTA}{'='*60}")
        print(f"{Fore.MAGENTA}🚀 Scroll Flashloan Arbitrage Scanner Started")
        print(f"{Fore.MAGENTA}Network: {config.NETWORK_MODE.upper()}")
        print(f"{Fore.MAGENTA}RPC: {config.ACTIVE_RPC}")
        print(f"{Fore.MAGENTA}Scanning {len(self.dexes)} DEXes | {len(self.tokens)} tokens")
        print(f"{Fore.MAGENTA}Profit Threshold: {config.PROFIT_THRESHOLD*100}%")
        print(f"{Fore.MAGENTA}{'='*60}\n")

        scan_count = 0
        while True:
            scan_count += 1
            print(f"{Fore.BLUE}[Scan #{scan_count}] {datetime.now().strftime('%H:%M:%S')}")

            # Scan all token pairs
            for i, token_in in enumerate(self.tokens):
                for token_out in self.tokens[i+1:]:
                    await self.scan_pair(token_in, token_out, amount=1.0)

            print(f"{Fore.WHITE}Scan complete. Opportunities found: {len(self.opportunities)}")

            # Wait before next scan
            await asyncio.sleep(3)  # Scan every 3 seconds

async def main():
    scanner = ScrollDEXScanner()
    await scanner.run_continuous_scan()

if __name__ == "__main__":
    asyncio.run(main())
