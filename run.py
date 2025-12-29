#!/usr/bin/env python3
"""
Main entry point for Sonicarbi Flashloan Arbitrage Bot.

Usage:
    python run.py
"""

import asyncio
import sys
from src.scanner import ScrollDEXScanner

def main():
    """Run the scanner"""
    try:
        print("Starting Sonicarbi Flashloan Arbitrage Bot...")
        scanner = ScrollDEXScanner()
        asyncio.run(scanner.run_continuous_scan())
    except KeyboardInterrupt:
        print("\n\nShutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nFatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
