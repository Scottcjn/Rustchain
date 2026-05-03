// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/EIP712.sol";

contract HumanVerificationCampaign is Ownable, ReentrancyGuard, EIP712 {
    using ECDSA for bytes32;

    IERC20 public rewardToken;
    uint256 public constant POOL_SIZE = 500 * 10**18; // 500 RTC with 18 decimals
    uint256 public constant CAMPAIGN_DURATION = 14 days;
    uint256 public campaignStart;
    uint256 public totalClaimed;
    bool public campaignActive;

    struct HumanVerification {
        address agent;
        address human;
        uint256 timestamp;
        bool verified;
    }

    mapping(address => HumanVerification) public verifications;
    mapping(address => bool) public hasClaimed;
    mapping(address => uint256) public agentVerificationCount;

    // Events
    event HumanVerified(address indexed agent, address indexed human, uint256 timestamp);
    event RewardClaimed(address indexed agent, address indexed human, uint256 amount);
    event CampaignStarted(uint256 startTime, uint256 duration);
    event CampaignEnded(uint256 endTime);

    // Errors
    error CampaignNotActive();
    error CampaignAlreadyActive();
    error CampaignEnded();
    error AlreadyVerified();
    error AlreadyClaimed();
    error InvalidSignature();
    error InsufficientPoolBalance();
    error NotAgentOwner();

    constructor(address _rewardToken) EIP712("HumanVerificationCampaign", "1") {
        rewardToken = IERC20(_rewardToken);
    }

    modifier onlyDuringCampaign() {
        if (!campaignActive) revert CampaignNotActive();
        if (block.timestamp > campaignStart + CAMPAIGN_DURATION) revert CampaignEnded();
        _;
    }

    function startCampaign() external onlyOwner {
        if (campaignActive) revert CampaignAlreadyActive();
        if (rewardToken.balanceOf(address(this)) < POOL_SIZE) revert InsufficientPoolBalance();
        
        campaignActive = true;
        campaignStart = block.timestamp;
        emit CampaignStarted(campaignStart, CAMPAIGN_DURATION);
    }

    function endCampaign() external onlyOwner {
        campaignActive = false;
        emit CampaignEnded(block.timestamp);
    }

    function verifyHuman(
        address _agent,
        address _human,
        bytes calldata _signature
    ) external onlyDuringCampaign nonReentrant {
        if (verifications[_agent].verified) revert AlreadyVerified();
        if (msg.sender != _agent && msg.sender != _human) revert NotAgentOwner();

        // Verify the signature proves human control
        bytes32 structHash = keccak256(
            abi.encode(
                keccak256("HumanVerification(address agent,address human,uint256 deadline)"),
                _agent,
                _human,
                block.timestamp + 1 hours
            )
        );
        
        bytes32 hash = _hashTypedDataV4(structHash);
        address signer = ECDSA.recover(hash, _signature);
        
        if (signer != _human) revert InvalidSignature();

        verifications[_agent] = HumanVerification({
            agent: _agent,
            human: _human,
            timestamp: block.timestamp,
            verified: true
        });

        agentVerificationCount[_agent]++;
        
        emit HumanVerified(_agent, _human, block.timestamp);
    }

    function claimReward(address _agent) external nonReentrant {
        if (!campaignActive && block.timestamp > campaignStart + CAMPAIGN_DURATION) {
            // Allow claiming after campaign ends
        } else if (!campaignActive) {
            revert CampaignNotActive();
        }

        HumanVerification storage verification = verifications[_agent];
        if (!verification.verified) revert CampaignNotActive();
        if (hasClaimed[_agent]) revert AlreadyClaimed();

        uint256 rewardAmount = calculateReward(_agent);
        if (rewardAmount == 0) revert InsufficientPoolBalance();
        if (rewardToken.balanceOf(address(this)) < rewardAmount) revert InsufficientPoolBalance();

        hasClaimed[_agent] = true;
        totalClaimed += rewardAmount;

        // Transfer reward to the human
        require(rewardToken.transfer(verification.human, rewardAmount), "Transfer failed");
        
        emit RewardClaimed(_agent, verification.human, rewardAmount);
    }

    function calculateReward(address _agent) public view returns (uint256) {
        if (!verifications[_agent].verified) return 0;
        if (hasClaimed[_agent]) return 0;

        uint256 remainingPool = POOL_SIZE - totalClaimed;
        uint256 totalVerifications = getTotalVerifications();
        
        if (totalVerifications == 0) return 0;
        
        // Equal distribution among all verified humans
        return remainingPool / totalVerifications;
    }

    function getTotalVerifications() public view returns (uint256) {
        uint256 count;
        // This is a simplified version - in production you'd use an array or mapping
        // For this example, we'll iterate through a fixed set
        return count;
    }

    function getCampaignStatus() external view returns (
        bool active,
        uint256 startTime,
        uint256 endTime,
        uint256 poolRemaining,
        uint256 totalClaimedAmount
    ) {
        return (
            campaignActive,
            campaignStart,
            campaignStart + CAMPAIGN_DURATION,
            POOL_SIZE - totalClaimed,
            totalClaimed
        );
    }

    function withdrawRemaining() external onlyOwner {
        require(!campaignActive || block.timestamp > campaignStart + CAMPAIGN_DURATION, "Campaign still active");
        uint256 balance = rewardToken.balanceOf(address(this));
        if (balance > 0) {
            require(rewardToken.transfer(owner(), balance), "Transfer failed");
        }
    }

    // Fallback to receive RTC tokens
    receive() external payable {
        // Handle direct token transfers if needed
    }
}
