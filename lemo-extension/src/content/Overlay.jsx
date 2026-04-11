import React, { useState } from 'react';
import { X, Minus, MessageSquare, Settings, Wallet } from 'lucide-react';
import ChatWindow from '../components/ChatWindow';
import SettingsTab from '../components/SettingsTab';
import WalletPopup from '../components/WalletPopup';

const Overlay = ({ onClose, onMinimize }) => {
  const [activeTab, setActiveTab] = useState('chat');

  return (
    <div className="lemo-overlay-container">
      {/* Header */}
      <div className="lemo-overlay-header">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center text-lg">
              <img src={chrome.runtime.getURL('logo.png')} alt="Lemo" className="w-6 h-6 rounded-full object-cover" />
            </div>
            <div className="absolute bottom-0 right-0 w-2 h-2 bg-green-400 rounded-full border border-white"></div>
          </div>
          <div>
            <h3 className="font-semibold text-sm text-white">Lemo AI</h3>
            <p className="text-xs text-orange-100">Smart Assistant</p>
          </div>
        </div>

        {/* Tab Icons */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setActiveTab('chat')}
            className={`p-2 rounded-lg transition-all ${
              activeTab === 'chat'
                ? 'bg-white/30 text-white'
                : 'text-orange-100 hover:text-white hover:bg-white/20'
            }`}
            title="Chat"
          >
            <MessageSquare className="w-4 h-4" />
          </button>
          <button
            onClick={() => setActiveTab('wallet')}
            className={`p-2 rounded-lg transition-all ${
              activeTab === 'wallet'
                ? 'bg-white/30 text-white'
                : 'text-orange-100 hover:text-white hover:bg-white/20'
            }`}
            title="Wallet"
          >
            <Wallet className="w-4 h-4" />
          </button>
          <button
            onClick={() => setActiveTab('settings')}
            className={`p-2 rounded-lg transition-all ${
              activeTab === 'settings'
                ? 'bg-white/30 text-white'
                : 'text-orange-100 hover:text-white hover:bg-white/20'
            }`}
            title="Settings"
          >
            <Settings className="w-4 h-4" />
          </button>

          {/* Divider */}
          <div className="w-px h-6 bg-white/30 mx-1"></div>

          {/* Control Buttons */}
          <button
            onClick={onMinimize}
            className="p-2 rounded-lg text-orange-100 hover:text-white hover:bg-white/20 transition-all"
            title="Minimize"
          >
            <Minus className="w-4 h-4" />
          </button>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-orange-100 hover:text-red-200 hover:bg-red-500/20 transition-all"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="lemo-overlay-content">
        {activeTab === 'chat' && <ChatWindow />}
        {activeTab === 'wallet' && <WalletPopup />}
        {activeTab === 'settings' && <SettingsTab />}
      </div>
    </div>
  );
};

export default Overlay;