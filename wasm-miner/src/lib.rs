use wasm_bindgen::prelude::*;
use rustchain_core::{compute_hash, mine_chunk};

#[wasm_bindgen(start)]
pub fn init() {
    console_error_panic_hook::set_once();
    web_sys::console::log_1(&"RustChain WASM Miner initialized".into());
}

#[wasm_bindgen]
pub fn hash_block(data: &str, nonce: u32) -> String {
    compute_hash(data, nonce as u64)
}

#[wasm_bindgen]
pub fn find_nonce(data: &str, start: u32, difficulty: u32) -> Option<u32> {
    // Run mining in chunks to avoid blocking the JS event loop
    let chunk_size = 10000;
    for batch in 0..100 {
        let start_nonce = (start as u64).wrapping_add(batch * chunk_size);
        if let Some(n) = mine_chunk(data, start_nonce, chunk_size, difficulty as u64) {
            return Some(n as u32);
        }
    }
    None
}
