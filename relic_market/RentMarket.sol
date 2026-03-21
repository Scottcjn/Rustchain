// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title RentMarket - ERC-721 based vintage machine rental marketplace
/// @notice Each machine is an ERC-721 NFT. Rentals lock RTC in escrow and grant time-limited access.
contract RentMarket is ERC721, ERC721URIStorage, Ownable, ReentrancyGuard {
    // Machine NFT counter
    uint256 private _machineTokenIdCounter;

    // Machine data struct
    struct Machine {
        string name;
        string model;           // e.g., "POWER8", "Mac G5", "Sun UltraSPARC"
        string specs;           // JSON string: CPU, RAM, storage, etc.
        string photoCID;        // IPFS CID for machine photo
        uint256 hourlyRateRTC;  // RTC per hour
        uint256 totalUptimeSeconds;
        uint256 totalRentals;
        bool isActive;
        address ed25519PubKey; // On-chain reference to machine's Ed25519 verification key
    }

    // Rental state
    struct Rental {
        uint256 machineTokenId;
        address renter;
        uint64 startTime;
        uint64 endTime;         // Unix timestamp
        uint256 slotHours;      // 1, 4, or 24
        uint256 rtcLocked;
        bool active;
        bytes32 outputHash;     // Hash of computed output (set after session)
        string attestationProof;
    }

    // Machine tokenId -> Machine
    mapping(uint256 => Machine) public machines;

    // Rental ID -> Rental
    mapping(bytes32 => Rental) public rentals;

    // Machine tokenId -> array of rental IDs (for history)
    mapping(uint256 => bytes32[]) public machineRentalHistory;

    // Events
    event MachineRegistered(uint256 indexed tokenId, string name, string model, uint256 hourlyRate);
    event MachineUpdated(uint256 indexed tokenId, string photoCID, bool isActive);
    event RentalCreated(bytes32 indexed rentalId, uint256 indexed machineTokenId, address renter, uint64 startTime, uint64 endTime, uint256 rtcLocked);
    event RentalStarted(bytes32 indexed rentalId);
    event RentalCompleted(bytes32 indexed rentalId, bytes32 outputHash, string attestationProof);
    event RentalCancelled(bytes32 indexed rentalId, uint256 rtcRefunded);
    event UptimeReported(uint256 indexed tokenId, uint256 addedSeconds);

    constructor() ERC721("RustChain Relic", "RRELIC") Ownable(msg.sender) {}

    // ─── Machine Management ────────────────────────────────────────────────────

    /// @notice Register a new vintage machine as an ERC-721 NFT
    function registerMachine(
        string calldata name,
        string calldata model,
        string calldata specs,
        string calldata photoCID,
        uint256 hourlyRateRTC,
        address ed25519PubKey
    ) external onlyOwner returns (uint256 tokenId) {
        tokenId = _machineTokenIdCounter++;
        _safeMint(address(this), tokenId);

        machines[tokenId] = Machine({
            name: name,
            model: model,
            specs: specs,
            photoCID: photoCID,
            hourlyRateRTC: hourlyRateRTC,
            totalUptimeSeconds: 0,
            totalRentals: 0,
            isActive: true,
            ed25519PubKey: ed25519PubKey
        });

        emit MachineRegistered(tokenId, name, model, hourlyRateRTC);
    }

    /// @notice Update machine metadata
    function updateMachine(uint256 tokenId, string calldata photoCID, bool isActive) external onlyOwner {
        require(ownerOf(tokenId) == address(this), "Not the machine owner");
        machines[tokenId].photoCID = photoCID;
        machines[tokenId].isActive = isActive;
        emit MachineUpdated(tokenId, photoCID, isActive);
    }

    /// @notice Report uptime after a completed rental
    function reportUptime(uint256 tokenId, uint256 addedSeconds) external onlyOwner {
        machines[tokenId].totalUptimeSeconds += addedSeconds;
        emit UptimeReported(tokenId, addedSeconds);
    }

    // ─── Rental Lifecycle ──────────────────────────────────────────────────────

    /// @notice Create a rental reservation. RTC is locked in escrow.
    /// @param machineTokenId The machine to rent
    /// @param slotHours Duration: 1, 4, or 24 hours
    /// @param startTime Unix timestamp for when rental begins
    /// @return rentalId unique rental identifier
    function createRental(
        uint256 machineTokenId,
        uint256 slotHours,
        uint64 startTime
    ) external nonReentrant returns (bytes32 rentalId) {
        require(machines[machineTokenId].isActive, "Machine not available");
        require(slotHours == 1 || slotHours == 4 || slotHours == 24, "Invalid slot duration");
        require(startTime >= block.timestamp, "Start time must be in future");

        uint64 endTime = startTime + uint64(slotHours) * 3600;
        uint256 rtcLocked = machines[machineTokenId].hourlyRateRTC * slotHours;

        rentalId = keccak256(abi.encode(machineTokenId, msg.sender, block.timestamp, slotHours));

        rentals[rentalId] = Rental({
            machineTokenId: machineTokenId,
            renter: msg.sender,
            startTime: startTime,
            endTime: endTime,
            slotHours: slotHours,
            rtcLocked: rtcLocked,
            active: true,
            outputHash: bytes32(0),
            attestationProof: ""
        });

        machineRentalHistory[machineTokenId].push(rentalId);
        machines[machineTokenId].totalRentals++;

        emit RentalCreated(rentalId, machineTokenId, msg.sender, startTime, endTime, rtcLocked);
    }

    /// @notice Mark rental as started (called by renter or agent)
    function startRental(bytes32 rentalId) external {
        require(rentals[rentalId].renter == msg.sender, "Not the renter");
        require(rentals[rentalId].active, "Rental not active");
        emit RentalStarted(rentalId);
    }

    /// @notice Complete a rental and record output hash + attestation proof
    function completeRental(
        bytes32 rentalId,
        bytes32 outputHash,
        string calldata attestationProof
    ) external onlyOwner {
        require(rentals[rentalId].active, "Rental not active");

        rentals[rentalId].outputHash = outputHash;
        rentals[rentalId].attestationProof = attestationProof;
        rentals[rentalId].active = false;

        // Release escrow to machine owner (this contract holds it)
        // In production, integrate with wRTC payment channel here

        emit RentalCompleted(rentalId, outputHash, attestationProof);
    }

    /// @notice Cancel a rental and refund RTC
    function cancelRental(bytes32 rentalId) external {
        require(rentals[rentalId].renter == msg.sender, "Not the renter");
        require(rentals[rentalId].active, "Rental not active or already completed");
        require(block.timestamp < rentals[rentalId].startTime, "Rental already started");

        uint256 refund = rentals[rentalId].rtcLocked;
        rentals[rentalId].active = false;

        emit RentalCancelled(rentalId, refund);
    }

    // ─── Views ────────────────────────────────────────────────────────────────

    /// @notice List all machines
    function getAllMachines() external view returns (Machine[] memory) {
        Machine[] memory result = new Machine[](_machineTokenIdCounter);
        for (uint256 i = 0; i < _machineTokenIdCounter; i++) {
            result[i] = machines[i];
        }
        return result;
    }

    /// @notice Get rental history for a machine
    function getMachineHistory(uint256 tokenId) external view returns (bytes32[] memory) {
        return machineRentalHistory[tokenId];
    }

    /// @notice Get rental details
    function getRental(bytes32 rentalId) external view returns (Rental memory) {
        return rentals[rentalId];
    }

    // ─── ERC-721 Overrides ────────────────────────────────────────────────────
    function tokenURI(uint256 tokenId) public view override(ERC721, ERC721URIStorage) returns (string memory) {
        return machines[tokenId].photoCID;
    }

    function supportsInterface(bytes4 interfaceId) public view override(ERC721, ERC721URIStorage) returns (bool) {
        return super.supportsInterface(interfaceId);
    }

    // ─── MCP Tool Bridge ──────────────────────────────────────────────────────

    /// @notice Simplified reserve endpoint — called by MCP tool or Beacon
    function mcpReserve(
        uint256 machineTokenId,
        uint256 slotHours,
        uint64 startTime,
        address renter
    ) external onlyOwner returns (bytes32 rentalId) {
        return createRental(machineTokenId, slotHours, startTime);
    }

    /// @notice Get available time slots for a machine (stub — full impl in Python layer)
    function getAvailableSlots(uint256 machineTokenId) external view returns (uint64[] memory starts, uint64[] memory ends) {
        // Placeholder: returns empty arrays. Real availability computed in Python layer.
        return (new uint64[](0), new uint64[](0));
    }
}
