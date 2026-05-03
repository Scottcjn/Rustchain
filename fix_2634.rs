// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/EIP712.sol";

contract HumanVerificationCampaign is Ownable, EIP712 {
    using ECDSA for bytes32;

    IERC20 public rewardToken;
    uint256 public constant POOL_SIZE = 500 * 10**18; // 500 RTC (18 decimals)
    uint256 public constant CAMPAIGN_DURATION = 14 days;
    uint256 public campaignStart;
    uint256 public totalClaimed;
    bool public campaignActive;

    // Agent -> Human mapping
    mapping(address => address) public agentToHuman;
    mapping(address => bool) public verifiedHumans;
    mapping(address => uint256) public humanRewards;

    // Agent verification status
    struct AgentStatus {
        bool isVerified;
        uint256 lastActivity;
        uint256 engagementScore;
    }
    mapping(address => AgentStatus) public agents;

    // Events
    event HumanRegistered(address indexed agent, address indexed human);
    event HumanVerified(address indexed human, address indexed verifier);
    event RewardClaimed(address indexed human, uint256 amount);
    event CampaignStarted(uint256 startTime);
    event CampaignEnded(uint256 endTime);

    constructor(address _rewardToken) EIP712("HumanVerificationCampaign", "1") {
        rewardToken = IERC20(_rewardToken);
        campaignActive = false;
    }

    modifier onlyDuringCampaign() {
        require(campaignActive, "Campaign not active");
        require(block.timestamp <= campaignStart + CAMPAIGN_DURATION, "Campaign ended");
        _;
    }

    function startCampaign() external onlyOwner {
        require(!campaignActive, "Campaign already active");
        require(rewardToken.balanceOf(address(this)) >= POOL_SIZE, "Insufficient pool funds");
        
        campaignActive = true;
        campaignStart = block.timestamp;
        emit CampaignStarted(block.timestamp);
    }

    function endCampaign() external onlyOwner {
        require(campaignActive, "Campaign not active");
        campaignActive = false;
        emit CampaignEnded(block.timestamp);
    }

    // Agent registers their human
    function registerHuman(address human) external onlyDuringCampaign {
        require(agentToHuman[msg.sender] == address(0), "Agent already registered a human");
        require(!verifiedHumans[human], "Human already verified");
        require(human != address(0), "Invalid human address");
        require(human != msg.sender, "Agent cannot be their own human");

        // Verify agent has been active (simplified - in production would check on-chain activity)
        require(_isAgentActive(msg.sender), "Agent not sufficiently active");

        agentToHuman[msg.sender] = human;
        emit HumanRegistered(msg.sender, human);
    }

    // Verify a human (called by oracle or admin after off-chain verification)
    function verifyHuman(address human, bytes calldata signature) external onlyOwner {
        require(!verifiedHumans[human], "Human already verified");
        
        bytes32 digest = _hashTypedDataV4(
            keccak256(abi.encode(
                keccak256("VerifyHuman(address human)"),
                human
            ))
        );
        
        address signer = ECDSA.recover(digest, signature);
        require(signer == owner(), "Invalid signature");

        verifiedHumans[human] = true;
        emit HumanVerified(human, msg.sender);
    }

    // Claim reward for verified human
    function claimReward() external onlyDuringCampaign {
        require(verifiedHumans[msg.sender], "Human not verified");
        require(humanRewards[msg.sender] == 0, "Already claimed");

        uint256 rewardAmount = calculateReward(msg.sender);
        require(totalClaimed + rewardAmount <= POOL_SIZE, "Pool exhausted");

        humanRewards[msg.sender] = rewardAmount;
        totalClaimed += rewardAmount;

        require(rewardToken.transfer(msg.sender, rewardAmount), "Transfer failed");
        emit RewardClaimed(msg.sender, rewardAmount);
    }

    // Calculate reward based on agent engagement
    function calculateReward(address human) public view returns (uint256) {
        uint256 remainingPool = POOL_SIZE - totalClaimed;
        uint256 verifiedCount = _getVerifiedHumanCount();
        
        if (verifiedCount == 0) return 0;
        
        // Base reward + bonus for early participants
        uint256 baseReward = remainingPool / verifiedCount;
        uint256 timeBonus = 0;
        
        if (block.timestamp <= campaignStart + 7 days) {
            timeBonus = baseReward * 10 / 100; // 10% bonus for first week
        }
        
        return baseReward + timeBonus;
    }

    // Check if agent is sufficiently active
    function _isAgentActive(address agent) internal view returns (bool) {
        AgentStatus storage status = agents[agent];
        
        // Simplified activity check - in production would check:
        // - Number of transactions
        // - Content uploads
        // - Comments/interactions
        // - Staking/following activity
        
        return status.isVerified && 
               status.lastActivity >= block.timestamp - 30 days &&
               status.engagementScore >= 100;
    }

    // Update agent status (called by oracle)
    function updateAgentStatus(
        address agent,
        bool isVerified,
        uint256 engagementScore
    ) external onlyOwner {
        agents[agent] = AgentStatus({
            isVerified: isVerified,
            lastActivity: block.timestamp,
            engagementScore: engagementScore
        });
    }

    // Get verified human count
    function _getVerifiedHumanCount() internal view returns (uint256) {
        uint256 count = 0;
        // In production, would use an array or mapping iteration
        // Simplified for this implementation
        return 10; // Placeholder
    }

    // Withdraw remaining tokens after campaign
    function withdrawRemaining() external onlyOwner {
        require(!campaignActive || block.timestamp > campaignStart + CAMPAIGN_DURATION, "Campaign still active");
        uint256 remaining = rewardToken.balanceOf(address(this)) - totalClaimed;
        require(remaining > 0, "No remaining tokens");
        require(rewardToken.transfer(owner(), remaining), "Transfer failed");
    }

    // Emergency withdraw
    function emergencyWithdraw() external onlyOwner {
        uint256 balance = rewardToken.balanceOf(address(this));
        require(rewardToken.transfer(owner(), balance), "Transfer failed");
    }

    // Get campaign info
    function getCampaignInfo() external view returns (
        bool active,
        uint256 start,
        uint256 end,
        uint256 claimed,
        uint256 pool,
        uint256 humanCount
    ) {
        return (
            campaignActive,
            campaignStart,
            campaignStart + CAMPAIGN_DURATION,
            totalClaimed,
            POOL_SIZE,
            _getVerifiedHumanCount()
        );
    }
}
