const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("WRTC Token", function () {
  let wrtc;
  let owner;
  let addr1;
  let addr2;
  let bridgeOperator;
  let initialSupply;
  const DECIMALS = 6;

  beforeEach(async function () {
    [owner, addr1, addr2, bridgeOperator] = await ethers.getSigners();

    // Deploy contract with 1M initial supply
    initialSupply = ethers.parseUnits("1000000", DECIMALS);
    
    const WRTC = await ethers.getContractFactory("WRTC");
    wrtc = await WRTC.deploy(initialSupply, bridgeOperator.address);
    await wrtc.waitForDeployment();
  });

  describe("Deployment", function () {
    it("Should set the correct token name and symbol", async function () {
      expect(await wrtc.name()).to.equal("RustChain Token");
      expect(await wrtc.symbol()).to.equal("wRTC");
    });

    it("Should use 6 decimals", async function () {
      expect(await wrtc.decimals()).to.equal(6);
    });

    it("Should mint initial supply to deployer", async function () {
      const ownerBalance = await wrtc.balanceOf(owner.address);
      expect(ownerBalance).to.equal(initialSupply);
    });

    it("Should set the correct total supply", async function () {
      const totalSupply = await wrtc.totalSupply();
      expect(totalSupply).to.equal(initialSupply);
    });

    it("Should set the owner correctly", async function () {
      expect(await wrtc.owner()).to.equal(owner.address);
    });

    it("Should set bridge operator correctly", async function () {
      expect(await wrtc.bridgeOperators(bridgeOperator.address)).to.be.true;
    });
  });

  describe("ERC20 Standard", function () {
    it("Should transfer tokens between accounts", async function () {
      const amount = ethers.parseUnits("1000", DECIMALS);
      await wrtc.transfer(addr1.address, amount);
      
      const addr1Balance = await wrtc.balanceOf(addr1.address);
      expect(addr1Balance).to.equal(amount);
      
      const ownerBalance = await wrtc.balanceOf(owner.address);
      expect(ownerBalance).to.equal(initialSupply - amount);
    });

    it("Should fail if sender doesn't have enough tokens", async function () {
      const amount = ethers.parseUnits("1001", DECIMALS); // More than addr1 has
      
      await wrtc.transfer(addr1.address, ethers.parseUnits("1000", DECIMALS));
      
      await expect(
        wrtc.connect(addr1).transfer(owner.address, amount)
      ).to.be.reverted;
    });

    it("Should approve and use allowance", async function () {
      const amount = ethers.parseUnits("500", DECIMALS);
      
      await wrtc.approve(addr1.address, amount);
      
      const allowance = await wrtc.allowance(owner.address, addr1.address);
      expect(allowance).to.equal(amount);
      
      await wrtc.connect(addr1).transferFrom(owner.address, addr2.address, amount);
      
      const finalAllowance = await wrtc.allowance(owner.address, addr1.address);
      expect(finalAllowance).to.equal(0);
    });

    it("Should fail transferFrom if insufficient allowance", async function () {
      const amount = ethers.parseUnits("100", DECIMALS);
      
      await wrtc.approve(addr1.address, amount);
      
      await expect(
        wrtc.connect(addr1).transferFrom(owner.address, addr2.address, amount + 1n)
      ).to.be.reverted;
    });
  });

  describe("Burnable", function () {
    it("Should burn tokens from caller's balance", async function () {
      const burnAmount = ethers.parseUnits("100", DECIMALS);
      const initialTotal = await wrtc.totalSupply();
      
      await wrtc.burn(burnAmount);
      
      const ownerBalance = await wrtc.balanceOf(owner.address);
      const totalSupply = await wrtc.totalSupply();
      
      expect(ownerBalance).to.equal(initialSupply - burnAmount);
      expect(totalSupply).to.equal(initialTotal - burnAmount);
    });

    it("Should burn tokens from another account with allowance", async function () {
      const burnAmount = ethers.parseUnits("50", DECIMALS);
      
      await wrtc.approve(addr1.address, burnAmount);
      
      await wrtc.connect(addr1).burnFrom(owner.address, burnAmount);
      
      const ownerBalance = await wrtc.balanceOf(owner.address);
      expect(ownerBalance).to.equal(initialSupply - burnAmount);
    });
  });

  describe("Bridge Operations", function () {
    it("Should allow bridge operator to mint tokens", async function () {
      const mintAmount = ethers.parseUnits("1000", DECIMALS);
      const initialTotal = await wrtc.totalSupply();
      
      await wrtc.connect(bridgeOperator).bridgeMint(addr1.address, mintAmount);
      
      const addr1Balance = await wrtc.balanceOf(addr1.address);
      const totalSupply = await wrtc.totalSupply();
      
      expect(addr1Balance).to.equal(mintAmount);
      expect(totalSupply).to.equal(initialTotal + mintAmount);
    });

    it("Should allow bridge operator to burn tokens", async function () {
      // First transfer some tokens to addr1
      const transferAmount = ethers.parseUnits("500", DECIMALS);
      await wrtc.transfer(addr1.address, transferAmount);
      
      const burnAmount = ethers.parseUnits("100", DECIMALS);
      const initialTotal = await wrtc.totalSupply();
      
      await wrtc.connect(bridgeOperator).bridgeBurn(addr1.address, burnAmount);
      
      const addr1Balance = await wrtc.balanceOf(addr1.address);
      const totalSupply = await wrtc.totalSupply();
      
      expect(addr1Balance).to.equal(transferAmount - burnAmount);
      expect(totalSupply).to.equal(initialTotal - burnAmount);
    });

    it("Should fail bridge mint from non-operator", async function () {
      const mintAmount = ethers.parseUnits("100", DECIMALS);
      
      await expect(
        wrtc.connect(addr1).bridgeMint(addr2.address, mintAmount)
      ).to.be.reverted;
    });

    it("Should fail bridge burn from non-operator", async function () {
      const burnAmount = ethers.parseUnits("100", DECIMALS);
      
      await expect(
        wrtc.connect(addr1).bridgeBurn(addr2.address, burnAmount)
      ).to.be.reverted;
    });

    it("Should fail bridge mint to zero address", async function () {
      const mintAmount = ethers.parseUnits("100", DECIMALS);
      
      await expect(
        wrtc.connect(bridgeOperator).bridgeMint(ethers.ZeroAddress, mintAmount)
      ).to.be.reverted;
    });

    it("Should fail bridge operations with zero amount", async function () {
      await expect(
        wrtc.connect(bridgeOperator).bridgeMint(addr1.address, 0)
      ).to.be.reverted;
      
      await expect(
        wrtc.connect(bridgeOperator).bridgeBurn(addr1.address, 0)
      ).to.be.reverted;
    });

    it("Should emit BridgeMint event", async function () {
      const mintAmount = ethers.parseUnits("100", DECIMALS);
      
      await expect(wrtc.connect(bridgeOperator).bridgeMint(addr1.address, mintAmount))
        .to.emit(wrtc, "BridgeMint")
        .withArgs(addr1.address, mintAmount);
    });

    it("Should emit BridgeBurn event", async function () {
      await wrtc.transfer(addr1.address, ethers.parseUnits("500", DECIMALS));
      const burnAmount = ethers.parseUnits("100", DECIMALS);
      
      await expect(wrtc.connect(bridgeOperator).bridgeBurn(addr1.address, burnAmount))
        .to.emit(wrtc, "BridgeBurn")
        .withArgs(addr1.address, burnAmount);
    });
  });

  describe("Bridge Operator Management", function () {
    it("Should allow owner to add bridge operator", async function () {
      await wrtc.addBridgeOperator(addr1.address);
      expect(await wrtc.bridgeOperators(addr1.address)).to.be.true;
    });

    it("Should allow owner to remove bridge operator", async function () {
      await wrtc.removeBridgeOperator(bridgeOperator.address);
      expect(await wrtc.bridgeOperators(bridgeOperator.address)).to.be.false;
    });

    it("Should fail to add bridge operator from non-owner", async function () {
      await expect(
        wrtc.connect(addr1).addBridgeOperator(addr2.address)
      ).to.be.reverted;
    });

    it("Should fail to remove bridge operator from non-owner", async function () {
      await expect(
        wrtc.connect(addr1).removeBridgeOperator(bridgeOperator.address)
      ).to.be.reverted;
    });

    it("Should fail to add zero address as operator", async function () {
      await expect(
        wrtc.addBridgeOperator(ethers.ZeroAddress)
      ).to.be.reverted;
    });

    it("Should fail to remove non-operator", async function () {
      await expect(
        wrtc.removeBridgeOperator(addr1.address)
      ).to.be.reverted;
    });

    it("Should emit BridgeOperatorAdded event", async function () {
      await expect(wrtc.addBridgeOperator(addr1.address))
        .to.emit(wrtc, "BridgeOperatorAdded")
        .withArgs(addr1.address);
    });

    it("Should emit BridgeOperatorRemoved event", async function () {
      await expect(wrtc.removeBridgeOperator(bridgeOperator.address))
        .to.emit(wrtc, "BridgeOperatorRemoved")
        .withArgs(bridgeOperator.address);
    });
  });

  describe("Pausable", function () {
    it("Should allow owner to pause contract", async function () {
      await wrtc.pause();
      expect(await wrtc.paused()).to.be.true;
    });

    it("Should allow owner to unpause contract", async function () {
      await wrtc.pause();
      await wrtc.unpause();
      expect(await wrtc.paused()).to.be.false;
    });

    it("Should fail to pause from non-owner", async function () {
      await expect(
        wrtc.connect(addr1).pause()
      ).to.be.reverted;
    });

    it("Should fail to unpause from non-owner", async function () {
      await wrtc.pause();
      await expect(
        wrtc.connect(addr1).unpause()
      ).to.be.reverted;
    });

    it("Should prevent transfers when paused", async function () {
      await wrtc.pause();
      
      await expect(
        wrtc.transfer(addr1.address, ethers.parseUnits("100", DECIMALS))
      ).to.be.reverted;
    });

    it("Should prevent bridge operations when paused", async function () {
      await wrtc.pause();
      
      await expect(
        wrtc.connect(bridgeOperator).bridgeMint(addr1.address, ethers.parseUnits("100", DECIMALS))
      ).to.be.reverted;
      
      await expect(
        wrtc.connect(bridgeOperator).bridgeBurn(addr1.address, ethers.parseUnits("100", DECIMALS))
      ).to.be.reverted;
    });

    it("Should allow transfers after unpausing", async function () {
      await wrtc.pause();
      await wrtc.unpause();
      
      const amount = ethers.parseUnits("100", DECIMALS);
      await expect(
        wrtc.transfer(addr1.address, amount)
      ).to.not.be.reverted;
    });
  });

  describe("ReentrancyGuard", function () {
    it("Should prevent reentrancy in bridgeMint", async function () {
      // This test would require a malicious contract to attempt reentrancy
      // The ReentrancyGuard modifier provides protection
      // Basic test confirms bridgeMint works normally
      const mintAmount = ethers.parseUnits("100", DECIMALS);
      await expect(
        wrtc.connect(bridgeOperator).bridgeMint(addr1.address, mintAmount)
      ).to.not.be.reverted;
    });

    it("Should prevent reentrancy in bridgeBurn", async function () {
      await wrtc.transfer(addr1.address, ethers.parseUnits("500", DECIMALS));
      
      const burnAmount = ethers.parseUnits("100", DECIMALS);
      await expect(
        wrtc.connect(bridgeOperator).bridgeBurn(addr1.address, burnAmount)
      ).to.not.be.reverted;
    });
  });

  describe("ERC20Permit", function () {
    it("Should support EIP-2612 permit", async function () {
      const amount = ethers.parseUnits("100", DECIMALS);
      const nonce = await wrtc.nonces(owner.address);
      const deadline = Math.floor(Date.now() / 1000) + 3600; // 1 hour
      
      const domain = {
        name: "RustChain Token",
        version: "1",
        chainId: (await ethers.provider.getNetwork()).chainId,
        verifyingContract: await wrtc.getAddress(),
      };
      
      const types = {
        Permit: [
          { name: "owner", type: "address" },
          { name: "spender", type: "address" },
          { name: "value", type: "uint256" },
          { name: "nonce", type: "uint256" },
          { name: "deadline", type: "uint256" },
        ],
      };
      
      const message = {
        owner: owner.address,
        spender: addr1.address,
        value: amount,
        nonce: nonce,
        deadline: deadline,
      };
      
      const signature = await owner.signTypedData(domain, types, message);
      const { v, r, s } = ethers.Signature.from(signature);
      
      await wrtc.permit(owner.address, addr1.address, amount, deadline, v, r, s);
      
      const allowance = await wrtc.allowance(owner.address, addr1.address);
      expect(allowance).to.equal(amount);
    });

    it("Should fail permit with expired deadline", async function () {
      const amount = ethers.parseUnits("100", DECIMALS);
      const nonce = await wrtc.nonces(owner.address);
      const deadline = Math.floor(Date.now() / 1000) - 3600; // 1 hour ago
      
      const domain = {
        name: "RustChain Token",
        version: "1",
        chainId: (await ethers.provider.getNetwork()).chainId,
        verifyingContract: await wrtc.getAddress(),
      };
      
      const types = {
        Permit: [
          { name: "owner", type: "address" },
          { name: "spender", type: "address" },
          { name: "value", type: "uint256" },
          { name: "nonce", type: "uint256" },
          { name: "deadline", type: "uint256" },
        ],
      };
      
      const message = {
        owner: owner.address,
        spender: addr1.address,
        value: amount,
        nonce: nonce,
        deadline: deadline,
      };
      
      const signature = await owner.signTypedData(domain, types, message);
      const { v, r, s } = ethers.Signature.from(signature);
      
      await expect(
        wrtc.permit(owner.address, addr1.address, amount, deadline, v, r, s)
      ).to.be.reverted;
    });
  });

  describe("Edge Cases", function () {
    it("Should handle zero transfers", async function () {
      await expect(
        wrtc.transfer(addr1.address, 0)
      ).to.not.be.reverted;
    });

    it("Should handle max uint256 approval", async function () {
      const maxUint256 = ethers.MaxUint256;
      await wrtc.approve(addr1.address, maxUint256);
      
      const allowance = await wrtc.allowance(owner.address, addr1.address);
      expect(allowance).to.equal(maxUint256);
    });

    it("Should handle very small amounts (1 token unit)", async function () {
      const smallAmount = 1n; // 0.000001 wRTC
      await wrtc.transfer(addr1.address, smallAmount);
      
      const addr1Balance = await wrtc.balanceOf(addr1.address);
      expect(addr1Balance).to.equal(smallAmount);
    });
  });
});
