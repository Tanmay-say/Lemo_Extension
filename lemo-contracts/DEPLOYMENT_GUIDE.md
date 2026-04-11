# 🚀 Deployment Guide - Quick Start

This guide will walk you through deploying and configuring the Lighthouse + FVM integration contracts.

## 📋 Prerequisites

- [ ] MetaMask wallet installed with some test ETH on Sepolia
- [ ] MetaMask configured with Filecoin Calibration testnet
- [ ] Lighthouse account and API key ([Get it here](https://files.lighthouse.storage/))
- [ ] LEMO tokens on Sepolia (address: `0x14572da77700C59D2f8D61a3C4b25744D6dCde8D`)

## 🏗️ Step 1: Deploy Smart Contracts

### A. Deploy to Sepolia

1. Open [Remix IDE](https://remix.ethereum.org)
2. Upload contract files from `contracts/` folder
3. Compile with Solidity 0.8.18+
4. Switch MetaMask to Sepolia network

**Deploy in this order:**

```
1. LighthouseReceipt.sol
   ✓ Click Deploy
   ✓ Copy deployed address
   ✓ Save to .env as: SEPOLIA_LIGHTHOUSE_RECEIPT_ADDRESS

2. TrustlessAgentFeedback.sol
   ✓ Click Deploy
   ✓ Copy deployed address
   ✓ Save to .env as: SEPOLIA_TRUSTLESS_AGENT_FEEDBACK_ADDRESS

3. AgentRegistry.sol
   ✓ Click Deploy
   ✓ Copy deployed address
   ✓ Save to .env as: SEPOLIA_AGENT_REGISTRY_ADDRESS
```

### B. Deploy to Filecoin Calibration

1. Switch MetaMask to Calibration network
2. Deploy `LighthouseReceipt.sol`
3. Save address to .env as: `CALIBRATION_LIGHTHOUSE_RECEIPT_ADDRESS`

### C. Deploy FVM Shop Contract

1. Clone: `https://github.com/ethonline25-lemo/filecoin-shop-example`
2. Follow deployment instructions in that repo
3. Save address to .env as: `CALIBRATION_FVM_SHOP_ADDRESS`

## 💰 Step 2: Fund the Feedback Contract

The `TrustlessAgentFeedback` contract needs LEMO tokens to reward users.

### Quick Fund (Recommended: 100M LEMO for 100 feedbacks)

1. In Remix, load LEMO token at: `0x14572dA77700c59D2F8D61a3c4B25744D6DcDE8D`
2. Call `approve(feedbackContractAddress, 100000000000000000000000000)`
   - `feedbackContractAddress`: Your deployed TrustlessAgentFeedback address
   - Amount: 100000000 * 10^18 (100M LEMO)
3. In TrustlessAgentFeedback contract, call `fundContract(100000000000000000000000000)`
4. Verify: call `getLEMOBalance()` - should return `100000000000000000000000000`

**Calculation:**
- Each feedback: 1,000,000 LEMO (10^24 wei)
- For 100 feedbacks: 100,000,000 LEMO (10^26 wei)

## ⚙️ Step 3: Configure Environment

1. Copy the template:
   ```bash
   cp .env.local .env
   ```

2. Edit `.env` and fill in:
   ```bash
   # Contract addresses from Step 1
   SEPOLIA_LIGHTHOUSE_RECEIPT_ADDRESS=0xYourDeployedAddress
   SEPOLIA_TRUSTLESS_AGENT_FEEDBACK_ADDRESS=0xYourDeployedAddress
   SEPOLIA_AGENT_REGISTRY_ADDRESS=0xYourDeployedAddress
   CALIBRATION_LIGHTHOUSE_RECEIPT_ADDRESS=0xYourDeployedAddress
   
   # Lighthouse API key from lighthouse.storage
   LIGHTHOUSE_API_KEY=your-actual-api-key-here
   ```

3. Update `LEMO-extension/src/utils/contractConfig.js`:
   ```javascript
   export const CONTRACT_ADDRESSES = {
     sepolia: {
       LighthouseReceipt: '0xYourAddress',
       TrustlessAgentFeedback: '0xYourAddress',
       AgentRegistry: '0xYourAddress',
       LEMOToken: '0x14572da77700C59D2f8D61a3C4b25744D6dCde8D',
     },
     calibration: {
       LighthouseReceipt: '0xYourAddress',
     }
   };
   
   export const LIGHTHOUSE_CONFIG = {
     apiKey: 'your-lighthouse-api-key'
   };
   ```

## 🔨 Step 4: Build Extension

```bash
cd LEMO-extension
npm run build
```

Load the extension in Chrome:
1. Go to `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select the `LEMO-extension/dist` folder

## ✅ Step 5: Test the Integration

### Test 1: Buy Now Flow
1. Open extension on any e-commerce page
2. Connect your wallet
3. Click "Buy Now" on a product
4. Approve MetaMask transaction
5. **Expected:** Receipt card appears in chat with IPFS link

### Test 2: Submit Feedback
1. Click "Submit Feedback" on receipt card
2. Rate the product (1-5 stars)
3. Write a comment
4. Click "Submit & Earn LEMO"
5. Approve MetaMask transaction
6. **Expected:** 1,000,000 LEMO transferred to your wallet

### Test 3: View Rewards
1. Go to Wallet tab in extension
2. **Expected:** Golden LEMO Rewards card showing:
   - Current LEMO balance
   - Total rewards earned
   - Recent rewards list

## 🐛 Troubleshooting

### "Contract has insufficient LEMO tokens for reward"
**Solution:** Fund the contract (see Step 2)

### "Lighthouse upload failed"
**Solution:** Check API key in `.env` and `contractConfig.js`

### "Transaction failed"
**Solution:** 
- Ensure you have enough ETH/tFIL for gas
- Verify you're on correct network (Sepolia or Calibration)
- Check contract addresses are correct

### "LEMO balance not updating"
**Solution:**
- Wait for transaction confirmation (15-30 seconds)
- Refresh the extension
- Check transaction on Etherscan

## 📊 Monitoring

### View Receipts
- Sepolia: `https://sepolia.etherscan.io/address/[LighthouseReceiptAddress]`
- IPFS: `https://gateway.lighthouse.storage/ipfs/[CID]`

### View LEMO Transfers
- Token: `https://sepolia.etherscan.io/token/0x14572da77700C59D2f8D61a3C4b25744D6dCde8D`
- Your Address: `https://sepolia.etherscan.io/token/0x14572da77700C59D2f8D61a3C4b25744D6dCde8D?a=[YourAddress]`

### Check Contract Balance
In Remix, call `getLEMOBalance()` on TrustlessAgentFeedback contract.

## 🎯 Success Criteria

- ✅ All contracts deployed and verified
- ✅ Feedback contract funded with LEMO
- ✅ Buy Now creates receipt on-chain
- ✅ Receipt viewable on IPFS
- ✅ Feedback submission earns LEMO
- ✅ LEMO balance visible in wallet tab
- ✅ All transactions confirmed on explorers

## 📞 Need Help?

1. Check the main [README.md](./README.md) for detailed instructions
2. Review contract comments in source code
3. Test on Sepolia before Calibration
4. Verify all addresses are correct in `.env`

---

**🎉 Congratulations!** Your Lighthouse + FVM integration is now live!

