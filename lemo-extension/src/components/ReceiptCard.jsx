import React from 'react';
import { FileText, ExternalLink, MessageSquare, Clock, DollarSign, CreditCard } from 'lucide-react';
import { getLighthouseGatewayUrl } from '../utils/contractConfig.js';

const ReceiptCard = ({ receiptData, onFeedbackClick }) => {
  const {
    receiptId,
    productName,
    productId,
    amount,
    currency,
    timestamp,
    receiptCid,
    txHash,
    network = 'sepolia',
    paymentMethod
  } = receiptData;
  
  const gatewayUrl = getLighthouseGatewayUrl(receiptCid);
  const explorerUrl = network === 'sepolia' 
    ? `https://sepolia.etherscan.io/tx/${txHash}`
    : `https://calibration.filfox.info/tx/${txHash}`;
  
  const formatDate = (ts) => {
    const date = new Date(ts);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };
  
  const getPaymentMethodBadge = () => {
    const method = paymentMethod || currency;
    switch (method) {
      case 'PYUSD':
        return {
          bgColor: 'bg-blue-500/20',
          borderColor: 'border-blue-500/40',
          textColor: 'text-blue-700',
          label: '💳 PayPal USD'
        };
      case 'USDC':
        return {
          bgColor: 'bg-indigo-500/20',
          borderColor: 'border-indigo-500/40',
          textColor: 'text-indigo-700',
          label: '💵 USDC'
        };
      case 'ETH':
        return {
          bgColor: 'bg-purple-500/20',
          borderColor: 'border-purple-500/40',
          textColor: 'text-purple-700',
          label: '⟠ ETH'
        };
      default:
        return {
          bgColor: 'bg-gray-500/20',
          borderColor: 'border-gray-500/40',
          textColor: 'text-gray-700',
          label: method || 'Crypto'
        };
    }
  };
  
  const paymentBadge = getPaymentMethodBadge();
  
  return (
    <div className="mt-4">
      <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-blue-400/15 via-blue-300/10 to-blue-500/20 backdrop-blur-sm border border-blue-200/25 shadow-lg">
        <div className="relative p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-full bg-gradient-to-r from-blue-500 to-blue-600 flex items-center justify-center">
                <FileText className="w-3 h-3 text-white" />
              </div>
              <h3 className="text-sm font-bold text-blue-800">Purchase Receipt</h3>
            </div>
            <div className="px-2 py-1 rounded-full bg-green-500/20 border border-green-500/30">
              <span className="text-xs font-semibold text-green-700">Verified</span>
            </div>
          </div>
          
          <div className="mb-3 p-2 rounded-lg bg-white/20">
            <div className="text-xs text-gray-600 mb-0.5">Receipt ID</div>
            <div className="text-sm font-mono font-semibold text-gray-800">#{receiptId}</div>
          </div>
          
          <div className="mb-3">
            <div className="text-xs text-gray-600 mb-1">Product</div>
            <div className="text-sm font-semibold text-gray-800 line-clamp-2">{productName}</div>
            <div className="text-xs text-gray-500 mt-0.5 font-mono">{productId}</div>
          </div>
          
          <div className="grid grid-cols-2 gap-2 mb-3">
            <div className="p-2 rounded-lg bg-white/15">
              <div className="flex items-center gap-1 mb-1">
                <DollarSign className="w-3 h-3 text-gray-600" />
                <span className="text-xs text-gray-600">Amount</span>
              </div>
              <div className="text-sm font-bold text-gray-800">{amount} {currency}</div>
            </div>
            <div className="p-2 rounded-lg bg-white/15">
              <div className="flex items-center gap-1 mb-1">
                <Clock className="w-3 h-3 text-gray-600" />
                <span className="text-xs text-gray-600">Date</span>
              </div>
              <div className="text-xs font-semibold text-gray-800">{formatDate(timestamp)}</div>
            </div>
          </div>
          
          {paymentMethod && (
            <div className="mb-3">
              <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${paymentBadge.bgColor} border ${paymentBadge.borderColor}`}>
                <CreditCard className={`w-4 h-4 ${paymentBadge.textColor}`} />
                <span className={`text-xs font-semibold ${paymentBadge.textColor}`}>
                  Paid with {paymentBadge.label}
                </span>
              </div>
            </div>
          )}
          
          <div className="flex flex-col gap-2 mb-3">
            <a
              href={gatewayUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-between p-2 rounded-lg bg-white/15 hover:bg-white/25 transition-all"
            >
              <div className="flex items-center gap-2">
                <FileText className="w-3 h-3 text-blue-600" />
                <span className="text-xs font-medium text-blue-700">View on IPFS</span>
              </div>
              <ExternalLink className="w-3 h-3 text-blue-600" />
            </a>
            
            {txHash && (
              <a
                href={explorerUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between p-2 rounded-lg bg-white/15 hover:bg-white/25 transition-all"
              >
                <div className="flex items-center gap-2">
                  <ExternalLink className="w-3 h-3 text-gray-600" />
                  <span className="text-xs font-medium text-gray-700">View Transaction</span>
                </div>
                <ExternalLink className="w-3 h-3 text-gray-600" />
              </a>
            )}
          </div>
          
          <button
            onClick={() => onFeedbackClick(receiptId)}
            className="w-full bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 text-white font-bold py-2.5 px-4 rounded-lg transition-all flex items-center justify-center gap-2 shadow-md hover:shadow-lg transform hover:scale-105"
          >
            <MessageSquare className="w-4 h-4" />
            <span className="text-sm">Submit Feedback & Earn LEMO</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default ReceiptCard;



