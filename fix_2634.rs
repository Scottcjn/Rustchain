// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Counters.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract HumanVerificationCampaign is Ownable, ReentrancyGuard {
    using Counters for Counters.Counter;
    
    IERC20 public rewardToken;
    uint256 public constant POOL_SIZE = 500 * 10**18; // 500 RTC with 18 decimals
    uint256 public constant CAMPAIGN_DURATION = 14 days;
    uint256 public campaignStart;
    uint256 public campaignEnd;
    bool public campaignActive;
    
    struct Agent {
        address agentAddress;
        string agentName;
        address humanAddress;
        uint256 registrationTime;
        bool verified;
        bool claimed;
    }
    
    struct Human {
        address humanAddress;
        string humanName;
        uint256 registrationTime;
        bool verified;
        bool claimed;
    }
    
    mapping(address => Agent) public agents;
    mapping(address => Human) public humans;
    address[] public agentList;
    address[] public humanList;
    
    Counters.Counter private _agentCount;
    Counters.Counter private _humanCount;
    
    event AgentRegistered(address indexed agent, string name, address indexed human);
    event HumanRegistered(address indexed human, string name);
    event AgentVerified(address indexed agent);
    event HumanVerified(address indexed human);
    event RewardClaimed(address indexed claimant, uint256 amount);
    event CampaignStarted(uint256 startTime, uint256 endTime);
    event CampaignEnded(uint256 endTime);
    
    modifier campaignIsActive() {
        require(campaignActive, "Campaign is not active");
        require(block.timestamp >= campaignStart && block.timestamp <= campaignEnd, "Campaign is not in active period");
        _;
    }
    
    modifier notRegistered() {
        require(agents[msg.sender].agentAddress == address(0), "Already registered as agent");
        require(humans[msg.sender].humanAddress == address(0), "Already registered as human");
        _;
    }
    
    constructor(address _rewardToken) {
        require(_rewardToken != address(0), "Invalid token address");
        rewardToken = IERC20(_rewardToken);
    }
    
    function startCampaign() external onlyOwner {
        require(!campaignActive, "Campaign already active");
        campaignActive = true;
        campaignStart = block.timestamp;
        campaignEnd = block.timestamp + CAMPAIGN_DURATION;
        
        require(rewardToken.transferFrom(msg.sender, address(this), POOL_SIZE), "Token transfer failed");
        
        emit CampaignStarted(campaignStart, campaignEnd);
    }
    
    function registerAgent(string memory _agentName, address _humanAddress) external notRegistered campaignIsActive {
        require(_humanAddress != address(0), "Invalid human address");
        require(_humanAddress != msg.sender, "Agent cannot be same as human");
        
        agents[msg.sender] = Agent({
            agentAddress: msg.sender,
            agentName: _agentName,
            humanAddress: _humanAddress,
            registrationTime: block.timestamp,
            verified: false,
            claimed: false
        });
        
        agentList.push(msg.sender);
        _agentCount.increment();
        
        emit AgentRegistered(msg.sender, _agentName, _humanAddress);
    }
    
    function registerHuman(string memory _humanName) external notRegistered campaignIsActive {
        humans[msg.sender] = Human({
            humanAddress: msg.sender,
            humanName: _humanName,
            registrationTime: block.timestamp,
            verified: false,
            claimed: false
        });
        
        humanList.push(msg.sender);
        _humanCount.increment();
        
        emit HumanRegistered(msg.sender, _humanName);
    }
    
    function verifyAgent(address _agentAddress) external onlyOwner {
        require(agents[_agentAddress].agentAddress != address(0), "Agent not registered");
        require(!agents[_agentAddress].verified, "Agent already verified");
        
        agents[_agentAddress].verified = true;
        emit AgentVerified(_agentAddress);
    }
    
    function verifyHuman(address _humanAddress) external onlyOwner {
        require(humans[_humanAddress].humanAddress != address(0), "Human not registered");
        require(!humans[_humanAddress].verified, "Human already verified");
        
        humans[_humanAddress].verified = true;
        emit HumanVerified(_humanAddress);
    }
    
    function claimReward() external nonReentrant {
        require(campaignActive || block.timestamp > campaignEnd, "Campaign still active");
        
        uint256 rewardAmount = 0;
        bool isAgent = false;
        bool isHuman = false;
        
        if (agents[msg.sender].agentAddress != address(0) && agents[msg.sender].verified && !agents[msg.sender].claimed) {
            isAgent = true;
            agents[msg.sender].claimed = true;
        }
        
        if (humans[msg.sender].humanAddress != address(0) && humans[msg.sender].verified && !humans[msg.sender].claimed) {
            isHuman = true;
            humans[msg.sender].claimed = true;
        }
        
        require(isAgent || isHuman, "Not eligible for reward");
        
        uint256 totalEligible = _agentCount.current() + _humanCount.current();
        require(totalEligible > 0, "No eligible participants");
        
        rewardAmount = POOL_SIZE / totalEligible;
        require(rewardAmount > 0, "Reward too small");
        
        require(rewardToken.transfer(msg.sender, rewardAmount), "Reward transfer failed");
        
        emit RewardClaimed(msg.sender, rewardAmount);
    }
    
    function endCampaign() external onlyOwner {
        require(campaignActive, "Campaign not active");
        campaignActive = false;
        campaignEnd = block.timestamp;
        
        emit CampaignEnded(block.timestamp);
    }
    
    function getAgentCount() external view returns (uint256) {
        return _agentCount.current();
    }
    
    function getHumanCount() external view returns (uint256) {
        return _humanCount.current();
    }
    
    function getTotalParticipants() external view returns (uint256) {
        return _agentCount.current() + _humanCount.current();
    }
    
    function getHumanRatio() external view returns (uint256) {
        uint256 total = _agentCount.current() + _humanCount.current();
        if (total == 0) return 0;
        return (_humanCount.current() * 100) / total;
    }
    
    function getCampaignStatus() external view returns (bool active, uint256 start, uint256 end, uint256 remaining) {
        active = campaignActive;
        start = campaignStart;
        end = campaignEnd;
        if (block.timestamp < campaignStart) {
            remaining = campaignStart - block.timestamp;
        } else if (block.timestamp <= campaignEnd) {
            remaining = campaignEnd - block.timestamp;
        } else {
            remaining = 0;
        }
    }
}
