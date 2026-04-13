import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  CheckCircle,
  ChevronDown,
  Copy,
  ExternalLink,
  RefreshCw,
  User,
  Wallet,
  XCircle,
} from 'lucide-react';

import RegistrationModal from './RegistrationModal';
import {
  checkUserExists,
  clearConnectedWallet,
  getConnectedWallet,
  registerUser,
  loginWithSIWE,
} from '../utils/auth.js';

const NETWORKS = [
  { id: 'sepolia', name: 'Sepolia', tokens: ['ETH', 'USDC', 'PYUSD'] },
  { id: 'filecoin-calibration', name: 'Filecoin Calibration', tokens: ['FIL', 'TFIL'] },
];

const NETWORK_LABELS = {
  sepolia: 'Sepolia',
  'filecoin-calibration': 'Filecoin Calibration',
};

const WalletConnect = () => {
  const [account, setAccount] = useState(null);
  const [network, setNetwork] = useState(null);
  const [selectedNetwork, setSelectedNetwork] = useState('sepolia');
  const [selectedToken, setSelectedToken] = useState('ETH');
  const [showNetworkDropdown, setShowNetworkDropdown] = useState(false);
  const [showTokenDropdown, setShowTokenDropdown] = useState(false);
  const [showRegistrationModal, setShowRegistrationModal] = useState(false);
  const [userData, setUserData] = useState(null);
  const [balances, setBalances] = useState(null);
  const [currentBalance, setCurrentBalance] = useState(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isRegistering, setIsRegistering] = useState(false);
  const [isCheckingUser, setIsCheckingUser] = useState(false);
  const [isLoadingBalances, setIsLoadingBalances] = useState(false);
  const [isLoadingSpecificBalance, setIsLoadingSpecificBalance] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    initialize();
  }, []);

  useEffect(() => {
    if (account) {
      void fetchBalances();
    }
  }, [account, selectedNetwork]);

  useEffect(() => {
    if (account && selectedToken) {
      void fetchSpecificTokenBalance();
    }
  }, [account, selectedToken, selectedNetwork]);

  const getAvailableTokens = () => {
    const current = NETWORKS.find((item) => item.id === selectedNetwork);
    return current ? current.tokens : [];
  };

  const safeSendMessage = async (message, timeoutMs = 15000) => {
    const timeout = new Promise((_, reject) => {
      setTimeout(() => reject(new Error('Operation timed out')), timeoutMs);
    });
    return Promise.race([chrome.runtime.sendMessage(message), timeout]);
  };

  const syncNetworkState = (networkName) => {
    if (!networkName) {
      return;
    }
    setNetwork(networkName);
    if (NETWORK_LABELS[networkName]) {
      setSelectedNetwork(networkName);
      const firstToken = NETWORKS.find((item) => item.id === networkName)?.tokens?.[0];
      if (firstToken) {
        setSelectedToken(firstToken);
      }
    }
  };

  const initialize = async () => {
    try {
      const storedWallet = await getConnectedWallet();
      if (storedWallet) {
        setAccount(storedWallet);
      }
      await checkConnection(storedWallet);
    } catch (err) {
      console.error('Wallet initialization error:', err);
      setError(err.message || 'Failed to initialize wallet state');
    }
  };

  const checkConnection = async (knownWallet = null) => {
    try {
      const response = await safeSendMessage({ action: 'CHECK_WALLET' });
      if (!response?.success || !response?.result?.isInstalled) {
        return;
      }

      const walletAddress = response.result.accounts?.[0] || knownWallet;
      if (walletAddress) {
        setAccount(walletAddress);
        syncNetworkState(response.result.network?.name);
        await checkAndAuthenticateUser(walletAddress);
      }
    } catch (err) {
      console.error('Error checking wallet connection:', err);
    }
  };

  const connectWallet = async () => {
    setIsConnecting(true);
    setError(null);
    try {
      const response = await safeSendMessage({ action: 'CONNECT_WALLET' });
      const walletAddress = response?.result?.accounts?.[0];
      if (!response?.success || !walletAddress) {
        throw new Error(response?.error || 'Failed to connect wallet');
      }

      setAccount(walletAddress);
      syncNetworkState(response.result.network?.name);
      await chrome.storage.sync.set({ connectedWallet: walletAddress });
      await checkAndAuthenticateUser(walletAddress);
    } catch (err) {
      console.error('Wallet connection error:', err);
      setError(err.message || 'Failed to connect wallet');
    } finally {
      setIsConnecting(false);
    }
  };

  const disconnectWallet = async () => {
    await clearConnectedWallet();
    setAccount(null);
    setNetwork(null);
    setBalances(null);
    setCurrentBalance(null);
    setUserData(null);
    setError(null);
  };

  const handleNetworkChange = async (networkId) => {
    setShowNetworkDropdown(false);
    setSelectedNetwork(networkId);
    const nextToken = NETWORKS.find((item) => item.id === networkId)?.tokens?.[0];
    if (nextToken) {
      setSelectedToken(nextToken);
    }

    setIsConnecting(true);
    setError(null);
    try {
      const action = networkId === 'sepolia' ? 'SWITCH_TO_SEPOLIA' : 'SWITCH_TO_FILECOIN';
      const response = await safeSendMessage({ action });
      if (!response?.success) {
        throw new Error(response?.error || 'Network switch failed');
      }
      syncNetworkState(networkId);
    } catch (err) {
      console.error('Network switch error:', err);
      setError(err.message || 'Failed to switch network');
    } finally {
      setIsConnecting(false);
    }
  };

  const fetchBalances = async () => {
    if (!account) {
      return;
    }
    setIsLoadingBalances(true);
    try {
      const response = await safeSendMessage({ action: 'GET_TOKEN_BALANCES' });
      if (response?.success && response?.result) {
        setBalances(response.result);
        syncNetworkState(response.result.network?.name);
      } else {
        throw new Error(response?.error || 'Failed to load balances');
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
      return;
    }
    setIsLoadingSpecificBalance(true);
    try {
      const response = await safeSendMessage({
        action: 'GET_SPECIFIC_TOKEN_BALANCE',
        tokenSymbol: selectedToken,
        account,
      });
      if (response?.success && response?.result) {
        setCurrentBalance(response.result);
      } else {
        throw new Error(response?.error || 'Failed to fetch token balance');
      }
    } catch (err) {
      console.error('Error fetching token balance:', err);
      setError(err.message || 'Failed to fetch token balance');
      setCurrentBalance(null);
    } finally {
      setIsLoadingSpecificBalance(false);
    }
  };

  const checkAndAuthenticateUser = async (walletAddress) => {
    setIsCheckingUser(true);
    setError(null);
    try {
      const result = await checkUserExists(walletAddress);
      if (result.isInactive) {
        setUserData(null);
        setError(result.error || 'User account is inactive');
        return;
      }

      if (result.exists) {
        const signMessage = async (message) => {
          const response = await safeSendMessage({
            action: 'SIGN_MESSAGE',
            account: walletAddress,
            message,
          });
          if (response?.success && response?.signature) {
            return response.signature;
          }
          throw new Error(response?.error || 'Failed to sign message');
        };

        const loginResult = await loginWithSIWE(walletAddress, signMessage);
        if (!loginResult.success) {
          throw new Error(loginResult.error || 'Authentication failed');
        }

        const user = loginResult.user || result.user || {};
        setUserData({
          id: user.id || walletAddress,
          email: user.email || '',
          firstName: user.first_name || user.firstName || '',
          lastName: user.last_name || user.lastName || '',
          walletAddress: user.wallet_address || user.walletAddress || walletAddress,
        });
        return;
      }

      setShowRegistrationModal(true);
    } catch (err) {
      console.error('Authentication flow error:', err);
      setError(err.message || 'Authentication failed');
    } finally {
      setIsCheckingUser(false);
    }
  };

  const handleRegistration = async (formData) => {
    if (!account) {
      return;
    }
    setIsRegistering(true);
    setError(null);
    try {
      await registerUser(account, formData);
      setShowRegistrationModal(false);
      await checkAndAuthenticateUser(account);
    } catch (err) {
      console.error('Registration error:', err);
      setError(err.message || 'Registration failed');
    } finally {
      setIsRegistering(false);
    }
  };

  const formatAddress = (value) => {
    if (!value) {
      return '';
    }
    return `${value.slice(0, 6)}...${value.slice(-4)}`;
  };

  const formatBalance = (value) => {
    if (value == null) {
      return '0.0000';
    }
    const numeric = Number(value);
    if (Number.isNaN(numeric)) {
      return String(value);
    }
    return numeric.toFixed(4);
  };

  const getDisplayedTokenBalance = () => {
    if (isLoadingSpecificBalance) {
      return 'Loading...';
    }
    if (!currentBalance) {
      return '0.0000';
    }
    if (currentBalance.balance != null) {
      return `${formatBalance(currentBalance.balance)} ${currentBalance.symbol || selectedToken}`;
    }
    return '0.0000';
  };

  const copyAddress = async () => {
    if (!account) {
      return;
    }
    await navigator.clipboard.writeText(account);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const renderStatus = () => {
    if (error) {
      return (
        <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      );
    }

    if (isCheckingUser) {
      return (
        <div className="flex items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm text-blue-700">
          <RefreshCw className="h-4 w-4 animate-spin" />
          <span>Checking account status...</span>
        </div>
      );
    }

    if (userData) {
      return (
        <div className="flex items-center gap-2 rounded-xl border border-green-200 bg-green-50 p-3 text-sm text-green-700">
          <CheckCircle className="h-4 w-4" />
          <span>Authenticated as {userData.firstName || 'wallet user'}</span>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-orange-200 bg-gradient-to-br from-orange-50 to-white p-4 shadow-sm">
        <div className="mb-4 flex items-center gap-3">
          <div className="rounded-full bg-orange-100 p-3 text-orange-600">
            <Wallet className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-gray-900">Wallet</h2>
            <p className="text-sm text-gray-500">Connect MetaMask and sync your Lemo account</p>
          </div>
        </div>

        {!account ? (
          <button
            onClick={connectWallet}
            disabled={isConnecting}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-orange-500 to-orange-600 px-4 py-3 font-medium text-white transition hover:shadow-lg disabled:opacity-60"
          >
            {isConnecting ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Wallet className="h-4 w-4" />}
            <span>{isConnecting ? 'Connecting...' : 'Connect Wallet'}</span>
          </button>
        ) : (
          <div className="space-y-4">
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-medium text-gray-600">Connected Address</span>
                <button
                  onClick={copyAddress}
                  className="flex items-center gap-1 text-xs text-orange-600 hover:text-orange-700"
                >
                  <Copy className="h-3.5 w-3.5" />
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </div>
              <div className="font-mono text-sm text-gray-900">{formatAddress(account)}</div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="relative">
                <button
                  onClick={() => setShowNetworkDropdown((value) => !value)}
                  className="flex w-full items-center justify-between rounded-xl border border-gray-200 bg-white px-3 py-3 text-sm"
                >
                  <span>{NETWORK_LABELS[selectedNetwork] || selectedNetwork}</span>
                  <ChevronDown className="h-4 w-4 text-gray-500" />
                </button>
                {showNetworkDropdown && (
                  <div className="absolute z-10 mt-2 w-full rounded-xl border border-gray-200 bg-white shadow-lg">
                    {NETWORKS.map((item) => (
                      <button
                        key={item.id}
                        onClick={() => void handleNetworkChange(item.id)}
                        className="block w-full px-3 py-2 text-left text-sm hover:bg-orange-50"
                      >
                        {item.name}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="relative">
                <button
                  onClick={() => setShowTokenDropdown((value) => !value)}
                  className="flex w-full items-center justify-between rounded-xl border border-gray-200 bg-white px-3 py-3 text-sm"
                >
                  <span>{selectedToken}</span>
                  <ChevronDown className="h-4 w-4 text-gray-500" />
                </button>
                {showTokenDropdown && (
                  <div className="absolute z-10 mt-2 w-full rounded-xl border border-gray-200 bg-white shadow-lg">
                    {getAvailableTokens().map((token) => (
                      <button
                        key={token}
                        onClick={() => {
                          setSelectedToken(token);
                          setShowTokenDropdown(false);
                        }}
                        className="block w-full px-3 py-2 text-left text-sm hover:bg-orange-50"
                      >
                        {token}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="mb-1 text-sm font-medium text-gray-600">Selected Token Balance</div>
              <div className="text-lg font-semibold text-gray-900">{getDisplayedTokenBalance()}</div>
              {balances?.network?.name && (
                <div className="mt-1 text-xs text-gray-500">Network: {NETWORK_LABELS[balances.network.name] || balances.network.name}</div>
              )}
            </div>

            {renderStatus()}

            {userData && (
              <div className="rounded-xl border border-gray-200 bg-white p-4">
                <div className="mb-2 flex items-center gap-2 text-sm font-medium text-gray-700">
                  <User className="h-4 w-4 text-orange-500" />
                  Account Profile
                </div>
                <div className="space-y-1 text-sm text-gray-600">
                  <div>{[userData.firstName, userData.lastName].filter(Boolean).join(' ') || 'Wallet User'}</div>
                  {userData.email ? <div>{userData.email}</div> : null}
                </div>
              </div>
            )}

            <div className="flex gap-2">
              <button
                onClick={() => void fetchBalances()}
                disabled={isLoadingBalances}
                className="flex-1 rounded-xl border border-orange-200 bg-orange-50 px-4 py-3 text-sm font-medium text-orange-700 transition hover:bg-orange-100 disabled:opacity-60"
              >
                {isLoadingBalances ? 'Refreshing...' : 'Refresh'}
              </button>
              <button
                onClick={() => void disconnectWallet()}
                className="flex-1 rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
              >
                Disconnect
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-gray-200 bg-white p-4 text-sm text-gray-600">
        <div className="mb-2 font-medium text-gray-800">Current Network</div>
        <div className="flex items-center gap-2">
          {network ? (
            <>
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span>{NETWORK_LABELS[network] || network}</span>
            </>
          ) : (
            <>
              <XCircle className="h-4 w-4 text-gray-400" />
              <span>Not connected</span>
            </>
          )}
        </div>
      </div>

      {showRegistrationModal ? (
        <RegistrationModal
          walletAddress={account}
          onSubmit={handleRegistration}
          onCancel={() => setShowRegistrationModal(false)}
          isLoading={isRegistering}
        />
      ) : null}
    </div>
  );
};

export default WalletConnect;
