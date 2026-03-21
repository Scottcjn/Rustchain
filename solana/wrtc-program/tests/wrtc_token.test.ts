import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { Keypair, PublicKey, SystemProgram } from "@solana/web3.js";
import { Token, TOKEN_PROGRAM_ID } from "@solana/spl-token";
import { wrtc_token } from "../target/types/wrtc_token";

describe("wRTC Token", () => {
  // Configure the client to use the local cluster.
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);

  const program = anchor.workspace.wrtc_token as Program<wrtc_token>;

  // Keypairs for testing
  const mintKeypair = Keypair.generate();
  const authorityKeypair = provider.wallet as any;
  const freezeAuthority = Keypair.generate();
  const recipientKeypair = Keypair.generate();
  const holderKeypair = Keypair.generate();

  let mintAddress: PublicKey;
  let recipientTokenAccount: PublicKey;
  let holderTokenAccount: PublicKey;

  const DECIMALS = 6;
  const INITIAL_MINT_AMOUNT = 1000_000_000; // 1000 wRTC (with 6 decimals)
  const TRANSFER_AMOUNT = 100_000_000; // 100 wRTC

  before(async () => {
    // Airdrop SOL to test accounts
    const airdropSig = await provider.connection.requestAirdrop(
      recipientKeypair.publicKey,
      2 * anchor.web3.LAMPORTS_PER_SOL
    );
    await provider.connection.confirmTransaction(airdropSig);

    const airdropSig2 = await provider.connection.requestAirdrop(
      holderKeypair.publicKey,
      2 * anchor.web3.LAMPORTS_PER_SOL
    );
    await provider.connection.confirmTransaction(airdropSig2);
  });

  it("Initialize the wRTC mint", async () => {
    mintAddress = mintKeypair.publicKey;

    console.log("Initializing mint at:", mintAddress.toBase58());

    const tx = await program.methods
      .initialize(DECIMALS)
      .accounts({
        mint: mintAddress,
        mintAuthority: authorityKeypair.publicKey,
        freezeAuthority: freezeAuthority.publicKey,
        systemProgram: SystemProgram.programId,
        tokenProgram: TOKEN_PROGRAM_ID,
      })
      .signers([mintKeypair])
      .rpc();

    console.log("Initialize transaction:", tx);

    // Fetch and verify the mint account
    const mintAccount = await program.account.mint.fetch(mintAddress);
    console.log("Mint decimals:", mintAccount.decimals);
    console.log("Mint authority:", mintAccount.mintAuthority.toBase58());

    anchor.assert(mintAccount.decimals === DECIMALS);
    anchor.assert(mintAccount.mintAuthority.toBase58() === authorityKeypair.publicKey.toBase58());
  });

  it("Create recipient token account", async () => {
    const token = new Token(
      provider.connection,
      mintAddress,
      TOKEN_PROGRAM_ID,
      authorityKeypair
    );

    recipientTokenAccount = await token.createAssociatedTokenAccount(
      recipientKeypair.publicKey
    );

    console.log("Recipient token account:", recipientTokenAccount.toBase58());
  });

  it("Mint wRTC tokens", async () => {
    console.log("Minting to:", recipientTokenAccount.toBase58());

    const tx = await program.methods
      .mint(new anchor.BN(INITIAL_MINT_AMOUNT))
      .accounts({
        mint: mintAddress,
        tokenAccount: recipientTokenAccount,
        authority: authorityKeypair.publicKey,
        tokenProgram: TOKEN_PROGRAM_ID,
      })
      .rpc();

    console.log("Mint transaction:", tx);

    // Verify the balance
    const token = new Token(
      provider.connection,
      mintAddress,
      TOKEN_PROGRAM_ID,
      authorityKeypair
    );
    const balance = await token.getAccountInfo(recipientTokenAccount);
    console.log("Recipient balance:", balance.amount.toString());

    anchor.assert(balance.amount.toString() === INITIAL_MINT_AMOUNT.toString());
  });

  it("Create holder token account and transfer tokens", async () => {
    const token = new Token(
      provider.connection,
      mintAddress,
      TOKEN_PROGRAM_ID,
      authorityKeypair
    );

    holderTokenAccount = await token.createAssociatedTokenAccount(
      holderKeypair.publicKey
    );

    console.log("Holder token account:", holderTokenAccount.toBase58());

    // Transfer tokens to holder
    await token.transfer(
      recipientTokenAccount,
      holderTokenAccount,
      authorityKeypair,
      [],
      TRANSFER_AMOUNT
    );

    console.log("Transferred", TRANSFER_AMOUNT, "wRTC to holder");

    const holderBalance = await token.getAccountInfo(holderTokenAccount);
    console.log("Holder balance:", holderBalance.amount.toString());

    const recipientBalance = await token.getAccountInfo(recipientTokenAccount);
    console.log("Recipient balance after transfer:", recipientBalance.amount.toString());
  });

  it("Burn wRTC tokens from holder", async () => {
    console.log("Burning from:", holderTokenAccount.toBase58());

    const tx = await program.methods
      .burn(new anchor.BN(TRANSFER_AMOUNT))
      .accounts({
        mint: mintAddress,
        tokenAccount: holderTokenAccount,
        authority: authorityKeypair.publicKey,
        tokenProgram: TOKEN_PROGRAM_ID,
      })
      .rpc();

    console.log("Burn transaction:", tx);

    // Verify the balance
    const token = new Token(
      provider.connection,
      mintAddress,
      TOKEN_PROGRAM_ID,
      authorityKeypair
    );
    const balance = await token.getAccountInfo(holderTokenAccount);
    console.log("Holder balance after burn:", balance.amount.toString());

    anchor.assert(balance.amount.toString() === "0");
  });

  it("Set new bridge authority", async () => {
    const newAuthority = Keypair.generate();

    console.log("Current authority:", authorityKeypair.publicKey.toBase58());
    console.log("New authority:", newAuthority.publicKey.toBase58());

    const tx = await program.methods
      .setBridgeAuthority(newAuthority.publicKey)
      .accounts({
        mint: mintAddress,
        currentAuthority: authorityKeypair.publicKey,
        systemProgram: SystemProgram.programId,
      })
      .rpc();

    console.log("Set authority transaction:", tx);

    // Verify the new authority
    const mintAccount = await program.account.mint.fetch(mintAddress);
    console.log("New mint authority:", mintAccount.mintAuthority.toBase58());

    anchor.assert(mintAccount.mintAuthority.toBase58() === newAuthority.publicKey.toBase58());
  });

  it("Verify mint info", async () => {
    const mintAccount = await program.account.mint.fetch(mintAddress);
    console.log("Mint Info:");
    console.log("  decimals:", mintAccount.decimals);
    console.log("  mintAuthority:", mintAccount.mintAuthority.toBase58());
    console.log("  supply:", mintAccount.supply.toString());
    console.log("  freezeAuthority:", mintAccount.freezeAuthority?.toBase58() || "None");

    anchor.assert(mintAccount.decimals === DECIMALS);
  });
});
