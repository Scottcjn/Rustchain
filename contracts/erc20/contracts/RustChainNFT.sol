// SPDX-License-Identifier: MIT
// RustChain NFT (RCNFT) - ERC-721 metadata support on Base

pragma solidity ^0.8.25;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title RustChainNFT
 * @dev ERC-721 compatible NFT contract for RustChain collectibles and badges.
 *
 * Supports the issue #2717 requirements:
 * - NFT minting by the owner or approved NFT minters
 * - ERC-721 transfers and approvals
 * - Per-token metadata URI management
 */
contract RustChainNFT is ERC721URIStorage, Ownable, Pausable {
    mapping(address => bool) public nftMinters;

    uint256 private _nextTokenId = 1;

    event NFTMinterAdded(address indexed minter);
    event NFTMinterRemoved(address indexed minter);
    event MetadataUpdated(uint256 indexed tokenId, string tokenURI);

    constructor(address initialMinter) ERC721("RustChain Relic NFT", "RCNFT") Ownable(msg.sender) {
        if (initialMinter != address(0)) {
            _addNFTMinter(initialMinter);
        }
    }

    /**
     * @dev Mint a new NFT with metadata URI.
     * @param to Recipient address.
     * @param tokenURI_ Metadata URI for the token.
     */
    function mint(address to, string calldata tokenURI_) external whenNotPaused returns (uint256) {
        require(_isAuthorizedMinter(msg.sender), "RustChainNFT: Not authorized to mint");
        require(to != address(0), "RustChainNFT: Mint to zero address");
        require(bytes(tokenURI_).length > 0, "RustChainNFT: Metadata URI required");

        uint256 tokenId = _nextTokenId;
        _nextTokenId += 1;

        _safeMint(to, tokenId);
        _setTokenURI(tokenId, tokenURI_);

        emit MetadataUpdated(tokenId, tokenURI_);
        return tokenId;
    }

    /**
     * @dev Update token metadata URI. Owner or NFT minter only.
     * @param tokenId Token to update.
     * @param tokenURI_ New metadata URI.
     */
    function setTokenURI(uint256 tokenId, string calldata tokenURI_) external {
        require(_isAuthorizedMinter(msg.sender), "RustChainNFT: Not authorized to update metadata");
        require(bytes(tokenURI_).length > 0, "RustChainNFT: Metadata URI required");

        ownerOf(tokenId);
        _setTokenURI(tokenId, tokenURI_);

        emit MetadataUpdated(tokenId, tokenURI_);
    }

    function addNFTMinter(address minter) external onlyOwner {
        _addNFTMinter(minter);
    }

    function removeNFTMinter(address minter) external onlyOwner {
        require(nftMinters[minter], "RustChainNFT: Not a minter");

        nftMinters[minter] = false;
        emit NFTMinterRemoved(minter);
    }

    function nextTokenId() external view returns (uint256) {
        return _nextTokenId;
    }

    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }

    function _addNFTMinter(address minter) internal {
        require(minter != address(0), "RustChainNFT: Zero address");
        require(!nftMinters[minter], "RustChainNFT: Already minter");

        nftMinters[minter] = true;
        emit NFTMinterAdded(minter);
    }

    function _isAuthorizedMinter(address account) internal view returns (bool) {
        return account == owner() || nftMinters[account];
    }

    function _update(
        address to,
        uint256 tokenId,
        address auth
    ) internal override whenNotPaused returns (address) {
        return super._update(to, tokenId, auth);
    }
}
