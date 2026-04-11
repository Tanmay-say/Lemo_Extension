/**
 * Contract Configuration for Lemo Extension
 * Centralizes all contract addresses, ABIs, and network configs
 */

// Network configurations
export const NETWORKS = {
  sepolia: {
    chainId: 11155111,
    name: 'Sepolia Testnet',
    rpcUrl: 'https://rpc.sepolia.org',
    explorer: 'https://sepolia.etherscan.io',
    nativeCurrency: {
      name: 'Sepolia ETH',
      symbol: 'ETH',
      decimals: 18
    }
  },
  calibration: {
    chainId: 314159,
    name: 'Filecoin Calibration',
    rpcUrl: 'https://api.calibration.node.glif.io/rpc/v1',
    explorer: 'https://calibration.filfox.info',
    nativeCurrency: {
      name: 'Test Filecoin',
      symbol: 'tFIL',
      decimals: 18
    }
  }
};

// Contract addresses (Updated with deployed addresses)
export const CONTRACT_ADDRESSES = {
  sepolia: {
    LighthouseReceipt: '0xca17ed5b8bc6c80c69b1451e452cdf26453755b5',
    TrustlessAgentFeedback: '0x1c1454258fd663520148c8e13f484557d15202ef',
    AgentRegistry: '0x7f3d98f604ea312a95b648d7127b6be9ba2d6c8a',
    PaymentProcessor: '0x210c251e5a39bd12234d3564ce61168c1bec5922',
    LEMOToken: '0x14572dA77700c59D2F8D61a3c4B25744D6DcDE8D',
    USDC: '0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238',
    PYUSD: '0xCaC524BcA292aaade2DF8A05cC58F0a65B1B3bB9'
  },
  calibration: {
    LighthouseReceipt: '0x785c2fba7d753fe80b4afe5746e9e54a5c421e26',
    FVMShop: '0xea9d2e308394555b914dfd962e8c97dca2bef73a'
  }
};

// Token configurations
export const TOKENS = {
  sepolia: {
    LEMO: {
      address: '0x14572dA77700c59D2F8D61a3c4B25744D6DcDE8D',
      symbol: 'LEMO',
      decimals: 18,
      name: 'Lemo Token'
    },
    USDC: {
      address: '0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238',
      symbol: 'USDC',
      decimals: 6,
      name: 'USD Coin'
    },
    PYUSD: {
      address: '0xCaC524BcA292aaade2DF8A05cC58F0a65B1B3bB9',
      symbol: 'PYUSD',
      decimals: 6,
      name: 'PayPal USD'
    }
  },
  calibration: {
    tFIL: {
      address: '0x0000000000000000000000000000000000000000',
      symbol: 'tFIL',
      decimals: 18,
      name: 'Test Filecoin'
    }
  }
};

// Lighthouse configuration
export const LIGHTHOUSE_CONFIG = {
  apiEndpoint: 'https://node.lighthouse.storage/api/v0/add',
  gatewayUrl: 'https://gateway.lighthouse.storage/ipfs',
  apiKey: '33aad03e.bb3506b68665403b80cb4d30fc6129e4'
};

// Reward configuration
export const REWARD_CONFIG = {
  amount: '1000000', // 1,000,000 LEMO
  decimals: 18,
  token: 'LEMO',
  formatted: '1,000,000 LEMO'
};

// Merchant wallet for PYUSD payments
export const MERCHANT_WALLET = '0x286bd33A27079f28a4B4351a85Ad7f23A04BDdfC';

// Contract ABIs
export const ABIS = {
  LighthouseReceipt: [
    'function recordReceipt(address buyer, string productId, string cid, address paymentToken, uint256 amountPaid, string currency) external returns (uint256)',
    'function getReceipt(uint256 receiptId) external view returns (tuple(address buyer, string productId, string cid, address paymentToken, uint256 amountPaid, string currency, uint256 timestamp))',
    'function getReceiptsByBuyer(address buyer) external view returns (uint256[])',
    'event ReceiptRecorded(uint256 indexed receiptId, address indexed buyer, string productId, string cid, address paymentToken, uint256 amountPaid, string currency, uint256 timestamp)'
  ],
  
  TrustlessAgentFeedback: [
    'function submitFeedback(uint256 receiptId, string feedbackCid) external returns (uint256)',
    'function getFeedback(uint256 feedbackId) external view returns (tuple(uint256 receiptId, address user, string feedbackCid, uint256 timestamp, bool rewarded))',
    'function hasFeedback(uint256 receiptId) external view returns (bool)',
    'function getLEMOBalance() external view returns (uint256)',
    'event FeedbackSubmitted(uint256 indexed feedbackId, uint256 indexed receiptId, address indexed user, string feedbackCid, uint256 reward, uint256 timestamp)'
  ],
  
  PaymentProcessor: [
    'function processPayment(string productId, uint256 amount, string receiptCid, address paymentToken, string currency) external returns (uint256 paymentId, uint256 receiptId)',
    'function getPaymentDetails(uint256 paymentId) external view returns (tuple(uint256 paymentId, address buyer, string productId, uint256 amount, address paymentToken, string currency, uint256 receiptId, string receiptCid, uint256 timestamp, bool completed))',
    'function getPaymentsByBuyer(address buyer) external view returns (uint256[])',
    'function merchantWallet() external view returns (address)',
    'event PaymentProcessed(uint256 indexed paymentId, address indexed buyer, string productId, uint256 amount, address paymentToken, uint256 receiptId, string receiptCid, uint256 timestamp)'
  ],
  
  ERC20: [
    'function balanceOf(address account) external view returns (uint256)',
    'function transfer(address to, uint256 amount) external returns (bool)',
    'function approve(address spender, uint256 amount) external returns (bool)',
    'function allowance(address owner, address spender) external view returns (uint256)',
    'function decimals() external view returns (uint8)',
    'function symbol() external view returns (string)',
    'event Transfer(address indexed from, address indexed to, uint256 value)',
    'event Approval(address indexed owner, address indexed spender, uint256 value)'
  ]
};

// Helper functions
export function getContractAddress(network, contractName) {
  const addresses = CONTRACT_ADDRESSES[network];
  if (!addresses || !addresses[contractName]) {
    throw new Error(`Contract ${contractName} not found for network ${network}`);
  }
  return addresses[contractName];
}

export function getNetworkConfig(networkNameOrChainId) {
  if (typeof networkNameOrChainId === 'number') {
    return Object.values(NETWORKS).find(n => n.chainId === networkNameOrChainId);
  }
  return NETWORKS[networkNameOrChainId];
}

export function getTokenConfig(network, tokenSymbol) {
  const tokens = TOKENS[network];
  if (!tokens || !tokens[tokenSymbol]) {
    return null;
  }
  return tokens[tokenSymbol];
}

export function formatLEMOReward(amount) {
  return new Intl.NumberFormat('en-US').format(amount);
}

export function getLighthouseGatewayUrl(cid) {
  return `${LIGHTHOUSE_CONFIG.gatewayUrl}/${cid}`;
}

export default {
  NETWORKS,
  CONTRACT_ADDRESSES,
  TOKENS,
  LIGHTHOUSE_CONFIG,
  REWARD_CONFIG,
  MERCHANT_WALLET,
  ABIS,
  getContractAddress,
  getNetworkConfig,
  getTokenConfig,
  formatLEMOReward,
  getLighthouseGatewayUrl
};