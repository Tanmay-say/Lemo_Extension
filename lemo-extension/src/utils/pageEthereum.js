/**
 * Access window.ethereum from page context
 * Injected into the page to provide MetaMask access
 */

export function injectEthereumAccess() {
  // Check if we're in an extension context
  if (typeof window === 'undefined' || typeof chrome === 'undefined') {
    return null;

  // If we're in page context, return window.ethereum directly
  if (typeof window.ethereum !== 'undefined') {
    return window.ethereum;
  }
  
  // Otherwise, we need to access it via postMessage
  return null;
}

/**
 * Gets the ethereum provider from page context
 */
export async function getPageEthereum() {
  return new Promise((resolve, reject) => {
    // Check if wallet bridge is already injected
    if (document.querySelector('script[data-lemo-wallet-bridge]')) {
      // Listen for window.ethereum to become available
      const checkEthereum = () => {
        if (typeof window.ethereum !== 'undefined') {
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
            resolve(window.ethereum);
          } else {
            setTimeout(checkEthereum, 100);
          }
        };
        setTimeout(checkEthereum, 100);
      };
    }
  });
}

export default { getPageEthereum, injectEthereumAccess };

