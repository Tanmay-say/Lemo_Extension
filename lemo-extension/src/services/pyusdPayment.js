// LEMO-extension/src/services/pyusdPayment.js

import { ethers } from 'ethers';
import { CONTRACT_ADDRESSES, TOKENS, ABIS, MERCHANT_WALLET } from '../utils/contractConfig';

/**
 * @notice Uploads receipt data to Lighthouse and returns CID
 * @param {object} receiptData The receipt data to upload
 * @returns {Promise<string>} The IPFS CID
 */
async function uploadReceiptToLighthouse(receiptData) {
  try {
    const LIGHTHOUSE_API_KEY = '33aad03e.bb3506b68665403b80cb4d30fc6129e4';
    const response = await fetch('https://node.lighthouse.storage/api/v0/add', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${LIGHTHOUSE_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(receiptData)
    });
    
    if (!response.ok) {
      throw new Error(`Lighthouse upload failed: ${response.statusText}`);
    }
    
    const data = await response.json();
    return data.Hash || data.cid;
  } catch (error) {
    console.error('[PYUSD Payment] Lighthouse upload error:', error);
    // Fallback to mock CID for testing
    return `Qm${Math.random().toString(36).substring(2, 15)}${Math.random().toString(36).substring(2, 15)}`;
  }
}

/**
 * @notice Checks the user's PYUSD balance
 * @param {string} walletAddress The user's wallet address
 * @param {ethers.Provider} provider The ethers.js provider
 * @returns {Promise<ethers.BigNumber>} The PYUSD balance
 */
export async function checkPYUSDBalance(walletAddress, provider) {
  try {
    const pyusdToken = TOKENS.sepolia.PYUSD;
    const tokenContract = new ethers.Contract(pyusdToken.address, ABIS.ERC20, provider);
    const balance = await tokenContract.balanceOf(walletAddress);
    console.log(`[PYUSD Payment] User balance: ${ethers.formatUnits(balance, pyusdToken.decimals)} PYUSD`);
    return balance;
  } catch (error) {
    console.error('[PYUSD Payment] Error checking PYUSD balance:', error);
    throw new Error(`Failed to check PYUSD balance: ${error.message}`);
  }
}

/**
 * @notice Approves the PaymentProcessor contract to spend PYUSD
 * @param {string} spenderAddress The PaymentProcessor contract address
 * @param {ethers.BigNumber} amount The amount to approve
 * @param {ethers.Signer} signer The ethers.js signer
 * @returns {Promise<ethers.ContractReceipt>} The transaction receipt
 */
export async function approvePYUSD(spenderAddress, amount, signer) {
  try {
    const pyusdToken = TOKENS.sepolia.PYUSD;
    const tokenContract = new ethers.Contract(pyusdToken.address, ABIS.ERC20, signer);
    
    console.log(`[PYUSD Payment] Approving ${ethers.formatUnits(amount, pyusdToken.decimals)} PYUSD for ${spenderAddress}`);
    
    const tx = await tokenContract.approve(spenderAddress, amount);
    console.log(`[PYUSD Payment] Approval transaction sent: ${tx.hash}`);
    
    const receipt = await tx.wait();
    console.log(`[PYUSD Payment] Approval confirmed in block ${receipt.blockNumber}`);
    
    return receipt;
  } catch (error) {
    console.error('[PYUSD Payment] Error approving PYUSD:', error);
    throw new Error(`Failed to approve PYUSD: ${error.message}`);
  }
}

/**
 * @notice Processes a PYUSD payment and records receipt on-chain
 * @param {object} productData Details of the product being purchased
 * @param {string} amount The amount to pay (in human-readable format, e.g., "10.50")
 * @param {string} walletAddress The user's wallet address
 * @param {ethers.Provider} provider The ethers.js provider
 * @returns {Promise<object>} Payment result containing txHash, receiptId, and receiptCid
 */
