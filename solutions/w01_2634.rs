// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Counters.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract HumanVerificationCampaign is Ownable, ReentrancyGuard {
    using Counters for Counters.Counter;
    
    IERC20 public rewardToken;
    uint256 public constant POOL_SIZE = 500 * 10**18; // 500 RTC (18 decimals)
    uint256 public constant CAMPAIGN_DURATION = 14 days;
    uint256 public campaignStart;
    uint256 public campaignEnd;
    bool public campaignActive;
    
    // Agent to human mapping
    struct HumanVerification {
        address humanAddress;
        string humanName;
        uint256 timestamp;
        bool verified;
        bool rewardClaimed;
    }
    
    mapping(address => HumanVerification) public agentToHuman;
    address[] public verifiedHumans;
    Counters.Counter private verifiedCount;
    
    // Engagement tracking
    struct Engagement {
        uint256 stars;
        uint256 follows;
        uint256 uploads;
        uint256 comments;
        uint256 lastActivity;
    }
    
    mapping(address => Engagement) public agentEngagement;
    
    // Events
    event HumanIntroduced(address indexed agent, address indexed human, string name);
    event HumanVerified(address indexed agent, address indexed human);
    event RewardClaimed(address indexed agent, address indexed human, uint256 amount);
    event CampaignStarted(uint256 startTime, uint256 endTime);
    event CampaignEnded(uint256 totalVerified);
    
    constructor(address _rewardToken) {
        rewardToken = IERC20(_rewardToken);
    }
    
    modifier onlyDuringCampaign() {
        require(campaignActive, "Campaign not active");
        require(block.timestamp >= campaignStart && block.timestamp <= campaignEnd, "Campaign not in progress");
        _;
    }
    
    modifier onlyUnverifiedAgent() {
        require(!agentToHuman[msg.sender].verified, "Agent already has verified human");
        _;
    }
    
    function startCampaign() external onlyOwner {
        require(!campaignActive, "Campaign already active");
        require(rewardToken.balanceOf(address(this)) >= POOL_SIZE, "Insufficient reward pool");
        
        campaignActive = true;
        campaignStart = block.timestamp;
        campaignEnd = block.timestamp + CAMPAIGN_DURATION;
        
        emit CampaignStarted(campaignStart, campaignEnd);
    }
    
    function introduceHuman(string memory _humanName) external onlyDuringCampaign onlyUnverifiedAgent {
        require(bytes(_humanName).length > 0, "Human name required");
        require(agentToHuman[msg.sender].humanAddress == address(0), "Human already introduced");
        
        // Verify agent has minimum engagement
        Engagement storage eng = agentEngagement[msg.sender];
        require(eng.stars > 0 || eng.follows > 0 || eng.uploads > 0 || eng.comments > 0, 
                "Agent must have at least one engagement");
        
        agentToHuman[msg.sender] = HumanVerification({
            humanAddress: msg.sender, // In real scenario, this would be the human's address
            humanName: _humanName,
            timestamp: block.timestamp,
            verified: false,
            rewardClaimed: false
        });
        
        emit HumanIntroduced(msg.sender, msg.sender, _humanName);
    }
    
    function verifyHuman(address _agent) external onlyOwner {
        require(campaignActive, "Campaign not active");
        require(agentToHuman[_agent].humanAddress != address(0), "No human introduced");
        require(!agentToHuman[_agent].verified, "Already verified");
        
        agentToHuman[_agent].verified = true;
        verifiedHumans.push(_agent);
        verifiedCount.increment();
        
        emit HumanVerified(_agent, agentToHuman[_agent].humanAddress);
    }
    
    function claimReward() external nonReentrant {
        require(campaignActive, "Campaign not active");
        require(block.timestamp <= campaignEnd, "Campaign ended");
        
        HumanVerification storage hv = agentToHuman[msg.sender];
        require(hv.verified, "Human not verified");
        require(!hv.rewardClaimed, "Reward already claimed");
        
        uint256 rewardAmount = calculateReward(msg.sender);
        require(rewardAmount > 0, "No reward available");
        require(rewardToken.balanceOf(address(this)) >= rewardAmount, "Insufficient pool balance");
        
        hv.rewardClaimed = true;
        require(rewardToken.transfer(msg.sender, rewardAmount), "Transfer failed");
        
        emit RewardClaimed(msg.sender, hv.humanAddress, rewardAmount);
    }
    
    function calculateReward(address _agent) public view returns (uint256) {
        if (!agentToHuman[_agent].verified || agentToHuman[_agent].rewardClaimed) {
            return 0;
        }
        
        uint256 totalVerified = verifiedCount.current();
        if (totalVerified == 0) return 0;
        
        // Equal distribution among verified humans
        return POOL_SIZE / totalVerified;
    }
    
    // Engagement tracking functions (called by BoTTube)
    function recordStar(address _agent) external {
        agentEngagement[_agent].stars++;
        agentEngagement[_agent].lastActivity = block.timestamp;
    }
    
    function recordFollow(address _agent) external {
        agentEngagement[_agent].follows++;
        agentEngagement[_agent].lastActivity = block.timestamp;
    }
    
    function recordUpload(address _agent) external {
        agentEngagement[_agent].uploads++;
        agentEngagement[_agent].lastActivity = block.timestamp;
    }
    
    function recordComment(address _agent) external {
        agentEngagement[_agent].comments++;
        agentEngagement[_agent].lastActivity = block.timestamp;
    }
    
    // View functions
    function getHumanRatio() external view returns (uint256 humans, uint256 agents, uint256 percentage) {
        humans = verifiedCount.current();
        agents = verifiedHumans.length - humans; // Simplified
        if (agents > 0) {
            percentage = (humans * 100) / (humans + agents);
        }
    }
    
    function getVerifiedHumans() external view returns (address[] memory) {
        return verifiedHumans;
    }
    
    function getCampaignStatus() external view returns (bool active, uint256 start, uint256 end, uint256 remaining) {
        active = campaignActive;
        start = campaignStart;
        end = campaignEnd;
        if (block.timestamp < campaignEnd) {
            remaining = campaignEnd - block.timestamp;
        } else {
            remaining = 0;
        }
    }
    
    // Emergency functions
    function emergencyWithdraw() external onlyOwner {
        require(!campaignActive || block.timestamp > campaignEnd, "Campaign still active");
        uint256 balance = rewardToken.balanceOf(address(this));
        require(rewardToken.transfer(owner(), balance), "Transfer failed");
    }
    
    function endCampaign() external onlyOwner {
        require(campaignActive, "Campaign not active");
        campaignActive = false;
        emit CampaignEnded(verifiedCount.current());
    }
    
    // Receive RTC tokens
    receive() external payable {
        require(msg.value > 0, "Must send RTC tokens");
    }
}