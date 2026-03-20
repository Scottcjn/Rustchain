// SPDX-License-Identifier: MIT

use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use std::fs;
use std::process::Command;
use ed25519_dalek::{Keypair, PublicKey, SecretKey, Signature, Signer, Verifier};
use sha2::{Digest, Sha256};
use rand::rngs::OsRng;
use serde::{Deserialize, Serialize};
use serde_json;

const DIFFICULTY_TARGET: u32 = 4;
const BLOCK_REWARD: f64 = 50.0;
const MIN_TRANSACTIONS: usize = 1;
const MAX_TRANSACTIONS: usize = 1000;

#[derive(Serialize, Deserialize, Clone, Debug)]
struct Transaction {
    from_address: String,
    to_address: String,
    amount: f64,
    timestamp: u64,
    signature: String,
    tx_hash: String,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
struct Block {
    index: u64,
    timestamp: u64,
    previous_hash: String,
    merkle_root: String,
    transactions: Vec<Transaction>,
    nonce: u64,
    hash: String,
    miner_address: String,
    difficulty: u32,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
struct Attestation {
    validator_address: String,
    block_hash: String,
    timestamp: u64,
    signature: String,
}

#[derive(Clone)]
struct HardwareInfo {
    cpu_model: String,
    cpu_cores: u32,
    memory_total: u64,
    architecture: String,
    platform: String,
}

struct RustChainMiner {
    keypair: Keypair,
    address: String,
    mining_active: Arc<Mutex<bool>>,
    blockchain: Arc<Mutex<Vec<Block>>>,
    pending_transactions: Arc<Mutex<Vec<Transaction>>>,
    attestations: Arc<Mutex<Vec<Attestation>>>,
    hardware_info: HardwareInfo,
    mining_threads: u32,
}

impl RustChainMiner {
    fn new() -> Result<Self, Box<dyn std::error::Error>> {
        let mut csprng = OsRng {};
        let keypair = Keypair::generate(&mut csprng);
        let address = hex::encode(keypair.public.as_bytes());

        let hardware_info = Self::detect_hardware()?;
        let mining_threads = std::cmp::min(hardware_info.cpu_cores, 8);

        println!("RustChain Miner v2.0 - Native Rust Implementation");
        println!("Miner Address: {}", address);
        println!("Hardware: {} - {} cores", hardware_info.cpu_model, hardware_info.cpu_cores);
        println!("Architecture: {} on {}", hardware_info.architecture, hardware_info.platform);
        println!("Mining Threads: {}", mining_threads);

        let genesis_block = Self::create_genesis_block(&address)?;
        let mut blockchain = vec![genesis_block];

        Ok(RustChainMiner {
            keypair,
            address,
            mining_active: Arc::new(Mutex::new(false)),
            blockchain: Arc::new(Mutex::new(blockchain)),
            pending_transactions: Arc::new(Mutex::new(Vec::new())),
            attestations: Arc::new(Mutex::new(Vec::new())),
            hardware_info,
            mining_threads,
        })
    }

    fn detect_hardware() -> Result<HardwareInfo, Box<dyn std::error::Error>> {
        let cpu_model = Self::get_cpu_info().unwrap_or_else(|| "Unknown CPU".to_string());
        let cpu_cores = num_cpus::get() as u32;
        let memory_total = Self::get_memory_info().unwrap_or(0);
        let architecture = std::env::consts::ARCH.to_string();
        let platform = std::env::consts::OS.to_string();

        Ok(HardwareInfo {
            cpu_model,
            cpu_cores,
            memory_total,
            architecture,
            platform,
        })
    }

    fn get_cpu_info() -> Option<String> {
        #[cfg(target_os = "linux")]
        {
            if let Ok(cpuinfo) = fs::read_to_string("/proc/cpuinfo") {
                for line in cpuinfo.lines() {
                    if line.starts_with("model name") {
                        if let Some(model) = line.split(':').nth(1) {
                            return Some(model.trim().to_string());
                        }
                    }
                }
            }
        }

        #[cfg(target_os = "macos")]
        {
            if let Ok(output) = Command::new("sysctl")
                .arg("-n")
                .arg("machdep.cpu.brand_string")
                .output()
            {
                if let Ok(model) = String::from_utf8(output.stdout) {
                    return Some(model.trim().to_string());
                }
            }
        }

        None
    }

    fn get_memory_info() -> Option<u64> {
        #[cfg(target_os = "linux")]
        {
            if let Ok(meminfo) = fs::read_to_string("/proc/meminfo") {
                for line in meminfo.lines() {
                    if line.starts_with("MemTotal:") {
                        if let Some(mem_str) = line.split_whitespace().nth(1) {
                            if let Ok(mem_kb) = mem_str.parse::<u64>() {
                                return Some(mem_kb * 1024);
                            }
                        }
                    }
                }
            }
        }

        #[cfg(target_os = "macos")]
        {
            if let Ok(output) = Command::new("sysctl")
                .arg("-n")
                .arg("hw.memsize")
                .output()
            {
                if let Ok(mem_str) = String::from_utf8(output.stdout) {
                    if let Ok(mem_bytes) = mem_str.trim().parse::<u64>() {
                        return Some(mem_bytes);
                    }
                }
            }
        }

        None
    }

