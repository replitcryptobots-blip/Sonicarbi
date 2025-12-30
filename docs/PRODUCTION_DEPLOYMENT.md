# Production Deployment Checklist

**CRITICAL**: This is a production deployment checklist for running Sonicarbi on Scroll mainnet with real funds. Follow every step carefully.

---

## Pre-Deployment Checklist

### 1. Testing & Validation ✅

- [ ] **All tests passing**
  ```bash
  pytest -v
  pytest --cov=src --cov=utils --cov-report=html
  ```
  - Minimum 80% code coverage
  - All unit tests passing
  - All integration tests passing

- [ ] **Testnet validation**
  - Run on Scroll Sepolia testnet for minimum 48 hours
  - Monitor for opportunities and execution
  - Verify profit calculations are correct
  - Confirm gas estimates are accurate
  - Test failure recovery (circuit breaker, RPC failures)

- [ ] **Configuration validation**
  ```bash
  python scripts/validate_config.py
  ```
  - All required config present
  - RPC connectivity verified
  - Wallet funded with ETH for gas
  - Contract addresses verified

- [ ] **Smart contract audit**
  - Flashloan contract deployed and verified
  - Contract ownership transferred to bot wallet
  - Emergency pause functionality tested
  - Withdraw functions tested

### 2. Security Hardening ✅

- [ ] **Private key security**
  - Use hardware wallet or secure key management system
  - Never commit `.env` file to version control
  - Rotate keys regularly
  - Use separate wallet for production (never reuse testnet wallet)

- [ ] **Contract security**
  - Contract verified on Scrollscan
  - onlyOwner modifiers on critical functions
  - Reentrancy guards in place
  - Slippage protection enabled
  - Emergency pause tested

- [ ] **RPC security**
  - Use dedicated RPC endpoint (not public)
  - Implement rate limiting
  - Fallback RPC configured
  - Monitor RPC health

- [ ] **Operational security**
  - 2FA enabled on all accounts
  - SSH keys only (no passwords)
  - Firewall configured
  - Auto-updates enabled for security patches

### 3. Risk Management ✅

- [ ] **Position sizing**
  - Start with small amounts (0.01-0.1 ETH equivalent)
  - Gradually increase based on performance
  - Never risk more than you can afford to lose

- [ ] **Circuit breakers**
  - Max failures: 5 in 5 minutes
  - Cooldown period: 10 minutes
  - Test failure scenarios

- [ ] **Slippage protection**
  - Max slippage: 2% (configurable)
  - Frontrun detection enabled
  - Sandwich attack monitoring

- [ ] **Gas limits**
  - Max gas price: 0.1 gwei (Scroll is cheap)
  - Gas estimation buffer: 20%
  - Monitor gas price trends

### 4. Monitoring & Alerting ✅

- [ ] **Telegram alerts**
  - Opportunities found
  - Trades executed
  - Errors and failures
  - Daily summary reports

- [ ] **Discord webhooks**
  - System status updates
  - Performance metrics
  - Alert on circuit breaker trips

- [ ] **Logging**
  - Structured logging enabled
  - Log rotation configured (10MB max, 5 backups)
  - Logs backed up daily
  - Error tracking (Sentry/similar)

- [ ] **Metrics tracking**
  - Success rate
  - Profit/loss
  - Gas costs
  - Execution time
  - RPC latency

### 5. Infrastructure ✅

- [ ] **Server requirements**
  - Minimum 2GB RAM
  - 20GB+ disk space
  - Python 3.11+
  - PostgreSQL (optional but recommended)

- [ ] **Network**
  - Low-latency connection to Scroll RPC
  - Stable internet (99.9%+ uptime)
  - DDoS protection
  - Backup connectivity

- [ ] **Backup & Recovery**
  - Database backups (if using DB)
  - Config backups
  - Private key backup (encrypted, offline storage)
  - Disaster recovery plan documented

---

## Deployment Steps

### Step 1: Environment Setup

