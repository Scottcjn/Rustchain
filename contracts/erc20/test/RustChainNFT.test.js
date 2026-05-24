const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("RustChainNFT", function () {
  let nft;
  let owner;
  let minter;
  let collector;
  let recipient;
  let other;

  const FIRST_URI = "ipfs://rustchain/relic-1.json";
  const UPDATED_URI = "ipfs://rustchain/relic-1-v2.json";

  beforeEach(async function () {
    [owner, minter, collector, recipient, other] = await ethers.getSigners();

    const RustChainNFT = await ethers.getContractFactory("RustChainNFT");
    nft = await RustChainNFT.deploy(minter.address);
    await nft.waitForDeployment();
  });

  describe("Deployment", function () {
    it("sets the ERC-721 collection name and symbol", async function () {
      expect(await nft.name()).to.equal("RustChain Relic NFT");
      expect(await nft.symbol()).to.equal("RCNFT");
    });

    it("starts token ids at 1 and grants the initial minter", async function () {
      expect(await nft.nextTokenId()).to.equal(1);
      expect(await nft.nftMinters(minter.address)).to.equal(true);
      expect(await nft.owner()).to.equal(owner.address);
    });
  });

  describe("Minting and metadata", function () {
    it("allows the owner to mint an NFT with metadata", async function () {
      await expect(nft.mint(collector.address, FIRST_URI))
        .to.emit(nft, "MetadataUpdated")
        .withArgs(1, FIRST_URI);

      expect(await nft.ownerOf(1)).to.equal(collector.address);
      expect(await nft.tokenURI(1)).to.equal(FIRST_URI);
      expect(await nft.nextTokenId()).to.equal(2);
    });

    it("allows an approved minter to mint an NFT", async function () {
      await nft.connect(minter).mint(collector.address, FIRST_URI);

      expect(await nft.ownerOf(1)).to.equal(collector.address);
      expect(await nft.tokenURI(1)).to.equal(FIRST_URI);
    });

    it("rejects minting by unapproved accounts", async function () {
      await expect(
        nft.connect(other).mint(collector.address, FIRST_URI)
      ).to.be.revertedWith("RustChainNFT: Not authorized to mint");
    });

    it("requires a recipient and metadata URI", async function () {
      await expect(nft.mint(ethers.ZeroAddress, FIRST_URI)).to.be.revertedWith(
        "RustChainNFT: Mint to zero address"
      );

      await expect(nft.mint(collector.address, "")).to.be.revertedWith(
        "RustChainNFT: Metadata URI required"
      );
    });

    it("allows authorized metadata updates", async function () {
      await nft.mint(collector.address, FIRST_URI);

      await expect(nft.connect(minter).setTokenURI(1, UPDATED_URI))
        .to.emit(nft, "MetadataUpdated")
        .withArgs(1, UPDATED_URI);

      expect(await nft.tokenURI(1)).to.equal(UPDATED_URI);
    });

    it("rejects unauthorized metadata updates", async function () {
      await nft.mint(collector.address, FIRST_URI);

      await expect(
        nft.connect(other).setTokenURI(1, UPDATED_URI)
      ).to.be.revertedWith("RustChainNFT: Not authorized to update metadata");
    });
  });

  describe("ERC-721 transfers", function () {
    beforeEach(async function () {
      await nft.mint(collector.address, FIRST_URI);
    });

    it("allows the owner to transfer an NFT", async function () {
      await nft.connect(collector).transferFrom(collector.address, recipient.address, 1);

      expect(await nft.ownerOf(1)).to.equal(recipient.address);
    });

    it("allows approved operators to transfer an NFT", async function () {
      await nft.connect(collector).approve(other.address, 1);
      await nft.connect(other).transferFrom(collector.address, recipient.address, 1);

      expect(await nft.ownerOf(1)).to.equal(recipient.address);
    });
  });

  describe("Minter management and pause", function () {
    it("lets the owner add and remove NFT minters", async function () {
      await expect(nft.addNFTMinter(other.address))
        .to.emit(nft, "NFTMinterAdded")
        .withArgs(other.address);

      expect(await nft.nftMinters(other.address)).to.equal(true);

      await expect(nft.removeNFTMinter(other.address))
        .to.emit(nft, "NFTMinterRemoved")
        .withArgs(other.address);

      expect(await nft.nftMinters(other.address)).to.equal(false);
    });

    it("rejects minter management by non-owners", async function () {
      await expect(
        nft.connect(other).addNFTMinter(recipient.address)
      ).to.be.revertedWithCustomError(nft, "OwnableUnauthorizedAccount");
    });

    it("blocks minting and transfers while paused", async function () {
      await nft.mint(collector.address, FIRST_URI);
      await nft.pause();

      await expect(nft.mint(collector.address, UPDATED_URI)).to.be.revertedWithCustomError(
        nft,
        "EnforcedPause"
      );

      await expect(
        nft.connect(collector).transferFrom(collector.address, recipient.address, 1)
      ).to.be.revertedWithCustomError(nft, "EnforcedPause");
    });
  });
});
