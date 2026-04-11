// Chatbot functionality for Lemo AI Assistant Extension
class LemoChatbot {
    constructor() {
        this.chatMessages = document.getElementById('chatMessages');
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.clearChatButton = document.getElementById('clearChat');
        this.charCounter = document.getElementById('charCounter');
        this.typingIndicator = document.getElementById('typingIndicator');
        
        this.conversations = [];
        this.responses = this.initializeResponses();
        
        this.init();
    }

    init() {
        this.loadStoredConversations();
        this.bindEvents();
        this.updateSendButton();
    }

    bindEvents() {
        // Send message events
        this.sendButton.addEventListener('click', () => this.sendMessage());
        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Input validation and character counter
        this.messageInput.addEventListener('input', () => {
            this.autoResizeTextarea();
            this.updateCharCounter();
            this.updateSendButton();
        });

        // Clear chat
        this.clearChatButton.addEventListener('click', () => this.clearChat());

        // Auto-focus input
        this.messageInput.focus();
    }

    autoResizeTextarea() {
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = this.messageInput.scrollHeight + 'px';
    }

    updateCharCounter() {
        const length = this.messageInput.value.length;
        this.charCounter.textContent = `${length}/500`;
        
        if (length > 400) {
            this.charCounter.style.color = '#dc3545';
        } else if (length > 300) {
            this.charCounter.style.color = '#fd7e14';
        } else {
            this.charCounter.style.color = '#6c757d';
        }
    }

