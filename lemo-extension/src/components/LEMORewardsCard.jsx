import React from 'react';
import { Trophy, Sparkles, ExternalLink, TrendingUp, Award } from 'lucide-react';
import { formatRewardAmount } from '../utils/rewardsStorage.js';

const LEMORewardsCard = ({ lemoBalance, totalRewards, recentRewards, walletAddress }) => {
  const sepoliaExplorerUrl = `https://sepolia.etherscan.io/token/0x14572dA77700c59D2F8D61a3c4B25744D6DcDE8D?a=${walletAddress}`;

  const formatDate = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  return (
    <div className="mt-4">
      {/* Golden Rewards Card */}
      <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-yellow-400/20 via-yellow-500/15 to-yellow-600/25 backdrop-blur-sm border border-yellow-300/30 shadow-xl">
        {/* Sparkle Effects */}
        <div className="absolute top-2 right-2 animate-pulse">
          <Sparkles className="w-6 h-6 text-yellow-400/50" />
        </div>
        <div className="absolute bottom-2 left-2 animate-pulse" style={{ animationDelay: '1s' }}>
          <Sparkles className="w-4 h-4 text-yellow-400/40" />
        </div>

        {/* Card Content */}
        <div className="relative p-4">
          {/* Header */}
          <div className="flex items-center gap-2 mb-3">
            <div className="w-8 h-8 rounded-full bg-gradient-to-r from-yellow-500 to-yellow-600 flex items-center justify-center shadow-lg">
              <Trophy className="w-4 h-4 text-white" />
            </div>
            <div>
              <h3 className="text-base font-bold text-yellow-800">LEMO Rewards</h3>
              <p className="text-xs text-yellow-700">Your earnings from feedback</p>
            </div>
          </div>

          {/* Main Balance */}
          <div className="mb-4 p-4 rounded-lg bg-gradient-to-r from-yellow-500/20 to-yellow-600/20 border border-yellow-400/30">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs text-yellow-700 mb-1">Current Balance</div>
                <div className="text-2xl font-bold text-yellow-900">
                  {formatRewardAmount(lemoBalance)}
                  <span className="text-sm font-normal ml-1 text-yellow-700">LEMO</span>
                </div>
              </div>
              <Award className="w-12 h-12 text-yellow-500/30" />
            </div>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-2 gap-2 mb-4">
            <div className="p-3 rounded-lg bg-white/15 backdrop-blur-sm">
              <div className="flex items-center gap-1 mb-1">
                <TrendingUp className="w-3 h-3 text-yellow-600" />
                <span className="text-xs text-yellow-700">Total Earned</span>
              </div>
              <div className="text-lg font-bold text-yellow-900">
                {formatRewardAmount(totalRewards)}
              </div>
            </div>
            <div className="p-3 rounded-lg bg-white/15 backdrop-blur-sm">
              <div className="flex items-center gap-1 mb-1">
                <Trophy className="w-3 h-3 text-yellow-600" />
                <span className="text-xs text-yellow-700">Feedbacks</span>
              </div>
              <div className="text-lg font-bold text-yellow-900">
                {recentRewards?.length || 0}
              </div>
            </div>
          </div>

          {/* Recent Rewards */}
          {recentRewards && recentRewards.length > 0 && (
            <div className="mb-4">
              <div className="text-xs font-semibold text-yellow-800 mb-2 flex items-center gap-1">
                <Sparkles className="w-3 h-3" />
                Recent Rewards
              </div>
              <div className="space-y-1.5">
                {recentRewards.slice(0, 5).map((reward, index) => (
                  <div
                    key={reward.id || index}
                    className="flex items-center justify-between p-2 rounded-lg bg-white/10 hover:bg-white/15 transition-all duration-200"
                  >
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-yellow-500/20 flex items-center justify-center">
                        <Trophy className="w-3 h-3 text-yellow-600" />
                      </div>
                      <div>
                        <div className="text-xs font-semibold text-yellow-900">
                          +{formatRewardAmount(reward.amount)} LEMO
                        </div>
                        <div className="text-[10px] text-yellow-700">
                          Receipt #{reward.receiptId}
                        </div>
                      </div>
                    </div>
                    <div className="text-[10px] text-yellow-700">
                      {formatDate(reward.timestamp)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* View on Explorer Button */}
          <a
            href={sepoliaExplorerUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="w-full bg-gradient-to-r from-yellow-500 to-yellow-600 hover:from-yellow-600 hover:to-yellow-700 text-white font-bold py-2.5 px-4 rounded-lg transition-all duration-200 flex items-center justify-center gap-2 shadow-md hover:shadow-lg transform hover:scale-105"
          >
            <ExternalLink className="w-4 h-4" />
            <span className="text-sm">View on Etherscan</span>
          </a>
        </div>

        {/* Glow Effect */}
        <div className="absolute -top-20 -right-20 w-40 h-40 bg-yellow-400/10 rounded-full blur-3xl"></div>
        <div className="absolute -bottom-20 -left-20 w-40 h-40 bg-yellow-500/10 rounded-full blur-3xl"></div>
      </div>
    </div>
  );
};

export default LEMORewardsCard;











