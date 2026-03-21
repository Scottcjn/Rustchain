use anchor_lang::prelude::*;
use anchor_spl::token::{Mint, TokenAccount, TokenInterface, MintTo};
use anchor_lang::context::Context;

/// Mint new wRTC tokens to a recipient's token account.
/// Only the mint authority (bridge authority) can invoke this instruction.
#[derive(Accounts)]
pub struct MintTokens<'info> {
    #[account(mut)]
    pub mint: Account<'info, Mint>,
    #[account(mut)]
    pub token_account: Account<'info, TokenAccount>,
    #[account(signer)]
    pub authority: Account<'info, Signer>,
    pub token_program: Interface<'info, TokenInterface>,
}

/// Mint new wRTC tokens to the specified recipient account.
///
/// # Arguments
/// * `amount` - Number of tokens to mint (in smallest unit, considering decimals)
pub fn mint(ctx: Context<MintTokens>, amount: u64) -> Result<()> {
    msg!("Minting {} tokens to {}", amount, ctx.accounts.token_account.key());
    token::mint_to(ctx.accounts.into_mint_to_ctx(), amount)?;
    msg!("Successfully minted {} tokens", amount);
    Ok(())
}

impl<'info> MintTokens<'info> {
    fn into_mint_to_ctx(&self) -> CpiContext<'_, '_, '_, 'info, MintTo<'info>> {
        let cpi_accounts = MintTo {
            mint: self.mint.to_account_info(),
            to: self.token_account.to_account_info(),
            authority: self.authority.to_account_info(),
        };
        CpiContext::new(self.token_program.to_account_info(), cpi_accounts)
    }
}
