import React, { useState, useEffect } from 'react';
import { ShoppingCart, ExternalLink, Heart, Plus, ChevronDown } from 'lucide-react';
import { checkPYUSDBalance, formatPYUSDAmount } from '../services/pyusdPayment';
import { ethers } from 'ethers';

const BuyCard = ({ productData, onBuyClick, walletAddress }) => {
  const [paymentMethod, setPaymentMethod] = useState('PYUSD');
  const [pyusdBalance, setPyusdBalance] = useState('0.000000');
  const [isLoadingBalance, setIsLoadingBalance] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);
  
  // Extract product information
  const {
    title = 'Product Name',
    price = '₹0',
    originalPrice = '',
    discount = '',
    image = '',
    description = 'Premium product with excellent features',
    url = '#'
  } = productData;

  // Convert INR to USD (approximate rate)
  const convertToUSD = (priceStr) => {
    const numericPrice = parseFloat(priceStr.replace(/[₹,]/g, ''));
    if (isNaN(numericPrice)) return '$0';
    const usdPrice = (numericPrice * 0.012).toFixed(2);
    return `$${usdPrice}`;
  };

  const usdPrice = convertToUSD(price);

  // Fetch PYUSD balance when wallet is connected
  useEffect(() => {
    if (walletAddress && paymentMethod === 'PYUSD') {
      fetchPYUSDBalance();
    }
  }, [walletAddress, paymentMethod]);

  const fetchPYUSDBalance = async () => {
    if (!walletAddress) {
      console.log('[BuyCard] No wallet connected');
      setPyusdBalance('0');
      return;
    }
    
    setIsLoadingBalance(true);
    try {
      // Access MetaMask via wallet bridge in page context
      const response = await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          window.removeEventListener('message', handler);
          reject(new Error('Balance fetch timeout'));
        }, 10000); // 10 second timeout
        
        window.postMessage({
          source: 'lemo-extension',
          action: 'GET_SPECIFIC_TOKEN_BALANCE',
          tokenSymbol: 'PYUSD',
          account: walletAddress
        }, '*');
        
        // Listen for response
        const handler = (event) => {
          if (event.source === window && event.data && event.data.source === 'lemo-extension-response') {
            clearTimeout(timeout);
            window.removeEventListener('message', handler);
            resolve(event.data);
          }
        };
        window.addEventListener('message', handler);
      });
      
      if (response && response.success && response.result) {
        const balance = response.result.balance || '0';
        const formattedBalance = parseFloat(balance).toFixed(6);
        console.log('[BuyCard] PYUSD balance fetched successfully:', {
          rawBalance: balance,
          formattedBalance: formattedBalance,
          decimals: response.result.decimals,
          symbol: response.result.symbol
        });
        setPyusdBalance(formattedBalance);
      } else {
        console.error('[BuyCard] Failed to fetch PYUSD balance:', {
          response: response,
          success: response?.success,
          result: response?.result,
          error: response?.error
        });
        setPyusdBalance('0.000000');
      }
    } catch (error) {
      console.error('[BuyCard] Error fetching PYUSD balance:', error);
      setPyusdBalance('0.000000');
    } finally {
      setIsLoadingBalance(false);
    }
  };

  const handleBuyNowClick = async () => {
    if (!walletAddress) {
      setError('Please connect your wallet first');
      return;
    }

    setIsProcessing(true);
    setError(null);

    try {
      // Call parent component's handler with payment method
      await onBuyClick(productData, paymentMethod);
    } catch (err) {
      console.error('Buy Now error:', err);
      setError(err.message || 'Payment failed. Please try again.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="mt-4">
      {/* Compact Card Container */}
      <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-orange-400/15 via-orange-300/10 to-orange-500/20 backdrop-blur-sm border border-orange-200/25 shadow-lg">
        {/* Card Content */}
        <div className="relative p-4">
          {/* Header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-full bg-gradient-to-r from-orange-500 to-orange-600 flex items-center justify-center">
                <ShoppingCart className="w-3 h-3 text-white" />
              </div>
              <h3 className="text-sm font-bold text-orange-800">Ready to Purchase?</h3>
            </div>
            <button className="p-1.5 rounded-full bg-white/20 hover:bg-white/30 transition-all duration-200 backdrop-blur-sm">
              <Heart className="w-4 h-4 text-orange-600" />
            </button>
          </div>

          {/* Product Image */}
          <div className="mb-3">
            <div className="relative w-full h-32 rounded-lg overflow-hidden bg-gradient-to-br from-orange-100 to-orange-200 shadow-md">
              {image ? (
                <img 
                  src={image} 
                  alt={title}
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    e.target.style.display = 'none';
                    e.target.nextSibling.style.display = 'flex';
                  }}
                />
              ) : null}
              <div className="w-full h-full bg-gradient-to-br from-orange-400 to-orange-500 flex items-center justify-center text-white">
                <div className="text-center">
                  <div className="text-3xl font-bold mb-1">{title.charAt(0)}</div>
                  <div className="text-xs opacity-80">Product Image</div>
                </div>
              </div>
              
              {/* Discount Badge */}
              {discount && (
                <div className="absolute top-2 left-2 bg-gradient-to-r from-red-500 to-red-600 text-white px-2 py-1 rounded-full text-xs font-bold shadow-md">
                  {discount} OFF
                </div>
              )}
            </div>
          </div>

          {/* Product Title */}
          <h4 className="text-sm font-bold text-gray-800 mb-2 leading-tight line-clamp-2">
            {title}
          </h4>

          {/* Price Section */}
          <div className="mb-3">
            <div className="flex items-baseline gap-2 mb-1">
              <span className="text-lg font-bold text-orange-600">{price}</span>
              <span className="text-sm text-gray-500 font-medium">{usdPrice}</span>
            </div>
            {originalPrice && (
              <div className="text-xs text-gray-500 line-through">
                {originalPrice}
              </div>
            )}
          </div>

          {/* Description */}
          <div className="mb-4">
            <p className="text-gray-700 leading-relaxed text-xs line-clamp-2">
              {description}
            </p>
          </div>

          {/* Payment Method Dropdown */}
          <div className="mb-3">
            <label className="text-xs font-semibold text-gray-700 mb-1 block">
              Payment Method
            </label>
            <div className="relative">
              <select
                value={paymentMethod}
                onChange={(e) => setPaymentMethod(e.target.value)}
                className="w-full bg-white/40 backdrop-blur-sm border border-orange-200/50 rounded-lg px-3 py-2 text-sm font-medium text-gray-800 appearance-none cursor-pointer hover:bg-white/50 transition-colors focus:outline-none focus:ring-2 focus:ring-orange-500/50"
                disabled={isProcessing}
              >
                <option value="PYUSD">PYUSD (PayPal USD)</option>
                <option value="USDC">USDC</option>
                <option value="ETH">ETH</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" />
            </div>
            
            {/* Balance Display */}
            {paymentMethod === 'PYUSD' && walletAddress && (
              <div className="mt-1.5 text-xs text-gray-600 flex items-center justify-between">
                <span>Your Balance:</span>
                <span className="font-semibold text-orange-700">
                  {isLoadingBalance ? (
                    <span className="animate-pulse">Loading...</span>
                  ) : (
                    `${pyusdBalance || '0'} PYUSD`
                  )}
                </span>
              </div>
            )}
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-xs text-red-700">{error}</p>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-2">
            {/* Add to Cart Button */}
            <button 
              className="flex-1 bg-white/30 hover:bg-white/40 backdrop-blur-sm text-orange-700 font-semibold py-2 px-3 rounded-lg transition-all duration-200 flex items-center justify-center gap-1 border border-orange-200/50 hover:border-orange-300/70 shadow-md hover:shadow-lg transform hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={isProcessing}
            >
              <Plus className="w-3 h-3" />
              <span className="text-xs">Add to Cart</span>
            </button>

            {/* Buy Now Button */}
            <button
              onClick={handleBuyNowClick}
              disabled={isProcessing}
              className="flex-1 bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 text-white font-bold py-2 px-3 rounded-lg transition-all duration-200 flex items-center justify-center gap-1 shadow-md hover:shadow-lg transform hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isProcessing ? (
                <>
                  <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span className="text-xs">Processing...</span>
                </>
              ) : (
                <>
                  <ShoppingCart className="w-3 h-3" />
                  <span className="text-xs">Buy with {paymentMethod}</span>
                </>
              )}
            </button>
          </div>

          {/* Payment Method Info */}
          {paymentMethod === 'PYUSD' && (
            <div className="mt-2 text-[10px] text-center text-gray-600">
              💳 Secure payment with PayPal USD stablecoin
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default BuyCard;