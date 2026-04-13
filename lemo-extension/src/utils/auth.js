// Authentication utilities for LEMO Extension
// Implements proper SIWE → JWT flow

const siweLoginPromises = new Map();

/**
 * Get the configured backend URL from storage
 * @returns {Promise<string>} Backend URL
 */
export const getBackendUrl = async () => {
  try {
    const result = await chrome.storage.sync.get(['backendUrl']);
    return result.backendUrl || 'http://localhost:8000';
  } catch (error) {
    console.error('Error getting backend URL:', error);
    return 'http://localhost:8000';
  }
};

/**
 * Get the stored JWT token
 * @returns {Promise<string|null>} JWT token or null
 */
export const getJwtToken = async () => {
  try {
    const result = await chrome.storage.local.get(['jwtToken']);
    return result.jwtToken || null;
  } catch (error) {
    console.error('Error getting JWT token:', error);
    return null;
  }
};

/**
 * Save the JWT token returned from backend login
 * @param {string} token - JWT token
 */
export const saveJwtToken = async (token) => {
  try {
    await chrome.storage.local.set({ jwtToken: token });
  } catch (error) {
    console.error('Error saving JWT token:', error);
    throw error;
  }
};

/**
 * Clear the stored JWT token (on logout)
 */
export const clearJwtToken = async () => {
  try {
    await chrome.storage.local.remove(['jwtToken']);
  } catch (error) {
    console.error('Error clearing JWT token:', error);
  }
};

/**
 * Build Authorization header using stored JWT token
 * @returns {Promise<string>} Bearer token header value
 */
export const getAuthHeader = async () => {
  const token = await getJwtToken();
  return token ? `Bearer ${token}` : null;
};

/**
 * Check if a user exists and is active.
 * @param {string} walletAddress - The user's wallet address
 * @returns {Promise<{exists: boolean, user?: object, error?: string, isInactive?: boolean}>}
 */
export const checkUserExists = async (walletAddress) => {
  try {
    const backendUrl = await getBackendUrl();
    const response = await fetch(`${backendUrl}/auth/user/${walletAddress}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });

    if (response.ok) {
      const data = await response.json().catch(() => ({}));
      return { exists: true, user: data.user };
    } else if (response.status === 404) {
      return { exists: false };
    } else if (response.status === 403) {
      const errorData = await response.json().catch(() => ({}));
      return {
        exists: true,
        isInactive: true,
        user: errorData.user,
        error: errorData.error || 'User account is inactive',
      };
    } else {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || errorData.message || 'Failed to check user');
    }
  } catch (error) {
    console.error('Error checking user exists:', error);
    throw error;
  }
};

/**
 * Full SIWE authentication flow:
 *  1. GET /auth/nonce/{wallet}             → get server-generated nonce
 *  2. Sign the nonce message with MetaMask
 *  3. POST /auth/login/{wallet}            → get JWT token
 * On success, saves the JWT to local storage.
 *
 * @param {string} walletAddress - The user's wallet address
 * @param {Function} signMessage - async fn(message: string) → signature string
 * @returns {Promise<{success: boolean, token?: string, user?: object, error?: string}>}
 */
export const loginWithSIWE = async (walletAddress, signMessage) => {
  const normalizedWallet = walletAddress?.toLowerCase?.() || walletAddress;

  if (normalizedWallet && siweLoginPromises.has(normalizedWallet)) {
    return siweLoginPromises.get(normalizedWallet);
  }

  const loginPromise = (async () => {
    try {
    const backendUrl = await getBackendUrl();

    // Step 1: request nonce
    const nonceRes = await fetch(`${backendUrl}/auth/nonce/${walletAddress}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!nonceRes.ok) {
      const err = await nonceRes.json().catch(() => ({}));
      throw new Error(err.error || 'Failed to get nonce');
    }
    const { nonce, message: nonceMessage } = await nonceRes.json();
    console.log('[AUTH] Got nonce:', nonce);

    // Step 2: sign with MetaMask
    const signature = await signMessage(nonceMessage);
    console.log('[AUTH] Signed message, requesting login...');

    // Step 3: send signature to backend
    const loginRes = await fetch(`${backendUrl}/auth/login/${walletAddress}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: nonceMessage, signature }),
    });
    if (!loginRes.ok) {
      const err = await loginRes.json().catch(() => ({}));
      throw new Error(err.error || 'Authentication failed');
    }
    const loginData = await loginRes.json();
    const token = loginData.access_token;
    await saveJwtToken(token);
    await saveConnectedWallet(walletAddress);
    console.log('[AUTH] Login successful, JWT stored.');
    return { success: true, token, user: loginData.data?.user };
    } catch (error) {
      console.error('[AUTH] SIWE login failed:', error);
      return { success: false, error: error.message };
    } finally {
      if (normalizedWallet) {
        siweLoginPromises.delete(normalizedWallet);
      }
    }
  })();

  if (normalizedWallet) {
    siweLoginPromises.set(normalizedWallet, loginPromise);
  }

  return loginPromise;
};

/**
 * Register a new user with wallet address and details
 * FIX C3 (Claude): correct endpoint is POST /auth/register/{walletAddress}
 * @param {string} walletAddress - The user's wallet address
 * @param {object} userData - User details {email, firstName, lastName, otherDetails}
 * @returns {Promise<object>} Created user data
 */
export const registerUser = async (walletAddress, userData) => {
  try {
    const backendUrl = await getBackendUrl();
    // FIX: was /auth/${walletAddress} — should be /auth/register/${walletAddress}
    const response = await fetch(`${backendUrl}/auth/register/${walletAddress}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(userData),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || errorData.error || 'Failed to register user');
    }

    return await response.json();
  } catch (error) {
    console.error('Error registering user:', error);
    throw error;
  }
};

/**
 * Get the currently connected wallet address
 * @returns {Promise<string|null>} Wallet address or null if not connected
 */
export const getConnectedWallet = async () => {
  try {
    const result = await chrome.storage.sync.get(['connectedWallet']);
    return result.connectedWallet || null;
  } catch (error) {
    console.error('Error getting connected wallet:', error);
    return null;
  }
};

/**
 * Save the connected wallet address
 * @param {string} walletAddress - The wallet address to save
 */
export const saveConnectedWallet = async (walletAddress) => {
  try {
    await chrome.storage.sync.set({ connectedWallet: walletAddress });
  } catch (error) {
    console.error('Error saving connected wallet:', error);
    throw error;
  }
};

/**
 * Clear the connected wallet address and JWT token (full logout)
 */
export const clearConnectedWallet = async () => {
  try {
    await chrome.storage.sync.remove(['connectedWallet']);
    await clearJwtToken();
  } catch (error) {
    console.error('Error clearing connected wallet:', error);
    throw error;
  }
};
