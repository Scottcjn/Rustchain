use anchor_lang::prelude::*;
use anchor_spl::token::{Mint, TokenInterface};

/// Initialize the wRTC mint account.
/// Sets the decimals, mint authority, and freeze authority.
#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub mint: Account<'info, Mint>,
    pub mint_authority: Signer<'info>,
    pub freeze_authority: Signer<'info>,
    pub system_program: Program<'info, System>,
    pub token_program: Interface<'info, TokenInterface>,
}

/// Initialize the wRTC mint with specified decimals.
/// 
/// # Arguments
/// * `decimals` - Number of decimal places for the token (6 for wRTC, matching RTC internal precision)
pub fn initialize(ctx: Context<Initialize>, decimals: u8) -> Result<()> {
    let mint = &mut ctx.accounts.mint;
    mint.decimals = decimals;
    mint.mint_authority = ctx.accounts.mint_authority.key();
    mint.freeze_authority = Some(ctx.accounts.freeze_authority.key());
    msg!("wRTC mint initialized with decimals: {}, mint_authority: {}", decimals, ctx.accounts.mint_authority.key());
    Ok(())
}
