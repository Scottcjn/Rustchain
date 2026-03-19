// SPDX-License-Identifier: MIT
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH, Duration};
use tokio::sync::RwLock;
use tokio::time::sleep;
use serde_json::Value;
use sha2::{Sha256, Digest};
use ed25519_dalek::{Keypair, Signature, Signer, PUBLIC_KEY_LENGTH, SIGNATURE_LENGTH};
use rand::rngs::OsRng;
use reqwest::Client;
use sysinfo::{System, SystemExt, CpuExt};

const DIFFICULTY_TARGET: u32 = 0x1d00ffff;
const MAX_NONCE: u64 = 0xffffffff;
const MINING_THREADS: usize = 4;

#[derive(Clone)]
struct HardwareInfo {
    cpu_model: String,
    cpu_cores: usize,
    memory_gb: u64,
    hardware_id: String,
}

struct MinerState {
    keypair: Keypair,
    hardware: HardwareInfo,
    node_url: String,
    mining_active: bool,
    blocks_mined: u64,
    total_hashes: u64,
}

struct Block {
    index: u64,
    timestamp: u64,
    transactions: Vec<String>,
    previous_hash: String,
    nonce: u64,
    difficulty: u32,
    miner_pubkey: [u8; PUBLIC_KEY_LENGTH],
    signature: Option<[u8; SIGNATURE_LENGTH]>,
}

impl Block {
    fn calculate_hash(&self) -> Vec<u8> {
        let mut hasher = Sha256::new();
        hasher.update(self.index.to_be_bytes());
        hasher.update(self.timestamp.to_be_bytes());
        hasher.update(self.previous_hash.as_bytes());
        hasher.update(self.nonce.to_be_bytes());
        hasher.update(self.difficulty.to_be_bytes());
        hasher.update(&self.miner_pubkey);
        
        for tx in &self.transactions {
            hasher.update(tx.as_bytes());
        }
        
        hasher.finalize().to_vec()
    }
    
    fn meets_difficulty(&self, target: u32) -> bool {
        let hash = self.calculate_hash();
        let hash_value = u32::from_be_bytes([hash[0], hash[1], hash[2], hash[3]]);
        hash_value < target
    }
}

fn detect_hardware() -> HardwareInfo {
    let mut sys = System::new_all();
    sys.refresh_all();
    
    let cpu_model = sys.global_cpu_info().brand().to_string();
    let cpu_cores = sys.cpus().len();
    let memory_gb = sys.total_memory() / 1024 / 1024 / 1024;
    
    let mut hasher = Sha256::new();
    hasher.update(cpu_model.as_bytes());
    hasher.update(cpu_cores.to_be_bytes());
    hasher.update(memory_gb.to_be_bytes());
    
    let hardware_id = format!("{:x}", hasher.finalize());
    
    HardwareInfo {
        cpu_model,
        cpu_cores,
        memory_gb,
        hardware_id: hardware_id[..16].to_string(),
    }
}

fn generate_keypair() -> Keypair {
    let mut csprng = OsRng{};
    Keypair::generate(&mut csprng)
}

async fn fetch_pending_transactions(client: &Client, node_url: &str) -> Vec<String> {
    match client.get(&format!("{}/api/mempool", node_url)).send().await {
        Ok(response) => {
            if let Ok(data) = response.json::<Value>().await {
                if let Some(txs) = data["transactions"].as_array() {
                    return txs.iter()
                        .filter_map(|tx| tx.as_str().map(|s| s.to_string()))
                        .take(100)
                        .collect();
                }
            }
        }
        Err(_) => {}
    }
    vec![]
}

async fn get_latest_block_info(client: &Client, node_url: &str) -> (u64, String, u32) {
    match client.get(&format!("{}/api/latest", node_url)).send().await {
        Ok(response) => {
            if let Ok(data) = response.json::<Value>().await {
                let index = data["index"].as_u64().unwrap_or(0) + 1;
                let hash = data["hash"].as_str().unwrap_or("0").to_string();
                let difficulty = data["difficulty"].as_u64().unwrap_or(DIFFICULTY_TARGET as u64) as u32;
                return (index, hash, difficulty);
            }
        }
        Err(_) => {}
    }
    (1, "0".to_string(), DIFFICULTY_TARGET)
}

fn mine_block(mut block: Block, difficulty: u32) -> Option<Block> {
    for nonce in 0..MAX_NONCE {
        block.nonce = nonce;
        if block.meets_difficulty(difficulty) {
            return Some(block);
        }
    }
    None
}

