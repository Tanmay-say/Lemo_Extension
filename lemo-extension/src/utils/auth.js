// Authentication utilities for LEMO Extension

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
 * Check if a user exists with the given wallet address
 * @param {string} walletAddress - The user's wallet address
 * @returns {Promise<{exists: boolean, user?: object, error?: string, isInactive?: boolean}>}
 */
export const checkUserExists = async (walletAddress) => {
  try {
    const backendUrl = await getBackendUrl();
    const response = await fetch(`${backendUrl}/auth/${walletAddress}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (response.ok) {
      const data = await response.json();
      // Backend returns: { success: true, data: { user: {...} } }
      const user = data.data?.user || data.user || data;
      return { exists: true, user };
    } else if (response.status === 404) {
      return { exists: false };
    } else if (response.status === 403) {
      const errorData = await response.json().catch(() => ({}));
      const errorMsg = errorData.error || 'User account is inactive';
      return { 
        exists: true, 
        isInactive: true, 
        error: errorMsg 
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
 * Register a new user with wallet address and details
 * @param {string} walletAddress - The user's wallet address
 * @param {object} userData - User details {email, firstName, lastName, otherDetails}
 * @returns {Promise<object>} Created user data
 */
export const registerUser = async (walletAddress, userData) => {
  try {
    const backendUrl = await getBackendUrl();
    const response = await fetch(`${backendUrl}/auth/${walletAddress}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(userData),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || errorData.error || 'Failed to register user');
    }

    const user = await response.json();
    return user;
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
 * Clear the connected wallet address
 */
export const clearConnectedWallet = async () => {
  try {
    await chrome.storage.sync.remove(['connectedWallet']);
  } catch (error) {
    console.error('Error clearing connected wallet:', error);
    throw error;
  }
};

