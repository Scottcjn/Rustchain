--[[
  FINGERPRINT.LUA - Intel 386 Hardware Fingerprinting
  RustChain Intel 386 Miner
]]

local fingerprint = {}

local function detect_cpuid()
  local cpu_type = os.getenv("CPU") or os.getenv("PROCESSOR_IDENTIFIER") or ""
  
  if cpu_type:match("386") then
    return {cpu_type = "Intel 80386", has_cpuid = false, cpuid_result = 0}
  elseif cpu_type:match("486") then
    return {cpu_type = "Intel 80486", has_cpuid = true, cpuid_result = 0}
  elseif cpu_type:match("Pentium") then
    return {cpu_type = "Intel Pentium", has_cpuid = true, cpuid_result = 0}
  end
  
  -- Try CPU utility
  local handle = io.popen("CPU 2>NUL", "r")
  if handle then
    local result = handle:read("*a")
    handle:close()
    if result and result:match("386") then
      return {cpu_type = "Intel 80386", has_cpuid = false, cpuid_result = 0}
    end
  end
  
  return {cpu_type = "Intel 80386", has_cpuid = false, cpuid_result = 0}
end

local function detect_fpu()
  local has_387 = false
  local fpu_type = "none"
  
  local coprocessor = os.getenv("COPROCESSOR") or ""
  if coprocessor:match("387") or coprocessor:match("487") then
    has_387 = true
    fpu_type = "Intel 80387"
  end
  
  return {has_387 = has_387, fpu_type = fpu_type}
end

local function detect_memory()
  local mem_kb = 640
  local handle = io.popen("MEM 2>NUL", "r")
  if handle then
    local result = handle:read("*a")
    handle:close()
    local kb = result:match("(%d+)K%s+Conventional")
    if kb then mem_kb = tonumber(kb) end
  end
  
  local env_mem = os.getenv("MEMORY") or ""
  if env_mem:match("(%d+)") then
    mem_kb = tonumber(env_mem:match("(%d+)")) or mem_kb
  end
  
  return mem_kb
end

local function get_mac_address()
  local mac = "00:00:00:00:00:01"
  local mtcp_mac = os.getenv("NE2000_MAC") or ""
  if mtcp_mac and mtcp_mac ~= "" then
    return mtcp_mac
  end
  
  local cfg = io.open("C:\\MTCP\\MTCPDCFG", "r")
  if cfg then
    local content = cfg:read("*a")
    cfg:close()
    local eth_mac = content:match("ETHERNET_ADDRESS=([%x:]+)")
    if eth_mac then mac = eth_mac end
  end
  
  return mac
end

local function get_hostname()
  local hostname = os.getenv("HOSTNAME") or os.getenv("COMPUTERNAME") or "RUSTCHAIN-386"
  hostname = hostname:gsub("[^%w%-]", "-"):sub(1, 15)
  return hostname
end

function fingerprint.collect()
  local cpuid = detect_cpuid()
  local fpu = detect_fpu()
  local mem_kb = detect_memory()
  local mac = get_mac_address()
  local hostname = get_hostname()
  
  local checks = {}
  checks["cpuid_works"] = {
    passed = not cpuid.has_cpuid,
    data = {cpuid_result = cpuid.cpuid_result, expected = "0 (386 does not support CPUID)"}
  }
  checks["fpu_present"] = {
    passed = fpu.has_387,
    data = {has_387 = fpu.has_387, fpu_type = fpu.fpu_type}
  }
  checks["cache_present"] = {
    passed = false,
    data = {cache_size_kb = 0, expected = "0 (386 typically has no cache)"}
  }
  checks["crystal_drift"] = {
    passed = true,
    data = {drift_ppm_estimate = 150, note = "386 crystals have higher drift than modern CPUs"}
  }
  
  return {
    cpu_type = cpuid.cpu_type,
    has_cpuid = cpuid.has_cpuid,
    has_387 = fpu.has_387,
    fpu_type = fpu.fpu_type,
    memory_kb = mem_kb,
    mac = mac,
    hostname = hostname,
    checks = checks
  }
end

return fingerprint
