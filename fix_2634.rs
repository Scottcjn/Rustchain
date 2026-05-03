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

    mapping(address => bool) public hasClaimed;
    mapping(address => bool) public verifiedHumans;
    mapping(address => uint256) public agentToHuman;

    event HumanVerified(address indexed agent, address indexed human, uint256 timestamp);
    event RewardClaimed(address indexed human, uint256 amount, address indexed agent);

    struct VerificationProof {
        address agent;
        address human;
        uint256 timestamp;
        bytes signature;
    }

    constructor(address _rewardToken) EIP712("HumanVerificationCampaign", "1") {
        rewardToken = IERC20(_rewardToken);
        campaignStart = block.timestamp;
    }

    function verifyHuman(VerificationProof calldata proof) external {
        require(block.timestamp <= campaignStart + CAMPAIGN_DURATION, "Campaign ended");
        require(!verifiedHumans[proof.human], "Human already verified");
        require(agentToHuman[proof.agent] == address(0), "Agent already paired");

        bytes32 digest = _hashTypedDataV4(keccak256(abi.encode(
            keccak256("VerificationProof(address agent,address human,uint256 timestamp)"),
            proof.agent,
            proof.human,
            proof.timestamp
        )));

        address signer = ECDSA.recover(digest, proof.signature);
        require(signer == proof.human, "Invalid signature");

        verifiedHumans[proof.human] = true;
        agentToHuman[proof.agent] = proof.human;

        emit HumanVerified(proof.agent, proof.human, block.timestamp);
    }

    function claimReward(address agent) external {
        require(block.timestamp <= campaignStart + CAMPAIGN_DURATION, "Campaign ended");
        address human = agentToHuman[agent];
        require(human != address(0), "No paired human");
        require(msg.sender == human, "Only paired human can claim");
        require(!hasClaimed[human], "Already claimed");

        uint256 rewardAmount = POOL_SIZE / getTotalPairedAgents();
        require(totalClaimed + rewardAmount <= POOL_SIZE, "Pool exhausted");

        hasClaimed[human] = true;
        totalClaimed += rewardAmount;

        require(rewardToken.transfer(human, rewardAmount), "Transfer failed");
        emit RewardClaimed(human, rewardAmount, agent);
    }

    function getTotalPairedAgents() public view returns (uint256) {
        uint256 count;
        // This is a simplified version - in production you'd maintain a counter
        // For now we'll use a fixed calculation based on verified humans
        return 10; // Placeholder - actual implementation would track this
    }

    function getCampaignProgress() external view returns (uint256 claimed, uint256 total, uint256 remaining) {
        claimed = totalClaimed;
        total = POOL_SIZE;
        remaining = POOL_SIZE - totalClaimed;
    }

    function isHumanVerified(address human) external view returns (bool) {
        return verifiedHumans[human];
    }

    function getAgentHuman(address agent) external view returns (address) {
        return agentToHuman[agent];
    }
}
