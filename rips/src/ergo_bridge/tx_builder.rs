use ergo_lib::chain::address::AddressEncoder;
use ergo_lib::chain::ergo_box::box_builder::ErgoBoxCandidateBuilder;
use ergo_lib::chain::transaction::unsigned::UnsignedTransaction;
use ergo_lib::chain::transaction::TxId;
use ergo_lib::ergotree_ir::chain::address::{Address, NetworkPrefix};
use ergo_lib::ergotree_ir::chain::ergo_box::BoxValue;
use ergo_lib::ergotree_ir::chain::token::Token;
use ergo_lib::ergotree_ir::mir::constant::Constant;
use ergo_lib::wallet::box_selector::{BoxSelection, DefaultBoxSelector, SimpleBoxSelector};
use ergo_lib::wallet::tx_builder::TxBuilder;
use anyhow::{Result, Context, ensure};
use uuid::Uuid;
use crate::ergo_bridge::{BridgeRequest, BridgeStatus};

/// Minimum value for an Ergo box to prevent dust (0.001 ERG)
pub const MIN_BOX_VALUE: u64 = 1_000_000;

pub struct ErgoTxBuilder {
    network: NetworkPrefix,
}

impl ErgoTxBuilder {
    pub fn new(is_mainnet: bool) -> Self {
        Self {
            network: if is_mainnet { NetworkPrefix::Mainnet } else { NetworkPrefix::Testnet },
        }
    }

    /// Constructs an unsigned Ergo transaction for the bridge request.
    /// This includes the user's funds and embeds the Rustchain Request ID in R4.
    pub fn build_bridge_tx(
        &self,
        request: &BridgeRequest,
        input_boxes: BoxSelection<ergo_lib::chain::ergo_box::ErgoBox>,
        current_height: u32,
        change_address: Address,
        fee_value: BoxValue,
    ) -> Result<UnsignedTransaction> {
        let amount_nano_ergs = request.amount.0;
        
        // INTEGRITY: MinBoxValue validation (dust protection)
        ensure!(
            amount_nano_ergs >= MIN_BOX_VALUE,
            "Bridge amount {} is below minimum box value (dust protection): {}",
            amount_nano_ergs,
            MIN_BOX_VALUE
        );

        let target_address = AddressEncoder::new(self.network)
            .parse_address_from_str(&request.target_ergo_address)
            .map_err(|e| anyhow::anyhow!("Invalid Ergo address: {}", e))?;

        // 1. Prepare Output Box for the user
        let mut user_box_builder = ErgoBoxCandidateBuilder::new(
            BoxValue::try_from(amount_nano_ergs).context("Invalid amount value")?,
            target_address.script().context("Failed to get script from address")?,
            current_height,
        );

        // 2. Embed Metadata in Registers
        // R4: Rustchain Request ID (UUID as bytes)
        user_box_builder.set_register_value(
            ergo_lib::ergotree_ir::mir::extra_fn::RegisterId::R4,
            Constant::from(request.id.as_bytes().to_vec()),
        );

        // 3. Build the transaction
        let tx_builder = TxBuilder::new(
            input_boxes,
            vec![user_box_builder.build()?],
            current_height,
            fee_value,
            change_address,
        );

        let unsigned_tx = tx_builder.build().context("Failed to build unsigned transaction")?;
        Ok(unsigned_tx)
    }
}
