// SPDX-License-Identifier: MIT
// RustChain Token (wRTC) - ERC-20 on Base
// RIP-305 Track B: Base ERC-20 Deployment
// Bounty #1510

pragma solidity ^0.8.25;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title WRTC
 * @dev RustChain Token wrapped for Base network
 * 
 * Key features:
 * - Standard ERC-20 with permit (EIP-2612)
 * - Burnable for cross-chain bridge operations
 * - Pausable for emergency scenarios
 * - Ownable for administrative control
 * - 6 decimals (matching Solana wRTC for consistency)
 * 
 * @notice This contract is designed for integration with the BoTTube Bridge
 * and RustChain's cross-chain infrastructure.
 */
contract WRTC is ERC20, ERC20Permit, ERC20Burnable, Ownable, Pausable, ReentrancyGuard {
    // Bridge operators who can mint/burn for cross-chain transfers
    mapping(address => bool) public bridgeOperators;
    
    // Events
    event BridgeOperatorAdded(address indexed operator);
    event BridgeOperatorRemoved(address indexed operator);
    event BridgeMint(address indexed to, uint256 amount);
    event BridgeBurn(address indexed from, uint256 amount);
    
    /**
     * @dev Constructor - mints initial supply to deployer
     * @param initialSupply Initial token supply (in atomic units, 6 decimals)
     * @param bridgeOperator Initial bridge operator address (can be zero for no operator)
     */
    constructor(
        uint256 initialSupply,
        address bridgeOperator
    ) 
        ERC20("RustChain Token", "wRTC")
        ERC20Permit("RustChain Token")
        Ownable(msg.sender)
    {
        if (initialSupply > 0) {
            _mint(msg.sender, initialSupply);
        }
        if (bridgeOperator != address(0)) {
            _addBridgeOperator(bridgeOperator);
        }
    }
    
    /**
     * @dev Returns the number of decimals used for display purposes
     * Using 6 decimals to match Solana wRTC and USDC on Base
     */
    function decimals() public pure override returns (uint8) {
        return 6;
    }
    
    /**
     * @dev Adds a bridge operator (only owner)
     * @param operator Address to grant bridge operator privileges
     */
    function addBridgeOperator(address operator) external onlyOwner {
        _addBridgeOperator(operator);
    }
    
    /**
     * @dev Removes a bridge operator (only owner)
     * @param operator Address to revoke bridge operator privileges
     */
    function removeBridgeOperator(address operator) external onlyOwner {
        _removeBridgeOperator(operator);
    }
    
    /**
     * @dev Mint tokens by bridge operator (for cross-chain deposits)
     * @param to Recipient address
     * @param amount Amount to mint (in atomic units)
     */
    function bridgeMint(address to, uint256 amount) 
        external 
        whenNotPaused 
        nonReentrant 
    {
        require(bridgeOperators[msg.sender], "WRTC: Not a bridge operator");
        require(to != address(0), "WRTC: Mint to zero address");
        require(amount > 0, "WRTC: Amount must be positive");
        
        _mint(to, amount);
        emit BridgeMint(to, amount);
    }
    
    /**
     * @dev Burn tokens by bridge operator (for cross-chain withdrawals)
     * @param from Account to burn from
     * @param amount Amount to burn (in atomic units)
     */
    function bridgeBurn(address from, uint256 amount) 
        external 
        whenNotPaused 
        nonReentrant 
    {
        require(bridgeOperators[msg.sender], "WRTC: Not a bridge operator");
        require(amount > 0, "WRTC: Amount must be positive");
        
        _burn(from, amount);
        emit BridgeBurn(from, amount);
    }
    
    /**
     * @dev Pause all transfers (only owner, emergency use)
     */
    function pause() external onlyOwner {
        _pause();
    }
    
    /**
     * @dev Unpause transfers (only owner)
     */
    function unpause() external onlyOwner {
        _unpause();
    }

    /**
     * @dev Override transfer to check pause status
     */
    function _update(
        address from,
        address to,
        uint256 amount
    ) internal override whenNotPaused {
        super._update(from, to, amount);
    }
    
    /**
     * @dev Internal function to add bridge operator
     */
    function _addBridgeOperator(address operator) internal {
        require(operator != address(0), "WRTC: Zero address");
        require(!bridgeOperators[operator], "WRTC: Already operator");
        
        bridgeOperators[operator] = true;
        emit BridgeOperatorAdded(operator);
    }
    
    /**
     * @dev Internal function to remove bridge operator
     */
    function _removeBridgeOperator(address operator) internal {
        require(bridgeOperators[operator], "WRTC: Not an operator");
        
        bridgeOperators[operator] = false;
        emit BridgeOperatorRemoved(operator);
    }
}
