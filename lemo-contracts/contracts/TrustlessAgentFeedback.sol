// SPDX-License-Identifier: MIT
pragma solidity ^0.8.18;

/**
 * @title TrustlessAgentFeedback
 * @notice Accepts user feedback (stored on IPFS/Lighthouse) and automatically distributes LEMO token rewards
 * @dev IMPORTANT: This contract must be funded with LEMO tokens before users can submit feedback.
 *      The reward mechanism is automatic (no manual validation for now).
 *      One feedback per receipt to prevent spam.
 *      
 *      SECURITY FIX: Added buyer verification to prevent anyone from draining rewards
 */

// Minimal IERC20 interface
interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

// Interface for LighthouseReceipt to verify receipt ownership
interface ILighthouseReceipt {
    function getReceipt(uint256 receiptId) external view returns (
        uint256 id,
        address buyer,
        string memory productId,
        string memory cid,
        address paymentToken,
        uint256 amountPaid,
        string memory currency,
        uint256 timestamp
    );
}

contract TrustlessAgentFeedback {
    
    struct Feedback {
        uint256 receiptId;
        address user;
        string feedbackCid;    // IPFS/Lighthouse CID of feedback JSON
        uint256 timestamp;
        bool rewarded;
    }
    
    // State variables
    address public owner;
    uint256 public feedbackCount;
    address public lighthouseReceiptContract;
    
    // LEMO Token Configuration
    // NOTE: Replace this address if deploying to a different network or if LEMO address changes
    address public constant LEMO_TOKEN_ADDRESS = 0x14572dA77700c59D2F8D61a3c4B25744D6DcDE8D;
    
    // Reward amount: 1,000,000 LEMO tokens (assumes 18 decimals)
    // IMPORTANT: If LEMO has different decimals, adjust this value accordingly
    uint256 public constant REWARD_AMOUNT = 1_000_000 * 10**18;
    
    // Mappings
    mapping(uint256 => Feedback) public feedbacks;
    mapping(uint256 => bool) public receiptFeedbackExists;  // One feedback per receipt
    
    // Reentrancy guard
    uint256 private constant NOT_ENTERED = 1;
    uint256 private constant ENTERED = 2;
    uint256 private _status;
    
    // Events
    event FeedbackSubmitted(
        uint256 indexed feedbackId,
        uint256 indexed receiptId,
        address indexed user,
        string feedbackCid,
        uint256 reward,
        uint256 timestamp
    );
    
    event ContractFunded(address indexed funder, uint256 amount);
    event LEMOWithdrawn(address indexed to, uint256 amount);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event LighthouseReceiptContractUpdated(address indexed newContract);
    
    // Modifiers
    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this function");
        _;
    }
    
    modifier nonReentrant() {
        require(_status != ENTERED, "ReentrancyGuard: reentrant call");
        _status = ENTERED;
        _;
        _status = NOT_ENTERED;
    }
    
    constructor(address _lighthouseReceiptContract) {
        require(_lighthouseReceiptContract != address(0), "Invalid LighthouseReceipt address");
        owner = msg.sender;
        feedbackCount = 0;
        _status = NOT_ENTERED;
        lighthouseReceiptContract = _lighthouseReceiptContract;
    }
    
    /**
     * @notice Submits feedback for a receipt and automatically transfers LEMO reward to the user
     * @dev SECURITY FIX: Verifies that msg.sender is the buyer of the receipt
     *      The feedback JSON must be uploaded to Lighthouse/IPFS before calling this function.
     *      One feedback per receipt to prevent duplicate rewards.
     * @param receiptId The ID of the receipt this feedback is for
     * @param feedbackCid IPFS/Lighthouse CID of the feedback JSON (includes rating, comments, etc.)
     * @return feedbackId The unique ID of the submitted feedback
     */
    function submitFeedback(
        uint256 receiptId,
        string memory feedbackCid
    ) external nonReentrant returns (uint256 feedbackId) {
        require(bytes(feedbackCid).length > 0, "Feedback CID cannot be empty");
        require(!receiptFeedbackExists[receiptId], "Feedback already submitted for this receipt");
        
        // SECURITY FIX: Verify that msg.sender is the buyer of this receipt
        (
            ,
            address buyer,
            ,
            ,
            ,
            ,
            ,
        ) = ILighthouseReceipt(lighthouseReceiptContract).getReceipt(receiptId);
        
        require(msg.sender == buyer, "Only the buyer of this receipt can submit feedback");
        
        // Check if contract has sufficient LEMO tokens for reward
        IERC20 lemoToken = IERC20(LEMO_TOKEN_ADDRESS);
        uint256 contractBalance = lemoToken.balanceOf(address(this));
        require(contractBalance >= REWARD_AMOUNT, "Contract has insufficient LEMO tokens for reward");
        
        feedbackId = feedbackCount;
        feedbackCount++;
        
        // Store feedback
        feedbacks[feedbackId] = Feedback({
            receiptId: receiptId,
            user: msg.sender,
            feedbackCid: feedbackCid,
            timestamp: block.timestamp,
            rewarded: true
        });
        
        receiptFeedbackExists[receiptId] = true;
        
        // Transfer LEMO reward to user
        bool transferSuccess = lemoToken.transfer(msg.sender, REWARD_AMOUNT);
        require(transferSuccess, "LEMO reward transfer failed");
        
        emit FeedbackSubmitted(
            feedbackId,
            receiptId,
            msg.sender,
            feedbackCid,
            REWARD_AMOUNT,
            block.timestamp
        );
        
        return feedbackId;
    }
    
    /**
     * @notice Retrieves feedback by ID
     * @param feedbackId The ID of the feedback to retrieve
     * @return Feedback struct containing all feedback data
     */
    function getFeedback(uint256 feedbackId) external view returns (Feedback memory) {
        require(feedbackId < feedbackCount, "Feedback does not exist");
        return feedbacks[feedbackId];
    }
    
    /**
     * @notice Checks if a receipt already has feedback
     * @param receiptId The receipt ID to check
     * @return bool indicating if feedback exists for this receipt
     */
    function hasFeedback(uint256 receiptId) external view returns (bool) {
        return receiptFeedbackExists[receiptId];
    }
    
    /**
     * @notice Returns the contract's current LEMO balance
     * @return Current LEMO token balance
     */
    function getLEMOBalance() external view returns (uint256) {
        IERC20 lemoToken = IERC20(LEMO_TOKEN_ADDRESS);
        return lemoToken.balanceOf(address(this));
    }
    
    /**
     * @notice Owner can fund the contract with LEMO tokens
     * @dev The owner must first approve this contract to spend their LEMO tokens
     * @param amount Amount of LEMO tokens to transfer to the contract
     */
    function fundContract(uint256 amount) external onlyOwner {
        require(amount > 0, "Amount must be greater than 0");
        
        IERC20 lemoToken = IERC20(LEMO_TOKEN_ADDRESS);
        bool transferSuccess = lemoToken.transferFrom(msg.sender, address(this), amount);
        require(transferSuccess, "LEMO transfer failed");
        
        emit ContractFunded(msg.sender, amount);
    }
    
    /**
     * @notice Emergency withdrawal of LEMO tokens by owner
     * @dev Use this to withdraw remaining LEMO tokens if needed
     */
    function withdrawLEMO() external onlyOwner {
        IERC20 lemoToken = IERC20(LEMO_TOKEN_ADDRESS);
        uint256 balance = lemoToken.balanceOf(address(this));
        require(balance > 0, "No LEMO tokens to withdraw");
        
        bool transferSuccess = lemoToken.transfer(owner, balance);
        require(transferSuccess, "LEMO withdrawal failed");
        
        emit LEMOWithdrawn(owner, balance);
    }
    
    /**
     * @notice Updates the LighthouseReceipt contract address
     * @param newContract Address of the new LighthouseReceipt contract
     */
    function updateLighthouseReceiptContract(address newContract) external onlyOwner {
        require(newContract != address(0), "Invalid contract address");
        lighthouseReceiptContract = newContract;
        emit LighthouseReceiptContractUpdated(newContract);
    }
    
    /**
     * @notice Transfers ownership of the contract
     * @param newOwner Address of the new owner
     */
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "New owner cannot be zero address");
        address previousOwner = owner;
        owner = newOwner;
        emit OwnershipTransferred(previousOwner, newOwner);
    }
}
