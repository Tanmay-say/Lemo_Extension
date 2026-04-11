// Content script for Lemo AI Assistant Overlay
(function() {
    'use strict';

    let chatOverlay = null;
    let toggleButton = null;
    let isVisible = false;
    let isMinimized = false;

    // Initialize the chatbot overlay
    function initializeChatbot() {
        if (chatOverlay) return; // Already initialized

        createOverlay();
        createToggleButton();
        loadChatbotContent();
        
        // Set initial state - completely hidden
        chatOverlay.style.display = 'none';
        toggleButton.style.display = 'none';
        isVisible = false;
        isMinimized = false;
    }

    function createOverlay() {
        // Create the main overlay container
        chatOverlay = document.createElement('div');
        chatOverlay.className = 'lemo-chat-overlay hidden';
        chatOverlay.innerHTML = `
            <button class="lemo-minimize-btn" title="Close">×</button>
            <button class="lemo-close-btn" title="Minimize">−</button>
            <div class="lemo-chat-content"></div>
        `;

        // Add event listeners for overlay controls
        const minimizeBtn = chatOverlay.querySelector('.lemo-minimize-btn');
        const closeBtn = chatOverlay.querySelector('.lemo-close-btn');

        minimizeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            hideOverlay(); // Close button functionality - completely hide overlay
        });

        closeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            minimizeOverlay(); // Minimize button functionality - just minimize
        });

        document.body.appendChild(chatOverlay);
    }

    function createToggleButton() {
        toggleButton = document.createElement('button');
        toggleButton.className = 'lemo-toggle-btn';
        toggleButton.innerHTML = '🤖';
        toggleButton.title = 'Open Lemo AI Assistant';

        toggleButton.addEventListener('click', () => {
            if (isMinimized) {
                maximizeOverlay();
            } else if (!isVisible) {
                showOverlay();
            }
        });

        document.body.appendChild(toggleButton);
    }

    function loadChatbotContent() {
        const contentContainer = chatOverlay.querySelector('.lemo-chat-content');
        
        // Create the chatbot HTML structure
        contentContainer.innerHTML = `
            <div class="chat-container">
                <!-- Header -->
                <div class="chat-header">
                    <div class="header-avatar">
                        <div class="avatar-circle">
                            <span class="avatar-icon">🚀</span>
                        </div>
                        <div class="status-indicator"></div>
                    </div>
                    <div class="header-info">
                        <h3 class="assistant-name">Lemo AI</h3>
                        <p class="assistant-status">Online</p>
                    </div>
                    <div class="header-actions">
                        <button class="action-btn" id="clearChatOverlay" title="Clear chat">
                            <span class="clear-icon">🗑️</span>
                        </button>
                    </div>
                </div>

                <!-- Chat Messages Area -->
                <div class="chat-messages" id="chatMessagesOverlay">
                    <!-- Welcome message -->
                    <div class="message bot-message">
                        <div class="message-avatar">
                            <span class="bot-avatar">🚀</span>
                        </div>
                        <div class="message-content">
                            <div class="message-bubble">
                                <p>Hello! I'm your Lemo AI. How can I help you today?</p>
                                <span class="message-time">Just now</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Typing Indicator -->
                <div class="typing-indicator" id="typingIndicatorOverlay" style="display: none;">
                    <div class="message bot-message">
                        <div class="message-avatar">
                            <span class="bot-avatar">🚀</span>
                        </div>
                        <div class="message-content">
                            <div class="typing-bubble">
                                <div class="typing-dots">
                                    <span></span>
                                    <span></span>
                                    <span></span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Input Area -->
                <div class="chat-input">
                    <div class="input-container">
                        <textarea 
                            id="messageInputOverlay" 
                            placeholder="Type your message here..." 
                            rows="1"
                            maxlength="500"
                        ></textarea>
                        <button id="sendButtonOverlay" class="send-button" disabled>
                            <span class="send-icon">➤</span>
                        </button>
                    </div>
                    <div class="input-footer">
                        <span class="char-counter" id="charCounterOverlay">0/500</span>
                        <span class="powered-by">Powered by Lemo AI</span>
                    </div>
                </div>
            </div>
        `;

        // Add the original popup styles for the content
        addChatbotStyles();

        // Initialize chatbot functionality
        initializeChatbotLogic();
    }

    function addChatbotStyles() {
        // If styles are already added, don't add again
        if (document.getElementById('lemo-chatbot-styles')) return;

        const styleElement = document.createElement('style');
        styleElement.id = 'lemo-chatbot-styles';
        styleElement.textContent = `
            .lemo-chat-overlay .chat-container {
                height: 100vh;
                display: flex;
                flex-direction: column;
                background: #ffffff;
                overflow: hidden;
            }

            .lemo-chat-overlay .chat-header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 16px 20px;
                display: flex;
                align-items: center;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                position: relative;
                flex-shrink: 0;
            }

            .lemo-chat-overlay .header-avatar {
                position: relative;
                margin-right: 12px;
            }

            .lemo-chat-overlay .avatar-circle {
                width: 32px;
                height: 32px;
                border-radius: 50%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
            }

            .lemo-chat-overlay .avatar-icon {
                font-size: 16px;
            }

            .lemo-chat-overlay .status-indicator {
                position: absolute;
                bottom: 0px;
                right: 0px;
                width: 10px;
                height: 10px;
                background: #10b981;
                border-radius: 50%;
                border: 2px solid white;
            }


            .lemo-chat-overlay .header-info {
                flex: 1;
            }

            .lemo-chat-overlay .assistant-name {
                font-size: 16px;
                font-weight: 600;
                margin-bottom: 2px;
                margin: 0;
            }

            .lemo-chat-overlay .assistant-status {
                font-size: 12px;
                opacity: 0.8;
                margin: 0;
            }

            .lemo-chat-overlay .header-actions {
                display: flex;
                gap: 8px;
            }

            .lemo-chat-overlay .action-btn {
                background: #f3f4f6;
                border: 1px solid #e5e7eb;
                color: #6b7280;
                width: 28px;
                height: 28px;
                border-radius: 6px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.2s ease;
            }

            .lemo-chat-overlay .action-btn:hover {
                background: #e5e7eb;
                color: #374151;
            }

            .lemo-chat-overlay .clear-icon {
                font-size: 14px;
            }

            .lemo-chat-overlay .chat-messages {
                flex: 1;
                overflow-y: auto;
                padding: 20px;
                background: #f8f9fa;
                scroll-behavior: smooth;
            }

            .lemo-chat-overlay .chat-messages::-webkit-scrollbar {
                width: 4px;
            }

            .lemo-chat-overlay .chat-messages::-webkit-scrollbar-track {
                background: transparent;
            }

            .lemo-chat-overlay .chat-messages::-webkit-scrollbar-thumb {
                background: #d1d9e6;
                border-radius: 2px;
            }

            .lemo-chat-overlay .chat-messages::-webkit-scrollbar-thumb:hover {
                background: #a8b8d0;
            }

            .lemo-chat-overlay .message {
                display: flex;
                margin-bottom: 16px;
                animation: messageSlideIn 0.3s ease-out;
            }

            @keyframes messageSlideIn {
                from {
                    opacity: 0;
                    transform: translateY(10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            .lemo-chat-overlay .user-message {
                flex-direction: row-reverse;
            }

            .lemo-chat-overlay .message-avatar {
                width: 32px;
                height: 32px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 14px;
                flex-shrink: 0;
                margin: 0 8px;
            }

            .lemo-chat-overlay .bot-message .message-avatar {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }

            .lemo-chat-overlay .user-message .message-avatar {
                background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                color: white;
            }

            .lemo-chat-overlay .bot-avatar, .lemo-chat-overlay .user-avatar {
                font-size: 16px;
            }

            .lemo-chat-overlay .message-content {
                flex: 1;
                max-width: 70%;
            }

            .lemo-chat-overlay .message-bubble {
                padding: 12px 16px;
                border-radius: 18px;
                position: relative;
                word-wrap: break-word;
            }

            .lemo-chat-overlay .bot-message .message-bubble {
                background: white;
                border: 1px solid #e9ecef;
                border-bottom-left-radius: 4px;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            }

            .lemo-chat-overlay .user-message .message-bubble {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border-bottom-right-radius: 4px;
                margin-left: auto;
            }

            .lemo-chat-overlay .message-bubble p {
                margin: 0;
                line-height: 1.4;
                font-size: 14px;
            }

            .lemo-chat-overlay .message-time {
                font-size: 11px;
                opacity: 0.6;
                display: block;
                margin-top: 4px;
            }

            .lemo-chat-overlay .user-message .message-time {
                text-align: right;
            }

            .lemo-chat-overlay .typing-indicator {
                padding: 0 20px;
            }

            .lemo-chat-overlay .typing-bubble {
                background: white;
                border: 1px solid #e9ecef;
                padding: 12px 16px;
                border-radius: 18px;
                border-bottom-left-radius: 4px;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                width: fit-content;
            }

            .lemo-chat-overlay .typing-dots {
                display: flex;
                gap: 3px;
                align-items: center;
            }

            .lemo-chat-overlay .typing-dots span {
                width: 6px;
                height: 6px;
                border-radius: 50%;
                background: #667eea;
                animation: typing 1.4s infinite ease-in-out;
            }

            .lemo-chat-overlay .typing-dots span:nth-child(1) { animation-delay: 0s; }
            .lemo-chat-overlay .typing-dots span:nth-child(2) { animation-delay: 0.2s; }
            .lemo-chat-overlay .typing-dots span:nth-child(3) { animation-delay: 0.4s; }

            @keyframes typing {
                0%, 60%, 100% {
                    transform: translateY(0);
                    opacity: 0.4;
                }
                30% {
                    transform: translateY(-10px);
                    opacity: 1;
                }
            }

            .lemo-chat-overlay .chat-input {
                background: white;
                border-top: 1px solid #e9ecef;
                padding: 16px 20px;
                flex-shrink: 0;
            }

            .lemo-chat-overlay .input-container {
                display: flex;
                align-items: flex-end;
                gap: 12px;
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 24px;
                padding: 8px 16px;
                transition: border-color 0.2s ease;
            }

            .lemo-chat-overlay .input-container:focus-within {
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }

            .lemo-chat-overlay #messageInputOverlay {
                flex: 1;
                border: none;
                outline: none;
                background: transparent;
                font-size: 14px;
                line-height: 1.4;
                resize: none;
                max-height: 100px;
                min-height: 20px;
                font-family: inherit;
                color: #333;
            }

            .lemo-chat-overlay #messageInputOverlay::placeholder {
                color: #6c757d;
            }

            .lemo-chat-overlay .send-button {
                width: 36px;
                height: 36px;
                border-radius: 50%;
                border: none;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.2s ease;
                flex-shrink: 0;
            }

            .lemo-chat-overlay .send-button:enabled:hover {
                transform: scale(1.05);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
            }

            .lemo-chat-overlay .send-button:disabled {
                background: #e9ecef;
                color: #6c757d;
                cursor: not-allowed;
                transform: scale(1);
                box-shadow: none;
            }

            .lemo-chat-overlay .send-icon {
                font-size: 16px;
                transform: translateX(1px);
            }

            .lemo-chat-overlay .input-footer {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-top: 8px;
                font-size: 11px;
                color: #6c757d;
            }

            .lemo-chat-overlay .char-counter {
                font-weight: 500;
            }

            .lemo-chat-overlay .powered-by {
                opacity: 0.7;
            }
        `;

        document.head.appendChild(styleElement);
    }

    function initializeChatbotLogic() {
        // Initialize the chatbot with the same logic as popup.js, but adapted for overlay
        const messageInput = document.getElementById('messageInputOverlay');
        const sendButton = document.getElementById('sendButtonOverlay');
        const clearButton = document.getElementById('clearChatOverlay');
        const charCounter = document.getElementById('charCounterOverlay');
        const chatMessages = document.getElementById('chatMessagesOverlay');
        const typingIndicator = document.getElementById('typingIndicatorOverlay');

        let conversations = [{
            text: "Hello! I'm your Lemo AI. How can I help you today?",
            sender: "bot",
            timestamp: new Date().toISOString()
        }];

        // Event listeners
        sendButton.addEventListener('click', sendMessage);
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        messageInput.addEventListener('input', () => {
            autoResizeTextarea();
            updateCharCounter();
            updateSendButton();
        });

        clearButton.addEventListener('click', clearChat);
        messageInput.focus();

        function autoResizeTextarea() {
            messageInput.style.height = 'auto';
            messageInput.style.height = messageInput.scrollHeight + 'px';
        }

        function updateCharCounter() {
            const length = messageInput.value.length;
            charCounter.textContent = `${length}/500`;
            
            if (length > 400) {
                charCounter.style.color = '#dc3545';
            } else if (length > 300) {
                charCounter.style.color = '#fd7e14';
            } else {
                charCounter.style.color = '#6c757d';
            }
        }

        function updateSendButton() {
            const hasContent = messageInput.value.trim().length > 0;
            sendButton.disabled = !hasContent;
        }

        async function sendMessage() {
            const message = messageInput.value.trim();
            if (!message) return;

            addMessage(message, 'user');
            messageInput.value = '';
            messageInput.style.height = 'auto';
            updateCharCounter();
            updateSendButton();

            showTypingIndicator();

            await delay(800 + Math.random() * 1200);

            const response = generateResponse(message);
            hideTypingIndicator();
            addMessage(response, 'bot');
        }

        function addMessage(text, sender) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${sender}-message`;
            
            const avatar = sender === 'bot' ? '🚀' : '👤';
            const avatarClass = sender === 'bot' ? 'bot-avatar' : 'user-avatar';
            
            messageDiv.innerHTML = `
                <div class="message-avatar">
                    <span class="${avatarClass}">${avatar}</span>
                </div>
                <div class="message-content">
                    <div class="message-bubble">
                        <p>${escapeHtml(text)}</p>
                        <span class="message-time">${getCurrentTime()}</span>
                    </div>
                </div>
            `;

            chatMessages.appendChild(messageDiv);
            scrollToBottom();

            conversations.push({
                text: text,
                sender: sender,
                timestamp: new Date().toISOString()
            });
        }

        function showTypingIndicator() {
            typingIndicator.style.display = 'block';
            scrollToBottom();
        }

        function hideTypingIndicator() {
            typingIndicator.style.display = 'none';
        }

        function scrollToBottom() {
            setTimeout(() => {
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }, 100);
        }

        function generateResponse(userMessage) {
            const message = userMessage.toLowerCase();
            
            const responses = {
                'hello|hi|hey|good morning|good afternoon|good evening': [
                    "Hello! Great to see you today! How can I assist you?",
                    "Hi there! I'm excited to help you out. What's on your mind?",
                    "Hey! Welcome back! What can I help you with today?",
                    "Good to see you! How can I make your day better?",
                    "Hello! Ready to tackle some tasks together?"
                ],
                'how are you|how do you do|what\'s up': [
                    "I'm doing great, thanks for asking! Ready to help with whatever you need.",
                    "I'm fantastic and ready to assist! How are you doing?",
                    "I'm doing well! Excited to help you with your questions or tasks.",
                    "I'm great! What brings you here today?",
                    "Doing wonderful! How can I make your day more productive?"
                ],
                'what can you do|what are your capabilities|help me|what do you offer': [
                    "I can help with a wide variety of tasks! I can answer questions, provide information, help with problem-solving, assist with planning, and much more. What specific area would you like help with?",
                    "I'm here to assist with questions, provide explanations, help brainstorm ideas, offer suggestions, and support you with various tasks. What would you like to work on?",
                    "Great question! I can help with research, answer questions, provide advice, assist with writing, help solve problems, and much more. What do you need help with today?",
                    "I'm designed to be your helpful assistant! I can provide information, answer questions, help with tasks, offer suggestions, and support your projects. What shall we start with?"
                ],
                'thanks|thank you|appreciate': [
                    "You're very welcome! Happy to help anytime!",
                    "My pleasure! That's what I'm here for.",
                    "You're welcome! Feel free to ask if you need anything else.",
                    "Glad I could help! Don't hesitate to reach out again.",
                    "Anytime! I enjoy being helpful."
                ],
                'bye|goodbye|see you|farewell': [
                    "Goodbye! Have a wonderful day ahead!",
                    "See you later! Feel free to come back anytime you need help.",
                    "Take care! I'll be here whenever you need assistance.",
                    "Farewell! Hope to chat with you again soon!",
                    "Bye for now! Wishing you all the best!"
                ],
                'joke|funny|laugh|humor': [
                    "Why don't scientists trust atoms? Because they make up everything! 😄",
                    "What do you call a bear with no teeth? A gummy bear! 🐻",
                    "Why did the scarecrow win an award? He was outstanding in his field! 🌾",
                    "What do you call a fake noodle? An impasta! 🍝",
                    "Why don't eggs tell jokes? They'd crack each other up! 🥚"
                ]
            };

            for (const [pattern, responseArray] of Object.entries(responses)) {
                const keywords = pattern.split('|');
                if (keywords.some(keyword => message.includes(keyword.toLowerCase()))) {
                    return responseArray[Math.floor(Math.random() * responseArray.length)];
                }
            }

            const defaultResponses = [
                "That's interesting! Can you tell me more about that?",
                "I understand. How can I help you with this?",
                "Thanks for sharing! What would you like to do next?",
                "I see. Is there anything specific you'd like assistance with?",
                "That's a great question! Let me think about how I can help.",
                "I appreciate you reaching out! What can I do for you today?"
            ];

            return defaultResponses[Math.floor(Math.random() * defaultResponses.length)];
        }

        function clearChat() {
            const messages = chatMessages.querySelectorAll('.message');
            messages.forEach((message, index) => {
                if (index > 0) {
                    message.remove();
                }
            });

            conversations = conversations.slice(0, 1);
            messageInput.focus();
        }

        function getCurrentTime() {
            const now = new Date();
            return now.toLocaleTimeString([], { 
                hour: '2-digit', 
                minute: '2-digit' 
            });
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function delay(ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
        }
    }

    // Debounce helper for performance
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Page content adjustment functions
    function adjustPageContent(overlayVisible) {
        const overlayWidth = overlayVisible ? 400 : 0;
        
        // Adjust document body with smooth transition
        if (document.body) {
            if (!document.body.style.transition.includes('margin-right')) {
                document.body.style.transition = (document.body.style.transition || '') + ' margin-right 0.2s ease-in-out';
            }
            document.body.style.marginRight = overlayVisible ? `${overlayWidth}px` : '0px';
        }
        
        // Find and adjust main content containers
        const mainSelectors = [
            'main', '[role="main"]', '.main-content', '#main', '#content',
            '.container', '.wrapper', '.page-content', 'article', '.app'
        ];
        
        mainSelectors.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(element => {
                if (element !== chatOverlay && element !== toggleButton) {
                    if (!element.style.transition.includes('margin-right')) {
                        element.style.transition = (element.style.transition || '') + ' margin-right 0.2s ease-in-out';
                    }
                    element.style.marginRight = overlayVisible ? `${overlayWidth}px` : '0px';
                }
            });
        });
        
        // Handle fixed/sticky position elements more efficiently
        const fixedSelectors = [
            '[style*="position: fixed"]', '[style*="position:fixed"]',
            '[style*="position: sticky"]', '[style*="position:sticky"]',
            '.fixed', '.sticky', '.navbar-fixed', '.header-fixed'
        ];
        
        fixedSelectors.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(element => {
                const computedStyle = window.getComputedStyle(element);
                if ((computedStyle.position === 'fixed' || computedStyle.position === 'sticky') && 
                    element !== chatOverlay && element !== toggleButton) {
                    
                    if (overlayVisible && !element.getAttribute('data-lemo-adjusted')) {
                        element.style.transition = (element.style.transition || '') + ' right 0.2s ease-in-out';
                        const currentRight = parseInt(computedStyle.right) || 0;
                        element.style.right = `${currentRight + overlayWidth}px`;
                        element.setAttribute('data-lemo-adjusted', 'true');
                        element.setAttribute('data-lemo-original-right', computedStyle.right);
                    } else if (!overlayVisible && element.getAttribute('data-lemo-adjusted')) {
                        // Restore original position
                        const originalRight = element.getAttribute('data-lemo-original-right');
                        element.style.right = originalRight === 'auto' ? 'auto' : (originalRight || '0px');
                        element.removeAttribute('data-lemo-adjusted');
                        element.removeAttribute('data-lemo-original-right');
                    }
                }
            });
        });
        
        // Trigger a resize event after a short delay to help responsive elements adjust
        setTimeout(() => {
            window.dispatchEvent(new Event('resize'));
        }, 50);
    }

    // Debounced version for better performance during rapid toggling
    const debouncedAdjustPageContent = debounce(adjustPageContent, 100);

    // Cache frequently used selectors for better performance
    const selectorCache = new Map();
    function getCachedElements(selector) {
        if (!selectorCache.has(selector)) {
            selectorCache.set(selector, document.querySelectorAll(selector));
        }
        return selectorCache.get(selector);
    }

    // Clear selector cache when DOM changes significantly
    function clearSelectorCache() {
        selectorCache.clear();
    }

    // Performance monitoring (optional)
    let performanceDebug = false;
    function logPerformance(operation, startTime) {
        if (performanceDebug) {
            const duration = performance.now() - startTime;
            console.log(`Lemo AI: ${operation} took ${duration.toFixed(2)}ms`);
        }
    }

    // Optimized page adjustment with performance monitoring
    function optimizedAdjustPageContent(overlayVisible) {
        const startTime = performance.now();
        
        try {
            adjustPageContent(overlayVisible);
            logPerformance('Page content adjustment', startTime);
        } catch (error) {
            console.warn('Error in page content adjustment:', error);
        }
    }

    // Mutation observer to handle dynamic content changes
    let mutationObserver;
    function setupMutationObserver() {
        if (!mutationObserver) {
            mutationObserver = new MutationObserver((mutations) => {
                let shouldClearCache = false;
                
                mutations.forEach(mutation => {
                    // Clear cache if new elements are added that might match our selectors
                    if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                        for (let node of mutation.addedNodes) {
                            if (node.nodeType === Node.ELEMENT_NODE) {
                                // Check if the added element or its children might match our selectors
                                if (node.matches && (
                                    node.matches('main, [role="main"], .main-content, #main, #content, .container, .wrapper, .page-content, article, .app') ||
                                    node.matches('[style*="position: fixed"], [style*="position:fixed"], [style*="position: sticky"], [style*="position:sticky"], .fixed, .sticky, .navbar-fixed, .header-fixed') ||
                                    node.querySelector('main, [role="main"], .main-content, #main, #content, .container, .wrapper, .page-content, article, .app, [style*="position: fixed"], [style*="position:fixed"], [style*="position: sticky"], [style*="position:sticky"], .fixed, .sticky, .navbar-fixed, .header-fixed')
                                )) {
                                    shouldClearCache = true;
                                    break;
                                }
                            }
                        }
                    }
                });
                
                if (shouldClearCache) {
                    clearSelectorCache();
                    // Re-adjust if overlay is currently visible
                    if (isVisible && !isMinimized) {
                        debouncedAdjustPageContent(true);
                    }
                }
            });
            
            mutationObserver.observe(document.body, {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: ['style', 'class']
            });
        }
    }

    // Overlay control functions
    function showOverlay() {
        if (!chatOverlay) return;
        
        chatOverlay.style.display = 'block';
        chatOverlay.classList.remove('hidden', 'minimized');
        chatOverlay.classList.add('entering');
        toggleButton.style.display = 'none';
        isVisible = true;
        isMinimized = false;

        // Adjust page content
        adjustPageContent(true);

        setTimeout(() => {
            chatOverlay.classList.remove('entering');
        }, 400);

        // Focus on input
        const messageInput = document.getElementById('messageInputOverlay');
        if (messageInput) {
            setTimeout(() => messageInput.focus(), 500);
        }

        // Notify background script
        try {
            if (chrome.runtime && chrome.runtime.sendMessage) {
                chrome.runtime.sendMessage({
                    action: "chatbot_toggled",
                    isVisible: true
                });
            }
        } catch (error) {
            console.log('Lemo AI: Could not send message to background:', error);
        }
    }

    function hideOverlay() {
        if (!chatOverlay) return;
        
        chatOverlay.style.display = 'none';
        chatOverlay.classList.remove('minimized');
        toggleButton.style.display = 'none';
        isVisible = false;
        isMinimized = false;

        // Restore page content
        adjustPageContent(false);

        // Notify background script
        try {
            if (chrome.runtime && chrome.runtime.sendMessage) {
                chrome.runtime.sendMessage({
                    action: "chatbot_toggled",
                    isVisible: false
                });
            }
        } catch (error) {
            console.log('Lemo AI: Could not send message to background:', error);
        }
    }

    function minimizeOverlay() {
        if (!chatOverlay) return;
        
        chatOverlay.style.display = 'none';
        chatOverlay.classList.add('minimized');
        toggleButton.style.display = 'block';
        isMinimized = true;
        isVisible = false;

        // Restore page content when minimized
        adjustPageContent(false);

        // Notify background script
        try {
            if (chrome.runtime && chrome.runtime.sendMessage) {
                chrome.runtime.sendMessage({
                    action: "chatbot_toggled",
                    isVisible: false
                });
            }
        } catch (error) {
            console.log('Lemo AI: Could not send message to background:', error);
        }
    }

    function maximizeOverlay() {
        if (!chatOverlay) return;
        
        chatOverlay.style.display = 'block';
        chatOverlay.classList.remove('minimized', 'hidden');
        toggleButton.style.display = 'none';
        isMinimized = false;
        isVisible = true;

        // Adjust page content when maximized
        adjustPageContent(true);

        // Focus on input
        const messageInput = document.getElementById('messageInputOverlay');
        if (messageInput) {
            setTimeout(() => messageInput.focus(), 100);
        }

        // Notify background script
        try {
            if (chrome.runtime && chrome.runtime.sendMessage) {
                chrome.runtime.sendMessage({
                    action: "chatbot_toggled",
                    isVisible: true
                });
            }
        } catch (error) {
            console.log('Lemo AI: Could not send message to background:', error);
        }
    }

    // Listen for messages from background script
    if (chrome.runtime && chrome.runtime.onMessage) {
        chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
            try {
                if (request.action === "toggle_chatbot") {
                    if (!chatOverlay) {
                        initializeChatbot();
                        setTimeout(() => showOverlay(), 100);
                    } else if (isVisible && !isMinimized) {
                        // If visible and not minimized, minimize it
                        minimizeOverlay();
                    } else if (isMinimized) {
                        // If minimized, maximize it
                        maximizeOverlay();
                    } else {
                        // If hidden, show it
                        showOverlay();
                    }
                    sendResponse({success: true});
                }
            } catch (error) {
                console.log('Lemo AI: Error handling message:', error);
                sendResponse({success: false, error: error.message});
            }
        });
    }

    // Simple cleanup function
    function cleanupPageAdjustments() {
        try {
            // Remove overlay if it exists
            const overlay = document.querySelector('.lemo-chat-overlay');
            if (overlay) {
                overlay.remove();
            }
            
            // Remove toggle button if it exists
            const toggle = document.querySelector('.lemo-toggle-btn');
            if (toggle) {
                toggle.remove();
            }
        } catch (error) {
            console.warn('Error during cleanup:', error);
        }
    }

    // Optimized initialization with duplicate prevention
    function safeInitialize() {
        try {
            // Prevent multiple initializations
            if (document.querySelector('.lemo-chat-overlay')) {
                console.log('Lemo AI: Already initialized');
                return;
            }
            
            initializeChatbot();
            console.log('Lemo AI: Initialized successfully');
        } catch (error) {
            console.log('Lemo AI: Initialization error, retrying...', error);
            setTimeout(safeInitialize, 1500);
        }
    }

    // Enhanced DOM ready detection for better performance
    function initWhenReady() {
        if (document.body && document.head) {
            safeInitialize();
        } else {
            setTimeout(initWhenReady, 100);
        }
    }

    // Cleanup on page unload
    window.addEventListener('beforeunload', cleanupPageAdjustments, { passive: true });
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initWhenReady, { once: true, passive: true });
    } else {
        requestIdleCallback ? requestIdleCallback(initWhenReady) : setTimeout(initWhenReady, 0);
    }

})();
