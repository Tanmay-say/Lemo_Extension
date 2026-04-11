# Real Payment Implementation Required

## Current Status: NOT WORKING
The Buy Now button currently shows an error message. Payment processing is **NOT** implemented.

## What's Needed to Make Smart Contracts Work

### 1. Background Script Handler
**File:** `LEMO-extension/src/background/index.js`

Add a handler for payment requests:

```javascript
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'process_payment') {
    processPayment(message.productData, message.paymentMethod, message.walletAddress)
      .then(result => sendResponse({ success: true, result }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true; // Keep channel open for async
  }
});
```

### 2. Access Page Context from Background
**Problem:** Background script needs to inject ethers.js into page context and call contracts.

**Solution:** Use `chrome.scripting.executeScript()` to inject payment handler into the page.

### 3. Payment Flow Implementation

#### Step 1: Connect to MetaMask in Page Context
```javascript
// In injected script
const provider = new ethers.BrowserProvider(window.ethereum);
const signer = await provider.getSigner();
```

#### Step 2: Check PYUSD Balance
```javascript
const PYUSD_ADDRESS = '0xCaC524BcA292aaade2DF8A05cC58F0a65B1B3bB9';
const token = new ethers.Contract(PYUSD_ADDRESS, ERC20_ABI, provider);
const balance = await token.balanceOf(userAddress);
```

#### Step 3: Approve PaymentProcessor
```javascript
const amount = ethers.parseUnits('10.00', 6); // PYUSD has 6 decimals
const tx = await token.approve(PAYMENT_PROCESSOR_ADDRESS, amount);
await tx.wait();
```

#### Step 4: Process Payment
```javascript
const paymentProcessor = new ethers.Contract(
  PAYMENT_PROCESSOR_ADDRESS,
  PAYMENT_PROCESSOR_ABI,
  signer
);

const receiptData = { /* product details */ };
const receiptCid = await uploadToLighthouse(receiptData);

const tx = await paymentProcessor.processPayment(
  productData.productId,
  amount,
  receiptCid,
  PYUSD_ADDRESS,
  'PYUSD'
);
await tx.wait();
```

### 4. Required Files to Create/Modify

1. **Background Payment Handler**
   - File: `src/background/paymentProcessor.js`
   - Function: `async function processPayment(productData, paymentMethod, walletAddress)`
   - This will inject scripts into page context

2. **Injected Payment Script**
   - File: `src/content/paymentHandler.js` (to be injected)
   - Functions:
     - `connectMetaMask()` - Check connection
     - `checkBalance()` - Verify PYUSD balance
     - `approveTokens()` - Set allowance
     - `processPayment()` - Call smart contract
     - `uploadToLighthouse()` - Store receipt

3. **Update Background Listener**
   - File: `src/background/index.js`
   - Add message listener for 'process_payment'
   - Execute payment handler script in page context

### 5. Integration Points

**ChatWindow.jsx** (Already modified)
- Sends message to background
- Waits for response
- Displays receipt card or error

**BuyCard.jsx**
- Fetches PYUSD balance via walletBridge
- Shows balance or loading state
- Triggers buy flow on button click

### 6. Testing the Implementation

1. **Setup Sepolia Testnet**
   - Connect MetaMask to Sepolia
   - Get test ETH for gas
   - Get test PYUSD tokens

2. **Test Balance Display**
   - Should show actual PYUSD balance
   - Should update when balance changes

3. **Test Payment Flow**
   - Click "Buy with PYUSD"
   - MetaMask popup should appear
   - Approve PYUSD spending
   - Confirm payment transaction
   - Receipt should appear in chat

### 7. Contract Addresses (From deployment-config.json)

```javascript
const PAYMENT_PROCESSOR_ADDRESS = '0x210c251e5a39bd12234d3564ce61168c1bec5922';
const PYUSD_ADDRESS = '0xCaC524BcA292aaade2DF8A05cC58F0a65B1B3bB9';
const LIGHTHOUSE_RECEIPT_ADDRESS = '0xca17ed5b8bc6c80c69b1451e452cdf26453755b5';
```

## Why It's Not Working Now

1. **No Background Handler**: Background script doesn't listen for payment requests
2. **No Page Context Access**: Can't inject scripts to access window.ethereum
3. **No Contract Calls**: PaymentProcessor contract is never called
4. **UI Mockup Only**: Current code just shows errors

## Next Steps

1. Create `src/background/paymentProcessor.js`
2. Create `src/content/paymentHandler.js` (injectable script)
3. Update `src/background/index.js` to listen for payment messages
4. Test with actual Sepolia transactions

## Commands to Test

```bash
# Build extension
cd LEMO-extension && npm run build

# Load in Chrome
# 1. Go to chrome://extensions/
# 2. Enable Developer Mode
# 3. Click "Load unpacked"
# 4. Select the LEMO-extension/dist folder

# Test Payment
# 1. Connect MetaMask to Sepolia
# 2. Ensure PYUSD balance > 0
# 3. Open extension on any page
# 4. Ask AI about a product
# 5. Click "Buy with PYUSD"
# 6. Should see MetaMask popup
```

