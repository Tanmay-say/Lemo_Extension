// Session management utilities for LEMO Extension
// FIX C4: All API calls now use JWT Bearer token instead of raw wallet address
import { getBackendUrl, getAuthHeader } from './auth.js';

/**
 * Extract domain from URL
 * @param {string} url - Full URL
 * @returns {string} Domain name
 */
export const extractDomain = (url) => {
  try {
    const urlObj = new URL(url);
    return urlObj.hostname.replace(/^www\./, '');
  } catch (error) {
    console.error('Error extracting domain:', error);
    return 'unknown';
  }
};

const isTrackablePageUrl = (url = '') =>
  Boolean(url) &&
  !url.startsWith('chrome-extension://') &&
  !url.startsWith('chrome://') &&
  !url.startsWith('edge://') &&
  !url.startsWith('about:');

const PAGE_SESSION_STORAGE_KEY = 'pageSessionMap';

const normalizeSessionPageKey = (url = '') => {
  if (!isTrackablePageUrl(url)) {
    return null;
  }

  try {
    const parsed = new URL(url);
    return `${parsed.origin}${parsed.pathname}`;
  } catch (error) {
    console.error('Error normalizing page session key:', error);
    return null;
  }
};

/**
 * Get current tab URL and domain
 * @returns {Promise<{url: string, domain: string}>}
 */
export const getCurrentTabInfo = async () => {
  try {
    console.log('[SESSION] === Getting current tab info ===');

    try {
      const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
      if (tab && isTrackablePageUrl(tab.url)) {
        console.log('[SESSION] Active tab URL:', tab.url);
        return { url: tab.url, domain: extractDomain(tab.url) };
      }
    } catch (error) {
      console.log('[SESSION] chrome.tabs lookup failed:', error.message);
    }

    if (typeof window !== 'undefined' && window.location && isTrackablePageUrl(window.location.href)) {
      const currentUrl = window.location.href;
      console.log('[SESSION] Using window.location fallback:', currentUrl);
      return { url: currentUrl, domain: extractDomain(currentUrl) };
    }

    console.warn('[SESSION] No trackable product page detected');
    return { url: 'chrome://newtab', domain: 'chrome' };
  } catch (error) {
    console.error('[SESSION] Critical error getting tab info:', error);
    return { url: 'chrome://newtab', domain: 'chrome' };
  }
};

/**
 * Build authenticated headers (JWT Bearer token)
 * @returns {Promise<object>} Headers object
 */
const getAuthHeaders = async (extra = {}) => {
  const authHeader = await getAuthHeader();
  if (!authHeader) {
    throw new Error('Not authenticated. Please connect your wallet and log in first.');
  }
  return {
    Authorization: authHeader,
    'Content-Type': 'application/json',
    ...extra,
  };
};

/**
 * Create a new chat session
 * FIX C4: uses JWT Bearer token instead of raw wallet address
 */
export const createSession = async (userId, currentUrl, currentDomain) => {
  try {
    console.log('[SESSION API] Creating session for URL:', currentUrl);
    const backendUrl = await getBackendUrl();
    const headers = await getAuthHeaders();

    const response = await fetch(`${backendUrl}/sessions/`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ current_url: currentUrl, current_domain: currentDomain }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || errorData.message || errorData.error || 'Failed to create session');
    }

    return await response.json();
  } catch (error) {
    console.error('[SESSION API] Error creating session:', error);
    throw error;
  }
};

/**
 * Get session details including chat history
 * FIX C4: uses JWT Bearer token
 */
export const getSessionDetails = async (userId, sessionId) => {
  try {
    const backendUrl = await getBackendUrl();
    const headers = await getAuthHeaders();
    const response = await fetch(`${backendUrl}/sessions/data?id=${sessionId}`, {
      method: 'GET',
      headers,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || errorData.message || errorData.error || 'Failed to get session details');
    }

    return await response.json();
  } catch (error) {
    console.error('Error getting session details:', error);
    throw error;
  }
};

/**
 * Send a chat message and get AI response
 * FIX C4: uses JWT Bearer token
 */
export const sendChatMessage = async (userId, sessionId, userQuery) => {
  try {
    const backendUrl = await getBackendUrl();
    const headers = await getAuthHeaders();
    const response = await fetch(`${backendUrl}/query?session_id=${sessionId}`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ user_query: userQuery }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || errorData.message || errorData.error || 'Failed to send message');
    }

    return await response.json();
  } catch (error) {
    console.error('Error sending chat message:', error);
    throw error;
  }
};

/**
 * Store current session ID
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

export const savePageSession = async (url, sessionId) => {
  try {
    const pageKey = normalizeSessionPageKey(url);
    if (!pageKey) {
      return;
    }

    const result = await chrome.storage.local.get([PAGE_SESSION_STORAGE_KEY]);
    const pageSessionMap = result[PAGE_SESSION_STORAGE_KEY] || {};

    if (sessionId) {
      pageSessionMap[pageKey] = sessionId;
    } else {
      delete pageSessionMap[pageKey];
    }

    await chrome.storage.local.set({ [PAGE_SESSION_STORAGE_KEY]: pageSessionMap });
  } catch (error) {
    console.error('Error saving page session:', error);
    throw error;
  }
};

export const getPageSession = async (url) => {
  try {
    const pageKey = normalizeSessionPageKey(url);
    if (!pageKey) {
      return null;
    }

    const result = await chrome.storage.local.get([PAGE_SESSION_STORAGE_KEY]);
    const pageSessionMap = result[PAGE_SESSION_STORAGE_KEY] || {};
    return pageSessionMap[pageKey] || null;
  } catch (error) {
    console.error('Error getting page session:', error);
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
