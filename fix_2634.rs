// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/EIP712.sol";

contract HumanVerificationCampaign is Ownable, EIP712 {
    using ECDSA for bytes32;

    IERC20 public rewardToken;
    uint256 public constant POOL_SIZE = 500 * 10**18; // 500 RTC
    uint256 public constant CAMPAIGN_DURATION = 14 days;
    uint256 public campaignEnd;
    uint256 public totalClaimed;
    
    mapping(address => bool) public hasClaimed;
    mapping(address => uint256) public agentToHuman;
    
    event HumanVerified(address indexed agent, address indexed human, uint256 reward);
    event CampaignExtended(uint256 newEndTime);

    struct VerificationProof {
        address agent;
        address human;
        uint256 timestamp;
        bytes signature;
    }

    constructor(address _rewardToken) EIP712("HumanVerificationCampaign", "1") {
        rewardToken = IERC20(_rewardToken);
        campaignEnd = block.timestamp + CAMPAIGN_DURATION;
    }

    function verifyAndClaim(
        VerificationProof calldata proof,
        bytes32[] calldata merkleProof,
        bytes32 merkleRoot
    ) external {
        require(block.timestamp <= campaignEnd, "Campaign ended");
        require(!hasClaimed[proof.agent], "Already claimed");
        require(totalClaimed < POOL_SIZE, "Pool exhausted");
        
        // Verify human is not a contract
        require(!_isContract(proof.human), "Human must be EOA");
        
        // Verify signature from authorized verifier
        bytes32 digest = _hashTypedDataV4(
            keccak256(abi.encode(
                keccak256("Verification(address agent,address human,uint256 timestamp)"),
                proof.agent,
                proof.human,
                proof.timestamp
            ))
        );
        
        address signer = ECDSA.recover(digest, proof.signature);
        require(signer == owner(), "Invalid signature");
        
        // Verify merkle proof if provided
        if (merkleRoot != bytes32(0)) {
            bytes32 leaf = keccak256(abi.encodePacked(proof.agent, proof.human));
            require(_verifyMerkleProof(merkleProof, merkleRoot, leaf), "Invalid merkle proof");
        }
        
        // Calculate reward (equal distribution)
        uint256 reward = POOL_SIZE / (POOL_SIZE / 10**18); // Simplified for demo
        
        hasClaimed[proof.agent] = true;
        agentToHuman[proof.agent] = uint256(uint160(proof.human));
        totalClaimed += reward;
        
        require(rewardToken.transfer(proof.human, reward), "Transfer failed");
        
        emit HumanVerified(proof.agent, proof.human, reward);
    }

    function extendCampaign(uint256 _additionalDays) external onlyOwner {
        campaignEnd += _additionalDays * 1 days;
        emit CampaignExtended(campaignEnd);
    }

    function withdrawRemaining() external onlyOwner {
        require(block.timestamp > campaignEnd, "Campaign still active");
        uint256 remaining = POOL_SIZE - totalClaimed;
        require(remaining > 0, "Nothing to withdraw");
        require(rewardToken.transfer(owner(), remaining), "Transfer failed");
    }

    function _isContract(address _addr) private view returns (bool) {
        uint32 size;
        assembly {
            size := extcodesize(_addr)
        }
        return size > 0;
    }

    function _verifyMerkleProof(
        bytes32[] memory proof,
        bytes32 root,
        bytes32 leaf
    ) private pure returns (bool) {
        bytes32 computedHash = leaf;
        for (uint256 i = 0; i < proof.length; i++) {
            bytes32 proofElement = proof[i];
            if (computedHash <= proofElement) {
                computedHash = keccak256(abi.encodePacked(computedHash, proofElement));
            } else {
                computedHash = keccak256(abi.encodePacked(proofElement, computedHash));
            }
        }
        return computedHash == root;
    }

    // Fallback for agents without direct access
    function claimForAgent(address agent, address human, bytes calldata signature) external {
        require(block.timestamp <= campaignEnd, "Campaign ended");
        require(!hasClaimed[agent], "Already claimed");
        require(totalClaimed < POOL_SIZE, "Pool exhausted");
        require(!_isContract(human), "Human must be EOA");
        
        bytes32 digest = _hashTypedDataV4(
            keccak256(abi.encode(
                keccak256("AgentClaim(address agent,address human,uint256 deadline)"),
                agent,
                human,
                block.timestamp + 1 hours
            ))
        );
        
        address signer = ECDSA.recover(digest, signature);
        require(signer == agent, "Agent must sign");
        
        uint256 reward = POOL_SIZE / (POOL_SIZE / 10**18);
        
        hasClaimed[agent] = true;
        agentToHuman[agent] = uint256(uint160(human));
        totalClaimed += reward;
        
        require(rewardToken.transfer(human, reward), "Transfer failed");
        
        emit HumanVerified(agent, human, reward);
    }
}