async fn submit_block(client: &Client, node_url: &str, block: &Block) -> bool {
    let block_data = serde_json::json!({
        "index": block.index,
        "timestamp": block.timestamp,
        "transactions": block.transactions,
        "previous_hash": block.previous_hash,
        "nonce": block.nonce,
        "difficulty": block.difficulty,
        "miner_pubkey": hex::encode(&block.miner_pubkey),
        "signature": block.signature.map(|s| hex::encode(&s))
    });
    
    match client.post(&format!("{}/api/submit_block", node_url))
        .json(&block_data)
        .send().await {
        Ok(response) => response.status().is_success(),
        Err(_) => false,
    }
}

async fn generate_attestation(state: &MinerState) -> HashMap<String, Value> {
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();
    
    let mut attestation = HashMap::new();
    attestation.insert("miner_id".to_string(), 
        Value::String(hex::encode(&state.keypair.public.to_bytes())));
    attestation.insert("hardware_id".to_string(), 
        Value::String(state.hardware.hardware_id.clone()));
    attestation.insert("cpu_model".to_string(), 
        Value::String(state.hardware.cpu_model.clone()));
    attestation.insert("cpu_cores".to_string(), 
        Value::Number(state.hardware.cpu_cores.into()));
    attestation.insert("memory_gb".to_string(), 
        Value::Number(state.hardware.memory_gb.into()));
    attestation.insert("timestamp".to_string(), 
        Value::Number(timestamp.into()));
    attestation.insert("blocks_mined".to_string(), 
        Value::Number(state.blocks_mined.into()));
    attestation.insert("total_hashes".to_string(), 
        Value::Number(state.total_hashes.into()));
    
    let message = serde_json::to_string(&attestation).unwrap();
    let signature = state.keypair.sign(message.as_bytes());
    attestation.insert("signature".to_string(), 
        Value::String(hex::encode(&signature.to_bytes())));
    
    attestation
}

async fn submit_attestation(client: &Client, node_url: &str, attestation: &HashMap<String, Value>) -> bool {
    match client.post(&format!("{}/api/attestation", node_url))
        .json(attestation)
        .send().await {
        Ok(response) => response.status().is_success(),
        Err(_) => false,
    }
}

async fn mining_worker(state: Arc<RwLock<MinerState>>) {
    let client = Client::new();
    
    loop {
        let (node_url, keypair, should_mine) = {
            let s = state.read().await;
            (s.node_url.clone(), s.keypair, s.mining_active)
        };
        
        if !should_mine {
            sleep(Duration::from_secs(1)).await;
            continue;
        }
        
        let transactions = fetch_pending_transactions(&client, &node_url).await;
        let (index, prev_hash, difficulty) = get_latest_block_info(&client, &node_url).await;
        
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();
        
        let mut block = Block {
            index,
            timestamp,
            transactions,
            previous_hash: prev_hash,
            nonce: 0,
            difficulty,
            miner_pubkey: keypair.public.to_bytes(),
            signature: None,
        };
        
        if let Some(mined_block) = mine_block(block, difficulty) {
            let hash = mined_block.calculate_hash();
            let signature = keypair.sign(&hash);
            
            let mut final_block = mined_block;
            final_block.signature = Some(signature.to_bytes());
            
            if submit_block(&client, &node_url, &final_block).await {
                let mut s = state.write().await;
                s.blocks_mined += 1;
                s.total_hashes += final_block.nonce;
                println!("Block {} mined successfully!", final_block.index);
            }
        }
        
        sleep(Duration::from_millis(100)).await;
    }
}

async fn attestation_worker(state: Arc<RwLock<MinerState>>) {
    let client = Client::new();
    
    loop {
        let attestation = {
            let s = state.read().await;
            if !s.mining_active {
                sleep(Duration::from_secs(30)).await;
                continue;
            }
            generate_attestation(&*s).await
        };
        
        let node_url = {
            let s = state.read().await;
            s.node_url.clone()
        };
        
        submit_attestation(&client, &node_url, &attestation).await;
        sleep(Duration::from_secs(300)).await;
    }
}

#[tokio::main]
async fn main() {
    println!("RustChain Miner v2.0");
    
    let hardware = detect_hardware();
    println!("Hardware detected: {} cores, {}GB RAM", 
        hardware.cpu_cores, hardware.memory_gb);
    
    let keypair = generate_keypair();
    println!("Miner ID: {}", hex::encode(&keypair.public.to_bytes()));
    
    let state = Arc::new(RwLock::new(MinerState {
        keypair,
        hardware,
        node_url: "http://localhost:5000".to_string(),
        mining_active: true,
        blocks_mined: 0,
        total_hashes: 0,
    }));
    
    let mining_handle = tokio::spawn(mining_worker(state.clone()));
    let attestation_handle = tokio::spawn(attestation_worker(state.clone()));
    
    tokio::select! {
        _ = mining_handle => {},
        _ = attestation_handle => {},
    }
}