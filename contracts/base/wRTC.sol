// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title Wrapped RTC (wRTC)
 * @notice ERC-20 representation of RustChain RTC tokens on Base L2
 * @dev Implements RIP-305 Cross-Chain Airdrop Protocol
 *      6 decimal precision to match native RTC token
 *      Mint/burn functions for bridge integration (Phase 1: admin-controlled)
 */
contract WrappedRTC is ERC20, ERC20Burnable, Ownable {
    uint256 public constant MAX_SUPPLY = 50_000 * 10**6; // 50,000 wRTC (6 decimals)
    
    address public bridge;
    
    event BridgeSet(address indexed oldBridge, address indexed newBridge);
    event Minted(address indexed to, uint256 amount);
    event Burned(address indexed from, uint256 amount);

    modifier onlyBridgeOrOwner() {
        require(
            msg.sender == bridge || msg.sender == owner(),
            "wRTC: caller is not bridge or owner"
        );
        _;
    }

    constructor(address initialOwner) 
        ERC20("Wrapped RTC", "wRTC") 
        Ownable(initialOwner) 
    {}

    /**
     * @notice Returns token decimals — 6 to match native RTC precision
     */
    function decimals() public pure override returns (uint8) {
        return 6;
    }

    /**
     * @notice Set the authorized bridge address
     * @param _bridge Address of the RustChain bridge contract
     */
    function setBridge(address _bridge) external onlyOwner {
        require(_bridge != address(0), "wRTC: zero address");
        address old = bridge;
        bridge = _bridge;
        emit BridgeSet(old, _bridge);
    }

    /**
     * @notice Mint wRTC tokens — called by bridge when RTC is locked on RustChain
     * @param to Recipient address
     * @param amount Amount to mint (in 6-decimal units)
     */
    function mint(address to, uint256 amount) external onlyBridgeOrOwner {
        require(totalSupply() + amount <= MAX_SUPPLY, "wRTC: exceeds max supply");
        _mint(to, amount);
        emit Minted(to, amount);
    }

    /**
     * @notice Burn wRTC tokens — called by bridge when user wants to return to RustChain
     * @param from Address to burn from
     * @param amount Amount to burn (in 6-decimal units)
     */
    function burnFrom(address from, uint256 amount) public override onlyBridgeOrOwner {
        _burn(from, amount);
        emit Burned(from, amount);
    }

    /**
     * @notice Get remaining mintable supply
     */
    function remainingSupply() external view returns (uint256) {
        return MAX_SUPPLY - totalSupply();
    }
}
