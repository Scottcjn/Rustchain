pub mod instructions;

use anchor_lang::prelude::*;

pub use instructions::*;

/// wRTC Token Program - Solana SPL Token for RIP-305
/// 
/// This Anchor program implements the wRTC (Wrapped RTC) SPL token for Phase 1
/// of the cross-chain bridge described in RIP-305.
/// 
/// ## Token Details
/// - Name: "Wrapped RTC"
/// - Symbol: "wRTC"
/// - Decimals: 6 (matches RTC internal precision)
/// - Total Allocation: 30,000 wRTC on Solana
/// - Mint Authority: Elyan Labs multisig (upgradeable to DAO)
/// 
/// ## Program Instructions
/// 1. `initialize` - Initialize the wRTC mint with decimals
/// 2. `mint` - Mint new wRTC tokens (bridge operation)
/// 3. `burn` - Burn wRTC tokens (bridge operation)
/// 4. `set_bridge_authority` - Update the mint/bridge authority
declare_id!("wRTC1111111111111111111111111111111111111");

#[program]
pub mod wrtc_token {
    use super::*;

    /// Initialize the wRTC mint account.
    /// Sets the decimals, mint authority, and freeze authority.
    pub fn initialize(ctx: Context<Initialize>, decimals: u8) -> Result<()> {
        instructions::initialize::initialize(ctx, decimals)
    }

    /// Mint new wRTC tokens to a recipient's token account.
    /// Only the mint authority (bridge authority) can invoke this instruction.
    pub fn mint(ctx: Context<MintTokens>, amount: u64) -> Result<()> {
        instructions::mint::mint(ctx, amount)
    }

    /// Burn wRTC tokens from a holder's token account.
    /// Only the mint authority (bridge authority) can invoke this instruction.
    pub fn burn(ctx: Context<BurnTokens>, amount: u64) -> Result<()> {
        instructions::burn::burn(ctx, amount)
    }

    /// Set a new bridge authority (mint authority) for the wRTC mint.
    /// Only the current authority can invoke this instruction.
    pub fn set_bridge_authority(ctx: Context<SetBridgeAuthority>, new_authority: Pubkey) -> Result<()> {
        instructions::set_bridge_authority::set_bridge_authority(ctx, new_authority)
    }
}
