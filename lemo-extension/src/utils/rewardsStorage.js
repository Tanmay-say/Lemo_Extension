/**
 * Rewards storage utilities for LEMO Extension
 * FIX C5: This file was empty, causing a build crash in LEMORewardsCard.jsx
 */

/**
 * Format a LEMO token amount for display
 * @param {number|string} amount - The amount to format
 * @returns {string} Formatted amount string
 */
export const formatRewardAmount = (amount) => {
    const num = parseFloat(amount) || 0;
    if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(2)}M`;
    if (num >= 1_000) return `${(num / 1_000).toFixed(2)}K`;
    return num.toFixed(2);
};

/**
 * Save rewards data to local storage
 * @param {string} walletAddress - User's wallet address
 * @param {object} rewardsData - { lemoBalance, totalRewards, recentRewards }
 */
export const saveRewardsData = async (walletAddress, rewardsData) => {
    try {
        await chrome.storage.local.set({
            [`rewards_${walletAddress.toLowerCase()}`]: {
                ...rewardsData,
                updatedAt: Date.now(),
            },
        });
    } catch (error) {
        console.error('Error saving rewards data:', error);
    }
};

/**
 * Load rewards data from local storage
 * @param {string} walletAddress - User's wallet address
 * @returns {Promise<object|null>} Rewards data or null
 */
export const loadRewardsData = async (walletAddress) => {
    try {
        const result = await chrome.storage.local.get([`rewards_${walletAddress.toLowerCase()}`]);
        return result[`rewards_${walletAddress.toLowerCase()}`] || null;
    } catch (error) {
        console.error('Error loading rewards data:', error);
        return null;
    }
};
