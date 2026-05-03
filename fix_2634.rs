// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/Counters.sol";

contract HumanVerificationCampaign is Ownable, ReentrancyGuard {
    using Counters for Counters.Counter;
    using ECDSA for bytes32;

    IERC20 public rewardToken;
    uint256 public constant POOL_SIZE = 500 * 10**18; // 500 RTC (18 decimals)
    uint256 public constant CAMPAIGN_DURATION = 14 days;
    uint256 public constant MIN_HUMAN_RATIO = 23; // 23% target

    address public verifier;
    uint256 public campaignStart;
    uint256 public campaignEnd;
    bool public campaignActive;
    uint256 public totalRewardsClaimed;
    uint256 public humanCount;
    uint256 public agentCount;

    struct Participant {
        bool isHuman;
        bool verified;
        uint256 rewardAmount;
        uint256 timestamp;
        address agentAddress;
    }

    mapping(address => Participant) public participants;
    mapping(address => bool) public hasClaimed;
    mapping(bytes32 => bool) public usedSignatures;

    Counters.Counter private _participantIdCounter;
    mapping(uint256 => address) public participantIds;

    event CampaignStarted(uint256 startTime, uint256 endTime);
    event CampaignEnded(uint256 totalParticipants, uint256 humanRatio);
    event HumanVerified(address indexed human, address indexed agent, uint256 reward);
    event AgentRegistered(address indexed agent, address indexed human);
    event RewardClaimed(address indexed participant, uint256 amount);

    modifier onlyDuringCampaign() {
        require(campaignActive, "Campaign not active");
        require(block.timestamp >= campaignStart && block.timestamp <= campaignEnd, "Outside campaign period");
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
    }

    function startCampaign() external onlyOwner {
        require(!campaignActive, "Campaign already active");
        require(rewardToken.balanceOf(address(this)) >= POOL_SIZE, "Insufficient pool funds");
        
        campaignActive = true;
        campaignStart = block.timestamp;
        campaignEnd = block.timestamp + CAMPAIGN_DURATION;
        
        emit CampaignStarted(campaignStart, campaignEnd);
    }

    function registerAgent(address _human) external {
        require(campaignActive, "Campaign not active");
        require(!participants[_human].verified, "Human already verified");
        require(_human != address(0) && _human != msg.sender, "Invalid human address");
        
        participants[_human] = Participant({
            isHuman: true,
            verified: false,
            rewardAmount: 0,
            timestamp: block.timestamp,
            agentAddress: msg.sender
        });
        
        agentCount++;
        emit AgentRegistered(msg.sender, _human);
    }

    function verifyHuman(address _human, bytes calldata _signature) external onlyVerifier onlyDuringCampaign {
        require(!participants[_human].verified, "Already verified");
        require(participants[_human].agentAddress != address(0), "Not registered by agent");
        
        bytes32 messageHash = keccak256(abi.encodePacked(_human, block.timestamp));
        bytes32 ethSignedMessageHash = messageHash.toEthSignedMessageHash();
        address signer = ethSignedMessageHash.recover(_signature);
        
        require(signer == verifier, "Invalid signature");
        require(!usedSignatures[messageHash], "Signature already used");
        
        usedSignatures[messageHash] = true;
        participants[_human].verified = true;
        participants[_human].rewardAmount = calculateReward();
        
        humanCount++;
        _participantIdCounter.increment();
        participantIds[_participantIdCounter.current()] = _human;
        
        emit HumanVerified(_human, participants[_human].agentAddress, participants[_human].rewardAmount);
    }

    function claimReward() external nonReentrant {
        require(participants[msg.sender].verified, "Not verified");
        require(!hasClaimed[msg.sender], "Already claimed");
        require(participants[msg.sender].rewardAmount > 0, "No reward to claim");
        
        uint256 reward = participants[msg.sender].rewardAmount;
        hasClaimed[msg.sender] = true;
        totalRewardsClaimed += reward;
        
        require(rewardToken.transfer(msg.sender, reward), "Transfer failed");
        
        emit RewardClaimed(msg.sender, reward);
    }

    function calculateReward() public view returns (uint256) {
        uint256 remainingPool = POOL_SIZE - totalRewardsClaimed;
        uint256 unverifiedHumans = humanCount - getVerifiedCount();
        
        if (unverifiedHumans == 0) return 0;
        return remainingPool / unverifiedHumans;
    }

    function getVerifiedCount() public view returns (uint256) {
        uint256 count;
        for (uint256 i = 1; i <= _participantIdCounter.current(); i++) {
            if (participants[participantIds[i]].verified) {
                count++;
            }
        }
        return count;
    }

    function getHumanRatio() public view returns (uint256) {
        uint256 total = humanCount + agentCount;
        if (total == 0) return 0;
        return (humanCount * 100) / total;
    }

    function endCampaign() external onlyOwner {
        require(campaignActive, "Campaign not active");
        campaignActive = false;
        
        uint256 ratio = getHumanRatio();
        emit CampaignEnded(humanCount + agentCount, ratio);
    }

    function withdrawUnclaimed() external onlyOwner {
        require(!campaignActive, "Campaign still active");
        uint256 unclaimed = POOL_SIZE - totalRewardsClaimed;
        require(unclaimed > 0, "Nothing to withdraw");
        require(rewardToken.transfer(owner(), unclaimed), "Transfer failed");
    }

    function updateVerifier(address _newVerifier) external onlyOwner {
        require(_newVerifier != address(0), "Invalid address");
        verifier = _newVerifier;
    }

    // Fallback for direct RTC deposits
    receive() external payable {
        require(msg.value > 0, "Must send RTC");
    }
}
