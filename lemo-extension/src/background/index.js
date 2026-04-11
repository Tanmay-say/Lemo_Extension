// Background service worker for Lemo AI Assistant
console.log('Lemo AI Assistant: Background script starting...');

// Handle extension icon click
chrome.action.onClicked.addListener(async (tab) => {
  try {
    console.log('Lemo AI Assistant: Extension icon clicked for tab', tab.id);

    // Send message to content script to toggle overlay
    await chrome.tabs.sendMessage(tab.id, {
      action: 'toggle_overlay'
    });
  } catch (error) {
    console.log('Lemo AI Assistant: Error sending message:', error);

    // If content script isn't loaded, inject it
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['src/content/index.jsx']
      });

      // Inject CSS
      await chrome.scripting.insertCSS({
        target: { tabId: tab.id },
        files: ['src/styles/globals.css']
      });

      // Wait and try again
      setTimeout(async () => {
        try {
          await chrome.tabs.sendMessage(tab.id, {
            action: 'toggle_overlay'
          });
        } catch (e) {
          console.log('Could not send message after injection:', e);
        }
      }, 500);
    } catch (injectionError) {
      console.log('Could not inject content script:', injectionError);
    }
  }
});

// Listen for messages from content script and popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'overlay_toggled') {
    // Update badge
    chrome.action.setBadgeText({
      text: request.isVisible ? 'ON' : '',
      tabId: sender.tab.id
    });
    chrome.action.setBadgeBackgroundColor({
      color: '#667eea',
      tabId: sender.tab.id
    });
    sendResponse({ success: true });
    return true;
  }

  if (request.action === 'extension_closed') {
    // Clear badge completely
    chrome.action.setBadgeText({ text: '', tabId: sender.tab.id });
    sendResponse({ success: true });
    return true;
  }

  // Handle wallet operations
  if (request.action === 'CHECK_WALLET' || request.action === 'CONNECT_WALLET' ||
    request.action === 'SWITCH_TO_SEPOLIA' || request.action === 'SWITCH_TO_FILECOIN' ||
    request.action === 'GET_TOKEN_BALANCES' || request.action === 'GET_SPECIFIC_TOKEN_BALANCE') {
    handleWalletOperation(request, sender, sendResponse);
    return true; // Keep message channel open for async response
  }

  sendResponse({ success: true });
  return true;
});

// Handle wallet operations by communicating with content script
async function handleWalletOperation(request, sender, sendResponse) {
  try {
    // Determine target tab: prefer provided tabId from popup
    let tabId = request.tabId;
    if (!tabId) {
      // If no tabId provided (popup context), try to get the active tab
      try {
        const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
        tabId = activeTab?.id;
      } catch (tabError) {
        console.log('Could not query tabs:', tabError);
        // If we can't query tabs, try to use sender.tab.id if available
        tabId = sender.tab?.id;
      }
    }

    if (!tabId) {
      sendResponse({ success: false, error: 'No active tab found. Please open the extension on a web page.' });
      return;
    }

    // Send message to content script to relay to page context
    const response = await chrome.tabs.sendMessage(tabId, {
      action: 'WALLET_OPERATION',
      walletAction: request.action,
      requestId: Date.now(),
      tokenSymbol: request.tokenSymbol,  // Pass additional data
      account: request.account            // Pass additional data
    });

    sendResponse(response);
  } catch (error) {
    console.error('Wallet operation error:', error);
    sendResponse({
      success: false,
      error: error.message || 'Failed to perform wallet operation'
    });
  }
}

// Clear badge on tab close/navigation
chrome.tabs.onRemoved.addListener((tabId) => {
  chrome.action.setBadgeText({ text: '', tabId });
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status === 'loading') {
    chrome.action.setBadgeText({ text: '', tabId });
  }
});

console.log('Lemo AI Assistant: Background script initialized');
