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
    uint256 public maxHumans;
    
    address public verifier;
    mapping(address => bool) public verifiedHumans;
    mapping(address => bool) public hasClaimed;
    mapping(address => uint256) public agentToHuman;
    
    Counters.Counter private humanCount;
    
    event HumanVerified(address indexed agent, address indexed human, uint256 timestamp);
    event RewardClaimed(address indexed human, uint256 amount, uint256 timestamp);
    event CampaignStarted(uint256 start, uint256 end);
    event CampaignExtended(uint256 newEnd);

    modifier onlyDuringCampaign() {
        require(block.timestamp >= campaignStart && block.timestamp <= campaignEnd, "Campaign not active");
        _;
    }

    modifier onlyVerifier() {
        require(msg.sender == verifier, "Not authorized verifier");
        _;
    }

    constructor(address _rewardToken, address _verifier) {
        require(_rewardToken != address(0), "Invalid token address");
        require(_verifier != address(0), "Invalid verifier address");
        
        rewardToken = IERC20(_rewardToken);
        verifier = _verifier;
        campaignStart = block.timestamp;
        campaignEnd = block.timestamp + CAMPAIGN_DURATION;
        maxHumans = 63; // Target to match human/agent ratio
        
        emit CampaignStarted(campaignStart, campaignEnd);
    }

    function startCampaign() external onlyOwner {
        require(campaignStart == 0, "Campaign already started");
        campaignStart = block.timestamp;
        campaignEnd = block.timestamp + CAMPAIGN_DURATION;
        emit CampaignStarted(campaignStart, campaignEnd);
    }

    function extendCampaign(uint256 _extensionDays) external onlyOwner {
        require(_extensionDays > 0, "Extension must be positive");
        campaignEnd += _extensionDays * 1 days;
        emit CampaignExtended(campaignEnd);
    }

    function verifyHuman(address _agent, address _human, bytes calldata _signature) external onlyVerifier onlyDuringCampaign {
        require(!verifiedHumans[_human], "Human already verified");
        require(agentToHuman[_agent] == address(0), "Agent already has human");
        require(humanCount.current() < maxHumans, "Max humans reached");
        
        bytes32 message = keccak256(abi.encodePacked(_agent, _human, block.timestamp));
        bytes32 ethSignedMessage = message.toEthSignedMessageHash();
        require(ethSignedMessage.recover(_signature) == verifier, "Invalid signature");
        
        verifiedHumans[_human] = true;
        agentToHuman[_agent] = _human;
        humanCount.increment();
        
        emit HumanVerified(_agent, _human, block.timestamp);
    }

    function claimReward() external onlyDuringCampaign {
        require(verifiedHumans[msg.sender], "Not a verified human");
        require(!hasClaimed[msg.sender], "Already claimed");
        
        uint256 rewardAmount = calculateReward();
        require(totalClaimed + rewardAmount <= POOL_SIZE, "Pool exhausted");
        
        hasClaimed[msg.sender] = true;
        totalClaimed += rewardAmount;
        
        require(rewardToken.transfer(msg.sender, rewardAmount), "Transfer failed");
        
        emit RewardClaimed(msg.sender, rewardAmount, block.timestamp);
    }

    function calculateReward() public view returns (uint256) {
        uint256 verifiedCount = humanCount.current();
        if (verifiedCount == 0) return 0;
        return POOL_SIZE / verifiedCount;
    }

    function getRemainingPool() external view returns (uint256) {
        return POOL_SIZE - totalClaimed;
    }

    function getHumanCount() external view returns (uint256) {
        return humanCount.current();
    }

    function getAgentHuman(address _agent) external view returns (address) {
        return agentToHuman[_agent];
    }

    function isVerifiedHuman(address _human) external view returns (bool) {
        return verifiedHumans[_human];
    }

    function setVerifier(address _newVerifier) external onlyOwner {
        require(_newVerifier != address(0), "Invalid verifier address");
        verifier = _newVerifier;
    }

    function setMaxHumans(uint256 _newMax) external onlyOwner {
        require(_newMax > 0 && _newMax <= 207, "Invalid max humans");
        maxHumans = _newMax;
    }

    function withdrawRemainingPool() external onlyOwner {
        require(block.timestamp > campaignEnd, "Campaign still active");
        uint256 remaining = POOL_SIZE - totalClaimed;
        require(remaining > 0, "Pool already empty");
        require(rewardToken.transfer(owner(), remaining), "Transfer failed");
    }
}
