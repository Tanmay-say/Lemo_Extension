import React from 'react';
import ReactDOM from 'react-dom/client';
import Overlay from './Overlay';
import { injectOverlayStyles } from './OverlayStyles';
import '../styles/globals.css';

let overlayRoot = null;
let isVisible = false;

// Initialize overlay
const initializeOverlay = () => {
  if (overlayRoot) return;

  console.log('Lemo AI: Initializing overlay...');

  // Inject styles
  injectOverlayStyles();

  // Create wrapper div
  const wrapper = document.createElement('div');
  wrapper.id = 'lemo-overlay-root';
  wrapper.className = 'lemo-overlay-wrapper hidden';
  document.body.appendChild(wrapper);

  // Create toggle button
  const toggleButton = document.createElement('button');
  toggleButton.id = 'lemo-toggle-btn';
  toggleButton.className = 'lemo-toggle-button';
  toggleButton.innerHTML = '<img src="' + chrome.runtime.getURL('logo.png') + '" style="width: 32px; height: 32px; border-radius: 50%; object-fit: cover;" />';
  toggleButton.onclick = showOverlay;
  document.body.appendChild(toggleButton);

  // Create React root
  overlayRoot = ReactDOM.createRoot(wrapper);

  // Render overlay
  renderOverlay();
};

const renderOverlay = () => {
  if (!overlayRoot) return;

  overlayRoot.render(
    <React.StrictMode>
      <Overlay onClose={hideOverlay} onMinimize={minimizeOverlay} />
    </React.StrictMode>
  );
};

const showOverlay = () => {
  const wrapper = document.getElementById('lemo-overlay-root');
  const toggleButton = document.getElementById('lemo-toggle-btn');

  if (wrapper) {
    wrapper.classList.remove('hidden');
    document.body.classList.add('lemo-overlay-active');
    isVisible = true;
  }

  if (toggleButton) {
    toggleButton.classList.add('hidden');
  }

  // Notify background
  try {
    chrome.runtime.sendMessage({ action: 'overlay_toggled', isVisible: true }, () => {
      if (chrome.runtime.lastError) {
        console.log('Message send error (ignored):', chrome.runtime.lastError.message);
      }
    });
  } catch (error) {
    console.log('Runtime unavailable (ignored):', error.message);
  }
};

const hideOverlay = () => {
  const wrapper = document.getElementById('lemo-overlay-root');
  const toggleButton = document.getElementById('lemo-toggle-btn');
  
  if (wrapper) {
    wrapper.classList.add('hidden');
    document.body.classList.remove('lemo-overlay-active');
    isVisible = false;
  }
  
  if (toggleButton) {
    toggleButton.classList.remove('hidden');
  }
  
  // Notify background (with error handling)
  try {
    chrome.runtime.sendMessage({ action: 'overlay_toggled', isVisible: false }, () => {
      if (chrome.runtime.lastError) {
        console.log('Message send error (ignored):', chrome.runtime.lastError.message);
      }
    });
  } catch (error) {
    console.log('Runtime unavailable (ignored):', error.message);
  }
  
  // NEW: Completely unmount React and remove all elements
  if (overlayRoot) {
    overlayRoot.unmount();
    overlayRoot = null;
  }
  
  // Remove DOM elements
  if (wrapper) wrapper.remove();
  if (toggleButton) toggleButton.remove();
  
  // Clear state
  isVisible = false;
  
  // Notify background to clear badge (with error handling)
  try {
    chrome.runtime.sendMessage({ action: 'extension_closed' }, () => {
      if (chrome.runtime.lastError) {
        console.log('Extension closed message error (ignored):', chrome.runtime.lastError.message);
      }
    });
  } catch (error) {
    console.log('Runtime unavailable on close (ignored):', error.message);
  }
};

const minimizeOverlay = () => {
  const wrapper = document.getElementById('lemo-overlay-root');
  const toggleButton = document.getElementById('lemo-toggle-btn');

  if (wrapper) {
    wrapper.classList.add('hidden');
    document.body.classList.remove('lemo-overlay-active');
    isVisible = false;
  }

  if (toggleButton) {
    toggleButton.classList.remove('hidden');
  }

  // Notify background (with error handling)
  try {
    chrome.runtime.sendMessage({ action: 'overlay_toggled', isVisible: false }, () => {
      if (chrome.runtime.lastError) {
        console.log('Message send error (ignored):', chrome.runtime.lastError.message);
      }
    });
  } catch (error) {
    console.log('Runtime unavailable (ignored):', error.message);
  }
};

const toggleOverlay = () => {
  if (isVisible) {
    minimizeOverlay();
  } else {
    showOverlay();
  }
};

// Listen for messages from background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'toggle_overlay') {
    if (!overlayRoot) {
      initializeOverlay();
      setTimeout(showOverlay, 100);
    } else {
      toggleOverlay();
    }
    sendResponse({ success: true });
  }

  // Handle wallet operations
  if (request.action === 'WALLET_OPERATION') {
    handleWalletOperation(request, sendResponse);
    return true; // Keep message channel open for async response
  }
});

// Handle wallet operations by communicating with page context
async function handleWalletOperation(request, sendResponse) {
  try {
    const requestId = request.requestId || Date.now();
    
    // Ensure wallet bridge is injected
    if (!document.querySelector('script[data-lemo-wallet-bridge]')) {
      const script = document.createElement('script');
      script.src = chrome.runtime.getURL('src/content/walletBridge.js');
      script.setAttribute('data-lemo-wallet-bridge', 'true');
      document.head.appendChild(script);
      
      // Wait for script to load
      await new Promise((resolve) => {
        script.onload = resolve;
        script.onerror = resolve;
        setTimeout(resolve, 1000); // Fallback timeout
      });
    }
    
    // Send message to page context
    window.postMessage({
      source: 'lemo-extension',
      action: request.walletAction,
      requestId,
      tokenSymbol: request.tokenSymbol,  // Forward additional data
      account: request.account            // Forward additional data
    }, '*');

    // Listen for response from page context
    const responseHandler = (event) => {
      if (event.source !== window || 
          !event.data || 
          event.data.source !== 'lemo-extension-response' ||
          event.data.requestId !== requestId) {
        return;
      }

      window.removeEventListener('message', responseHandler);
      
      if (event.data.success) {
        sendResponse({
          success: true,
          result: event.data.result
        });
      } else {
        sendResponse({
          success: false,
          error: event.data.error
        });
      }
    };

    window.addEventListener('message', responseHandler);

    // Timeout after 15 seconds
    setTimeout(() => {
      window.removeEventListener('message', responseHandler);
      sendResponse({
        success: false,
        error: 'Wallet operation timeout'
      });
    }, 15000);

  } catch (error) {
    console.error('Wallet operation error:', error);
    sendResponse({
      success: false,
      error: error.message || 'Failed to perform wallet operation'
    });
  }
}

// Initialize when page loads
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeOverlay);
} else {
  initializeOverlay();
}

console.log('Lemo AI: Content script loaded');
