// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract HumanVerificationCampaign is Ownable, ReentrancyGuard {
    using ECDSA for bytes32;

    IERC20 public rewardToken;
    uint256 public constant POOL_SIZE = 500 * 10**18; // 500 RTC with 18 decimals
    uint256 public constant CAMPAIGN_DURATION = 14 days;
    uint256 public campaignStart;
    uint256 public totalClaimed;
    uint256 public maxRewardPerHuman = 10 * 10**18; // 10 RTC per human

    mapping(address => bool) public verifiedHumans;
    mapping(address => uint256) public claimedAmount;
    mapping(address => bool) public agentsRegistered;

    address public verifier;
    uint256 public humanCount;
    uint256 public agentCount;

    event HumanVerified(address indexed human, address indexed agent);
    event RewardClaimed(address indexed human, uint256 amount);
    event AgentRegistered(address indexed agent, address indexed human);

    modifier campaignActive() {
        require(block.timestamp >= campaignStart && block.timestamp <= campaignStart + CAMPAIGN_DURATION, "Campaign not active");
        _;
    }

    modifier onlyVerifier() {
        require(msg.sender == verifier, "Not verifier");
        _;
    }

    constructor(address _rewardToken, address _verifier) {
        rewardToken = IERC20(_rewardToken);
        verifier = _verifier;
        campaignStart = block.timestamp;
    }

    function registerAgent(address agent) external {
        require(!agentsRegistered[agent], "Agent already registered");
        agentsRegistered[agent] = true;
        agentCount++;
        emit AgentRegistered(agent, msg.sender);
    }

    function verifyHuman(address human, bytes calldata signature) external onlyVerifier campaignActive {
        require(!verifiedHumans[human], "Human already verified");
        
        bytes32 message = keccak256(abi.encodePacked(human, "verified-human"));
        bytes32 ethSignedMessage = message.toEthSignedMessageHash();
        require(ethSignedMessage.recover(signature) == verifier, "Invalid signature");

        verifiedHumans[human] = true;
        humanCount++;
        emit HumanVerified(human, msg.sender);
    }

    function claimReward() external nonReentrant campaignActive {
        require(verifiedHumans[msg.sender], "Human not verified");
        require(claimedAmount[msg.sender] == 0, "Already claimed");
        require(totalClaimed + maxRewardPerHuman <= POOL_SIZE, "Pool exhausted");

        claimedAmount[msg.sender] = maxRewardPerHuman;
        totalClaimed += maxRewardPerHuman;

        require(rewardToken.transfer(msg.sender, maxRewardPerHuman), "Transfer failed");
        emit RewardClaimed(msg.sender, maxRewardPerHuman);
    }

    function getCampaignStats() external view returns (uint256 humans, uint256 agents, uint256 claimed, uint256 remaining) {
        return (humanCount, agentCount, totalClaimed, POOL_SIZE - totalClaimed);
    }

    function withdrawRemaining() external onlyOwner {
        require(block.timestamp > campaignStart + CAMPAIGN_DURATION, "Campaign still active");
        uint256 remaining = POOL_SIZE - totalClaimed;
        require(rewardToken.transfer(owner(), remaining), "Transfer failed");
    }

    function setVerifier(address newVerifier) external onlyOwner {
        verifier = newVerifier;
    }

    function setMaxReward(uint256 newMax) external onlyOwner {
        maxRewardPerHuman = newMax;
    }
}
