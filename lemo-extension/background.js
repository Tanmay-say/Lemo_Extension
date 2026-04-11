// Background service worker for Lemo AI Assistant
console.log('Lemo AI Assistant: Background script starting...');

// Initialize extension functionality
function initializeExtension() {
    console.log('Lemo AI Assistant: Initializing extension...');
    
    // Set up installed listener if available
    if (chrome.runtime && chrome.runtime.onInstalled) {
        chrome.runtime.onInstalled.addListener(() => {
            console.log('Lemo AI Assistant installed');
        });
    } else {
        console.log('Lemo AI Assistant: chrome.runtime not available');
    }
    
    // Set up action click listener
    setupActionClickListener();
    
    // Set up message listener
    setupMessageListener();
    
    // Set up tab listeners
    setupTabListeners();
}

function setupActionClickListener() {
    if (chrome.action && chrome.action.onClicked) {
        console.log('Lemo AI Assistant: Setting up action click listener');
        chrome.action.onClicked.addListener(handleActionClick);
    } else {
        console.log('Lemo AI Assistant: chrome.action not available, retrying in 1s');
        setTimeout(() => {
            setupActionClickListener();
        }, 1000);
    }
}

async function handleActionClick(tab) {
    try {
        console.log('Lemo AI Assistant: Extension icon clicked for tab', tab.id);
        // Send message to content script to toggle the chatbot
        await chrome.tabs.sendMessage(tab.id, {
            action: "toggle_chatbot"
        });
    } catch (error) {
        console.log('Lemo AI Assistant: Error sending message to content script:', error);
        // If content script isn't loaded yet, inject it
        try {
            await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                files: ['content.js']
            });
            
            // Wait a moment for the script to initialize
            setTimeout(async () => {
                try {
                    await chrome.tabs.sendMessage(tab.id, {
                        action: "toggle_chatbot"
                    });
                } catch (e) {
                    console.log('Lemo AI Assistant: Could not send message after injection:', e);
                }
            }, 500);
        } catch (injectionError) {
            console.log('Lemo AI Assistant: Could not inject content script:', injectionError);
        }
    }
}

function setupMessageListener() {
    if (chrome.runtime && chrome.runtime.onMessage) {
        console.log('Lemo AI Assistant: Setting up message listener');
        chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
            if (request.action === "chatbot_toggled" && chrome.action) {
                try {
                    // Update icon badge to show if chatbot is active
                    chrome.action.setBadgeText({
                        text: request.isVisible ? "ON" : "",
                        tabId: sender.tab.id
                    });
                    chrome.action.setBadgeBackgroundColor({
                        color: "#667eea",
                        tabId: sender.tab.id
                    });
                } catch (error) {
                    console.log('Lemo AI Assistant: Could not set badge:', error);
                }
            }
        });
    } else {
        console.log('Lemo AI Assistant: chrome.runtime.onMessage not available');
    }
}

function setupTabListeners() {
    // Clear badge when tab is closed or navigated
    if (chrome.tabs && chrome.tabs.onRemoved) {
        chrome.tabs.onRemoved.addListener((tabId) => {
            if (chrome.action) {
                try {
                    chrome.action.setBadgeText({
                        text: "",
                        tabId: tabId
                    });
                } catch (error) {
                    console.log('Lemo AI Assistant: Could not clear badge on tab removal:', error);
                }
            }
        });
    }

    if (chrome.tabs && chrome.tabs.onUpdated) {
        chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
            if (changeInfo.status === 'loading' && chrome.action) {
                try {
                    chrome.action.setBadgeText({
                        text: "",
                        tabId: tabId
                    });
                } catch (error) {
                    console.log('Lemo AI Assistant: Could not clear badge on tab update:', error);
                }
            }
        });
    }
}

// Try to initialize immediately
initializeExtension();

// Also try after a delay in case Chrome APIs aren't ready yet
setTimeout(initializeExtension, 1000);
