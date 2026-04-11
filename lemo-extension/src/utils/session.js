// Session management utilities for LEMO Extension
import { getBackendUrl } from './auth.js';

/**
 * Extract domain from URL
 * @param {string} url - Full URL
 * @returns {string} Domain name
 */
export const extractDomain = (url) => {
  try {
    const urlObj = new URL(url);
    // Remove www. prefix if present
    return urlObj.hostname.replace(/^www\./, '');
  } catch (error) {
    console.error('Error extracting domain:', error);
    return 'unknown';
  }
};

/**
 * Get current tab URL and domain
 * @returns {Promise<{url: string, domain: string}>}
 */
export const getCurrentTabInfo = async () => {
  try {
    console.log('[SESSION] === Getting current tab info ===');
    
    // METHOD 1: Use window.location (most reliable since overlay is injected in page)
    if (typeof window !== 'undefined' && window.location && window.location.href) {
      const currentUrl = window.location.href;
      
      // Skip if it's an extension page
      if (!currentUrl.startsWith('chrome-extension://') && 
          !currentUrl.startsWith('chrome://') &&
          !currentUrl.startsWith('edge://') &&
          !currentUrl.startsWith('about:')) {
        console.log('[SESSION] ✓✓✓ Method 1 SUCCESS (window.location):', currentUrl);
        return {
          url: currentUrl,
          domain: extractDomain(currentUrl),
        };
      } else {
        console.log('[SESSION] ⚠ Method 1: Skipping browser-internal page:', currentUrl);
      }
    }
    
    // METHOD 2: Query for the active tab (fallback for popup context)
    try {
      const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
      if (tab && tab.url && !tab.url.startsWith('chrome-extension://') && !tab.url.startsWith('chrome://')) {
        console.log('[SESSION] ✓ Method 2 SUCCESS (chrome.tabs):', tab.url);
        return {
          url: tab.url,
          domain: extractDomain(tab.url),
        };
      }
      console.log('[SESSION] ✗ Method 2 FAILED - Tab:', tab?.url || 'no url');
    } catch (e) {
      console.log('[SESSION] ✗ Method 2 ERROR:', e.message);
    }
    
    // No valid URL found
    console.warn('[SESSION] ✗✗✗ FAILED: Could not find any valid page URL');
    console.warn('[SESSION] Make sure you\'re on a real website (not chrome:// or about: pages)');
    return {
      url: 'chrome://newtab',
      domain: 'chrome',
    };
  } catch (error) {
    console.error('[SESSION] ✗✗✗ CRITICAL ERROR getting tab info:', error);
    return {
      url: 'chrome://newtab',
      domain: 'chrome',
    };
  }
};

/**
 * Create a new chat session
 * @param {string} userId - User's wallet address
 * @param {string} currentUrl - Current page URL
 * @param {string} currentDomain - Current page domain
 * @returns {Promise<object>} Session data
 */
export const createSession = async (userId, currentUrl, currentDomain) => {
  try {
    console.log('[SESSION API] ========================================');
    console.log('[SESSION API] Creating session with:');
    console.log('[SESSION API]   - User ID:', userId);
    console.log('[SESSION API]   - URL:', currentUrl);
    console.log('[SESSION API]   - Domain:', currentDomain);
    
    const backendUrl = await getBackendUrl();
    console.log('[SESSION API]   - Backend URL:', backendUrl);
    
    const requestBody = {
      current_url: currentUrl,
      current_domain: currentDomain,
    };
    console.log('[SESSION API]   - Request body:', JSON.stringify(requestBody, null, 2));
    
    const fullUrl = `${backendUrl}/sessions/`;
    console.log('[SESSION API]   - Full URL:', fullUrl);
    
    const response = await fetch(fullUrl, {
      method: 'POST',
      headers: {
        'Authorization': userId,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });

    console.log('[SESSION API] ✓ Response received:', response.status, response.statusText);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      console.error('[SESSION API] ✗ Error response:', errorData);
      throw new Error(errorData.message || errorData.error || 'Failed to create session');
    }

    const session = await response.json();
    console.log('[SESSION API] ✓✓✓ Session created successfully:', session);
    console.log('[SESSION API] ========================================');
    return session;
  } catch (error) {
    console.error('[SESSION API] ✗✗✗ Error creating session:', error);
    console.error('[SESSION API] Error type:', error.constructor.name);
    console.error('[SESSION API] Error message:', error.message);
    throw error;
  }
};

/**
 * Get session details including chat history
 * @param {string} userId - User's wallet address
 * @param {string} sessionId - Session ID
 * @returns {Promise<object>} Session data with chat messages
 */
export const getSessionDetails = async (userId, sessionId) => {
  try {
    const backendUrl = await getBackendUrl();
    const response = await fetch(`${backendUrl}/sessions/data?id=${sessionId}`, {
      method: 'GET',
      headers: {
        'Authorization': userId,
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || errorData.error || 'Failed to get session details');
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error getting session details:', error);
    throw error;
  }
};

/**
 * Send a chat message and get AI response
 * @param {string} userId - User's wallet address
 * @param {string} sessionId - Session ID
 * @param {string} userQuery - User's message
 * @returns {Promise<{answer: string}>} AI response
 */
export const sendChatMessage = async (userId, sessionId, userQuery) => {
  try {
    const backendUrl = await getBackendUrl();
    const response = await fetch(`${backendUrl}/query?session_id=${sessionId}`, {
      method: 'POST',
      headers: {
        'Authorization': userId,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_query: userQuery,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || errorData.error || 'Failed to send message');
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error sending chat message:', error);
    throw error;
  }
};

/**
 * Store current session ID
 * @param {string} sessionId - Session ID to store
 */
export const saveCurrentSession = async (sessionId) => {
  try {
    await chrome.storage.local.set({ currentSessionId: sessionId });
  } catch (error) {
    console.error('Error saving current session:', error);
    throw error;
  }
};

/**
 * Get current session ID
 * @returns {Promise<string|null>} Session ID or null
 */
export const getCurrentSession = async () => {
  try {
    const result = await chrome.storage.local.get(['currentSessionId']);
    return result.currentSessionId || null;
  } catch (error) {
    console.error('Error getting current session:', error);
    return null;
  }
};

/**
 * Clear current session ID
 */
export const clearCurrentSession = async () => {
  try {
    await chrome.storage.local.remove(['currentSessionId']);
  } catch (error) {
    console.error('Error clearing current session:', error);
    throw error;
  }
};

