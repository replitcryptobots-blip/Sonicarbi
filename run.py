#!/usr/bin/env python3
"""
Main entry point for Sonicarbi Flashloan Arbitrage Bot.

Usage:
    python run.py
"""

import asyncio
from src.scanner import ScrollDEXScanner

def main():
    """Run the scanner"""
    print("Starting Sonicarbi Flashloan Arbitrage Bot...")
    scanner = ScrollDEXScanner()
    asyncio.run(scanner.run_continuous_scan())

if __name__ == "__main__":
    main()
