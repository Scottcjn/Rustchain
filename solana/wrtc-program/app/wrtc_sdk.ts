/**
 * wRTC Token SDK - TypeScript SDK for the wRTC SPL Token Program
 * 
 * This SDK provides a convenient interface for interacting with the wRTC
 * (Wrapped RTC) token program on Solana.
 * 
 * @module wrtc_sdk
 */

import {
  Connection,
  PublicKey,
  TransactionInstruction,
  Transaction,
  SystemProgram,
  Keypair,
} from "@solana/web3.js";
import {
  Program,
  AnchorProvider,
  Idl,
  BN,
} from "@coral-xyz/anchor";
import { TOKEN_PROGRAM_ID, Token, AccountInfo } from "@solana/spl-token";
import { wrtc_token, IDL } from "../target/types/wrtc_token";

// Type definitions
export interface MintInfo {
  decimals: number;
  mintAuthority: PublicKey;
  supply: BN;
  freezeAuthority: PublicKey | null;
}

export interface TokenAccountInfo {
  address: PublicKey;
  mint: PublicKey;
  owner: PublicKey;
  amount: BN;
  delegate: PublicKey | null;
  delegatedAmount: BN;
  isInitialized: boolean;
  isFrozen: boolean;
  isNative: boolean;
  rentExemptReserve: BN | null;
  closeAuthority: PublicKey | null;
}

export interface InitializeParams {
  decimals?: number;
  mintAuthority?: PublicKey;
  freezeAuthority?: PublicKey;
}

export interface MintParams {
  amount: number | BN;
  recipient: PublicKey;
}

export interface BurnParams {
  amount: number | BN;
  holder: PublicKey;
}

export interface SetBridgeAuthorityParams {
  newAuthority: PublicKey;
}

export interface TransferParams {
  amount: number | BN;
  from: PublicKey;
  to: PublicKey;
  authority: PublicKey;
}

/**
 * WRTCTokenSDK - TypeScript SDK for the wRTC Token Program
 * 
 * Provides methods for:
 * - Initializing the wRTC mint
 * - Minting new wRTC tokens
 * - Burning wRTC tokens
 * - Setting bridge authority
 * - Getting mint and account info
 * 
 * @example
 * ```typescript
 * const sdk = new WRTCTokenSDK(connection, program);
 * await sdk.initialize({ decimals: 6 });
 * await sdk.mint({ amount: 1000, recipient: recipientPubkey });
 * ```
 */
export class WRTCTokenSDK {
  /** Anchor program instance */
  program: Program<wrtc_token>;
  
  /** Solana connection */
  connection: Connection;
  
  /** wRTC mint address */
  mintAddress: PublicKey;
  
  /** Program ID */
  programId: PublicKey;
  
  /** Token program ID */
  tokenProgramId: PublicKey = TOKEN_PROGRAM_ID;

  /**
   * Create a new WRTCTokenSDK instance
   * 
   * @param connection - Solana connection instance
   * @param program - Anchor program instance (or program ID)
   * @param mintAddress - wRTC mint address (optional, will derive if not provided)
   */
  constructor(
    connection: Connection,
    program: Program<wrtc_token> | PublicKey,
    mintAddress?: PublicKey
  ) {
    this.connection = connection;
    this.programId = program instanceof PublicKey 
      ? program 
      : program.programId;
    this.program = program instanceof PublicKey 
      ? new Program(IDL as Idl, program, new AnchorProvider(connection, {} as any, {}))
      : program;
    this.mintAddress = mintAddress || this.deriveMintAddress();
  }

  /**
   * Derive the wRTC mint address using a program-derived address
   */
  private deriveMintAddress(): PublicKey {
    // For the wRTC program, we use a static mint address
    // In production, this would be the actual deployed mint
    return new PublicKey("wRTC1111111111111111111111111111111111111");
  }