    fn create_genesis_block(miner_address: &str) -> Result<Block, Box<dyn std::error::Error>> {
        let timestamp = SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs();
        let coinbase_tx = Transaction {
            from_address: "0".repeat(64),
            to_address: miner_address.to_string(),
            amount: BLOCK_REWARD,
            timestamp,
            signature: "genesis".to_string(),
            tx_hash: "genesis_tx".to_string(),
        };

        let transactions = vec![coinbase_tx];
        let merkle_root = Self::calculate_merkle_root(&transactions);

        let mut block = Block {
            index: 0,
            timestamp,
            previous_hash: "0".repeat(64),
            merkle_root,
            transactions,
            nonce: 0,
            hash: String::new(),
            miner_address: miner_address.to_string(),
            difficulty: DIFFICULTY_TARGET,
        };

        block.hash = Self::calculate_block_hash(&block);
        println!("Genesis block created: {}", &block.hash[..16]);
        Ok(block)
    }

    fn calculate_merkle_root(transactions: &[Transaction]) -> String {
        if transactions.is_empty() {
            return "0".repeat(64);
        }

        let mut hashes: Vec<String> = transactions.iter()
            .map(|tx| Self::hash_transaction(tx))
            .collect();

        while hashes.len() > 1 {
            let mut next_level = Vec::new();

            for chunk in hashes.chunks(2) {
                let combined = if chunk.len() == 2 {
                    format!("{}{}", chunk[0], chunk[1])
                } else {
                    format!("{}{}", chunk[0], chunk[0])
                };

                let mut hasher = Sha256::new();
                hasher.update(combined.as_bytes());
                next_level.push(hex::encode(hasher.finalize()));
            }

            hashes = next_level;
        }

        hashes[0].clone()
    }

    fn hash_transaction(tx: &Transaction) -> String {
        let tx_data = format!("{}{}{}{}",
            tx.from_address, tx.to_address, tx.amount, tx.timestamp);
        let mut hasher = Sha256::new();
        hasher.update(tx_data.as_bytes());
        hex::encode(hasher.finalize())
    }

    fn calculate_block_hash(block: &Block) -> String {
        let block_data = format!("{}{}{}{}{}{}{}",
            block.index,
            block.timestamp,
            block.previous_hash,
            block.merkle_root,
            block.nonce,
            block.miner_address,
            block.difficulty
        );
        let mut hasher = Sha256::new();
        hasher.update(block_data.as_bytes());
        hex::encode(hasher.finalize())
    }

    fn meets_difficulty(hash: &str, difficulty: u32) -> bool {
        hash.starts_with(&"0".repeat(difficulty as usize))
    }

    fn mine_block(&self, transactions: Vec<Transaction>) -> Result<Block, Box<dyn std::error::Error>> {
        let blockchain = self.blockchain.lock().unwrap();
        let last_block = blockchain.last().unwrap();
        let index = last_block.index + 1;
        let timestamp = SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs();
        let previous_hash = last_block.hash.clone();
        drop(blockchain);

        let merkle_root = Self::calculate_merkle_root(&transactions);

        let mut block = Block {
            index,
            timestamp,
            previous_hash,
            merkle_root,
            transactions,
            nonce: 0,
            hash: String::new(),
            miner_address: self.address.clone(),
            difficulty: DIFFICULTY_TARGET,
        };

        println!("Mining block #{} with {} transactions...", index, block.transactions.len());
        let start_time = SystemTime::now();
        let mining_active = self.mining_active.clone();

        // Multi-threaded mining
        let found_nonce = Arc::new(Mutex::new(None));
        let mut handles = vec![];

        for thread_id in 0..self.mining_threads {
            let block_clone = block.clone();
            let mining_active_clone = mining_active.clone();
            let found_nonce_clone = found_nonce.clone();

            let handle = thread::spawn(move || {
                let mut nonce = thread_id as u64;
                let mut hash_count = 0u64;

                while *mining_active_clone.lock().unwrap() {
                    if found_nonce_clone.lock().unwrap().is_some() {
                        break;
                    }

                    let mut test_block = block_clone.clone();
                    test_block.nonce = nonce;
                    let hash = Self::calculate_block_hash(&test_block);
                    hash_count += 1;

                    if Self::meets_difficulty(&hash, DIFFICULTY_TARGET) {
                        let mut found = found_nonce_clone.lock().unwrap();
                        if found.is_none() {
                            *found = Some((nonce, hash, hash_count));
                        }
                        break;
                    }

                    nonce += Self::mining_threads as u64;

                    if hash_count % 10000 == 0 {
                        println!("Thread {}: {} hashes, current nonce: {}",
                                thread_id, hash_count, nonce);
                    }
                }
            });

            handles.push(handle);
        }

        // Wait for mining threads
        for handle in handles {
            handle.join().unwrap();
        }

        let found = found_nonce.lock().unwrap();
        if let Some((nonce, hash, hash_count)) = found.as_ref() {
            block.nonce = *nonce;
            block.hash = hash.clone();

            let duration = start_time.elapsed()?.as_secs_f64();
            let hashrate = *hash_count as f64 / duration;

            println!("Block #{} mined! Hash: {}", index, &hash[..16]);
            println!("Nonce: {}, Time: {:.2}s, Hashrate: {:.2} H/s", nonce, duration, hashrate);

            Ok(block)
        } else {
            Err("Mining interrupted".into())
        }
    }