export async function processPYUSDPayment(productData, amount, walletAddress, provider) {
  try {
    console.log('[PYUSD Payment] Starting PYUSD payment process...', { productData, amount });
    
    const signer = await provider.getSigner();
    const pyusdToken = TOKENS.sepolia.PYUSD;
    const paymentProcessorAddress = CONTRACT_ADDRESSES.sepolia.PaymentProcessor;
    
    // Validate PaymentProcessor is deployed
    if (!paymentProcessorAddress || paymentProcessorAddress === '0x_REPLACE_AFTER_DEPLOYMENT') {
      throw new Error('PaymentProcessor contract not deployed yet. Please deploy it first.');
    }
    
    // Convert amount to token units (PYUSD has 6 decimals)
    const amountInTokenUnits = ethers.parseUnits(amount.toString(), pyusdToken.decimals);
    
    // Check user balance
    const balance = await checkPYUSDBalance(walletAddress, provider);
    if (balance < amountInTokenUnits) {
      throw new Error(`Insufficient PYUSD balance. You have ${ethers.formatUnits(balance, pyusdToken.decimals)} PYUSD but need ${amount} PYUSD`);
    }
    
    // Prepare receipt data
    const receiptData = {
      productId: productData.productId || productData.url || 'unknown',
      buyerAddress: walletAddress,
      amount: amount.toString(),
      currency: 'PYUSD',
      timestamp: new Date().toISOString(),
      productDetails: {
        title: productData.title,
        price: productData.price,
        image: productData.image,
        description: productData.description,
        url: productData.url
      }
    };
    
    // Upload receipt to Lighthouse
    console.log('[PYUSD Payment] Uploading receipt to Lighthouse...');
    const receiptCid = await uploadReceiptToLighthouse(receiptData);
    console.log('[PYUSD Payment] Receipt uploaded, CID:', receiptCid);
    
    // Check allowance
    const tokenContract = new ethers.Contract(pyusdToken.address, ABIS.ERC20, signer);
    const currentAllowance = await tokenContract.allowance(walletAddress, paymentProcessorAddress);
    
    // Approve if needed
    if (currentAllowance < amountInTokenUnits) {
      console.log('[PYUSD Payment] Requesting PYUSD approval...');
      await approvePYUSD(paymentProcessorAddress, amountInTokenUnits, signer);
    } else {
      console.log('[PYUSD Payment] Sufficient allowance already exists');
    }
    
    // Process payment through PaymentProcessor contract
    console.log('[PYUSD Payment] Processing payment through PaymentProcessor...');
    const paymentProcessor = new ethers.Contract(paymentProcessorAddress, ABIS.PaymentProcessor, signer);
    
    const tx = await paymentProcessor.processPayment(
      receiptData.productId,
      amountInTokenUnits,
      receiptCid,
      pyusdToken.address,
      'PYUSD'
    );
    
    console.log(`[PYUSD Payment] Payment transaction sent: ${tx.hash}`);
    
    const receipt = await tx.wait();
    console.log(`[PYUSD Payment] Payment confirmed in block ${receipt.blockNumber}`);
    
    // Extract payment and receipt IDs from events
    const paymentEvent = receipt.logs.find(log => {
      try {
        const parsed = paymentProcessor.interface.parseLog(log);
        return parsed.name === 'PaymentProcessed';
      } catch {
        return false;
      }
    });
    
    let paymentId, receiptId;
    if (paymentEvent) {
      const parsed = paymentProcessor.interface.parseLog(paymentEvent);
      paymentId = parsed.args.paymentId.toString();
      receiptId = parsed.args.receiptId.toString();
    }
    
    console.log('[PYUSD Payment] Payment successful!', { paymentId, receiptId });
    
    return {
      success: true,
      txHash: receipt.hash,
      paymentId: paymentId,
      receiptId: receiptId,
      receiptCid: receiptCid,
      productData: productData,
      amountPaid: amount.toString(),
      currency: 'PYUSD',
      paymentToken: pyusdToken.address,
      merchantWallet: MERCHANT_WALLET,
      blockNumber: receipt.blockNumber
    };
    
  } catch (error) {
    console.error('[PYUSD Payment] Payment processing failed:', error);
    
    // Provide user-friendly error messages
    let errorMessage = error.message;
    
    if (error.message.includes('insufficient funds')) {
      errorMessage = 'Insufficient ETH for gas fees. Please add more ETH to your wallet.';
    } else if (error.message.includes('user rejected')) {
      errorMessage = 'Transaction was rejected by user.';
    } else if (error.message.includes('Insufficient token allowance')) {
      errorMessage = 'Failed to approve PYUSD spending. Please try again.';
    }
    
    throw new Error(errorMessage);
  }
}

/**
 * @notice Formats PYUSD amount for display
 * @param {ethers.BigNumber|string} amount The amount in token units
 * @param {number} decimals The token decimals (default 6 for PYUSD)
 * @returns {string} Formatted amount
 */
export function formatPYUSDAmount(amount, decimals = 6) {
  try {
    if (typeof amount === 'string' && !amount.includes('.')) {
      return ethers.formatUnits(amount, decimals);
    }
    return amount.toString();
  } catch (error) {
    console.error('[PYUSD Payment] Error formatting amount:', error);
    return '0.00';
  }
}

/**
 * @notice Gets payment details from PaymentProcessor contract
 * @param {string} paymentId The payment ID
 * @param {ethers.Provider} provider The ethers.js provider
 * @returns {Promise<object>} Payment details
 */
export async function getPaymentDetails(paymentId, provider) {
  try {
    const paymentProcessorAddress = CONTRACT_ADDRESSES.sepolia.PaymentProcessor;
    const paymentProcessor = new ethers.Contract(paymentProcessorAddress, ABIS.PaymentProcessor, provider);
    const details = await paymentProcessor.getPaymentDetails(paymentId);
    return details;
  } catch (error) {
    console.error('[PYUSD Payment] Error getting payment details:', error);
    throw new Error(`Failed to get payment details: ${error.message}`);
  }
}

export default {
  processPYUSDPayment,
  checkPYUSDBalance,
  approvePYUSD,
  formatPYUSDAmount,
  getPaymentDetails
};

