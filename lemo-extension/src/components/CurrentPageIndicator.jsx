import React from 'react';
import { RefreshCw, Globe } from 'lucide-react';

const CurrentPageIndicator = ({ url, domain, onRefresh, isRefreshing }) => {
  // Format URL for display
  const formatUrlForDisplay = (url) => {
    if (!url) return 'No page detected';
    
    try {
      const urlObj = new URL(url);
      const hostname = urlObj.hostname.replace(/^www\./, '');
      const pathname = urlObj.pathname;
      
      // Truncate long paths
      const maxPathLength = 30;
      const displayPath = pathname.length > maxPathLength 
        ? pathname.substring(0, maxPathLength) + '...'
        : pathname;
      
      return `${hostname}${displayPath}`;
    } catch (error) {
      return url.length > 40 ? url.substring(0, 40) + '...' : url;
    }
  };

  const displayText = formatUrlForDisplay(url);

  return (
    <div className="mb-2">
      {/* Compact Current Page Indicator */}
      <div className="relative overflow-hidden rounded-lg bg-gradient-to-r from-orange-400/10 via-orange-300/8 to-orange-500/12 backdrop-blur-sm border border-orange-200/20 shadow-sm">
        {/* Content */}
        <div className="relative px-2.5 py-1.5 flex items-center justify-between">
          {/* Left side - Globe icon and URL */}
          <div className="flex items-center gap-1.5 flex-1 min-w-0">
            <div className="w-3.5 h-3.5 rounded-full bg-gradient-to-r from-orange-500 to-orange-600 flex items-center justify-center flex-shrink-0">
              <Globe className="w-2 h-2 text-white" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[11px] font-medium text-gray-600 truncate">
                {displayText}
              </div>
            </div>
          </div>

          {/* Right side - Refresh button */}
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="ml-1.5 p-1 rounded-md bg-white/15 hover:bg-white/25 backdrop-blur-sm transition-all duration-200 flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
            title="Refresh page context"
          >
            <RefreshCw 
              className={`w-2.5 h-2.5 text-orange-600 ${isRefreshing ? 'animate-spin' : ''}`} 
            />
          </button>
        </div>
      </div>
    </div>
  );
};

export default CurrentPageIndicator;