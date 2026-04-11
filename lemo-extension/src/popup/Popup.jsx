import React, { useState } from 'react';
import ChatWindow from '../components/ChatWindow';
import SettingsTab from '../components/SettingsTab';
import WalletPopup from '../components/WalletPopup';
import { Settings, MessageSquare, Wallet } from 'lucide-react';
import '../styles/globals.css';

function Popup() {
  const [activeTab, setActiveTab] = useState('chat'); // 'chat' or 'settings'

  return (
    <div className="w-[400px] h-[600px] bg-gradient-to-br from-orange-50 to-white flex flex-col">
      {/* Header */}
      <div className="bg-gradient-to-r from-[#FF7A00] to-[#E76500] text-white p-4 flex items-center justify-between shadow-lg">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-10 h-10 rounded-full bg-white/20 backdrop-blur-xl flex items-center justify-center text-2xl border-2 border-white/30">
              <img src={chrome.runtime.getURL('logo.png')} alt="Lemo" className="w-8 h-8 rounded-full object-cover" />
            </div>
            <div className="absolute bottom-0 right-0 w-3 h-3 bg-green-400 rounded-full border-2 border-white animate-pulse"></div>
          </div>
          <div>
            <h3 className="font-semibold text-base">Lemo AI</h3>
            <p className="text-xs opacity-80">Your Smart Assistant</p>
          </div>
        </div>
        
        {/* Tab Switcher */}
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('chat')}
            className={`p-2 rounded-lg transition-all ${
              activeTab === 'chat'
                ? 'bg-white/30 backdrop-blur-xl'
                : 'hover:bg-white/10'
            }`}
            title="Chat"
          >
            <MessageSquare className="w-5 h-5" />
          </button>
          <button
            onClick={() => setActiveTab('wallet')}
            className={`p-2 rounded-lg transition-all ${
              activeTab === 'wallet'
                ? 'bg-white/30 backdrop-blur-xl'
                : 'hover:bg-white/10'
            }`}
            title="Wallet"
          >
            <Wallet className="w-5 h-5" />
          </button>
          <button
            onClick={() => setActiveTab('settings')}
            className={`p-2 rounded-lg transition-all ${
              activeTab === 'settings'
                ? 'bg-white/30 backdrop-blur-xl'
                : 'hover:bg-white/10'
            }`}
            title="Settings"
          >
            <Settings className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'chat' ? <ChatWindow /> : activeTab === 'wallet' ? <WalletPopup /> : <SettingsTab />}
      </div>
    </div>
  );
}

export default Popup;