import React, { useState, useEffect } from 'react';
import { Wallet, CheckCircle, XCircle, AlertCircle, RefreshCw, ExternalLink, Copy, ChevronDown, User } from 'lucide-react';
import RegistrationModal from './RegistrationModal';
import { checkUserExists, registerUser, loginWithSIWE } from '../utils/auth.js';

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
        // User exists and is active, perform SIWE login to get JWT
        console.log('[AUTH] User exists, performing SIWE login...');
        
        // Create signing function for MetaMask
        const signMessage = async (message) => {
          const response = await safeSendMessage({
            action: 'SIGN_MESSAGE',
            message: message,
            account: walletAddress
          });
          
          if (response && response.success && response.signature) {
            return response.signature;
          } else {
            throw new Error(response?.error || 'Failed to sign message');
          }
        };
        
        // Perform SIWE login to obtain JWT token
        const loginResult = await loginWithSIWE(walletAddress, signMessage);
        
        if (loginResult.success) {
          // JWT token is now stored, format user data
          const user = loginResult.user || result.user;
          
          const formattedUser = {
            id: user?.id || walletAddress,
            email: user?.email,
            firstName: user?.first_name || user?.firstName,
            lastName: user?.last_name || user?.lastName,
            walletAddress: user?.wallet_address || user?.walletAddress || walletAddress,
            otherDetails: user?.other_details || user?.otherDetails,
          };
          
          setUserData(formattedUser);
          console.log('[AUTH] SIWE login successful, user authenticated:', formattedUser);
        } else {
          throw new Error(loginResult.error || 'SIWE authentication failed');
        }
      } else {
