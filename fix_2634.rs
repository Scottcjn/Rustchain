// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/EIP712.sol";

contract HumanVerificationCampaign is Ownable, EIP712 {
    using ECDSA for bytes32;

    IERC20 public rewardToken;
    uint256 public constant POOL_SIZE = 500 * 10**18; // 500 RTC with 18 decimals
    uint256 public constant CAMPAIGN_DURATION = 14 days;
    uint256 public campaignStart;
    uint256 public totalClaimed;
    uint256 public maxRewardPerHuman = 10 * 10**18; // 10 RTC per human

    mapping(address => bool) public verifiedHumans;
    mapping(address => uint256) public claimedAmount;
    mapping(address => bool) public agentLinked;

    event HumanVerified(address indexed human, address indexed agent);
    event RewardClaimed(address indexed human, uint256 amount);
    event CampaignExtended(uint256 newEndTime);

    struct VerificationProof {
        address human;
        address agent;
        uint256 timestamp;
        bytes signature;
    }

    constructor(address _rewardToken) EIP712("HumanVerificationCampaign", "1") {
        require(_rewardToken != address(0), "Invalid token address");
        rewardToken = IERC20(_rewardToken);
        campaignStart = block.timestamp;
    }

    modifier campaignActive() {
        require(block.timestamp <= campaignStart + CAMPAIGN_DURATION, "Campaign ended");
        _;
    }

    modifier notClaimed(address _human) {
        require(!verifiedHumans[_human], "Already verified");
        _;
    }

    function verifyHuman(
        address _human,
        address _agent,
        uint256 _timestamp,
        bytes calldata _signature
    ) external campaignActive notClaimed(_human) {
        require(_human != address(0), "Invalid human address");
        require(_agent != address(0), "Invalid agent address");
        require(_timestamp >= campaignStart, "Timestamp before campaign");
        require(_timestamp <= block.timestamp, "Future timestamp");

        bytes32 structHash = keccak256(
            abi.encode(
                keccak256("Verification(address human,address agent,uint256 timestamp)"),
                _human,
                _agent,
                _timestamp
            )
        );

        bytes32 hash = _hashTypedDataV4(structHash);
        address signer = ECDSA.recover(hash, _signature);
        require(signer == _agent, "Invalid signature from agent");

        verifiedHumans[_human] = true;
        agentLinked[_agent] = true;

        emit HumanVerified(_human, _agent);
    }

    function claimReward() external campaignActive {
        require(verifiedHumans[msg.sender], "Not verified");
        require(claimedAmount[msg.sender] == 0, "Already claimed");

        uint256 reward = maxRewardPerHuman;
        if (totalClaimed + reward > POOL_SIZE) {
            reward = POOL_SIZE - totalClaimed;
        }

        require(reward > 0, "Pool exhausted");
        require(rewardToken.transfer(msg.sender, reward), "Transfer failed");

        claimedAmount[msg.sender] = reward;
        totalClaimed += reward;

        emit RewardClaimed(msg.sender, reward);
    }

    function getRemainingPool() external view returns (uint256) {
        return POOL_SIZE - totalClaimed;
    }

    function getCampaignEnd() external view returns (uint256) {
        return campaignStart + CAMPAIGN_DURATION;
    }

    function isHumanVerified(address _human) external view returns (bool) {
        return verifiedHumans[_human];
    }

    function isAgentLinked(address _agent) external view returns (bool) {
        return agentLinked[_agent];
    }

    function withdrawRemaining() external onlyOwner {
        require(block.timestamp > campaignStart + CAMPAIGN_DURATION, "Campaign still active");
        uint256 remaining = POOL_SIZE - totalClaimed;
        require(remaining > 0, "Nothing to withdraw");
        require(rewardToken.transfer(owner(), remaining), "Transfer failed");
    }

    function updateMaxReward(uint256 _newMax) external onlyOwner {
        require(_newMax > 0, "Must be positive");
        maxRewardPerHuman = _newMax;
    }
}
