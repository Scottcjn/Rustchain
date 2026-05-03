// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";

contract HumanVerificationCampaign is Ownable {
    using ECDSA for bytes32;
    using MessageHashUtils for bytes32;

    IERC20 public rewardToken;
    uint256 public constant POOL_SIZE = 500 * 10**18; // 500 RTC with 18 decimals
    uint256 public constant CAMPAIGN_DURATION = 14 days;
    uint256 public campaignStart;
    uint256 public campaignEnd;
    uint256 public totalClaimed;

    mapping(address => bool) public hasClaimed;
    mapping(address => bool) public verifiedHumans;
    address public verifier;

    event HumanVerified(address indexed human, address indexed agent);
    event RewardClaimed(address indexed human, uint256 amount);
    event CampaignStarted(uint256 startTime, uint256 endTime);
    event VerifierUpdated(address indexed oldVerifier, address indexed newVerifier);

    modifier campaignActive() {
        require(block.timestamp >= campaignStart && block.timestamp <= campaignEnd, "Campaign not active");
        _;
    }

    modifier onlyVerifier() {
        require(msg.sender == verifier, "Only verifier can call this");
        _;
    }

    constructor(address _rewardToken, address _verifier) Ownable(msg.sender) {
        require(_rewardToken != address(0), "Invalid token address");
        require(_verifier != address(0), "Invalid verifier address");
        rewardToken = IERC20(_rewardToken);
        verifier = _verifier;
    }

    function startCampaign() external onlyOwner {
        require(campaignStart == 0, "Campaign already started");
        campaignStart = block.timestamp;
        campaignEnd = block.timestamp + CAMPAIGN_DURATION;
        emit CampaignStarted(campaignStart, campaignEnd);
    }

    function setVerifier(address _newVerifier) external onlyOwner {
        require(_newVerifier != address(0), "Invalid verifier address");
        address oldVerifier = verifier;
        verifier = _newVerifier;
        emit VerifierUpdated(oldVerifier, _newVerifier);
    }

    function verifyHuman(address human, bytes calldata signature) external onlyVerifier {
        require(!verifiedHumans[human], "Human already verified");
        
        bytes32 message = keccak256(abi.encodePacked(human, "HUMAN_VERIFICATION"));
        bytes32 ethSignedMessage = message.toEthSignedMessageHash();
        address signer = ethSignedMessage.recover(signature);
        
        require(signer == verifier, "Invalid signature");
        require(signer != address(0), "Invalid signer");
        
        verifiedHumans[human] = true;
        emit HumanVerified(human, msg.sender);
    }

    function claimReward() external campaignActive {
        require(verifiedHumans[msg.sender], "Human not verified");
        require(!hasClaimed[msg.sender], "Already claimed");
        require(totalClaimed < POOL_SIZE, "Pool exhausted");

        uint256 remaining = POOL_SIZE - totalClaimed;
        uint256 rewardAmount = remaining >= 10 * 10**18 ? 10 * 10**18 : remaining;

        hasClaimed[msg.sender] = true;
        totalClaimed += rewardAmount;

        require(rewardToken.transfer(msg.sender, rewardAmount), "Transfer failed");
        emit RewardClaimed(msg.sender, rewardAmount);
    }

    function getCampaignStatus() external view returns (
        bool isActive,
        uint256 startTime,
        uint256 endTime,
        uint256 claimed,
        uint256 poolSize,
        uint256 remaining
    ) {
        isActive = block.timestamp >= campaignStart && block.timestamp <= campaignEnd;
        startTime = campaignStart;
        endTime = campaignEnd;
        claimed = totalClaimed;
        poolSize = POOL_SIZE;
        remaining = POOL_SIZE - totalClaimed;
    }

    function withdrawRemaining() external onlyOwner {
        require(block.timestamp > campaignEnd, "Campaign still active");
        uint256 remaining = POOL_SIZE - totalClaimed;
        require(remaining > 0, "Nothing to withdraw");
        require(rewardToken.transfer(owner(), remaining), "Transfer failed");
    }
}
