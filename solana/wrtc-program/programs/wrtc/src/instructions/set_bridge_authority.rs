use anchor_lang::prelude::*;

/// Set a new bridge authority (mint authority) for the wRTC mint.
/// This allows the mint authority to be transferred to a new keypair or multisig.
/// Only the current authority can invoke this instruction.
#[derive(Accounts)]
pub struct SetBridgeAuthority<'info> {
    #[account(mut)]
    pub mint: Account<'info, Mint>,
    #[account(signer)]
    pub current_authority: Account<'info, Signer>,
    pub system_program: Program<'info, System>,
}

/// Update the bridge authority (mint authority) for the wRTC mint.
///
/// # Arguments
/// * `new_authority` - The new public key to set as the mint/bridge authority
///
/// # Security Notes
/// * This instruction should only be called through a governance process (multisig or DAO)
/// * The new authority receives full control over minting and burning wRTC tokens
pub fn set_bridge_authority(ctx: Context<SetBridgeAuthority>, new_authority: Pubkey) -> Result<()> {
    let old_authority = ctx.accounts.mint.mint_authority;
    ctx.accounts.mint.mint_authority = new_authority;
    msg!("Bridge authority updated: {} -> {}", old_authority, new_authority);
    Ok(())
}

use anchor_spl::token::Mint;
