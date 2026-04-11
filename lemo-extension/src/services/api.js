// API Service for LEMO Extension Backend Integration

class LemoAPI {
  constructor() {
    this.baseURL = null;
  }

  // Get backend URL from storage
  async getBaseURL() {
    if (this.baseURL) return this.baseURL;
    
    try {
      const result = await chrome.storage.sync.get(['backendUrl']);
      this.baseURL = result.backendUrl || 'http://localhost:8000';
      return this.baseURL;
    } catch (error) {
      console.error('Error getting backend URL:', error);
      return 'http://localhost:8000';
    }
  }

  // Helper method to make API calls
  async request(endpoint, options = {}) {
    const baseURL = await this.getBaseURL();
    const url = `${baseURL}${endpoint}`;
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, config);
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.message || data.error || 'API request failed');
      }
      
      return data;
    } catch (error) {
      console.error('API Error:', error);
      throw error;
    }
  }

  // Authentication APIs
  async authenticateUser(walletAddress) {
    return await this.request(`/auth/${walletAddress}`, {
      method: 'GET',
    });
  }

  async createUser(walletAddress, userData) {
    return await this.request(`/auth/${walletAddress}`, {
      method: 'POST',
      body: JSON.stringify(userData),
    });
  }

  // Session APIs
  async createSession(userId, currentUrl, currentDomain) {
    return await this.request('/sessions/', {
      method: 'POST',
      headers: {
        'Authorization': userId,
      },
      body: JSON.stringify({
        current_url: currentUrl,
        current_domain: currentDomain,
      }),
    });
  }

  async getAllSessions(userId) {
    return await this.request('/sessions/', {
      method: 'GET',
      headers: {
        'Authorization': userId,
      },
    });
  }

  async getSession(userId, sessionId) {
    return await this.request(`/sessions/data?id=${sessionId}`, {
      method: 'GET',
      headers: {
        'Authorization': userId,
      },
    });
  }

  async saveMessage(userId, messageData) {
    return await this.request('/sessions/message', {
      method: 'POST',
      headers: {
        'Authorization': userId,
      },
      body: JSON.stringify(messageData),
    });
  }

  // Query API - Main chat endpoint
  async sendQuery(userId, sessionId, userQuery) {
    return await this.request(`/query?session_id=${sessionId}`, {
      method: 'POST',
      headers: {
        'Authorization': userId,
      },
      body: JSON.stringify({
        user_query: userQuery,
      }),
    });
  }

  // Health check
  async healthCheck() {
    return await this.request('/');
  }
}

// Export singleton instance
const lemoAPI = new LemoAPI();
export default lemoAPI;
