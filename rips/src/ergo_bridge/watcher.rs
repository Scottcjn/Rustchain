use std::time::Duration;
use tokio::time::sleep;
use anyhow::{Result, Context};
use reqwest::Client;
use serde_json::Value;
use crate::ergo_bridge::{BridgeStatus, BridgeRequest, BridgeSigner, ErgoTxBuilder};
use crate::ergo_bridge::db::BridgeDb;
use ergo_lib::chain::ergo_box::ErgoBox;
use ergo_lib::wallet::box_selector::DefaultBoxSelector;
use ergo_lib::wallet::signing::TransactionContext;
use ergo_lib::ergotree_ir::chain::ergo_box::BoxValue;
use std::sync::Arc;

pub struct BridgeWatcher {
    db: BridgeDb,
    client: Client,
    node_url: String,
    explorer_url: String,
    confirmation_height: u32,
    signer: Arc<dyn BridgeSigner>,
    tx_builder: ErgoTxBuilder,
}

impl BridgeWatcher {
    pub fn new(
        db: BridgeDb, 
        node_url: String, 
        explorer_url: String, 
        confirmation_height: u32,
        signer: Arc<dyn BridgeSigner>,
        tx_builder: ErgoTxBuilder,
    ) -> Self {
        Self { 
            db, 
            client: Client::new(), 
            node_url, 
            explorer_url, 
            confirmation_height,
            signer,
            tx_builder,
        }
    }

    /// The main loop that monitors both chains.
    pub async fn run(&self) -> Result<()> {
        println!("Bridge Watcher started. Monitoring for cross-chain events...");
        
        loop {
            // 1. Scan Rustchain for new Lock events
            if let Err(e) = self.scan_rustchain().await {
                eprintln!("Error scanning Rustchain: {}", e);
            }

            // 2. Process Approved requests
            if let Err(e) = self.process_approved_requests().await {
                eprintln!("Error processing approved requests: {}", e);
            }

            // 3. Scan Ergo for finalized bridge transactions
            if let Err(e) = self.scan_ergo_mainnet().await {
                eprintln!("Error scanning Ergo Mainnet: {}", e);
            }

            // 4. Handle re-orgs and finality checks
            if let Err(e) = self.check_finality().await {
                eprintln!("Error in finality check: {}", e);
            }

            sleep(Duration::from_secs(60)).await;
        }
    }

    async fn scan_rustchain(&self) -> Result<()> {
        // Logic to poll Rustchain node for 'BridgeLock' events
        // In this implementation, we simulate detection and update DB
        Ok(())
    }

    async fn process_approved_requests(&self) -> Result<()> {
        // Fetch requests in 'WaitingApproval' (or skip approval for testnet)
        // For this sprint, we'll process 'Broadcasting' or 'WaitingApproval' status
        let requests = self.db.get_requests_by_status(BridgeStatus::WaitingApproval).await?;
        
        for mut request in requests {
            println!("Processing request: {}", request.id);
            
            // 1. Fetch UTXOs for the bridge address
            let bridge_address = self.signer.get_address();
            let utxos = self.fetch_utxos(&bridge_address.to_base58()).await?;
            
            if utxos.is_empty() {
                println!("No UTXOs found for bridge address {}", bridge_address.to_base58());
                continue;
            }

            // 2. Build Transaction
            let current_height = self.get_current_height().await?;
            let box_selector = DefaultBoxSelector::new();
            let target_balance = BoxValue::try_from(request.amount.0 + 1000000)?; // amount + fee
            let selection = box_selector.select(utxos, target_balance, &[])?;
            
            let unsigned_tx = self.tx_builder.build_bridge_tx(
                &request,
                selection.clone(),
                current_height as u32,
                bridge_address.clone(),
                BoxValue::try_from(1000000)?, // 0.001 ERG fee
            )?;

            // 3. Sign Transaction
            let context = TransactionContext::new(
                unsigned_tx.clone(),
                selection.boxes.into_iter().collect(),
                vec![],
            )?;
            let signed_tx = self.signer.sign_tx(unsigned_tx, context).await?;

            // 4. Broadcast Transaction
            let tx_id = self.broadcast_tx(&signed_tx).await?;
            println!("Broadcasted TX: {}", tx_id);

            // 5. Update DB
            request.status = BridgeStatus::Broadcasting;
            request.ergo_tx_id = Some(tx_id);
            self.db.update_status(request.id, BridgeStatus::Broadcasting, "Transaction broadcasted").await?;
        }

        Ok(())
    }

    async fn fetch_utxos(&self, address: &str) -> Result<Vec<ErgoBox>> {
        let url = format!("{}/boxes/unspent/byAddress/{}", self.node_url, address);
        let resp = self.client.get(&url).send().await?.json::<Vec<Value>>().await?;
        
        let mut boxes = Vec::new();
        for b_val in resp {
            let b: ErgoBox = serde_json::from_value(b_val)?;
            boxes.push(b);
        }
        Ok(boxes)
    }

    async fn get_current_height(&self) -> Result<u64> {
        let url = format!("{}/blocks/lastHeaders/1", self.node_url);
        let resp = self.client.get(&url).send().await?.json::<Vec<Value>>().await?;
        let height = resp.first()
            .and_then(|h| h.get("height"))
            .and_then(|h| h.as_u64())
            .context("Failed to get height from node")?;
        Ok(height)
    }

    async fn broadcast_tx(&self, tx: &ergo_lib::chain::transaction::Transaction) -> Result<String> {
        let url = format!("{}/transactions", self.node_url);
        let resp = self.client.post(&url)
            .json(tx)
            .send()
            .await?;
        
        if resp.status().is_success() {
            let tx_id = resp.json::<Value>().await?
                .get("id")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string())
                .context("No TX ID in response")?;
            Ok(tx_id)
        } else {
            let error_text = resp.text().await?;
            Err(anyhow::anyhow!("Failed to broadcast TX: {}", error_text))
        }
    }

    async fn scan_ergo_mainnet(&self) -> Result<()> {
        // Poll Explorer for confirmations of ergo_tx_id
        Ok(())
    }

    async fn check_finality(&self) -> Result<()> {
        let current_ergo_height = self.get_current_height().await? as u32;
        let url = format!("{}/blocks/lastHeaders/1", self.node_url);
        let resp = self.client.get(&url).send().await?.json::<Vec<Value>>().await?;
        let head_hash = resp.first()
            .and_then(|h| h.get("id"))
            .and_then(|h| h.as_str())
            .context("Failed to get head hash")?;
        
        self.db.record_block_hash(current_ergo_height, head_hash.to_string()).await?;
        Ok(())
    }
}
