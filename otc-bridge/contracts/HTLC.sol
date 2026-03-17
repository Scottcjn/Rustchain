// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title RustChain OTC Bridge HTLC
 * @notice Hash Time-Locked Contract for ETH/ERC20 side of RTC OTC swaps.
 *         RTC side is escrowed via RIP-302 Agent Economy on RustChain nodes.
 *         This contract handles the ETH/USDC/ERC20 side of the atomic swap.
 *
 * Flow:
 *   1. Seller creates RTC sell order on OTC Bridge (RTC locked in RIP-302 escrow)
 *   2. Buyer locks ETH/USDC in this HTLC with the seller's htlc_hash
 *   3. Seller reveals the secret (proves they released RTC escrow)
 *   4. Buyer can claim ETH/USDC with the revealed secret
 *   5. If timeout expires without reveal, buyer reclaims their ETH/USDC
 *
 * @author WireWork (wirework.dev)
 */

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract RustChainHTLC is ReentrancyGuard {
    using SafeERC20 for IERC20;

    struct Swap {
        address buyer;
        address seller;
        address token;        // address(0) for ETH
        uint256 amount;
        bytes32 hashlock;
        uint256 timelock;
        bool claimed;
        bool refunded;
        bytes32 preimage;     // Set when claimed
        string rtcOrderId;    // OTC Bridge order ID for cross-reference
    }

    mapping(bytes32 => Swap) public swaps;
    uint256 public swapCount;

    uint256 public constant MIN_TIMELOCK = 1 hours;
    uint256 public constant MAX_TIMELOCK = 7 days;

    // Events
    event SwapCreated(
        bytes32 indexed swapId,
        address indexed buyer,
        address indexed seller,
        address token,
        uint256 amount,
        bytes32 hashlock,
        uint256 timelock,
        string rtcOrderId
    );
    event SwapClaimed(bytes32 indexed swapId, bytes32 preimage);
    event SwapRefunded(bytes32 indexed swapId);

    // Errors
    error SwapExists();
    error SwapNotFound();
    error InvalidTimelock();
    error InvalidAmount();
    error InvalidHashlock();
    error AlreadyClaimed();
    error AlreadyRefunded();
    error TimelockNotExpired();
    error TimelockExpired();
    error InvalidPreimage();
    error NotBuyer();
    error NotSeller();
    error TransferFailed();

    /**
     * @notice Create a new HTLC swap with ETH
     * @param seller Address that can claim funds with the preimage
     * @param hashlock SHA256 hash of the secret (from OTC Bridge order)
     * @param timelock Unix timestamp when buyer can reclaim
     * @param rtcOrderId OTC Bridge order ID for cross-chain reference
     */
    function createSwapETH(
        address seller,
        bytes32 hashlock,
        uint256 timelock,
        string calldata rtcOrderId
    ) external payable nonReentrant returns (bytes32 swapId) {
        if (msg.value == 0) revert InvalidAmount();
        if (hashlock == bytes32(0)) revert InvalidHashlock();
        if (timelock < block.timestamp + MIN_TIMELOCK) revert InvalidTimelock();
        if (timelock > block.timestamp + MAX_TIMELOCK) revert InvalidTimelock();

        swapId = keccak256(abi.encodePacked(
            msg.sender, seller, address(0), msg.value, hashlock, timelock, swapCount++
        ));
        if (swaps[swapId].buyer != address(0)) revert SwapExists();

        swaps[swapId] = Swap({
            buyer: msg.sender,
            seller: seller,
            token: address(0),
            amount: msg.value,
            hashlock: hashlock,
            timelock: timelock,
            claimed: false,
            refunded: false,
            preimage: bytes32(0),
            rtcOrderId: rtcOrderId
        });

        emit SwapCreated(swapId, msg.sender, seller, address(0), msg.value, hashlock, timelock, rtcOrderId);
    }

    /**
     * @notice Create a new HTLC swap with an ERC20 token (e.g., USDC)
     * @param seller Address that can claim tokens with the preimage
     * @param token ERC20 token address
     * @param amount Token amount (in token decimals)
     * @param hashlock SHA256 hash of the secret
     * @param timelock Unix timestamp when buyer can reclaim
     * @param rtcOrderId OTC Bridge order ID
     */
    function createSwapERC20(
        address seller,
        address token,
        uint256 amount,
        bytes32 hashlock,
        uint256 timelock,
        string calldata rtcOrderId
    ) external nonReentrant returns (bytes32 swapId) {
        if (amount == 0) revert InvalidAmount();
        if (token == address(0)) revert InvalidAmount();
        if (hashlock == bytes32(0)) revert InvalidHashlock();
        if (timelock < block.timestamp + MIN_TIMELOCK) revert InvalidTimelock();
        if (timelock > block.timestamp + MAX_TIMELOCK) revert InvalidTimelock();

        swapId = keccak256(abi.encodePacked(
            msg.sender, seller, token, amount, hashlock, timelock, swapCount++
        ));
        if (swaps[swapId].buyer != address(0)) revert SwapExists();

        // Transfer tokens to this contract
        IERC20(token).safeTransferFrom(msg.sender, address(this), amount);

        swaps[swapId] = Swap({
            buyer: msg.sender,
            seller: seller,
            token: token,
            amount: amount,
            hashlock: hashlock,
            timelock: timelock,
            claimed: false,
            refunded: false,
            preimage: bytes32(0),
            rtcOrderId: rtcOrderId
        });

        emit SwapCreated(swapId, msg.sender, seller, token, amount, hashlock, timelock, rtcOrderId);
    }

    /**
     * @notice Seller claims funds by revealing the preimage
     * @param swapId The swap identifier
     * @param preimage The secret whose SHA256 matches the hashlock
     */
    function claim(bytes32 swapId, bytes32 preimage) external nonReentrant {
        Swap storage swap = swaps[swapId];
        if (swap.buyer == address(0)) revert SwapNotFound();
        if (swap.claimed) revert AlreadyClaimed();
        if (swap.refunded) revert AlreadyRefunded();
        if (block.timestamp >= swap.timelock) revert TimelockExpired();
        if (msg.sender != swap.seller) revert NotSeller();

        // Verify preimage
        if (sha256(abi.encodePacked(preimage)) != swap.hashlock) revert InvalidPreimage();

        swap.claimed = true;
        swap.preimage = preimage;

        // Transfer funds to seller
        if (swap.token == address(0)) {
            (bool ok, ) = payable(swap.seller).call{value: swap.amount}("");
            if (!ok) revert TransferFailed();
        } else {
            IERC20(swap.token).safeTransfer(swap.seller, swap.amount);
        }

        emit SwapClaimed(swapId, preimage);
    }

    /**
     * @notice Buyer reclaims funds after timelock expires
     * @param swapId The swap identifier
     */
    function refund(bytes32 swapId) external nonReentrant {
        Swap storage swap = swaps[swapId];
        if (swap.buyer == address(0)) revert SwapNotFound();
        if (swap.claimed) revert AlreadyClaimed();
        if (swap.refunded) revert AlreadyRefunded();
        if (block.timestamp < swap.timelock) revert TimelockNotExpired();
        if (msg.sender != swap.buyer) revert NotBuyer();

        swap.refunded = true;

        if (swap.token == address(0)) {
            (bool ok, ) = payable(swap.buyer).call{value: swap.amount}("");
            if (!ok) revert TransferFailed();
        } else {
            IERC20(swap.token).safeTransfer(swap.buyer, swap.amount);
        }

        emit SwapRefunded(swapId);
    }

    /**
     * @notice View swap details
     */
    function getSwap(bytes32 swapId) external view returns (
        address buyer,
        address seller,
        address token,
        uint256 amount,
        bytes32 hashlock,
        uint256 timelock,
        bool claimed,
        bool refunded,
        string memory rtcOrderId
    ) {
        Swap storage s = swaps[swapId];
        return (s.buyer, s.seller, s.token, s.amount,
                s.hashlock, s.timelock, s.claimed, s.refunded, s.rtcOrderId);
    }

    /**
     * @notice Check if preimage has been revealed (for cross-chain verification)
     */
    function getPreimage(bytes32 swapId) external view returns (bytes32) {
        return swaps[swapId].preimage;
    }
}