1. **Create production environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure environment**
   ```bash
   cp config/.env.example config/.env
   nano config/.env
   ```

   **Critical settings:**
   ```bash
   # Network
   NETWORK_MODE=mainnet
   SCROLL_RPC_URL=https://your-dedicated-rpc.scroll.io

   # Security
   PRIVATE_KEY=your_production_private_key_64_hex

   # Contracts
   FLASHLOAN_CONTRACT=0xYourDeployedFlashloanContractAddress
   AAVE_V3_POOL=0x11fCfe756c05AD438e312a7fd934381537D3cFfe

   # Risk management
   PROFIT_THRESHOLD=0.01  # 1% minimum
   SLIPPAGE_TOLERANCE=0.02  # 2% maximum
   MAX_GAS_PRICE=0.1  # gwei
   MIN_LIQUIDITY_USD=10000  # $10k minimum pool liquidity

   # Notifications
   ENABLE_TELEGRAM_ALERTS=true
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   DISCORD_WEBHOOK_URL=your_webhook_url
   ```

3. **Validate configuration**
   ```bash
   python scripts/validate_config.py
   ```

### Step 2: Smart Contract Deployment

1. **Deploy flashloan contract** (if not already deployed)
   ```bash
   cd contracts
   npm install
   npx hardhat run scripts/deploy.js --network scroll
   ```

2. **Verify contract**
   ```bash
   npx hardhat verify --network scroll DEPLOYED_CONTRACT_ADDRESS AAVE_POOL_ADDRESS
   ```

3. **Test contract**
   - Call `simulateArbitrage()` with test parameters
   - Verify owner is set correctly
   - Test pause/unpause functionality

### Step 3: Initial Testing

1. **Dry run mode** (no actual execution)
   - Scanner runs and finds opportunities
   - Simulations execute successfully
   - No transactions sent

   ```python
   # In scanner or executor initialization
   executor = ArbitrageExecutor(w3, dry_run=True)
   ```

2. **Monitor for 1 hour**
   - Verify opportunities are detected
   - Check simulation accuracy
   - Confirm no false positives

3. **Review metrics**
   - How many opportunities per hour?
   - What's the average profit?
   - Are gas costs reasonable?

### Step 4: Live Trading (Gradual Rollout)

**Phase 1: Minimal Exposure (24 hours)**
- Position size: 0.01 ETH equivalent
- Profit threshold: 2%
- Monitor every 4 hours

**Phase 2: Small Scale (1 week)**
- Position size: 0.1 ETH equivalent
- Profit threshold: 1%
- Monitor twice daily

**Phase 3: Normal Operations**
- Position size: 0.5-1.0 ETH equivalent
- Profit threshold: 0.5-1%
- Automated monitoring with alerts

### Step 5: Ongoing Monitoring

**Daily Tasks:**
- [ ] Check system status
- [ ] Review trades from last 24h
- [ ] Verify profit/loss matches expectations
- [ ] Check log files for errors
- [ ] Monitor gas costs

**Weekly Tasks:**
- [ ] Review performance metrics
- [ ] Optimize parameters if needed
- [ ] Update DEX configurations
- [ ] Check for smart contract updates
- [ ] Backup database

**Monthly Tasks:**
- [ ] Full security audit
- [ ] Review and rotate keys
- [ ] Update dependencies
- [ ] Performance optimization
- [ ] Disaster recovery test

---

## Emergency Procedures

### Circuit Breaker Tripped

**Symptoms:**
- Repeated execution failures
- Message: "Circuit breaker tripped"

**Actions:**
1. Check logs for root cause
2. Verify RPC connectivity
3. Check wallet balance (gas funds)
4. Verify contract hasn't been paused
5. Wait for cooldown period (10 min)
6. Test with dry run before resuming

### Contract Exploit Detected

**IMMEDIATE ACTIONS:**
1. **Pause contract**
   ```bash
   # Use flashloan contract's pause() function
   ```

2. **Stop bot**
   ```bash
   pkill -f "python.*scanner"
   ```

