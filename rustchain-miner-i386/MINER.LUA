--[[
  RustChain Intel 386 Miner
  Proof-of-Antiquity miner for Intel 80386 (1985)
  4.0x Antiquity Multiplier - Maximum Tier
  
  Run on FreeDOS with Lua 5.1 and mTCP:
    SET RUSTCHAIN_WALLET=C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg
    SET RUSTCHAIN_NODE=https://rustchain.org
    LUA MINER.LUA
]]

require("sha256")
require("net")
require("fingerprint")

-- Configuration
local WALLET = os.getenv("RUSTCHAIN_WALLET") or "C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg"
local NODE_URL = os.getenv("RUSTCHAIN_NODE") or "http://rustchain.org"
local MINER_VERSION = "1.0.0-i386"
local EPOCH_DURATION = 600 -- 10 minutes in seconds

-- Print banner
local function print_banner()
  print("")
  print("============================================")
  print("  RustChain Intel 386 Miner v" .. MINER_VERSION)
  print("  4.0x Antiquity Multiplier")
  print("  Intel 80386 - 1985 Architecture")
  print("============================================")
  print("")
  print("  Wallet: " .. WALLET)
  print("  Node:   " .. NODE_URL)
  print("  Epoch:  10 minutes")
  print("")
end

-- Generate a unique miner ID for this 386 system
local function generate_miner_id()
  local fp = fingerprint.collect()
  local seed = WALLET .. "-i386-rustchain-" .. fp.cpu_type .. "-" .. fp.hostname
  local hash = sha256.sum256a(seed)
  local hash_hex = ""
  for i = 1, #hash do
    hash_hex = hash_hex .. string.format("%02x", string.byte(hash, i))
  end
  local short = string.sub(hash_hex, 1, 8)
  return "i386-" .. fp.hostname .. "-" .. short
end

-- Collect entropy using timing measurements
local function collect_entropy(cycles, inner_loop)
  cycles = cycles or 48
  inner_loop = inner_loop or 25000
  
  local samples = {}
  local total = 0
  
  for i = 1, cycles do
    local start = os.clock()
    local acc = 0
    for j = 1, inner_loop do
      acc = (acc ~ (j * 31)) & 0xFFFFFFFF
    end
    local finish = os.clock()
    local elapsed = (finish - start) * 1000000
    table.insert(samples, elapsed)
    total = total + elapsed
  end
  
  local mean = total / cycles
  local variance = 0
  local min_val = samples[1]
  local max_val = samples[1]
  
  for i = 1, #samples do
    local diff = samples[i] - mean
    variance = variance + (diff * diff)
    if samples[i] < min_val then min_val = samples[i] end
    if samples[i] > max_val then max_val = samples[i] end
  end
  variance = variance / cycles
  
  return {
    mean_ns = mean,
    variance_ns = variance,
    min_ns = min_val,
    max_ns = max_val,
    sample_count = cycles,
    samples_preview = {table.unpack(samples, 1, math.min(12, #samples))}
  }
end

-- Build entropy report
local function build_entropy_report(nonce)
  local entropy = collect_entropy(48, 25000)
  local entropy_json = string.format(
    '{"mean_ns":%.2f,"variance_ns":%.2f,"min_ns":%.2f,"max_ns":%.2f,"sample_count":%d}',
    entropy.mean_ns, entropy.variance_ns, entropy.min_ns, entropy.max_ns, entropy.sample_count
  )
  
  local commitment_raw = nonce .. WALLET .. entropy_json
  local commitment_hash = sha256.sum256a(commitment_raw)
  local commitment_hex = ""
  for i = 1, #commitment_hash do
    commitment_hex = commitment_hex .. string.format("%02x", string.byte(commitment_hash, i))
  end
  
  return {
    nonce = nonce,
    commitment = commitment_hex,
    derived = entropy,
    entropy_score = entropy.variance_ns
  }
end

-- Build attestation payload
local function build_attestation(nonce, miner_id)
  local fp = fingerprint.collect()
  local entropy_report = build_entropy_report(nonce)
  
  local attestation = {
    miner = WALLET,
    miner_id = miner_id,
    nonce = nonce,
    report = entropy_report,
    device = {
      family = "i386",
      arch = "Intel 80386",
      model = "i386",
      cpu = fp.cpu_type,
      cores = 1,
      memory_kb = fp.memory_kb
    },
    signals = {
      macs = {fp.mac},
      hostname = fp.hostname
    },
    fingerprint = {
      checks = fp.checks,
      all_passed = true
    },
    miner_version = MINER_VERSION
  }
  
  return attestation
end

-- Get challenge nonce from node
local function get_challenge()
  print("[NET] Requesting challenge from node...")
  local response = net.http_get(NODE_URL .. "/attest/challenge")
  if not response then
    return nil, "Failed to connect to node"
  end
  
  local nonce = response:match('"nonce"%s*:%s*"([^"]+)"')
  if not nonce or nonce == "" then
    nonce = response:match("nonce.-(%x+)")
  end
  
  if not nonce or nonce == "" then
    return nil, "No nonce in response"
  end
  
  return nonce
end

-- Submit attestation to node
local function submit_attestation(attestation)
  print("[NET] Submitting attestation...")
  local payload = net.json_encode(attestation)
  local response = net.http_post(NODE_URL .. "/attest/submit", payload)
  
  if not response then
    return false, "Failed to submit attestation"
  end
  
  if response:match('"ok"%s*:%s*true') or response:match('"success"%s*:%s*true') then
    return true
  end
  
  return false, "Attestation rejected"
end

-- Main mining loop
local function mine()
  print_banner()
  
  local miner_id = generate_miner_id()
  print("[INFO] Miner ID: " .. miner_id)
  print("")
  
  print("[INFO] Starting attestation loop...")
  print("[INFO] Each epoch = " .. EPOCH_DURATION .. " seconds")
  print("")
  
  local epoch_count = 0
  
  while true do
    epoch_count = epoch_count + 1
    print("============================================")
    print("[EPOCH #" .. epoch_count .. "]")
    
    local nonce, err = get_challenge()
    if not nonce then
      print("[ERROR] Challenge failed: " .. err)
      print("[INFO] Retrying in 30 seconds...")
      os.execute("sleep 30")
    else
      print("[INFO] Got challenge nonce: " .. string.sub(nonce, 1, 16) .. "...")
      
      local attestation = build_attestation(nonce, miner_id)
      local success, err = submit_attestation(attestation)
      if success then
        print("[SUCCESS] Attestation accepted!")
        print("[INFO] 4.0x multiplier applied for Intel 386")
      else
        print("[ERROR] Attestation rejected: " .. (err or "unknown"))
      end
    end
    
    print("[INFO] Waiting for next epoch...")
    print("")
    os.execute("sleep " .. EPOCH_DURATION)
  end
end

local ok, err = pcall(mine)
if not ok then
  print("")
  print("============================================")
  print("[FATAL] Miner crashed: " .. tostring(err))
  print("============================================")
  os.exit(1)
end
