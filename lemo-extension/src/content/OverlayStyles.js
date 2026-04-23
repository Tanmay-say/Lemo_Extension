// Inject styles for the overlay
export const injectOverlayStyles = () => {
  if (document.getElementById('lemo-overlay-styles')) return;

  const styleSheet = document.createElement('style');
  styleSheet.id = 'lemo-overlay-styles';
  styleSheet.textContent = `
    /* Overlay Container */
    .lemo-overlay-wrapper {
      position: fixed;
      top: 0;
      right: 0;
      width: 420px;
      height: 100vh;
      z-index: 2147483647;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
      transform: translateX(0);
      transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .lemo-overlay-wrapper.hidden {
      transform: translateX(100%);
    }

    .lemo-overlay-container {
      width: 100%;
      height: 100%;
      background: white;
      box-shadow: -4px 0 24px rgba(255, 122, 0, 0.1);
      display: flex;
      flex-direction: column;
      border-left: 1px solid #e5e7eb;
    }

    /* Header */
    .lemo-overlay-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px 20px;
      background: linear-gradient(135deg, #FF7A00 0%, #E76500 100%);
      border-bottom: 1px solid #e5e7eb;
      flex-shrink: 0;
      box-shadow: 0 2px 8px rgba(255, 122, 0, 0.1);
    }

    /* Content */
    .lemo-overlay-content {
      flex: 1;
      overflow: hidden;
      background: white;
    }

    /* Toggle Button */
    .lemo-toggle-button {
      position: fixed;
      bottom: 24px;
      right: 24px;
      width: 56px;
      height: 56px;
      border-radius: 16px;
      background: linear-gradient(135deg, #FF7A00 0%, #E76500 100%);
      border: none;
      color: white;
      font-size: 24px;
      cursor: pointer;
      z-index: 2147483646;
      box-shadow: 0 4px 16px rgba(255, 122, 0, 0.3);
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .lemo-toggle-button:hover {
      transform: scale(1.05);
      box-shadow: 0 6px 20px rgba(255, 122, 0, 0.4);
    }

    .lemo-toggle-button.hidden {
      display: none;
    }

    /* Keep the host page stable. The overlay should float above it instead of
       forcing page reflow, which breaks layouts on Flipkart/Meesho. */
    body.lemo-overlay-active {
      margin-right: 0 !important;
      transition: none !important;
    }

    /* Responsive */
    @media (max-width: 768px) {
      .lemo-overlay-wrapper {
        width: 100%;
      }

      body.lemo-overlay-active {
        margin-right: 0 !important;
      }
    }

    /* Ensure overlay content doesn't interfere with page */
    .lemo-overlay-wrapper * {
      box-sizing: border-box;
    }

    /* White/Orange Theme Overrides */
    .lemo-overlay-container .bg-gradient-to-br.from-purple-50.to-blue-50 {
      background: linear-gradient(to bottom right, #fff7ed, #fefdfc);
    }

    .lemo-overlay-container .bg-gradient-to-r.from-\\[\\#667eea\\].to-\\[\\#764ba2\\] {
      background: linear-gradient(to right, #FF7A00, #E76500);
    }

    .lemo-overlay-container .text-purple-600 {
      color: #ea580c;
    }

    .lemo-overlay-container .bg-purple-100 {
      background-color: #ffedd5;
    }

    .lemo-overlay-container .text-purple-600 {
      color: #ea580c;
    }

    .lemo-overlay-container .focus\\:ring-purple-500:focus {
      --tw-ring-color: #f97316;
    }

    .lemo-overlay-container .focus\\:ring-purple-200:focus {
      --tw-ring-color: #fed7aa;
    }
  `;

  document.head.appendChild(styleSheet);
};