    fn create_coinbase_transaction(&self) -> Transaction {
        let timestamp = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();
        let tx = Transaction {
            from_address: "0".repeat(64),
            to_address: self.address.clone(),
            amount: BLOCK_REWARD,
            timestamp,
            signature: "coinbase".to_string(),
            tx_hash: "coinbase".to_string(),
        };
        tx
    }

    fn create_attestation(&self, block_hash: &str) -> Result<Attestation, Box<dyn std::error::Error>> {
        let timestamp = SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs();
        let message = format!("{}{}{}", self.address, block_hash, timestamp);
        let signature = self.keypair.sign(message.as_bytes());

        Ok(Attestation {
            validator_address: self.address.clone(),
            block_hash: block_hash.to_string(),
            timestamp,
            signature: hex::encode(signature.to_bytes()),
        })
    }

    fn verify_attestation(&self, attestation: &Attestation) -> Result<bool, Box<dyn std::error::Error>> {
        let public_key_bytes = hex::decode(&attestation.validator_address)?;
        let public_key = PublicKey::from_bytes(&public_key_bytes)?;
        let signature_bytes = hex::decode(&attestation.signature)?;
        let signature = Signature::from_bytes(&signature_bytes)?;

        let message = format!("{}{}{}",
            attestation.validator_address,
            attestation.block_hash,
            attestation.timestamp
        );

        match public_key.verify(message.as_bytes(), &signature) {
            Ok(_) => Ok(true),
            Err(_) => Ok(false),
        }
    }

    fn start_mining(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        *self.mining_active.lock().unwrap() = true;
        println!("Starting RustChain mining with {} threads...", self.mining_threads);

        while *self.mining_active.lock().unwrap() {
            let mut transactions = vec![self.create_coinbase_transaction()];

            // Add pending transactions
            let mut pending = self.pending_transactions.lock().unwrap();
            let tx_count = std::cmp::min(pending.len(), MAX_TRANSACTIONS - 1);
            transactions.extend(pending.drain(..tx_count));
            drop(pending);

            if transactions.len() >= MIN_TRANSACTIONS {
                match self.mine_block(transactions) {
                    Ok(block) => {
                        // Create attestation for the block
                        if let Ok(attestation) = self.create_attestation(&block.hash) {
                            self.attestations.lock().unwrap().push(attestation);
                            println!("Created attestation for block #{}", block.index);
                        }

                        self.blockchain.lock().unwrap().push(block);
                        println!("Block added to blockchain");
                    }
                    Err(e) => {
                        println!("Mining error: {}", e);
                        break;
                    }
                }
            }

            thread::sleep(Duration::from_millis(100));
        }

        Ok(())
    }

    fn stop_mining(&mut self) {
        *self.mining_active.lock().unwrap() = false;
        println!("Mining stopped");
    }

    fn get_blockchain_info(&self) -> serde_json::Value {
        let blockchain = self.blockchain.lock().unwrap();
        let attestations = self.attestations.lock().unwrap();
        let pending = self.pending_transactions.lock().unwrap();

        serde_json::json!({
            "chain_length": blockchain.len(),
            "latest_block": blockchain.last().map(|b| &b.hash[..16]).unwrap_or("none"),
            "pending_transactions": pending.len(),
            "attestations": attestations.len(),
            "miner_address": self.address,
            "hardware": {
                "cpu": self.hardware_info.cpu_model,
                "cores": self.hardware_info.cpu_cores,
                "memory": self.hardware_info.memory_total,
                "arch": self.hardware_info.architecture,
                "platform": self.hardware_info.platform
            }
        })
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("RustChain Native Miner - Starting...");

    let mut miner = RustChainMiner::new()?;

    // Display initial blockchain info
    let info = miner.get_blockchain_info();
    println!("Blockchain Info: {}", serde_json::to_string_pretty(&info)?);

    // Start mining in a separate thread for the example
    let mining_handle = {
        let mut miner_clone = miner.clone();
        thread::spawn(move || {
            if let Err(e) = miner_clone.start_mining() {
                eprintln!("Mining error: {}", e);
            }
        })
    };

    // Let it mine for a bit
    thread::sleep(Duration::from_secs(30));

    // Stop mining
    miner.stop_mining();
    mining_handle.join().unwrap();

    // Final blockchain info
    let final_info = miner.get_blockchain_info();
    println!("Final Blockchain Info: {}", serde_json::to_string_pretty(&final_info)?);

    Ok(())
}
