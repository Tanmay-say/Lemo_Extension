import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import AssistantInput from './AssistantInput';
import BuyCard from './BuyCard';
import ReceiptCard from './ReceiptCard';
import FeedbackCard from './FeedbackCard';
import CurrentPageIndicator from './CurrentPageIndicator';
import { AlertCircle, WalletIcon } from 'lucide-react';
import { ethers } from 'ethers';
import { getConnectedWallet } from '../utils/auth.js';
import { createSession, getCurrentSession, saveCurrentSession, getCurrentTabInfo, sendChatMessage, getSessionDetails } from '../utils/session.js';
import { handleBuyNowClick as processFVMTransaction } from '../services/fvmService.js';
import { submitFeedback } from '../services/fvmService.js';

const ChatWindow = () => {
  const [messages, setMessages] = useState([]);
  const [isTyping, setIsTyping] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [walletAddress, setWalletAddress] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [isLoadingSession, setIsLoadingSession] = useState(true);
  const [error, setError] = useState(null);
  const [isBackendAvailable, setIsBackendAvailable] = useState(true);
  const [currentProductData, setCurrentProductData] = useState(null);
  const [currentPageUrl, setCurrentPageUrl] = useState('');
  const [currentPageDomain, setCurrentPageDomain] = useState('');
  const [isRefreshingContext, setIsRefreshingContext] = useState(false);
  const messagesEndRef = useRef(null);
  const previousUrlRef = useRef('');

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    initializeChat();
  }, []);

  // URL change detection
  useEffect(() => {
    const checkUrlChange = async () => {
      try {
        const currentUrl = window.location.href;
        
        if (currentUrl !== previousUrlRef.current && previousUrlRef.current !== '') {
          console.log('[CHAT] Page change detected:', {
            from: previousUrlRef.current,
            to: currentUrl
          });
          
          // Update current page info
          const tabInfo = await getCurrentTabInfo();
          setCurrentPageUrl(tabInfo.url);
          setCurrentPageDomain(tabInfo.domain);
          
          // CLEAR previous messages (keep context fresh)
          setMessages([{
            id: `page-change-${Date.now()}`,
          type: 'bot',
            content: `🔄 **Page Changed!**

I've detected you're now on: **${tabInfo.domain}**

I've cleared my previous context and I'm ready to analyze this new page. Ask me anything about this product!`,
            timestamp: new Date().toISOString(),
          }]);
          
          // Create new session for new page
          if (walletAddress && tabInfo.url !== 'chrome://newtab') {
            try {
              const newSession = await createSession(walletAddress, tabInfo.url, tabInfo.domain);
              setSessionId(newSession.id || newSession.session_id);
              await saveCurrentSession(newSession.id || newSession.session_id);
            } catch (error) {
              console.error('Error creating session for new page:', error);
            }
          }
        }
        
        previousUrlRef.current = currentUrl;
      } catch (error) {
        console.error('Error checking URL change:', error);
      }
    };

    // Check URL change every 2 seconds
    const interval = setInterval(checkUrlChange, 2000);
    
    // Initial check
    checkUrlChange();

    return () => clearInterval(interval);
  }, [walletAddress]);

  const initializeChat = async () => {
    try {
      // Check if wallet is connected
      const wallet = await getConnectedWallet();
      
      if (!wallet) {
        setIsAuthenticated(false);
        setIsLoadingSession(false);
        setMessages([{
          id: 'welcome',
          type: 'bot',
          content: 'Please connect your wallet from the Wallet tab to start chatting.',
          timestamp: new Date().toISOString(),
        }]);
        return;
      }

      // Wallet is connected - enable chat
      setWalletAddress(wallet);
      setIsAuthenticated(true);

      // Initialize current page info
      const tabInfo = await getCurrentTabInfo();
      setCurrentPageUrl(tabInfo.url);
      setCurrentPageDomain(tabInfo.domain);
      previousUrlRef.current = tabInfo.url;

      // Try to load existing session (gracefully fail if backend unavailable)
      const existingSessionId = await getCurrentSession();
      
      if (existingSessionId) {
        // Try to load chat history from backend
        try {
          const sessionData = await getSessionDetails(wallet, existingSessionId);
          setSessionId(existingSessionId);
          setIsBackendAvailable(true);
          
          if (sessionData.session && sessionData.session.chat_messages) {
            // Convert backend messages to our format
            const formattedMessages = sessionData.session.chat_messages.map(msg => ({
              id: msg.id,
              type: msg.message_type === 'user' ? 'user' : 'bot',
              content: msg.message,
              timestamp: msg.created_at,
            }));
            setMessages(formattedMessages);
          }
        } catch (err) {
          console.error('Error loading session from backend:', err);
          // Backend unavailable, but chat still works
          setIsBackendAvailable(false);
          setError('Backend unavailable. Chat will work but history won\'t be saved.');
          setMessages([{
            id: 'welcome',
            type: 'bot',
            content: 'Hello! I\'m your Lemo AI Assistant. (⚠️ Backend offline - responses may be limited)',
            timestamp: new Date().toISOString(),
          }]);
        }
      } else {
        // No existing session, show welcome message
        setMessages([{
          id: 'welcome',
          type: 'bot',
          content: 'Hello! I\'m your Lemo AI Assistant. I can help you find products and compare prices across platforms. Try asking me about a product!',
          timestamp: new Date().toISOString(),
        }]);
      }
      
      setIsLoadingSession(false);
    } catch (err) {
      console.error('Error initializing chat:', err);
      setIsLoadingSession(false);
      setError('Failed to initialize chat. Please try again.');
    }
  };

  // Detect purchase intent from user message (LESS AGGRESSIVE)
  const detectPurchaseIntent = (message) => {
    // ONLY high intent keywords - very explicit buying signals
    const highIntentKeywords = [
      'buy', 'purchase', 'order', 'ready to buy', 'want to buy', 'i will buy',
      'show buy card', 'buy card', 'buy now', 'add to cart', 'checkout', 'proceed to buy'
    ];
    
    // REMOVED: mediumIntentKeywords and interestKeywords that were too aggressive
    
    const lowerMessage = message.toLowerCase().trim();
    
    // High intent detection
    const hasHighIntent = highIntentKeywords.some(keyword => lowerMessage.includes(keyword));
    if (hasHighIntent) return 'high';
    
    // Return 'none' for everything else - be much more conservative
    return 'none';
  };

  // Extract product data from AI response
  const extractProductData = (response) => {
    try {
      // Extract price (₹29,990 format)
      const priceMatch = response.match(/₹[\d,]+/);
      const price = priceMatch ? priceMatch[0] : '';
      
      // Extract USD price ($28 format)
      const usdMatch = response.match(/\$[\d.]+/);
      const usdPrice = usdMatch ? usdMatch[0] : '';
      
      // Extract rating (4.1/5 format)
      const ratingMatch = response.match(/(\d+\.?\d*)\/5/);
      const rating = ratingMatch ? ratingMatch[1] : '';
      
      // Extract review count
      const reviewMatch = response.match(/\((\d+[\d,]*) reviews?\)/);
      const reviewCount = reviewMatch ? reviewMatch[1] : '';
      
      // Extract discount
      const discountMatch = response.match(/(\d+)% off/);
      const discount = discountMatch ? `${discountMatch[1]}%` : '';
      
      // Extract title (first bold text)
      const titleMatch = response.match(/\*\*(.*?)\*\*/);
      const title = titleMatch ? titleMatch[1] : '';
      
      // Extract description (first sentence after title)
      const descMatch = response.match(/\*\*.*?\*\*\s*([^.]+)/);
      const description = descMatch ? descMatch[1].trim() : '';
      
      return {
        title,
        price,
        usdPrice,
        rating,
        reviewCount,
        discount,
        description,
        url: window.location.href
      };
    } catch (error) {
      console.error('Error extracting product data:', error);
      return null;
    }
  };

  const handleBuyNowClick = async (productData, paymentMethod) => {
    try {
      console.log('[ChatWindow] Buy Now clicked:', { productData, paymentMethod });
      
      if (!walletAddress) {
        throw new Error('Please connect your wallet first from the Wallet tab.');
      }

      // Add loading message
      const loadingMessage = {
        id: `loading-${Date.now()}`,
        type: 'bot',
        content: `🔄 **Processing ${paymentMethod} Payment...**\n\nPlease wait while we process your payment. This may take a few moments.`,
        timestamp: new Date().toISOString(),
        isLoading: true
      };
      setMessages(prev => [...prev, loadingMessage]);

      // Check MetaMask availability via wallet bridge
      const walletCheck = await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          window.removeEventListener('message', handler);
          reject(new Error('Wallet check timeout'));
        }, 5000);
        
        window.postMessage({
          source: 'lemo-extension',
          action: 'CHECK_WALLET'
        }, '*');
        
        const handler = (event) => {
          if (event.source === window && event.data && event.data.source === 'lemo-extension-response') {
            clearTimeout(timeout);
            window.removeEventListener('message', handler);
            resolve(event.data);
          }
        };
        window.addEventListener('message', handler);
      });

      if (!walletCheck.result || !walletCheck.result.isInstalled) {
        throw new Error('MetaMask is not installed. Please install MetaMask to process payments.');
      }

      if (!walletCheck.result.accounts || walletCheck.result.accounts.length === 0) {
        throw new Error('No MetaMask accounts connected. Please connect your wallet.');
      }

      // Process payment via wallet bridge
      console.log('[ChatWindow] Processing payment via wallet bridge...', { productData, paymentMethod, walletAddress });
      const result = await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          window.removeEventListener('message', handler);
          reject(new Error('Payment processing timeout'));
        }, 60000); // 60 second timeout for payment
        
        window.postMessage({
          source: 'lemo-extension',
          action: 'PROCESS_PAYMENT',
          productData: productData,
          paymentMethod: paymentMethod,
          walletAddress: walletAddress
        }, '*');
        
        const handler = (event) => {
          if (event.source === window && event.data && event.data.source === 'lemo-extension-response') {
            clearTimeout(timeout);
            window.removeEventListener('message', handler);
            resolve(event.data);
          }
        };
        window.addEventListener('message', handler);
      });
      
      if (result.success && result.result && result.result.success) {
        // Remove loading message
        setMessages(prev => prev.filter(msg => msg.id !== loadingMessage.id));
        
        // Extract payment details from the nested result
        const paymentData = result.result;
        console.log('[ChatWindow] Payment data received:', paymentData);
        console.log('[ChatWindow] Individual fields:');
        console.log('[ChatWindow] txHash:', paymentData.txHash);
        console.log('[ChatWindow] amountPaid:', paymentData.amountPaid);
        console.log('[ChatWindow] currency:', paymentData.currency);
        console.log('[ChatWindow] receiptId:', paymentData.receiptId);
        console.log('[ChatWindow] blockNumber:', paymentData.blockNumber);
        console.log('[ChatWindow] merchantWallet:', paymentData.merchantWallet);
        
        // Add success message
        const receiptUrl = paymentData.receiptCid ? `https://gateway.lighthouse.storage/ipfs/${paymentData.receiptCid}` : 'N/A';
        const content = `✅ **Payment Successful!**\n\n**Transaction Hash:** \`${paymentData.txHash || 'N/A'}\`\n**Amount Paid:** ${paymentData.amountPaid || 'N/A'} ${paymentData.currency || 'PYUSD'}\n**Receipt ID:** ${paymentData.receiptId || 'N/A'}\n**Block Number:** ${paymentData.blockNumber || 'N/A'}\n**Merchant Wallet:** \`${paymentData.merchantWallet || 'N/A'}\`\n**Receipt URL:** [View Receipt](${receiptUrl})\n\nYour PYUSD has been transferred to the merchant wallet. Thank you for your purchase!`;
        
        console.log('[ChatWindow] Final content string:', content);
        
        const successMessage = {
          id: `success-${Date.now()}`,
          type: 'bot',
          content: content,
          timestamp: new Date().toISOString(),
          isSuccess: true
        };
        setMessages(prev => [...prev, successMessage]);
        
        console.log('[ChatWindow] ✅ Payment successful:', paymentData);
      } else {
        console.error('[ChatWindow] Payment failed:', result);
        throw new Error(result.error || result.result?.error || 'Payment processing failed');
      }
      
    } catch (error) {
      console.error('[ChatWindow] Buy Now error:', error);
      
      // Remove loading message if it exists
      setMessages(prev => prev.filter(msg => !msg.isLoading));
      
      const errorMessage = {
        id: `error-${Date.now()}`,
        type: 'bot',
        content: `❌ **Payment Failed**\n\n${error.message}\n\nPlease ensure you are on Sepolia testnet and have sufficient balance.`,
        timestamp: new Date().toISOString(),
        isError: true
      };
      
      setMessages(prev => [...prev, errorMessage]);
    }
  };

  const handleRefreshContext = async () => {
    setIsRefreshingContext(true);
    try {
      const tabInfo = await getCurrentTabInfo();
      setCurrentPageUrl(tabInfo.url);
      setCurrentPageDomain(tabInfo.domain);
      
      // Create new session with refreshed URL
      if (walletAddress) {
        const newSession = await createSession(walletAddress, tabInfo.url, tabInfo.domain);
        setSessionId(newSession.id || newSession.session_id);
        await saveCurrentSession(newSession.id || newSession.session_id);
        
        // Add system message about page refresh
        const refreshMessage = {
          id: `refresh-${Date.now()}`,
          type: 'bot',
          content: '🔄 **Page context refreshed!** I\'ve updated my understanding of the current page.',
          timestamp: new Date().toISOString(),
        };
        setMessages(prev => [...prev, refreshMessage]);
      }
    } catch (error) {
      console.error('Error refreshing context:', error);
    } finally {
      setIsRefreshingContext(false);
    }
  };

  const handleSendMessage = async (inputValue) => {
    if (!inputValue.trim()) return;

    if (!isAuthenticated || !walletAddress) {
      setError('Please connect your wallet first.');
      return;
    }

    // Detect purchase intent
    const intent = detectPurchaseIntent(inputValue);
    console.log('[CHAT] Purchase intent detected:', intent);

    // Create user message
    const userMessage = {
      id: `user-${Date.now()}`,
      type: 'user',
      content: inputValue,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setIsTyping(true);
    setError(null);

    try {
      // Try to use backend
      let currentSessionId = sessionId;
      
      if (!currentSessionId) {
        try {
          console.log('[CHAT] ============================================');
          console.log('[CHAT] Creating new session...');
          console.log('[CHAT] Wallet Address:', walletAddress);
          
          const tabInfo = await getCurrentTabInfo();
          console.log('[CHAT] ✓ Got tab info:', tabInfo);
          console.log('[CHAT]   - URL:', tabInfo.url);
          console.log('[CHAT]   - Domain:', tabInfo.domain);
          
          console.log('[CHAT] Calling createSession API...');
          const newSession = await createSession(walletAddress, tabInfo.url, tabInfo.domain);
          console.log('[CHAT] ✓ Session created:', newSession);
          
          currentSessionId = newSession.id || newSession.session_id;
          console.log('[CHAT] ✓ Session ID:', currentSessionId);
          
          setSessionId(currentSessionId);
          await saveCurrentSession(currentSessionId);
          console.log('[CHAT] ✓ Session saved to storage');
          console.log('[CHAT] ============================================');
        } catch (sessionError) {
          console.error('[CHAT] ✗✗✗ Failed to create session:', sessionError);
          console.error('[CHAT] Error details:', {
            message: sessionError.message,
            stack: sessionError.stack,
          });
          // Continue without session - backend unavailable
        }
      }

      if (currentSessionId) {
        // Try to send message to backend
        try {
          const response = await sendChatMessage(walletAddress, currentSessionId, inputValue);
          
          // Extract product data and check for buy intent
          const productData = extractProductData(response.answer);
          const shouldShowBuyCard = intent !== 'none' && productData && productData.title;
          
          console.log('[CHAT] Purchase Intent Detection:', {
            userMessage: inputValue,
            detectedIntent: intent,
            extractedProductData: productData,
            shouldShowBuyCard: shouldShowBuyCard
          });
          
          if (shouldShowBuyCard) {
            setCurrentProductData(productData);
            console.log('[CHAT] ✓ Buy Card will be shown with:', productData);
          } else {
            console.log('[CHAT] ✗ Buy Card not shown. Reason:', {
              intent: intent,
              hasProductData: !!productData,
              hasTitle: !!(productData && productData.title)
            });
          }

          // Add bot response from backend
          const botMessage = {
            id: `bot-${Date.now()}`,
            type: 'bot',
            content: response.answer,
            timestamp: new Date().toISOString(),
            showBuyCard: shouldShowBuyCard,
            productData: productData
          };

          setMessages(prev => [...prev, botMessage]);
          setIsBackendAvailable(true);
        } catch (apiError) {
          console.error('Backend API error:', apiError);
          throw apiError; // Let outer catch handle it
        }
      } else {
        // No backend session - fallback message
        throw new Error('Backend service unavailable. Please check your settings and ensure the backend is running.');
      }
    } catch (err) {
      console.error('Error sending message:', err);
      setIsBackendAvailable(false);
      
      // Show error but don't completely break
      const errorDetails = err.message.includes('403') 
        ? 'Your account may be inactive. Please contact support or check your registration status.'
        : err.message;
      
      setError(`Backend error: ${errorDetails}`);
      
      // Add error message to chat
      const errorMessage = {
        id: `error-${Date.now()}`,
        type: 'bot',
        content: `⚠️ **Backend Service Error**

I couldn't process your request. ${errorDetails}

**Troubleshooting:**
- Check Settings → Backend Configuration
- Ensure backend server is running
- Verify your account is active`,
        timestamp: new Date().toISOString(),
        isError: true,
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  const clearChat = async () => {
    // Clear session
    setSessionId(null);
    await saveCurrentSession(null);
    
    // Reset messages
    setMessages([{
      id: 'welcome',
      type: 'bot',
      content: 'Hello! I\'m your Lemo AI Assistant. I can help you find products and compare prices across platforms. Try asking me about a product!',
      timestamp: new Date().toISOString(),
    }]);
  };

  const formatTime = (timestamp) => {
    try {
      const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (err) {
      return '';
    }
  };

  // Check if content is markdown
  const isMarkdown = (content) => {
    return /[#*_`\[\]]/g.test(content) || content.includes('\n\n');
  };

  if (isLoadingSession) {
    return (
      <div className="flex flex-col h-full bg-white items-center justify-center">
        <div className="w-12 h-12 border-4 border-orange-500 border-t-transparent rounded-full animate-spin mb-4"></div>
        <p className="text-gray-600">Loading chat...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Error Banner */}
      {error && (
        <div className="bg-red-50 border-b border-red-200 p-3 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
          <span className="text-sm text-red-700">{error}</span>
        </div>
      )}

      {/* Backend Status Warning */}
      {!isBackendAvailable && (
        <div className="bg-yellow-50 border-b border-yellow-200 p-3 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-yellow-600 flex-shrink-0" />
          <span className="text-sm text-yellow-800">
            Backend service is unavailable. Check your settings and backend connection.
          </span>
        </div>
      )}

      {/* Not Authenticated Warning */}
      {!isAuthenticated && (
        <div className="bg-orange-50 border-b border-orange-200 p-4 flex items-center justify-center gap-3">
          <WalletIcon className="w-5 h-5 text-orange-600" />
          <span className="text-sm text-orange-800 font-medium">
            Please connect your wallet from the Wallet tab to start chatting
          </span>
        </div>
      )}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gradient-to-b from-gray-50 to-white">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex gap-3 animate-slide-in-up ${
              message.type === 'user' ? 'flex-row-reverse' : 'flex-row'
            }`}
          >
            {/* Avatar */}
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 overflow-hidden ${
                message.type === 'bot'
                  ? message.isError 
                    ? 'bg-gradient-to-br from-red-500 to-red-600'
                    : 'bg-gradient-to-br from-orange-500 to-orange-600'
                  : 'bg-gradient-to-br from-blue-400 to-cyan-400'
              }`}
            >
              {message.type === 'bot' ? (
                <img src={chrome.runtime.getURL('logo.png')} alt="Lemo" className="w-6 h-6 rounded-full object-cover" />
              ) : (
                '👤'
              )}
            </div>

            {/* Message Content */}
            <div className={`flex-1 max-w-[75%] ${message.type === 'user' ? 'items-end' : 'items-start'}`}>
              <div
                className={`rounded-2xl px-4 py-3 shadow-sm ${
                  message.type === 'bot'
                    ? message.isError
                      ? 'bg-red-50 border border-red-200 rounded-tl-sm text-gray-800'
                      : 'bg-white border border-orange-200 rounded-tl-sm text-gray-800'
                    : 'bg-gradient-to-r from-[#FF7A00] to-[#E76500] text-white rounded-tr-sm'
                }`}
              >
                {isMarkdown(message.content) && message.type === 'bot' ? (
                  <div className="prose prose-sm max-w-none">
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                  </div>
                ) : (
                  <p className="text-sm leading-relaxed text-current whitespace-pre-wrap">{message.content}</p>
                )}
              </div>
              <span className="text-xs text-gray-400 mt-1 block px-2">
                {formatTime(message.timestamp)}
              </span>
              
              {/* Show Buy Card if message has buy intent */}
              {message.showBuyCard && message.productData && (
                <div className="mt-3">
                  <BuyCard 
                    productData={message.productData}
                    onBuyClick={handleBuyNowClick}
                    walletAddress={walletAddress}
                  />
                </div>
              )}
              
              {/* Show Receipt Card if purchase successful */}
              {message.showReceiptCard && message.receiptData && (
                  <div className="mt-3">
                  <ReceiptCard
                    receiptData={message.receiptData}
                    onFeedbackClick={(receiptId) => {
                      // Add feedback card to messages
                      const feedbackMessage = {
                        id: `feedback-${Date.now()}`,
                        type: 'bot',
                        content: 'We\'d love to hear your feedback! Please rate your experience.',
                        timestamp: new Date().toISOString(),
                        showFeedbackCard: true,
                        receiptId: receiptId
                      };
                      setMessages(prev => [...prev, feedbackMessage]);
                    }}
                    />
                  </div>
                )}

              {/* Show Feedback Card */}
              {message.showFeedbackCard && message.receiptId && (
                  <div className="mt-3">
                  <FeedbackCard
                    receiptId={message.receiptId}
                    onSubmit={async (receiptId, feedbackData) => {
                      // Submit feedback through FVM service
                      if (!window.ethereum || !walletAddress) return;
                      
                      const provider = new ethers.BrowserProvider(window.ethereum);
                      const result = await submitFeedback(receiptId, feedbackData, walletAddress, provider);
                      
                      if (result.success) {
                        // Update message with submission status and reward
                        setMessages(prev => prev.map(msg => 
                          msg.id === message.id 
                            ? { ...msg, isFeedbackSubmitted: true, feedbackReward: result.reward }
                            : msg
                        ));
                      } else {
                        throw new Error(result.error);
                      }
                    }}
                    isSubmitted={message.isFeedbackSubmitted}
                    reward={message.feedbackReward}
                  />
                  </div>
                )}
            </div>
          </div>
        ))}

        {/* Typing Indicator */}
        {isTyping && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center overflow-hidden">
              <img src={chrome.runtime.getURL('logo.png')} alt="Lemo" className="w-6 h-6 rounded-full object-cover" />
            </div>
            <div className="bg-white border border-orange-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0s' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-3 bg-white border-t border-gray-200">
        <CurrentPageIndicator 
          url={currentPageUrl}
          domain={currentPageDomain}
          onRefresh={handleRefreshContext}
          isRefreshing={isRefreshingContext}
        />
        <AssistantInput 
          onSendMessage={handleSendMessage}
          disabled={!isAuthenticated || isTyping}
        />
        <div className="flex justify-between mt-1.5 text-xs px-0.5">
          {sessionId && (
            <button
              onClick={clearChat}
              className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 text-white text-xs font-medium transition-all duration-200 shadow-sm hover:shadow-md transform hover:scale-105"
            >
              <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              New Chat
            </button>
          )}
          <span className="text-gray-400 opacity-70 ml-auto text-[10px]">Powered by Lemo AI</span>
        </div>
      </div>
    </div>
  );
};

export default ChatWindow;
