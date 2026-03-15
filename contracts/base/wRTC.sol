// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/// @title wRTC - Wrapped RustChain Token on Base L2
/// @notice ERC-20 representation of RTC for cross-chain bridging
contract WRTC is ERC20, ERC20Burnable, Ownable {
    uint8 private constant _decimals = 6;

    constructor() ERC20("Wrapped RustChain Token", "wRTC") Ownable(msg.sender) {}

    function decimals() public pure override returns (uint8) {
        return _decimals;
    }

    /// @notice Mint wRTC (bridge operator only)
    function mint(address to, uint256 amount) external onlyOwner {
        _mint(to, amount);
    }
}