  /**
   * Initialize the wRTC mint
   * 
   * @param params - Initialization parameters
   * @returns Transaction instruction
   * 
   * @example
   * ```typescript
   * const instruction = await sdk.initialize({
   *   decimals: 6,
   *   mintAuthority: myKeypair.publicKey,
   *   freezeAuthority: myKeypair.publicKey,
   * });
   * ```
   */
  async initialize(params: InitializeParams): Promise<TransactionInstruction> {
    const {
      decimals = 6,
      mintAuthority,
      freezeAuthority,
    } = params;

    if (!mintAuthority || !freezeAuthority) {
      throw new Error("mintAuthority and freezeAuthority are required");
    }

    const mintKeypair = Keypair.generate();
    this.mintAddress = mintKeypair.publicKey;

    return this.program.methods
      .initialize(decimals)
      .accounts({
        mint: this.mintAddress,
        mintAuthority,
        freezeAuthority,
        systemProgram: SystemProgram.programId,
        tokenProgram: this.tokenProgramId,
      })
      .instruction();
  }

  /**
   * Initialize and send the transaction
   * 
   * @param params - Initialization parameters
   * @param payer - Payer keypair
   * @returns Transaction signature
   */
  async initializeAndSend(
    params: InitializeParams,
    payer: Keypair
  ): Promise<string> {
    const instruction = await this.initialize(params);
    
    const transaction = new Transaction().add(instruction);
    transaction.feePayer = payer.publicKey;
    
    const signature = await this.connection.sendTransaction(transaction, [payer]);
    await this.connection.confirmTransaction(signature);
    
    return signature;
  }

  /**
   * Mint new wRTC tokens to a recipient
   * 
   * @param params - Mint parameters (amount and recipient)
   * @param authority - Authority signing the transaction (must be mint authority)
   * @returns Transaction signature
   * 
   * @example
   * ```typescript
   * const signature = await sdk.mint({
   *   amount: 1000_000_000, // 1000 wRTC (6 decimals)
   *   recipient: recipientPubkey,
   * }, authorityKeypair);
   * ```
   */
  async mint(params: MintParams, authority: Keypair): Promise<string> {
    const { amount, recipient } = params;
    
    // Get or create the recipient's token account
    const token = new Token(
      this.connection,
      this.mintAddress,
      this.tokenProgramId,
      authority
    );
    
    let recipientTokenAccount: PublicKey;
    try {
      recipientTokenAccount = await token.getAssociatedTokenAddress(recipient);
    } catch {
      recipientTokenAccount = await token.createAssociatedTokenAccount(recipient);
    }

    const tx = await this.program.methods
      .mint(new BN(amount.toString()))
      .accounts({
        mint: this.mintAddress,
        tokenAccount: recipientTokenAccount,
        authority: authority.publicKey,
        tokenProgram: this.tokenProgramId,
      })
      .signers([authority])
      .rpc();

    return tx;
  }

  /**
   * Burn wRTC tokens from a holder
   * 
   * @param params - Burn parameters (amount and holder)
   * @param authority - Authority signing the transaction (must be mint authority)
   * @returns Transaction signature
   * 
   * @example
   * ```typescript
   * const signature = await sdk.burn({
   *   amount: 100_000_000, // 100 wRTC
   *   holder: holderPubkey,
   * }, authorityKeypair);
   * ```
   */
  async burn(params: BurnParams, authority: Keypair): Promise<string> {
    const { amount, holder } = params;
    
    const token = new Token(
      this.connection,
      this.mintAddress,
      this.tokenProgramId,
      authority
    );
    
    const holderTokenAccount = await token.getAssociatedTokenAddress(holder);

    const tx = await this.program.methods
      .burn(new BN(amount.toString()))
      .accounts({
        mint: this.mintAddress,
        tokenAccount: holderTokenAccount,
        authority: authority.publicKey,
        tokenProgram: this.tokenProgramId,
      })
      .signers([authority])
      .rpc();

    return tx;
  }

  /**
   * Set a new bridge authority (mint authority)
   * 
   * @param params - New authority public key
   * @param currentAuthority - Current authority signing the transaction
   * @returns Transaction signature
   * 
   * @example
   * ```typescript
   * const signature = await sdk.setBridgeAuthority({
   *   newAuthority: newAuthorityPubkey,
   * }, currentAuthorityKeypair);
   * ```
   */
  async setBridgeAuthority(
    params: SetBridgeAuthorityParams,
    currentAuthority: Keypair
  ): Promise<string> {
    const { newAuthority } = params;

    const tx = await this.program.methods
      .setBridgeAuthority(newAuthority)
      .accounts({
        mint: this.mintAddress,
        currentAuthority: currentAuthority.publicKey,
        systemProgram: SystemProgram.programId,
      })
      .signers([currentAuthority])
      .rpc();

    return tx;
  }

