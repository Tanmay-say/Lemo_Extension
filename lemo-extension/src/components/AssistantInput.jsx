import React, { useState, useRef, useEffect } from 'react';

const AssistantInput = ({ onSendMessage, disabled = false }) => {
  const [inputValue, setInputValue] = useState('');
  const textareaRef = useRef(null);

  useEffect(() => {
    autoGrow();
  }, [inputValue]);

  useEffect(() => {
    // Fix initial height on mount
    autoGrow();
  }, []);

  const handleSend = () => {
    if (inputValue.trim()) {
      // Handle send action
      onSendMessage && onSendMessage(inputValue);
      setInputValue('');
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const autoGrow = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const max = 120; // px max height before scroll
    const newHeight = Math.min(el.scrollHeight, max);
    el.style.height = newHeight + 'px';
    el.style.overflowY = el.scrollHeight > max ? 'auto' : 'hidden';
  };

  return (
    <div className="assistant-input-bar" style={{ padding: '8px 12px', minHeight: '44px' }}>
      <textarea
        ref={textareaRef}
        className="input-area"
        rows={1}
        placeholder={disabled ? "Connect wallet to chat..." : "Ask anything..."}
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyPress={handleKeyPress}
        disabled={disabled}
        style={{ resize: 'none', fontSize: '14px' }}
      />
      <button className="icon-btn" title="Attach" disabled={disabled}>
        <svg viewBox="0 0 24 24" width="16" height="16">
          <path fill="currentColor" d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5v10.5c0 .55-.45 1-1 1s-1-.45-1-1V6H10v9.5c0 1.38 1.12 2.5 2.5 2.5s2.5-1.12 2.5-2.5V5c0-2.21-1.79-4-4-4S7 2.79 7 5v12.5c0 3.04 2.61 5.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
        </svg>
      </button>
      <button className="icon-btn" title="Voice" disabled={disabled}>
        <svg viewBox="0 0 24 24" width="16" height="16">
          <path fill="currentColor" d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V5zm6 6c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
        </svg>
      </button>
      <button className="icon-btn send-btn" title="Send" onClick={handleSend} disabled={disabled}>
        <svg viewBox="0 0 24 24" width="18" height="18">
          <path fill="currentColor" d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
        </svg>
      </button>
    </div>
  );
};

export default AssistantInput;
