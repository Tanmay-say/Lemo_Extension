/**
 * FVM Service for Buy Now Flow
 * Handles the complete purchase workflow: Payment → Lighthouse upload → On-chain receipt
 * Supports multiple payment methods: ETH, USDC, PYUSD
 */

import { ethers } from 'ethers';
import { 
  getContractAddress, 
  ABIS, 
  LIGHTHOUSE_CONFIG,
  getNetworkConfig 
} from '../utils/contractConfig.js';
import { processPYUSDPayment } from './pyusdPayment.js';

/**
 * Uploads receipt data to Lighthouse
 */
async function uploadReceiptToLighthouse(receiptData, apiKey) {
  try {
    const jsonString = JSON.stringify(receiptData, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const formData = new FormData();
    formData.append('file', blob, `receipt_${Date.now()}.json`);
    
    const response = await fetch(LIGHTHOUSE_CONFIG.apiEndpoint, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`
      },
      body: formData
    });
    
    if (!response.ok) {
      throw new Error(`Lighthouse upload failed: ${response.statusText}`);
    }
    
    const result = await response.json();
    return result.Hash;
  } catch (error) {
    console.error('[FVM Service] Lighthouse upload failed:', error);
    throw new Error(`Failed to upload receipt to Lighthouse: ${error.message}`);
  }
}

/**
 * Main handler for Buy Now click
 */
export async function handleBuyNowClick(productData, walletAddress, provider, paymentMethod = 'ETH') {
  try {
    console.log('[FVM Service] Starting Buy Now flow...', {
      product: productData.title,
      buyer: walletAddress,
      paymentMethod
    });
    
    // Route to PYUSD payment processor if PYUSD selected
    if (paymentMethod === 'PYUSD') {
      console.log('[FVM Service] Routing to PYUSD payment processor...');
      
      // Convert price to USD
      let usdAmount = '10.00';
      if (productData.price) {
        const priceStr = productData.price.toString();
        const numericPrice = parseFloat(priceStr.replace(/[^\d.]/g, ''));
        if (!isNaN(numericPrice)) {
          if (priceStr.includes('₹')) {
            usdAmount = (numericPrice * 0.012).toFixed(2);
          } else {
            usdAmount = numericPrice.toFixed(2);
          }
        }
      }
      
      const result = await processPYUSDPayment(productData, usdAmount, walletAddress, provider);
      return {
        success: result.success,
        txHash: result.txHash,
        receiptId: result.receiptId,
        receiptCid: result.receiptCid,
        productData: result.productData,
        paymentMethod: 'PYUSD',
        amountPaid: result.amountPaid,
        currency: result.currency
      };
    }
    
    // For ETH/USDC (mock flow for now)
    const signer = await provider.getSigner();
    const mockTxHash = `0x${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`;
    const receiptData = {
      version: '1.0',
      type: 'purchase_receipt',
      buyer: walletAddress,
      product: {
        id: productData.productId || `PROD-${Date.now()}`,
        name: productData.title,
        url: productData.url,
        price: productData.price,
        image: productData.image
      },
      payment: {
        token: ethers.ZeroAddress,
        amount: ethers.parseEther('0.01').toString(),
        currency: paymentMethod,
        txHash: mockTxHash
      },
      timestamp: Date.now(),
      network: 'sepolia'
    };
    
    console.log('[FVM Service] Uploading receipt to Lighthouse...');
    const receiptCid = await uploadReceiptToLighthouse(receiptData, LIGHTHOUSE_CONFIG.apiKey);
    
    return {
      success: true,
      txHash: mockTxHash,
      receiptId: null,
      receiptCid,
      productData: receiptData.product,
      paymentMethod,
      amountPaid: '0.01',
      currency: paymentMethod
    };
    
  } catch (error) {
    console.error('[FVM Service] Buy Now failed:', error);
    return {
      success: false,
      error: error.message || 'Purchase failed.'
    };
  }
}

export async function submitFeedback(receiptId, feedbackData, walletAddress, provider) {
  try {
    const signer = await provider.getSigner();
    const feedbackJson = {
      version: '1.0',
      type: 'product_feedback',
      receiptId,
      user: walletAddress,
      rating: feedbackData.rating,
      feedback: { comment: feedbackData.comment },
      timestamp: Date.now()
    };
    
    const jsonString = JSON.stringify(feedbackJson, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const formData = new FormData();
    formData.append('file', blob, `feedback_${Date.now()}.json`);
    
    const response = await fetch(LIGHTHOUSE_CONFIG.apiEndpoint, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${LIGHTHOUSE_CONFIG.apiKey}` },
      body: formData
    });
    
    if (!response.ok) throw new Error('Failed to upload feedback');
    const result = await response.json();
    const feedbackCid = result.Hash;
    
    const network = await signer.provider.getNetwork();
    const networkName = network.chainId === 11155111 ? 'sepolia' : 'calibration';
    const contractAddress = getContractAddress(networkName, 'TrustlessAgentFeedback');
    const contract = new ethers.Contract(contractAddress, ABIS.TrustlessAgentFeedback, signer);
    
    const tx = await contract.submitFeedback(receiptId, feedbackCid);
    const receipt = await tx.wait();
    
    const event = receipt.logs
      .map(log => {
        try { return contract.interface.parseLog(log); } catch { return null; }
      })
      .find(e => e && e.name === 'FeedbackSubmitted');
    
    return {
      success: true,
      feedbackId: event ? event.args.feedbackId.toString() : null,
      reward: event ? ethers.formatEther(event.args.reward) : '0',
      txHash: receipt.hash,
      feedbackCid
    };
    
  } catch (error) {
    return { success: false, error: error.message };
  }
}

export default { handleBuyNowClick, submitFeedback };