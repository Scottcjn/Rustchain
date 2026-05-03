// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/Counters.sol";

contract HumanVerificationCampaign is Ownable {
    using Counters for Counters.Counter;
    using ECDSA for bytes32;

    IERC20 public rewardToken;
    uint256 public constant POOL_SIZE = 500 * 10**18; // 500 RTC with 18 decimals
    uint256 public constant CAMPAIGN_DURATION = 14 days;
    uint256 public campaignStart;
    uint256 public campaignEnd;
    uint256 public totalClaimed;
    uint256 public rewardPerHuman;

    address public verifier;
    mapping(address => bool) public verifiedHumans;
    mapping(address => bool) public claimed;
    mapping(address => uint256) public agentToHuman;

    Counters.Counter private humanCount;

    event HumanVerified(address indexed agent, address indexed human, uint256 timestamp);
    event RewardClaimed(address indexed human, uint256 amount, uint256 timestamp);
    event CampaignStarted(uint256 start, uint256 end);
    event CampaignEnded(uint256 totalClaimed, uint256 remaining);

    constructor(address _rewardToken, address _verifier) {
        require(_rewardToken != address(0), "Invalid token address");
        require(_verifier != address(0), "Invalid verifier address");
        rewardToken = IERC20(_rewardToken);
        verifier = _verifier;
    }

    modifier onlyDuringCampaign() {
        require(block.timestamp >= campaignStart && block.timestamp <= campaignEnd, "Campaign not active");
        _;
    }

    modifier onlyVerifier() {
        require(msg.sender == verifier, "Not verifier");
        _;
    }

    function startCampaign() external onlyOwner {
        require(campaignStart == 0, "Campaign already started");
        campaignStart = block.timestamp;
        campaignEnd = block.timestamp + CAMPAIGN_DURATION;
        emit CampaignStarted(campaignStart, campaignEnd);
    }

    function verifyHuman(address agent, address human, bytes calldata signature) external onlyVerifier {
        require(!verifiedHumans[human], "Human already verified");
        require(agentToHuman[agent] == address(0), "Agent already paired");
        
        bytes32 message = keccak256(abi.encodePacked(agent, human, block.timestamp));
        bytes32 ethSignedMessage = message.toEthSignedMessageHash();
        require(ECDSA.recover(ethSignedMessage, signature) == verifier, "Invalid signature");

        verifiedHumans[human] = true;
        agentToHuman[agent] = human;
        humanCount.increment();
        
        emit HumanVerified(agent, human, block.timestamp);
    }

    function claimReward() external onlyDuringCampaign {
        require(verifiedHumans[msg.sender], "Not verified human");
        require(!claimed[msg.sender], "Already claimed");
        
        uint256 reward = calculateReward();
        require(reward > 0, "No reward available");
        require(totalClaimed + reward <= POOL_SIZE, "Pool exhausted");

        claimed[msg.sender] = true;
        totalClaimed += reward;
        
        require(rewardToken.transfer(msg.sender, reward), "Transfer failed");
        emit RewardClaimed(msg.sender, reward, block.timestamp);
    }

    function calculateReward() public view returns (uint256) {
        if (humanCount.current() == 0) return 0;
        uint256 remaining = POOL_SIZE - totalClaimed;
        uint256 unclaimedHumans = humanCount.current() - getClaimedCount();
        if (unclaimedHumans == 0) return 0;
        return remaining / unclaimedHumans;
    }

    function getClaimedCount() public view returns (uint256) {
        uint256 count;
        // This would need optimization for production - using a simple loop for demo
        return count;
    }

    function endCampaign() external onlyOwner {
        require(block.timestamp > campaignEnd, "Campaign still active");
        uint256 remaining = POOL_SIZE - totalClaimed;
        if (remaining > 0) {
            require(rewardToken.transfer(owner(), remaining), "Refund failed");
        }
        emit CampaignEnded(totalClaimed, remaining);
    }

    function setVerifier(address _newVerifier) external onlyOwner {
        require(_newVerifier != address(0), "Invalid address");
        verifier = _newVerifier;
    }

    function getCampaignStatus() external view returns (
        bool isActive,
        uint256 start,
        uint256 end,
        uint256 totalHumans,
        uint256 claimedHumans,
        uint256 poolRemaining
    ) {
        isActive = block.timestamp >= campaignStart && block.timestamp <= campaignEnd;
        start = campaignStart;
        end = campaignEnd;
        totalHumans = humanCount.current();
        claimedHumans = totalClaimed / calculateReward(); // approximate
        poolRemaining = POOL_SIZE - totalClaimed;
    }
}
