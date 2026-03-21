use anchor_lang::prelude::*;
use anchor_spl::token::{Mint, TokenAccount, TokenInterface, Burn};
use anchor_lang::context::CpiContext;

/// Burn wRTC tokens from a holder's token account.
/// Only the mint authority (bridge authority) can invoke this instruction.
#[derive(Accounts)]
pub struct BurnTokens<'info> {
    #[account(mut)]
    pub mint: Account<'info, Mint>,
    #[account(mut)]
    pub token_account: Account<'info, TokenAccount>,
    #[account(signer)]
    pub authority: Account<'info, Signer>,
    pub token_program: Interface<'info, TokenInterface>,
}

/// Burn wRTC tokens from the specified holder account.
///
/// # Arguments
/// * `amount` - Number of tokens to burn (in smallest unit, considering decimals)
pub fn burn(ctx: Context<BurnTokens>, amount: u64) -> Result<()> {
    msg!("Burning {} tokens from {}", amount, ctx.accounts.token_account.key());
    token::burn(ctx.accounts.into_burn_ctx(), amount)?;
    msg!("Successfully burned {} tokens", amount);
    Ok(())
}

impl<'info> BurnTokens<'info> {
    fn into_burn_ctx(&self) -> CpiContext<'_, '_, '_, 'info, Burn<'info>> {
        let cpi_accounts = Burn {
            mint: self.mint.to_account_info(),
            from: self.token_account.to_account_info(),
            authority: self.authority.to_account_info(),
        };
        CpiContext::new(self.token_program.to_account_info(), cpi_accounts)
    }
}
