import React, { useState, useEffect } from 'react';
import { Wallet, CheckCircle, XCircle, AlertCircle, RefreshCw, ExternalLink, Copy, ChevronDown, User } from 'lucide-react';
import RegistrationModal from './RegistrationModal';
import { checkUserExists, registerUser } from '../utils/auth.js';

const WalletConnect = () => {
  // Ultimate safety wrapper to prevent any crashes
  try {
  const [account, setAccount] = useState(null);
  const [network, setNetwork] = useState(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isLoadingBalances, setIsLoadingBalances] = useState(false);
  const [error, setError] = useState(null);
  const [balances, setBalances] = useState(null);
  const [selectedNetwork, setSelectedNetwork] = useState('sepolia');
  const [showNetworkDropdown, setShowNetworkDropdown] = useState(false);
  const [selectedToken, setSelectedToken] = useState('ETH');
  const [showTokenDropdown, setShowTokenDropdown] = useState(false);
  const [currentBalance, setCurrentBalance] = useState(null);
  const [isLoadingSpecificBalance, setIsLoadingSpecificBalance] = useState(false);
  
  // Authentication states
  const [showRegistrationModal, setShowRegistrationModal] = useState(false);
  const [isRegistering, setIsRegistering] = useState(false);
  const [userData, setUserData] = useState(null);
  const [isCheckingUser, setIsCheckingUser] = useState(false);

  const networks = [
    { id: 'sepolia', name: 'Sepolia', tokens: ['ETH', 'USDC', 'PYUSD'] },
    { id: 'filecoin-calibration', name: 'Filecoin Calibration', tokens: ['FIL', 'TFIL'] }
  ];

  const getAvailableTokens = () => {
    const currentNetwork = networks.find(n => n.id === selectedNetwork);
    return currentNetwork ? currentNetwork.tokens : [];
  };

  // Helper function to wrap async operations with timeout
  const withTimeout = (promise, timeoutMs) => {
    return Promise.race([
      promise,
      new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Operation timed out')), timeoutMs)
      )
    ]);
  };

  // Helper function to safely send messages with timeout
  const safeSendMessage = async (message, timeoutMs = 10000) => {
    try {
      // Check if runtime context is valid
      if (!chrome || !chrome.runtime || !chrome.runtime.sendMessage) {
        console.log('Runtime context is invalid, ignoring message');
        return null;
      }
      
      return await withTimeout(chrome.runtime.sendMessage(message), timeoutMs);
    } catch (err) {
      // Check for extension context invalidated error
      if (err && err.message && (err.message.includes('Extension context invalidated') || err.message.includes('context invalidated'))) {
        console.log('Extension context invalidated (ignoring):', err.message);
        return null;
      }
      console.error('Message send error:', err);
      throw new Error(`Failed to send message: ${err.message}`);
    }
  };

  // Helper function to safely display balance
  const displayBalance = (balance, decimals = 18) => {
    try {
      if (balance == null || balance === undefined || balance === '') return '0.0000';
      const parsed = parseInt(balance, 16);
      if (isNaN(parsed)) return '0.0000';
      return (parsed / Math.pow(10, decimals)).toFixed(4);
    } catch (err) {
      console.error('Balance parsing error:', err);
      return '0.0000';
    }
  };

  useEffect(() => {
    checkConnection();
    loadStoredPreferences();
    
    // Add comprehensive error handler to prevent popup from closing
    const handleUnhandledRejection = (event) => {
      console.error('Unhandled promise rejection:', event.reason);
      setError(`Error: ${event.reason?.message || 'Unknown error occurred'}`);
      event.preventDefault(); // Prevent popup from closing
      event.stopPropagation(); // Stop error propagation
    };
    
    const handleError = (event) => {
      console.error('Global error:', event.error);
      setError(`Error: ${event.error?.message || 'Unknown error occurred'}`);
      event.preventDefault(); // Prevent popup from closing
      event.stopPropagation(); // Stop error propagation
    };
    
    // Add additional error handlers for different error types
    const handleReferenceError = (event) => {
      console.error('Reference error:', event.error);
      setError(`Reference Error: ${event.error?.message || 'Function not defined'}`);
      event.preventDefault();
      event.stopPropagation();
    };
    
    window.addEventListener('unhandledrejection', handleUnhandledRejection);
    window.addEventListener('error', handleError);
    window.addEventListener('error', handleReferenceError);
    
    return () => {
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
      window.removeEventListener('error', handleError);
      window.removeEventListener('error', handleReferenceError);
    };
  }, []);

  useEffect(() => {
    if (account) {
      fetchBalances();
      fetchSpecificTokenBalance();
    }
  }, [account]);

  useEffect(() => {
    if (account && network) {
      fetchBalances();
      fetchSpecificTokenBalance();
    }
  }, [selectedNetwork]);

  useEffect(() => {
    if (account && selectedToken) {
      fetchSpecificTokenBalance();
      saveStoredPreferences();
    }
  }, [selectedToken]);

  const loadStoredPreferences = async () => {
    try {
      const result = await chrome.storage.sync.get(['selectedNetwork', 'selectedToken']);
      if (result.selectedNetwork) {
        setSelectedNetwork(result.selectedNetwork);
      }
      if (result.selectedToken) {
        setSelectedToken(result.selectedToken);
      }
    } catch (err) {
      console.error('Error loading stored preferences:', err);
    }
  };

  const saveStoredPreferences = async () => {
    try {
      await chrome.storage.sync.set({
        selectedNetwork: selectedNetwork,
        selectedToken: selectedToken
      });
    } catch (err) {
      console.error('Error saving preferences:', err);
    }
  };

  const checkConnection = async () => {
    try {
      // Check if we're in popup context (no chrome.tabs access)
      if (typeof chrome.tabs === 'undefined') {
        // In popup context, we need to get tab info differently
        const response = await safeSendMessage({ action: 'CHECK_WALLET' });
        
        if (response && response.success && response.result && response.result.isInstalled) {
          if (response.result.accounts && response.result.accounts.length > 0) {
            setAccount(response.result.accounts[0]);
            setNetwork(response.result.network.name);
            // Sync selectedNetwork with actual network
            if (response.result.network.name === 'sepolia') {
              setSelectedNetwork('sepolia');
            } else if (response.result.network.name === 'filecoin-calibration') {
              setSelectedNetwork('filecoin-calibration');
            }
          }
        }
        return;
      }

      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab) {
        console.log('No active tab found');
        return;
      }
      
      const response = await safeSendMessage({ action: 'CHECK_WALLET', tabId: tab.id });
      
      if (response && response.success && response.result && response.result.isInstalled) {
        if (response.result.accounts && response.result.accounts.length > 0) {
          setAccount(response.result.accounts[0]);
          setNetwork(response.result.network.name);
          // Sync selectedNetwork with actual network
          if (response.result.network.name === 'sepolia') {
            setSelectedNetwork('sepolia');
          } else if (response.result.network.name === 'filecoin-calibration') {
            setSelectedNetwork('filecoin-calibration');
          }
        }
        }
      } catch (err) {
        console.error('Error checking connection:', err);
      // Handle extension context invalidation
      if (err.message && err.message.includes('Extension context invalidated')) {
        setError('Extension needs to be reloaded. Please refresh the page.');
      }
    }
  };

  const connectWallet = async () => {
    setIsConnecting(true);
    setError(null);

    // Prevent popup from closing during connection
    const preventClose = () => {
      window.addEventListener('beforeunload', (e) => {
        e.preventDefault();
        e.returnValue = '';
      });
    };
    
    const allowClose = () => {
      window.removeEventListener('beforeunload', (e) => {
        e.preventDefault();
        e.returnValue = '';
      });
    };

    try {
      preventClose();
      
      // Check if we're in popup context (no chrome.tabs access)
      if (typeof chrome.tabs === 'undefined') {
        // In popup context, send message without tabId
        const response = await safeSendMessage({ action: 'CONNECT_WALLET' });
        
      if (response && response.success && response.result && response.result.accounts && response.result.accounts.length > 0) {
        const walletAddress = response.result.accounts[0];
        setAccount(walletAddress);
        setNetwork(response.result.network.name);
        
        // Sync selectedNetwork with actual network
        if (response.result.network.name === 'sepolia') {
          setSelectedNetwork('sepolia');
        } else if (response.result.network.name === 'filecoin-calibration') {
          setSelectedNetwork('filecoin-calibration');
        }
        
        // Store in chrome storage
        chrome.storage.sync.set({ connectedWallet: walletAddress });
        
        // Check if user exists in backend
        await checkAndAuthenticateUser(walletAddress);
      } else if (response && response.error) {
        setError(response.error);
      } else {
        setError('Failed to connect to wallet. Please try again.');
      }
      return;
      }

      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab) {
        setError('No active tab found. Please open the extension on a web page.');
      return;
    }

      const response = await safeSendMessage({ action: 'CONNECT_WALLET', tabId: tab.id });
      
      if (response && response.success && response.result && response.result.accounts && response.result.accounts.length > 0) {
        const walletAddress = response.result.accounts[0];
        setAccount(walletAddress);
        setNetwork(response.result.network.name);
        
        // Sync selectedNetwork with actual network
        if (response.result.network.name === 'sepolia') {
          setSelectedNetwork('sepolia');
        } else if (response.result.network.name === 'filecoin-calibration') {
          setSelectedNetwork('filecoin-calibration');
        }
        
        // Store in chrome storage
        chrome.storage.sync.set({ connectedWallet: walletAddress });
        
        // Check if user exists in backend
        await checkAndAuthenticateUser(walletAddress);
      } else if (response && response.error) {
        setError(response.error);
      } else {
        setError('Failed to connect to wallet. Please try again.');
      }
    } catch (err) {
      console.error('Wallet connection error:', err);
      if (err.message && err.message.includes('Extension context invalidated')) {
        setError('Extension needs to be reloaded. Please refresh the page.');
      } else if (err.message && err.message.includes('User rejected')) {
        setError('Connection was rejected. Please try again.');
      } else {
        setError(err.message || 'Failed to connect wallet. Please ensure MetaMask is installed and unlocked.');
      }
    } finally {
      allowClose();
      setIsConnecting(false);
    }
  };

  const switchToSepolia = async () => {
    setIsConnecting(true);
    setError(null);

    try {
      const response = await safeSendMessage({ action: 'SWITCH_TO_SEPOLIA' });
      
      if (response && response.success) {
        setNetwork('sepolia');
        setSelectedNetwork('sepolia');
        // Refresh balances after network switch
        setTimeout(() => {
          fetchBalances();
        }, 2000);
      } else if (response && response.error) {
        setError(response.error);
      }
    } catch (err) {
      setError(err.message || 'Failed to switch to Sepolia');
    } finally {
      setIsConnecting(false);
    }
  };

  const switchToFilecoin = async () => {
    setIsConnecting(true);
    setError(null);

    try {
      const response = await safeSendMessage({ action: 'SWITCH_TO_FILECOIN' });
      
      if (response && response.success) {
        setNetwork('filecoin-calibration');
        setSelectedNetwork('filecoin-calibration');
        // Refresh balances after network switch
        setTimeout(() => {
          fetchBalances();
        }, 2000);
      } else if (response && response.error) {
        setError(response.error);
      }
    } catch (err) {
      setError(err.message || 'Failed to switch to Filecoin Calibration');
    } finally {
      setIsConnecting(false);
    }
  };

  const handleNetworkChange = async (networkId) => {
    setSelectedNetwork(networkId);
    setShowNetworkDropdown(false);
    
    // Reset token selection to first available token for new network
    const availableTokens = networks.find(n => n.id === networkId)?.tokens || [];
    if (availableTokens.length > 0) {
      setSelectedToken(availableTokens[0]);
    }
    
    if (networkId === 'sepolia') {
      await switchToSepolia();
    } else if (networkId === 'filecoin-calibration') {
      await switchToFilecoin();
    }
  };

  const handleTokenChange = (tokenSymbol) => {
    setSelectedToken(tokenSymbol);
    setShowTokenDropdown(false);
  };

  const copyAddress = async () => {
    try {
      await navigator.clipboard.writeText(account);
      // You could add a toast notification here
      console.log('Address copied to clipboard');
    } catch (err) {
      console.error('Failed to copy address:', err);
    }
  };

  const fetchBalances = async () => {
    if (!account) return;
    
    setIsLoadingBalances(true);
    setError(null);

    try {
      console.log('Fetching balances for account:', account, 'network:', selectedNetwork);
      const response = await safeSendMessage({ action: 'GET_TOKEN_BALANCES' });
      console.log('Balance response:', response);
      
      if (response && response.success && response.result) {
        console.log('Setting balances:', response.result);
        setBalances(response.result);
      } else if (response && response.error) {
        console.error('Balance error:', response.error);
        setError(response.error);
      } else {
        console.log('No balance data received');
      }
    } catch (err) {
      console.error('Error fetching balances:', err);
      setError(err.message || 'Failed to fetch balances');
    } finally {
      setIsLoadingBalances(false);
    }
  };

  const fetchSpecificTokenBalance = async () => {
    if (!account || !selectedToken) {
      console.warn('Missing account or selectedToken for balance fetch:', { account, selectedToken });
      return;
    }
    
    setIsLoadingSpecificBalance(true);
    setError(null);

    try {
      console.log('Fetching specific token balance:', selectedToken, 'for account:', account);
      const response = await safeSendMessage({ 
        action: 'GET_SPECIFIC_TOKEN_BALANCE',
        tokenSymbol: selectedToken,
        account: account
      });
      console.log('Specific balance response:', response);
      
      if (response && response.success && response.result) {
        console.log('Setting specific balance:', response.result);
        setCurrentBalance(response.result);
        setError(null); // Clear any previous errors
      } else if (response && response.error) {
        console.error('Specific balance error:', response.error);
        setError(response.error);
        setCurrentBalance(null);
      } else {
        console.log('No specific balance data received');
        setCurrentBalance(null);
      }
    } catch (err) {
      console.error('Error fetching specific balance:', err);
      setError(err.message || 'Failed to fetch token balance');
      setCurrentBalance(null);
    } finally {
      setIsLoadingSpecificBalance(false);
    }
  };

  // Check if user exists in backend
  const checkAndAuthenticateUser = async (walletAddress) => {
    setIsCheckingUser(true);
    setError(null);
    
    try {
      const result = await checkUserExists(walletAddress);
      
      if (result.isInactive) {
        // User exists but is inactive
        setError(`⚠️ Account Inactive: ${result.error}. Please contact support to activate your account. Wallet features will still work.`);
        setUserData(null);
      } else if (result.exists) {
        // User exists and is active, load their data
        const user = result.user;
        
        // Format user data to match expected structure
        const formattedUser = {
          id: user.id || walletAddress,
          email: user.email,
          firstName: user.first_name || user.firstName,
          lastName: user.last_name || user.lastName,
          walletAddress: user.wallet_address || user.walletAddress || walletAddress,
          otherDetails: user.other_details || user.otherDetails,
        };
        
        setUserData(formattedUser);
        console.log('User authenticated:', formattedUser);
      } else {
        // New user, show registration modal
        setShowRegistrationModal(true);
      }
    } catch (err) {
      console.error('Error checking user:', err);
      setError(`Authentication failed: ${err.message}. You can still use the wallet features.`);
    } finally {
      setIsCheckingUser(false);
    }
  };

  // Handle user registration
  const handleRegistration = async (registrationData) => {
    setIsRegistering(true);
    setError(null);
    
    try {
      const response = await registerUser(account, registrationData);
      console.log('Registration response:', response);
      
      // Backend returns: { success: true, data: { user: {...} } }
      const user = response.data?.user || response.user || response;
      
      // Format user data to match expected structure
      const formattedUser = {
        id: user.id || account,
        email: user.email,
        firstName: user.first_name || user.firstName,
        lastName: user.last_name || user.lastName,
        walletAddress: user.wallet_address || user.walletAddress || account,
        otherDetails: user.other_details || user.otherDetails || registrationData.otherDetails,
      };
      
      setUserData(formattedUser);
      setShowRegistrationModal(false);
      console.log('User registered successfully:', formattedUser);
      
      // Force a re-render to show profile
      setTimeout(() => {
        setError(null);
      }, 100);
    } catch (err) {
      console.error('Error registering user:', err);
      setError(`Registration failed: ${err.message}`);
      setIsRegistering(false);
    }
  };

  // Cancel registration
  const handleCancelRegistration = () => {
    setShowRegistrationModal(false);
    // Optionally disconnect wallet if user cancels registration
    // disconnectWallet();
  };

  const disconnectWallet = () => {
    setAccount(null);
    setNetwork(null);
    setUserData(null);
    chrome.storage.sync.remove('connectedWallet');
  };

  const shortenAddress = (address) => {
    if (!address) return '';
    return `${address.substring(0, 6)}...${address.substring(address.length - 4)}`;
  };

  return (
    <div className="space-y-4">
      {/* Registration Modal */}
      {showRegistrationModal && (
        <RegistrationModal
          walletAddress={account}
          onSubmit={handleRegistration}
          onCancel={handleCancelRegistration}
          isLoading={isRegistering}
        />
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-red-700">{error}</div>
        </div>
      )}

      {/* Checking User Status */}
      {isCheckingUser && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-start gap-3">
          <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin flex-shrink-0 mt-0.5"></div>
          <div className="text-sm text-blue-700">Authenticating with backend...</div>
        </div>
      )}

      {!account ? (
        <div className="bg-gradient-to-br from-orange-50 to-orange-100 rounded-2xl p-6 border border-orange-200">
          <div className="text-center space-y-4">
            <div className="w-16 h-16 mx-auto bg-gradient-to-br from-[#FF7A00] to-[#E76500] rounded-full flex items-center justify-center">
              <Wallet className="w-8 h-8 text-white" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-800 mb-1">Connect Your Wallet</h3>
              <p className="text-sm text-gray-600">
                Connect MetaMask to access blockchain features
              </p>
            </div>
            <button
              onClick={connectWallet}
              disabled={isConnecting}
              className="w-full py-3 px-4 bg-gradient-to-r from-[#FF7A00] to-[#E76500] text-white rounded-xl font-medium hover:shadow-lg disabled:opacity-50 transition-all transform hover:scale-105"
            >
              {isConnecting ? (
                <span className="flex items-center justify-center gap-2">
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  Connecting...
                </span>
              ) : (
                'Connect MetaMask'
              )}
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Network Selector */}
          <div className="bg-gradient-to-br from-orange-50 to-white rounded-2xl p-4 border border-orange-200">
            <h3 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
              <ExternalLink className="w-5 h-5" />
              Select Network
            </h3>
            
            <div className="relative">
              <button
                onClick={() => setShowNetworkDropdown(!showNetworkDropdown)}
                className="w-full flex items-center justify-between p-3 bg-white border border-gray-300 rounded-xl hover:border-orange-300 transition-colors"
                disabled={isConnecting}
              >
                <div className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${
                    selectedNetwork === 'sepolia' ? 'bg-blue-500' : 'bg-purple-500'
                  }`}></div>
                  <span className="font-medium text-gray-700">
                    {networks.find(n => n.id === selectedNetwork)?.name}
                  </span>
                </div>
                <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform ${
                  showNetworkDropdown ? 'rotate-180' : ''
                }`} />
              </button>

              {showNetworkDropdown && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-300 rounded-xl shadow-lg z-10">
                  {networks.map((net) => (
                    <button
                      key={net.id}
                      onClick={() => handleNetworkChange(net.id)}
                      className={`w-full flex items-center gap-3 p-3 hover:bg-gray-50 transition-colors first:rounded-t-xl last:rounded-b-xl ${
                        selectedNetwork === net.id ? 'bg-orange-50' : ''
                      }`}
                    >
                      <div className={`w-3 h-3 rounded-full ${
                        net.id === 'sepolia' ? 'bg-blue-500' : 'bg-purple-500'
                      }`}></div>
                      <div className="text-left">
                        <div className="font-medium text-gray-700">{net.name}</div>
                        <div className="text-xs text-gray-500">
                          {net.tokens.join(', ')}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Connection Status */}
        <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-2xl p-6 border border-green-200">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-emerald-500 rounded-full flex items-center justify-center">
                <CheckCircle className="w-6 h-6 text-white" />
              </div>
              <div>
                <div className="text-sm text-gray-600">Connected</div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-semibold text-gray-800">
                  {shortenAddress(account)}
                    </span>
                    <button
                      onClick={copyAddress}
                      className="p-1 hover:bg-gray-200 rounded transition-colors"
                      title="Copy address"
                    >
                      <Copy className="w-4 h-4 text-gray-500" />
                    </button>
                </div>
              </div>
            </div>
            <button
              onClick={disconnectWallet}
              className="text-red-500 hover:text-red-700 transition-colors"
              title="Disconnect"
            >
              <XCircle className="w-5 h-5" />
            </button>
          </div>

          {network && (
              <div className="bg-white/50 rounded-lg p-3 border border-green-200 mb-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs text-gray-600 mb-1">Current Network</div>
                    <div className="font-semibold text-gray-800 capitalize">
                      {network.replace('-', ' ')}
                    </div>
                  </div>
                  <div className={`px-2 py-1 rounded text-xs font-medium ${
                    network === 'sepolia' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'
                  }`}>
                    {network === 'sepolia' ? 'ETH' : 'FIL'}
                  </div>
                </div>
              </div>
            )}

            {/* Refresh Button */}
            <button
              onClick={fetchBalances}
              disabled={isLoadingBalances}
              className="w-full flex items-center justify-center gap-2 py-2 px-4 bg-white/50 border border-green-200 rounded-lg hover:bg-white/70 disabled:opacity-50 transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${isLoadingBalances ? 'animate-spin' : ''}`} />
              <span className="text-sm font-medium">Refresh Balances</span>
            </button>
          </div>

          {/* User Profile Section */}
          {userData && (
            <div className="bg-gradient-to-br from-purple-50 to-white rounded-2xl p-6 border border-purple-200">
              <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
                <User className="w-5 h-5" />
                User Profile
              </h3>
              
              <div className="space-y-3">
                <div className="bg-white rounded-xl p-4 border border-purple-100">
                  <div className="text-xs text-gray-600 mb-1">Name</div>
                  <div className="font-semibold text-gray-800">
                    {userData.firstName} {userData.lastName}
                  </div>
                </div>

                <div className="bg-white rounded-xl p-4 border border-purple-100">
                  <div className="text-xs text-gray-600 mb-1">Email</div>
                  <div className="font-medium text-gray-800 break-all">
                    {userData.email}
                  </div>
                </div>

                {userData.otherDetails && userData.otherDetails.howDidYouHearAboutUs && (
                  <div className="bg-white rounded-xl p-4 border border-purple-100">
                    <div className="text-xs text-gray-600 mb-1">Source</div>
                    <div className="font-medium text-gray-800">
                      {userData.otherDetails.howDidYouHearAboutUs}
                    </div>
                  </div>
                )}

                <div className="text-xs text-gray-500 text-center pt-2">
                  Profile loaded from backend ✓
                </div>
              </div>
            </div>
          )}

          {/* Wallet Balances Section */}
          <div className="bg-gradient-to-br from-orange-50 to-white rounded-2xl p-6 border border-orange-200">
            <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <Wallet className="w-5 h-5" />
              Wallet Balances
            </h3>

            {/* Network Warning */}
            {network && network !== 'sepolia' && network !== 'filecoin-calibration' && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-4">
                <div className="flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-yellow-600" />
                  <span className="text-sm text-yellow-800">
                    Switch to Sepolia or Filecoin Calibration network to view balances.
                  </span>
                </div>
              </div>
            )}

            {/* Token Selection */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">Token</label>
              <div className="relative">
                <button
                  onClick={() => setShowTokenDropdown(!showTokenDropdown)}
                  className="w-full flex items-center justify-between p-3 bg-white border border-gray-300 rounded-xl hover:border-orange-300 transition-colors"
                  disabled={isLoadingSpecificBalance}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center ${
                      selectedToken === 'ETH' ? 'bg-gradient-to-br from-gray-400 to-gray-600' :
                      selectedToken === 'FIL' ? 'bg-gradient-to-br from-purple-400 to-purple-600' :
                      selectedToken === 'USDC' ? 'bg-gradient-to-br from-blue-400 to-blue-600' :
                      selectedToken === 'TFIL' ? 'bg-gradient-to-br from-purple-400 to-purple-600' :
                      'bg-gradient-to-br from-yellow-400 to-yellow-600'
                    }`}>
                      <span className="text-white font-bold text-xs">
                        {selectedToken === 'ETH' ? 'Ξ' : 
                         selectedToken === 'FIL' ? 'F' :
                         selectedToken === 'USDC' ? '$' :
                         selectedToken === 'TFIL' ? 'T' : 'P'}
                      </span>
                    </div>
                    <span className="font-medium text-gray-700">{selectedToken}</span>
                  </div>
                  <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform ${
                    showTokenDropdown ? 'rotate-180' : ''
                  }`} />
                </button>

                {showTokenDropdown && (
                  <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-300 rounded-xl shadow-lg z-10">
                    {getAvailableTokens().map((token) => (
                      <button
                        key={token}
                        onClick={() => handleTokenChange(token)}
                        className={`w-full flex items-center gap-3 p-3 hover:bg-gray-50 transition-colors first:rounded-t-xl last:rounded-b-xl ${
                          selectedToken === token ? 'bg-orange-50' : ''
                        }`}
                      >
                        <div className={`w-6 h-6 rounded-full flex items-center justify-center ${
                          token === 'ETH' ? 'bg-gradient-to-br from-gray-400 to-gray-600' :
                          token === 'FIL' ? 'bg-gradient-to-br from-purple-400 to-purple-600' :
                          token === 'USDC' ? 'bg-gradient-to-br from-blue-400 to-blue-600' :
                          token === 'TFIL' ? 'bg-gradient-to-br from-purple-400 to-purple-600' :
                          'bg-gradient-to-br from-yellow-400 to-yellow-600'
                        }`}>
                          <span className="text-white font-bold text-xs">
                            {token === 'ETH' ? 'Ξ' : 
                             token === 'FIL' ? 'F' :
                             token === 'USDC' ? '$' :
                             token === 'TFIL' ? 'T' : 'P'}
                          </span>
                        </div>
                        <span className="font-medium text-gray-700">{token}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Balance Display */}
            <div className="bg-white rounded-xl p-4 border border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm text-gray-600 mb-1">Balance</div>
                  <div className="font-semibold text-gray-800">
                    {isLoadingSpecificBalance ? (
                      <div className="flex items-center gap-2">
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        <span>Loading...</span>
                      </div>
                    ) : currentBalance && !currentBalance.error ? (
                      `${displayBalance(currentBalance.balance, currentBalance.decimals)} ${currentBalance.symbol}`
                    ) : currentBalance && currentBalance.error ? (
                      <div className="space-y-1">
                        <span className="text-red-500 text-sm block">Error: {currentBalance.error}</span>
                        {balances && balances.ethBalance && (
                          <span className="text-gray-600 text-xs">
                            ETH: {displayBalance(balances.ethBalance, 18)}
                          </span>
                        )}
                      </div>
                    ) : (
                      <div className="space-y-1">
                        <span className="text-gray-500">No balance data</span>
                        {balances && balances.ethBalance && (
                          <span className="text-gray-600 text-xs">
                            ETH: {displayBalance(balances.ethBalance, 18)}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={fetchSpecificTokenBalance}
                    disabled={isLoadingSpecificBalance}
                    className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                    title="Refresh balance"
                  >
                    <RefreshCw className={`w-4 h-4 text-gray-500 ${isLoadingSpecificBalance ? 'animate-spin' : ''}`} />
                  </button>
                  <button
                    onClick={() => {
                      console.log('Debug Info:', {
                        account,
                        selectedToken,
                        selectedNetwork,
                        currentBalance,
                        balances,
                        error
                      });
                    }}
                    className="p-2 hover:bg-gray-100 rounded-lg transition-colors text-xs"
                    title="Debug info"
                  >
                    🐛
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Token Balances */}
          {(balances && (balances.ethBalance || balances.tokenBalances)) && (
            <div className="bg-gradient-to-br from-orange-50 to-white rounded-2xl p-6 border border-orange-200">
              <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
                <Wallet className="w-5 h-5" />
                Token Balances
              </h3>

              {/* ETH/FIL Balance */}
              <div className="bg-white rounded-xl p-4 border border-gray-200 mb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                      selectedNetwork === 'sepolia' 
                        ? 'bg-gradient-to-br from-gray-400 to-gray-600' 
                        : 'bg-gradient-to-br from-purple-400 to-purple-600'
                    }`}>
                      <span className="text-white font-bold text-xs">
                        {selectedNetwork === 'sepolia' ? 'Ξ' : 'F'}
                      </span>
                    </div>
                    <div>
                      <div className="font-semibold text-gray-800">
                        {selectedNetwork === 'sepolia' ? 'ETH' : 'FIL'}
                      </div>
                      <div className="text-xs text-gray-500">
                        {selectedNetwork === 'sepolia' ? 'Ethereum' : 'Filecoin'}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-semibold text-gray-800">
                      {displayBalance(balances.ethBalance, 18)}
                    </div>
                  </div>
                </div>
              </div>

              {/* Token Balances - Show different tokens based on network */}
              {balances.tokenBalances && Object.entries(balances.tokenBalances).map(([tokenName, tokenData]) => {
                // Only show tokens relevant to the selected network
                const currentNetworkTokens = networks.find(n => n.id === selectedNetwork)?.tokens || [];
                if (!currentNetworkTokens.includes(tokenName)) return null;
                
                // Add defensive check for tokenData structure
                if (!tokenData || typeof tokenData !== 'object') return null;

                return (
                  <div key={tokenName} className="bg-white rounded-xl p-4 border border-gray-200 mb-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                          tokenName === 'USDC' ? 'bg-gradient-to-br from-blue-400 to-blue-600' :
                          tokenName === 'TFIL' ? 'bg-gradient-to-br from-purple-400 to-purple-600' :
                          'bg-gradient-to-br from-yellow-400 to-yellow-600'
                        }`}>
                          <span className="text-white font-bold text-xs">
                            {tokenName === 'USDC' ? '$' : tokenName === 'TFIL' ? 'T' : 'P'}
                          </span>
                        </div>
                        <div>
                          <div className="font-semibold text-gray-800">{tokenName}</div>
                          <div className="text-xs text-gray-500">
                            {tokenName === 'USDC' ? 'USD Coin' : 
                             tokenName === 'TFIL' ? 'Tokenized FIL' : 
                             'PayPal USD'}
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-semibold text-gray-800">
                          {tokenData.error ? 'Error' : (tokenData.balance != null ? displayBalance(tokenData.balance, tokenData.decimals) : '0.0000')}
                        </div>
                        {tokenData.error && (
                          <div className="text-xs text-red-500">Failed to load</div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Info Card */}
      <div className="bg-orange-50 border border-orange-200 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 bg-orange-500 rounded-lg flex items-center justify-center flex-shrink-0">
            💡
          </div>
          <div className="text-sm text-orange-900">
            <div className="font-semibold mb-1">Why connect a wallet?</div>
            <ul className="space-y-1 text-orange-800">
              <li>• Personalized product recommendations</li>
              <li>• Exclusive deals and rewards</li>
              <li>• Secure transaction history</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
  } catch (componentError) {
    console.error('Component error caught:', componentError);
    return (
      <div className="space-y-4">
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-red-800">
            Component Error: {componentError?.message || 'Unknown error occurred'}
          </div>
        </div>
        <div className="bg-orange-50 border border-orange-200 rounded-xl p-4">
          <div className="text-sm text-orange-900">
            Please refresh the extension or try again.
          </div>
        </div>
      </div>
    );
  }
};

export default WalletConnect;