3. **Withdraw funds**
   ```bash
   # Use contract's withdrawProfit() function
   ```

4. **Investigate**
   - Review transaction history
   - Check for unauthorized calls
   - Analyze attack vector

5. **Notify team**
   - Post-mortem report
   - Security patch
   - Resume only after fix verified

### RPC Failure

**Symptoms:**
- Connection timeouts
- Stale block data
- Failed transactions

**Actions:**
1. Check RPC status page
2. Switch to backup RPC (configure in `.env`)
3. Reduce request rate if rate-limited
4. Contact RPC provider if persistent

### Sandwich Attack Detected

**Symptoms:**
- Trades executing but lower profit than expected
- Transactions frontrun consistently

**Actions:**
1. Increase slippage protection
2. Use private mempool (if available)
3. Implement flashbots/MEV protection
4. Reduce position sizes
5. Increase minimum profit threshold

---

## Performance Optimization

### Gas Optimization
- Monitor average gas cost per trade
- Adjust `MAX_GAS_PRICE` based on network conditions
- Use dynamic gas estimation
- Bundle transactions when possible

### Profit Optimization
- Adjust `PROFIT_THRESHOLD` based on market conditions
- Monitor success rate vs threshold
- Consider multi-hop routes
- Optimize DEX selection

### Latency Optimization
- Use dedicated/paid RPC endpoint
- Deploy bot close to RPC server (same region)
- Optimize code (async operations)
- Reduce unnecessary RPC calls

---

## Success Metrics

### KPIs to Track

**Execution Metrics:**
- Opportunities detected per hour
- Execution success rate (target: >80%)
- Average profit per trade
- Gas cost as % of profit (target: <20%)

**Financial Metrics:**
- Total profit (USD)
- Net profit after gas (USD)
- ROI (%)
- Sharpe ratio

**System Metrics:**
- Uptime (target: 99.9%)
- RPC latency (target: <100ms)
- Error rate (target: <5%)
- Circuit breaker trips (target: <1/day)

---

## Troubleshooting

### Common Issues

**"Insufficient Profit" errors**
- Profit calculation might be off
- Gas prices higher than expected
- Slippage too high
- **Solution:** Review calculation logic, adjust thresholds

**"Slippage Exceeded" errors**
- Pool liquidity too low
- Large position size
- Price moving too fast
- **Solution:** Reduce position size, increase min liquidity

**"Transaction Reverted"**
- Simulation passed but execution failed
- Likely frontrun or sandwich attack
- **Solution:** Implement MEV protection, reduce slippage tolerance

**No opportunities found**
- Market efficient (good!)
- Profit threshold too high
- DEX configs outdated
- **Solution:** Lower threshold slightly, update configs

---

## Maintenance Schedule

### Daily
- 09:00 UTC: Review overnight performance
- 18:00 UTC: Check system health

### Weekly
- Monday: Performance review
- Wednesday: Update DEX configs if needed
- Friday: Backup database

### Monthly
- 1st: Security audit
- 15th: Dependency updates
- Last day: Monthly report

---

## Contacts & Resources

### Support
- GitHub Issues: https://github.com/yourusername/Sonicarbi/issues
- Telegram: Your support channel
- Discord: Your community server

### Scroll Resources
- Mainnet RPC: https://rpc.scroll.io
- Testnet RPC: https://sepolia-rpc.scroll.io
- Explorer: https://scrollscan.com
- Status: https://status.scroll.io

### Aave V3 on Scroll
- Pool: 0x11fCfe756c05AD438e312a7fd934381537D3cFfe
- Docs: https://docs.aave.com/developers/

---

**REMEMBER:**

🔴 **START SMALL** - Test with minimal funds first

🔴 **MONITOR CONSTANTLY** - Especially in first 48 hours

🔴 **HAVE AN EXIT PLAN** - Know how to pause and withdraw funds

🔴 **NEVER RISK MORE THAN YOU CAN AFFORD TO LOSE**

---

*Last Updated: 2025-12-30*
*Version: 1.0 (Production)*
