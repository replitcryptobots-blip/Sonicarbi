# Flashloan Arbitrage Smart Contracts

This directory contains the smart contracts for executing arbitrage opportunities using Aave V3 flashloans on Scroll network.

## Contracts

### FlashloanArbitrage.sol

Main contract that executes arbitrage trades using Aave V3 flashloans.

**Features:**
- Aave V3 flashloan integration
- Uniswap V2 compatible DEX swaps
- Profit verification and slippage protection
- Owner-only execution (can be modified for automation)
- Reentrancy protection
- Profit withdrawal functions
- Emergency token rescue

**Functions:**
- `executeArbitrage()`: Execute an arbitrage opportunity
- `simulateArbitrage()`: Simulate arbitrage to estimate profit
- `withdrawProfit()`: Withdraw accumulated profits
- `executeOperation()`: Aave V3 flashloan callback (internal)

## Deployment

### Prerequisites

1. Install dependencies:
```bash
npm install --save-dev hardhat @nomicfoundation/hardhat-toolbox
npm install @aave/core-v3 @openzeppelin/contracts
```

2. Create `hardhat.config.js`:
```javascript
require("@nomicfoundation/hardhat-toolbox");

module.exports = {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200
      }
    }
  },
  networks: {
    scroll: {
      url: process.env.SCROLL_RPC_URL,
      accounts: [process.env.PRIVATE_KEY]
    },
    scrollTestnet: {
      url: process.env.SCROLL_TESTNET_RPC,
      accounts: [process.env.PRIVATE_KEY]
    }
  }
};
```

### Deployment Script

Create `scripts/deploy.js`:
```javascript
const hre = require("hardhat");

async function main() {
  // Aave V3 Pool addresses
  const AAVE_POOL_SCROLL = "0x11fCfe756c05AD438e312a7fd934381537D3cFfe"; // Scroll mainnet
  const AAVE_POOL_TESTNET = "0x48914C788295b5db23aF2b5F0B3BE775C4eA9440"; // Scroll Sepolia testnet

  const network = hre.network.name;
  const poolAddress = network === "scroll" ? AAVE_POOL_SCROLL : AAVE_POOL_TESTNET;

  console.log(`Deploying FlashloanArbitrage to ${network}...`);
  console.log(`Aave Pool: ${poolAddress}`);

  const FlashloanArbitrage = await hre.ethers.getContractFactory("FlashloanArbitrage");
  const flashloan = await FlashloanArbitrage.deploy(poolAddress);

  await flashloan.waitForDeployment();

  const address = await flashloan.getAddress();
  console.log(`FlashloanArbitrage deployed to: ${address}`);

  // Verify on block explorer (if not local)
  if (network !== "hardhat" && network !== "localhost") {
    console.log("Waiting for block confirmations...");
    await flashloan.deploymentTransaction().wait(6);

    console.log("Verifying contract...");
    await hre.run("verify:verify", {
      address: address,
      constructorArguments: [poolAddress],
    });
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
```

### Deploy to Scroll Testnet

```bash
npx hardhat run scripts/deploy.js --network scrollTestnet
```

### Deploy to Scroll Mainnet

```bash
npx hardhat run scripts/deploy.js --network scroll
```

## Usage

### From Python Script

```python
from web3 import Web3
import json

w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Load contract
with open('contracts/FlashloanArbitrage.json', 'r') as f:
    abi = json.load(f)['abi']

contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=abi)

# Prepare arbitrage parameters
params = {
    'tokenBorrow': WETH_ADDRESS,
    'amount': w3.to_wei(1, 'ether'),
    'tokenTarget': USDC_ADDRESS,
    'buyDex': SYNCSWAP_ROUTER,
    'sellDex': ZEBRA_ROUTER,
    'minProfit': w3.to_wei(0.01, 'ether'),
    'deadline': int(time.time()) + 300
}

# Simulate first
expected_profit = contract.functions.simulateArbitrage(params).call()
print(f"Expected profit: {w3.from_wei(expected_profit, 'ether')} ETH")

# Execute if profitable
if expected_profit > params['minProfit']:
    tx = contract.functions.executeArbitrage(params).build_transaction({
        'from': account.address,
        'nonce': w3.eth.get_transaction_count(account.address),
        'gas': 500000,
        'gasPrice': w3.eth.gas_price
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    print(f"Arbitrage executed: {receipt['transactionHash'].hex()}")
```

## Security Considerations

1. **Owner-only execution**: Only the contract owner can execute arbitrage trades
2. **Reentrancy protection**: Uses OpenZeppelin's ReentrancyGuard
3. **Profit verification**: Ensures minimum profit before completing flashloan
4. **Deadline protection**: All trades have deadlines to prevent stale transactions
5. **Slippage protection**: Consider adding minimum output amounts for swaps

## Important Notes

- Always test on testnet first
- Start with small amounts
- Monitor gas costs
- Ensure sufficient profit to cover flashloan fees (0.09% on Aave V3)
- Keep private keys secure
- Consider upgradeability for production use

## Aave V3 Addresses on Scroll

- **Mainnet Pool**: `0x11fCfe756c05AD438e312a7fd934381537D3cFfe`
- **Testnet Pool**: `0x48914C788295b5db23aF2b5F0B3BE775C4eA9440`

## License

MIT