  /**
   * Transfer wRTC tokens between accounts
   * 
   * @param params - Transfer parameters
   * @param authority - Authority signing the transaction
   * @returns Transaction signature
   */
  async transfer(params: TransferParams, authority: Keypair): Promise<string> {
    const { amount, from, to } = params;
    
    const token = new Token(
      this.connection,
      this.mintAddress,
      this.tokenProgramId,
      authority
    );
    
    const fromTokenAccount = await token.getAssociatedTokenAddress(from);
    const toTokenAccount = await token.getAssociatedTokenAddress(to);

    const tx = await token.transfer(
      fromTokenAccount,
      toTokenAccount,
      authority,
      [],
      new BN(amount.toString())
    );

    return tx;
  }

  /**
   * Get mint information
   * 
   * @returns Mint info including decimals, supply, and authorities
   * 
   * @example
   * ```typescript
   * const info = await sdk.getMintInfo();
   * console.log('Decimals:', info.decimals);
   * console.log('Supply:', info.supply.toString());
   * ```
   */
  async getMintInfo(): Promise<MintInfo> {
    const mintAccount = await this.program.account.mint.fetch(this.mintAddress);
    
    return {
      decimals: mintAccount.decimals,
      mintAuthority: mintAccount.mintAuthority,
      supply: mintAccount.supply,
      freezeAuthority: mintAccount.freezeAuthority,
    };
  }

  /**
   * Get a holder's token balance
   * 
   * @param holder - Holder's public key
   * @returns Token balance (as number, considering decimals)
   * 
   * @example
   * ```typescript
   * const balance = await sdk.getBalance(holderPubkey);
   * console.log('Balance:', balance, 'wRTC');
   * ```
   */
  async getBalance(holder: PublicKey): Promise<number> {
    const token = new Token(
      this.connection,
      this.mintAddress,
      this.tokenProgramId,
      {} as any
    );
    
    try {
      const tokenAccount = await token.getAssociatedTokenAddress(holder);
      const accountInfo = await token.getAccountInfo(tokenAccount);
      
      // Convert from smallest unit to actual tokens
      const mintInfo = await this.getMintInfo();
      const divisor = Math.pow(10, mintInfo.decimals);
      
      return accountInfo.amount.toNumber() / divisor;
    } catch (error) {
      // Token account doesn't exist
      return 0;
    }
  }

  /**
   * Get the associated token account address for a wallet
   * 
   * @param wallet - Wallet public key
   * @returns Associated token account address
   */
  async getTokenAccountAddress(wallet: PublicKey): Promise<PublicKey> {
    const token = new Token(
      this.connection,
      this.mintAddress,
      this.tokenProgramId,
      {} as any
    );
    
    return token.getAssociatedTokenAddress(wallet);
  }

  /**
   * Create an associated token account for a wallet
   * 
   * @param wallet - Wallet public key
   * @param payer - Payer for the transaction
   * @returns Associated token account address
   */
  async createTokenAccount(
    wallet: PublicKey,
    payer: Keypair
  ): Promise<PublicKey> {
    const token = new Token(
      this.connection,
      this.mintAddress,
      this.tokenProgramId,
      payer
    );
    
    return token.createAssociatedTokenAccount(wallet);
  }

  /**
   * Get the program ID
   */
  getProgramId(): PublicKey {
    return this.programId;
  }

  /**
   * Get the mint address
   */
  getMintAddress(): PublicKey {
    return this.mintAddress;
  }
}

// Export factory function for convenience
export function createWRTCTokenSDK(
  connection: Connection,
  programId: PublicKey,
  mintAddress?: PublicKey
): WRTCTokenSDK {
  return new WRTCTokenSDK(connection, programId, mintAddress);
}

// Export IDL and types for external use
export { IDL, wrtc_token };