    updateSendButton() {
        const hasContent = this.messageInput.value.trim().length > 0;
        this.sendButton.disabled = !hasContent;
    }

    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message) return;

        // Add user message
        this.addMessage(message, 'user');
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';
        this.updateCharCounter();
        this.updateSendButton();

        // Show typing indicator
        this.showTypingIndicator();

        // Simulate thinking time
        await this.delay(800 + Math.random() * 1200);

        // Generate and add bot response
        const response = this.generateResponse(message);
        this.hideTypingIndicator();
        this.addMessage(response, 'bot');

        // Save conversation
        this.saveConversations();
    }

    addMessage(text, sender) {
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
                    <p>${this.escapeHtml(text)}</p>
                    <span class="message-time">${this.getCurrentTime()}</span>
                </div>
            </div>
        `;

        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();

        // Store in conversations
        this.conversations.push({
            text: text,
            sender: sender,
            timestamp: new Date().toISOString()
        });
    }

    showTypingIndicator() {
        this.typingIndicator.style.display = 'block';
        this.scrollToBottom();
    }

    hideTypingIndicator() {
        this.typingIndicator.style.display = 'none';
    }

    scrollToBottom() {
        setTimeout(() => {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }, 100);
    }

    generateResponse(userMessage) {
        const message = userMessage.toLowerCase();
        
        // Check for specific patterns and keywords
        for (const [pattern, responses] of Object.entries(this.responses)) {
            if (this.matchesPattern(message, pattern)) {
                return this.getRandomResponse(responses);
            }
        }

        // Default responses if no pattern matches
        const defaultResponses = [
            "That's interesting! Can you tell me more about that?",
            "I understand. How can I help you with this?",
            "Thanks for sharing! What would you like to do next?",
            "I see. Is there anything specific you'd like assistance with?",
            "That's a great question! Let me think about how I can help.",
            "I appreciate you reaching out! What can I do for you today?"
        ];

        return this.getRandomResponse(defaultResponses);
    }

    matchesPattern(message, pattern) {
        const keywords = pattern.split('|');
        return keywords.some(keyword => message.includes(keyword.toLowerCase()));
    }

    getRandomResponse(responses) {
        return responses[Math.floor(Math.random() * responses.length)];
    }

    initializeResponses() {
        return {
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
            'weather|temperature|forecast': [
                "I don't have access to real-time weather data, but I'd recommend checking your local weather app or website for the most accurate forecast!",
                "For current weather information, I suggest checking a reliable weather service like Weather.com or your local weather app.",
                "I wish I could check the weather for you! Try asking your phone's voice assistant or checking a weather website for current conditions."
            ],
            'time|date|day|today': [
                "I don't have access to real-time information, but you can check the current time and date on your device!",
                "For the current time and date, check your computer's clock or ask your device's voice assistant.",
                "I can't access real-time data, but your device should show the current time and date!"
            ],
            'joke|funny|laugh|humor': [
                "Why don't scientists trust atoms? Because they make up everything! 😄",
                "What do you call a bear with no teeth? A gummy bear! 🐻",
                "Why did the scarecrow win an award? He was outstanding in his field! 🌾",
                "What do you call a fake noodle? An impasta! 🍝",
                "Why don't eggs tell jokes? They'd crack each other up! 🥚"
            ],
            'problem|issue|error|bug|trouble': [
                "I'm sorry to hear you're having trouble! Can you describe the problem in more detail so I can try to help?",
                "That sounds frustrating! Let me know more about the issue and I'll do my best to assist.",
                "I'd be happy to help troubleshoot! What specific problem are you encountering?",
                "Problems can be challenging! Share more details and let's work through this together.",
                "I'm here to help resolve issues! What exactly is going wrong?"
            ],
            'chrome|browser|extension|plugin': [
                "I can help with Chrome and browser-related questions! What do you need to know about Chrome or extensions?",
                "Chrome is a great browser! Are you looking for help with Chrome features, settings, or extensions?",
                "I'm knowledgeable about browsers and extensions! What Chrome-related question can I help with?",
                "Chrome has lots of useful features! What specifically would you like to know about?"
            ]
        };
    }

    clearChat() {
        // Remove all messages except the welcome message
        const messages = this.chatMessages.querySelectorAll('.message');
        messages.forEach((message, index) => {
            if (index > 0) { // Keep the first welcome message
                message.remove();
            }
        });

        // Clear stored conversations except welcome
        this.conversations = this.conversations.slice(0, 1);
        this.saveConversations();

        // Focus back on input
        this.messageInput.focus();
    }

    getCurrentTime() {
        const now = new Date();
        const timeString = now.toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        
        const isToday = this.isToday(now);
        if (isToday) {
            return timeString;
        } else {
            return `${now.toLocaleDateString()} ${timeString}`;
        }
    }

    isToday(date) {
        const today = new Date();
        return date.toDateString() === today.toDateString();
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // Storage functionality
    saveConversations() {
        try {
            chrome.storage.local.set({
                'lemoChat_conversations': this.conversations
            });
        } catch (error) {
            // Fallback to localStorage if chrome.storage is not available
            localStorage.setItem('lemoChat_conversations', JSON.stringify(this.conversations));
        }
    }

    loadStoredConversations() {
        try {
            chrome.storage.local.get(['lemoChat_conversations'], (result) => {
                if (result.lemoChat_conversations && result.lemoChat_conversations.length > 1) {
                    this.restoreConversations(result.lemoChat_conversations);
                }
            });
        } catch (error) {
            // Fallback to localStorage
            const stored = localStorage.getItem('lemoChat_conversations');
            if (stored) {
                const conversations = JSON.parse(stored);
                if (conversations.length > 1) {
                    this.restoreConversations(conversations);
                }
            }
        }
    }

    restoreConversations(conversations) {
        // Clear existing messages first (except welcome)
        const existingMessages = this.chatMessages.querySelectorAll('.message');
        existingMessages.forEach((message, index) => {
            if (index > 0) {
                message.remove();
            }
        });

        // Restore conversations (skip the first welcome message)
        conversations.slice(1).forEach(conv => {
            this.addMessageFromStorage(conv.text, conv.sender, conv.timestamp);
        });

        this.conversations = conversations;
    }

    addMessageFromStorage(text, sender, timestamp) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        
        const avatar = sender === 'bot' ? '🚀' : '👤';
        const avatarClass = sender === 'bot' ? 'bot-avatar' : 'user-avatar';
        const timeDisplay = this.formatStoredTime(timestamp);
        
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <span class="${avatarClass}">${avatar}</span>
            </div>
            <div class="message-content">
                <div class="message-bubble">
                    <p>${this.escapeHtml(text)}</p>
                    <span class="message-time">${timeDisplay}</span>
                </div>
            </div>
        `;

        this.chatMessages.appendChild(messageDiv);
    }

    formatStoredTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        
        if (this.isToday(date)) {
            return date.toLocaleTimeString([], { 
                hour: '2-digit', 
                minute: '2-digit' 
            });
        } else {
            return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], { 
                hour: '2-digit', 
                minute: '2-digit' 
            })}`;
        }
    }
}

// Initialize the chatbot when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new LemoChatbot();
});

// Handle extension popup resizing
window.addEventListener('resize', () => {
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
});