/**
 * Access window.ethereum from page context
 * Injected into the page to provide MetaMask access
 */

export function injectEthereumAccess() {
  // Check if we're in an extension context
  if (typeof window === 'undefined' || typeof chrome === 'undefined') {
    return null;
  } // FIX C7: missing closing brace was here

  // If we're in page context, return window.ethereum directly
  if (typeof window.ethereum !== 'undefined') {
    return window.ethereum;
  }

  // Otherwise, we need to access it via postMessage
  return null;
}

/**
 * Gets the ethereum provider from page context
 * FIX NEW-3: Added 10-second timeout to prevent infinite hanging
 */
export async function getPageEthereum() {
  return new Promise((resolve, reject) => {
    const TIMEOUT_MS = 10000; // 10 second timeout
    let timeoutId;
    
    // Set timeout guard to prevent infinite hanging
    timeoutId = setTimeout(() => {
      reject(new Error('MetaMask not found: timeout after 10 seconds. Please ensure MetaMask is installed and enabled.'));
    }, TIMEOUT_MS);
    
    // Check if wallet bridge is already injected
    if (document.querySelector('script[data-lemo-wallet-bridge]')) {
      // Listen for window.ethereum to become available
      const checkEthereum = () => {
        if (typeof window.ethereum !== 'undefined') {
          clearTimeout(timeoutId);
          resolve(window.ethereum);
        } else {
          setTimeout(checkEthereum, 100);
        }
      };
      checkEthereum();
    } else {
      // Inject wallet bridge
      const script = document.createElement('script');
      script.src = chrome.runtime.getURL('src/content/walletBridge.js');
      script.setAttribute('data-lemo-wallet-bridge', 'true');
      document.head.appendChild(script);

      script.onload = () => {
        const checkEthereum = () => {
          if (typeof window.ethereum !== 'undefined') {
            clearTimeout(timeoutId);
            resolve(window.ethereum);
          } else {
            setTimeout(checkEthereum, 100);
          }
        };
        setTimeout(checkEthereum, 100);
      };
      
      script.onerror = () => {
        clearTimeout(timeoutId);
        reject(new Error('Failed to load wallet bridge script'));
      };
    }
  });
}

export default { getPageEthereum, injectEthereumAccess };
