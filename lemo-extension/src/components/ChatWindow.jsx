import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { AlertCircle, WalletIcon } from 'lucide-react';
import { ethers } from 'ethers';
import AssistantInput from './AssistantInput';
import BuyCard from './BuyCard';
import ReceiptCard from './ReceiptCard';
import FeedbackCard from './FeedbackCard';
import ComparisonTable from './ComparisonTable';
import CurrentPageIndicator from './CurrentPageIndicator';
import { checkUserExists, getAuthHeader, getConnectedWallet, loginWithSIWE } from '../utils/auth.js';
import {
  createSession,
  getCurrentSession,
  getCurrentTabInfo,
  getPageSession,
  getSessionDetails,
  saveCurrentSession,
  savePageSession,
  sendChatMessage,
} from '../utils/session.js';
import { submitFeedback } from '../services/fvmService.js';

const WELCOME_MESSAGE = 'Hello! I am your Lemo AI Assistant. I can help you understand products, compare prices, and shortlist better alternatives across platforms.';

const buildUiMessage = (message) => ({
  id: message.id,
  type: message.message_type === 'user' ? 'user' : 'bot',
  content: message.message,
  timestamp: message.created_at,
});

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

  const safeSendMessage = async (message, timeoutMs = 15000) => {
    const timeout = new Promise((_, reject) => {
      setTimeout(() => reject(new Error('Operation timed out')), timeoutMs);
    });
    return Promise.race([chrome.runtime.sendMessage(message), timeout]);
  };

  const ensureWalletAuthentication = async (wallet) => {
    const existingAuth = await getAuthHeader();
    if (existingAuth) {
      return true;
    }

    const userStatus = await checkUserExists(wallet);
    if (!userStatus.exists) {
      throw new Error('Your wallet is not registered yet. Open the Wallet tab and complete registration first.');
    }

    if (userStatus.isInactive) {
      throw new Error(userStatus.error || 'Your account is inactive.');
    }

    const signMessage = async (message) => {
      const response = await safeSendMessage({
        action: 'SIGN_MESSAGE',
        account: wallet,
        message,
      });
      if (response?.success && response?.signature) {
        return response.signature;
      }
      throw new Error(response?.error || 'Failed to sign authentication message');
    };

    const loginResult = await loginWithSIWE(wallet, signMessage);
    if (!loginResult.success) {
      throw new Error(loginResult.error || 'Authentication failed');
    }

    return true;
  };

  const isAuthFailure = (message = '') => {
    const normalized = message.toLowerCase();
    return normalized.includes('not authenticated')
      || normalized.includes('invalid or expired token')
      || normalized.includes('authentication failed')
      || normalized.includes('401')
      || normalized.includes('403')
      || normalized.includes('user not found');
  };

  const isTrackablePageUrl = (url = '') => (
    Boolean(url)
      && !url.startsWith('chrome://')
      && !url.startsWith('chrome-extension://')
      && !url.startsWith('edge://')
      && !url.startsWith('about:')
  );

  const createWelcomeMessage = (content = WELCOME_MESSAGE) => ({
    id: `welcome-${Date.now()}`,
    type: 'bot',
    content,
    timestamp: new Date().toISOString(),
  });

  const createContextSwitchMessage = (domain) => ({
    id: `page-switch-${Date.now()}`,
    type: 'bot',
    content: `### 🔄 Context updated\nYou are now browsing **${domain}**. I switched to this page's chat context so comparisons and recommendations stay tied to the current product.`,
    timestamp: new Date().toISOString(),
  });

  const loadSessionMessages = async (wallet, activeSessionId, { appendContextMessage = null } = {}) => {
    if (!activeSessionId) {
      const baseMessages = [createWelcomeMessage()];
      if (appendContextMessage) {
        baseMessages.push(appendContextMessage);
      }
      setMessages(baseMessages);
      return;
    }

    const sessionData = await getSessionDetails(wallet, activeSessionId);
    const history = sessionData?.session?.chat_messages || [];
    const formattedMessages = history.length ? history.map(buildUiMessage) : [createWelcomeMessage()];
    if (appendContextMessage) {
      formattedMessages.push(appendContextMessage);
    }
    setMessages(formattedMessages);
  };

  const ensureSessionForPage = async (wallet, tabInfo, { forceCreate = false, announceSwitch = false } = {}) => {
    const existingPageSessionId = !forceCreate ? await getPageSession(tabInfo.url) : null;
    let activeSessionId = existingPageSessionId;

    if (!activeSessionId) {
      const created = await createSession(wallet, tabInfo.url, tabInfo.domain);
      activeSessionId = created.id || created.session_id;
      await savePageSession(tabInfo.url, activeSessionId);
    }

    setSessionId(activeSessionId);
    await saveCurrentSession(activeSessionId);
    await loadSessionMessages(wallet, activeSessionId, {
      appendContextMessage: announceSwitch ? createContextSwitchMessage(tabInfo.domain) : null,
    });
    return activeSessionId;
  };

  useEffect(() => {
    const checkUrlChange = async () => {
      try {
        const tabInfo = await getCurrentTabInfo();
        const currentUrl = tabInfo.url;

        if (!isTrackablePageUrl(currentUrl)) {
          return;
        }

        if (currentUrl !== previousUrlRef.current && previousUrlRef.current !== '') {
          setCurrentPageUrl(tabInfo.url);
          setCurrentPageDomain(tabInfo.domain);
          setCurrentProductData(null);

          if (walletAddress) {
            try {
              await ensureSessionForPage(walletAddress, tabInfo, { announceSwitch: true });
            } catch (sessionError) {
              console.error('Error creating session for new page:', sessionError);
            }
          }
        }

        previousUrlRef.current = currentUrl;
      } catch (urlError) {
        console.error('Error checking URL change:', urlError);
      }
    };

    const interval = setInterval(checkUrlChange, 2000);
    checkUrlChange();
    return () => clearInterval(interval);
  }, [walletAddress]);

  const initializeChat = async () => {
    try {
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

      setWalletAddress(wallet);
      await ensureWalletAuthentication(wallet);
      setIsAuthenticated(true);

      const tabInfo = await getCurrentTabInfo();
      setCurrentPageUrl(tabInfo.url);
      setCurrentPageDomain(tabInfo.domain);
      previousUrlRef.current = tabInfo.url;

      const pageSessionId = await getPageSession(tabInfo.url);
      const existingSessionId = pageSessionId || await getCurrentSession();

      if (existingSessionId) {
        try {
          if (pageSessionId) {
            setSessionId(pageSessionId);
            await saveCurrentSession(pageSessionId);
            await loadSessionMessages(wallet, pageSessionId);
          } else {
            setSessionId(existingSessionId);
            await saveCurrentSession(existingSessionId);
            await loadSessionMessages(wallet, existingSessionId);
          }
          setIsBackendAvailable(true);
        } catch (sessionError) {
          console.error('Error loading session from backend:', sessionError);
          if (isAuthFailure(sessionError.message)) {
            setIsAuthenticated(false);
            setError(sessionError.message);
          } else {
            setIsBackendAvailable(false);
            setError('Backend unavailable. Chat will work but history will not be saved.');
          }
          setMessages([createWelcomeMessage('Hello! I am your Lemo AI Assistant. Backend connectivity is limited right now.')]);
        }
      } else {
        setMessages([createWelcomeMessage()]);
      }

      setIsLoadingSession(false);
    } catch (initError) {
      console.error('Error initializing chat:', initError);
      setIsLoadingSession(false);
      setIsAuthenticated(false);
      setError(initError.message || 'Failed to initialize chat. Please try again.');
    }
  };

  const detectPurchaseIntent = (message) => {
    const highIntentKeywords = [
      'buy', 'purchase', 'order', 'ready to buy', 'want to buy', 'i will buy',
      'show buy card', 'buy card', 'buy now', 'add to cart', 'checkout', 'proceed to buy',
    ];

    const lowerMessage = message.toLowerCase().trim();
    return highIntentKeywords.some((keyword) => lowerMessage.includes(keyword)) ? 'high' : 'none';
  };

  const extractProductData = (response) => {
    try {
      const priceMatch = response.match(/[₹$][\d,.]+/);
      const titleMatch = response.match(/\*\*(.*?)\*\*/);
      const ratingMatch = response.match(/(\d+\.?\d*)\/5/);
      const reviewMatch = response.match(/\((\d+[\d,]*) reviews?\)/i);
      const descMatch = response.match(/\*\*.*?\*\*\s*([^.]+)/);

      return {
        title: titleMatch ? titleMatch[1] : '',
        price: priceMatch ? priceMatch[0] : '',
        rating: ratingMatch ? ratingMatch[1] : '',
        reviewCount: reviewMatch ? reviewMatch[1] : '',
        description: descMatch ? descMatch[1].trim() : '',
        url: currentPageUrl || window.location.href,
      };
    } catch (extractError) {
      console.error('Error extracting product data:', extractError);
      return null;
    }
  };

  const handleBuyNowClick = async (productData, paymentMethod) => {
    try {
      if (!walletAddress) {
        throw new Error('Please connect your wallet first from the Wallet tab.');
      }

      const loadingMessage = {
        id: `loading-${Date.now()}`,
        type: 'bot',
        content: `Processing ${paymentMethod} payment...`,
        timestamp: new Date().toISOString(),
        isLoading: true,
      };
      setMessages((prev) => [...prev, loadingMessage]);

      const walletCheck = await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          window.removeEventListener('message', handler);
          reject(new Error('Wallet check timeout'));
        }, 5000);

        window.postMessage({
          source: 'lemo-extension',
          action: 'CHECK_WALLET',
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

      const result = await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          window.removeEventListener('message', handler);
          reject(new Error('Payment processing timeout'));
        }, 60000);

        window.postMessage({
          source: 'lemo-extension',
          action: 'PROCESS_PAYMENT',
          productData,
          paymentMethod,
          walletAddress,
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
        setMessages((prev) => prev.filter((msg) => msg.id !== loadingMessage.id));
        const paymentData = result.result;
        const receiptUrl = paymentData.receiptCid ? `https://gateway.lighthouse.storage/ipfs/${paymentData.receiptCid}` : 'N/A';
        const successMessage = {
          id: `success-${Date.now()}`,
          type: 'bot',
          content: `Payment successful.\n\nTransaction Hash: ${paymentData.txHash || 'N/A'}\nAmount Paid: ${paymentData.amountPaid || 'N/A'} ${paymentData.currency || 'PYUSD'}\nReceipt ID: ${paymentData.receiptId || 'N/A'}\nBlock Number: ${paymentData.blockNumber || 'N/A'}\nMerchant Wallet: ${paymentData.merchantWallet || 'N/A'}\nReceipt URL: ${receiptUrl}`,
          timestamp: new Date().toISOString(),
          isSuccess: true,
        };
        setMessages((prev) => [...prev, successMessage]);
      } else {
        throw new Error(result.error || result.result?.error || 'Payment processing failed');
      }
    } catch (buyError) {
      console.error('[ChatWindow] Buy Now error:', buyError);
      setMessages((prev) => prev.filter((msg) => !msg.isLoading));
      setMessages((prev) => [...prev, {
        id: `error-${Date.now()}`,
        type: 'bot',
        content: `Payment failed\n\n${buyError.message}\n\nPlease ensure you are on Sepolia testnet and have sufficient balance.`,
        timestamp: new Date().toISOString(),
        isError: true,
      }]);
    }
  };

  const handleRefreshContext = async () => {
    setIsRefreshingContext(true);
    try {
      const tabInfo = await getCurrentTabInfo();
      setCurrentPageUrl(tabInfo.url);
      setCurrentPageDomain(tabInfo.domain);
      setCurrentProductData(null);

      if (walletAddress) {
        await ensureSessionForPage(walletAddress, tabInfo, { forceCreate: true, announceSwitch: true });
      }
    } catch (refreshError) {
      console.error('Error refreshing context:', refreshError);
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

    const intent = detectPurchaseIntent(inputValue);
    const userMessage = {
      id: `user-${Date.now()}`,
      type: 'user',
      content: inputValue,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsTyping(true);
    setError(null);

    try {
      let currentSessionId = sessionId;
      let tabInfo = null;

      if (!currentSessionId) {
        try {
          tabInfo = await getCurrentTabInfo();
          currentSessionId = await ensureSessionForPage(walletAddress, tabInfo);
        } catch (sessionError) {
          console.error('[CHAT] Failed to create session:', sessionError);
          if (isAuthFailure(sessionError.message)) {
            if (!tabInfo) {
              tabInfo = await getCurrentTabInfo();
            }
            await ensureWalletAuthentication(walletAddress);
            currentSessionId = await ensureSessionForPage(walletAddress, tabInfo);
          }
        }
      }

      if (!currentSessionId) {
        throw new Error('Backend service unavailable. Please check your settings and ensure the backend is running.');
      }

      const sendAndRenderResponse = async () => {
        const response = await sendChatMessage(walletAddress, currentSessionId, inputValue);
        const productData = response.product || null;
        const comparisonData = response.comparison || null;
        const shouldShowBuyCard = intent !== 'none' && productData && productData.title && !comparisonData?.products?.length;

        if (productData?.title) {
          setCurrentProductData(productData);
        }

        const botMessage = {
          id: `bot-${Date.now()}`,
          type: 'bot',
          content: response.answer,
          timestamp: new Date().toISOString(),
          showBuyCard: shouldShowBuyCard,
          productData,
          showComparisonTable: Boolean(comparisonData?.products?.length),
          comparisonData,
        };

        setMessages((prev) => [...prev, botMessage]);
        setIsBackendAvailable(true);
      };

      try {
        await sendAndRenderResponse();
      } catch (apiError) {
        console.error('Backend API error:', apiError);
        if (isAuthFailure(apiError.message)) {
          await ensureWalletAuthentication(walletAddress);
          await sendAndRenderResponse();
        } else {
          throw apiError;
        }
      }
    } catch (sendError) {
      console.error('Error sending message:', sendError);
      setIsBackendAvailable(false);

      const errorDetails = sendError.message.includes('403')
        ? 'Your account may be inactive. Please contact support or check your registration status.'
        : sendError.message;

      setError(`Backend error: ${errorDetails}`);
      setMessages((prev) => [...prev, {
        id: `error-${Date.now()}`,
        type: 'bot',
        content: `Backend service error\n\nI couldn't process your request. ${errorDetails}\n\nTroubleshooting:\n- Check Settings -> Backend Configuration\n- Ensure backend server is running\n- Verify your account is active`,
        timestamp: new Date().toISOString(),
        isError: true,
      }]);
    } finally {
      setIsTyping(false);
    }
  };

  const clearChat = async () => {
    setSessionId(null);
    setCurrentProductData(null);
    await saveCurrentSession(null);
    await savePageSession(currentPageUrl, null);
    setMessages([createWelcomeMessage('Hello! I am your Lemo AI Assistant. I can help you find products and compare prices across platforms. Try asking me about the current product or tell me your budget and preferences.')]);
  };

  const formatTime = (timestamp) => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (err) {
      return '';
    }
  };

  const isMarkdown = (content) => /[#*_`\[\]]/g.test(content) || content.includes('\n\n');

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
      {error && (
        <div className="bg-red-50 border-b border-red-200 p-3 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
          <span className="text-sm text-red-700">{error}</span>
        </div>
      )}

      {!isBackendAvailable && (
        <div className="bg-yellow-50 border-b border-yellow-200 p-3 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-yellow-600 flex-shrink-0" />
          <span className="text-sm text-yellow-800">
            Backend service is unavailable. Check your settings and backend connection.
          </span>
        </div>
      )}

      {!isAuthenticated && (
        <div className="bg-orange-50 border-b border-orange-200 p-4 flex items-center justify-center gap-3">
          <WalletIcon className="w-5 h-5 text-orange-600" />
          <span className="text-sm text-orange-800 font-medium">
            Please connect your wallet from the Wallet tab to start chatting
          </span>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gradient-to-b from-gray-50 to-white">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex gap-3 animate-slide-in-up ${message.type === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
          >
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
                'U'
              )}
            </div>

            <div className={`flex-1 max-w-[82%] ${message.type === 'user' ? 'items-end' : 'items-start'}`}>
              <div
                className={`rounded-2xl px-4 py-3 shadow-sm ${
                  message.type === 'bot'
                    ? message.isError
                      ? 'bg-red-50 border border-red-200 rounded-tl-sm text-gray-800'
                      : 'bg-white border border-orange-200 rounded-tl-sm text-gray-800 shadow-[0_12px_30px_rgba(249,115,22,0.08)]'
                    : 'bg-gradient-to-r from-[#FF7A00] to-[#E76500] text-white rounded-tr-sm shadow-[0_12px_28px_rgba(231,101,0,0.24)]'
                }`}
              >
                {isMarkdown(message.content) && message.type === 'bot' ? (
                  <div className="prose prose-sm max-w-none prose-headings:mb-2 prose-headings:mt-0 prose-headings:text-gray-900 prose-p:my-2 prose-p:text-gray-700 prose-strong:text-gray-900 prose-ul:my-2 prose-li:my-1 prose-li:text-gray-700">
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                  </div>
                ) : (
                  <p className="text-sm leading-relaxed text-current whitespace-pre-wrap">{message.content}</p>
                )}
              </div>
              <span className="text-xs text-gray-400 mt-1 block px-2">
                {formatTime(message.timestamp)}
              </span>

              {message.showBuyCard && message.productData && (
                <div className="mt-3">
                  <BuyCard
                    productData={message.productData}
                    onBuyClick={handleBuyNowClick}
                    walletAddress={walletAddress}
                  />
                </div>
              )}

              {message.showComparisonTable && message.comparisonData && (
                <div className="mt-3">
                  <ComparisonTable comparisonData={message.comparisonData} />
                </div>
              )}

              {message.showReceiptCard && message.receiptData && (
                <div className="mt-3">
                  <ReceiptCard
                    receiptData={message.receiptData}
                    onFeedbackClick={(receiptId) => {
                      const feedbackMessage = {
                        id: `feedback-${Date.now()}`,
                        type: 'bot',
                        content: "We'd love to hear your feedback! Please rate your experience.",
                        timestamp: new Date().toISOString(),
                        showFeedbackCard: true,
                        receiptId,
                      };
                      setMessages((prev) => [...prev, feedbackMessage]);
                    }}
                  />
                </div>
              )}

              {message.showFeedbackCard && message.receiptId && (
                <div className="mt-3">
                  <FeedbackCard
                    receiptId={message.receiptId}
                    onSubmit={async (receiptId, feedbackData) => {
                      if (!window.ethereum || !walletAddress) return;

                      const provider = new ethers.BrowserProvider(window.ethereum);
                      const result = await submitFeedback(receiptId, feedbackData, walletAddress, provider);

                      if (result.success) {
                        setMessages((prev) => prev.map((msg) => (
                          msg.id === message.id
                            ? { ...msg, isFeedbackSubmitted: true, feedbackReward: result.reward }
                            : msg
                        )));
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
