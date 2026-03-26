--[[
  SHA-256 Implementation in Pure Lua
  For RustChain Intel 386 Miner
  Compatible with Lua 5.1 on FreeDOS
]]

local sha256 = {}

local function band(a, b)
  local result = 0
  local bit = 1
  while a > 0 or b > 0 do
    if a % 2 == 1 and b % 2 == 1 then
      result = result + bit
    end
    a = math.floor(a / 2)
    b = math.floor(b / 2)
    bit = bit * 2
  end
  return result
end

local function rrot(x, n)
  x = x & 0xFFFFFFFF
  n = n & 31
  return ((x >> n) | ((x << (32 - n)) & 0xFFFFFFFF)) & 0xFFFFFFFF
end

local function rshift(x, n)
  x = x & 0xFFFFFFFF
  n = n & 31
  return (x >> n) & 0x7FFFFFFF
end

local K = {
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
  0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
  0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
  0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
  0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
  0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
  0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
  0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
  0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
}

local H0 = {
  0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
  0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
}

local function pad_message(msg)
  local bytes = {}
  for i = 1, #msg do
    bytes[i] = string.byte(msg, i)
  end
  local bit_len = #msg * 8
  table.insert(bytes, 0x80)
  while (#bytes % 64) ~= 56 do
    table.insert(bytes, 0x00)
  end
  local high = math.floor(bit_len / 0x100000000)
  local low = bit_len & 0xFFFFFFFF
  for i = 24, 0, -8 do
    table.insert(bytes, (low >> i) & 0xFF)
  end
  for i = 24, 0, -8 do
    table.insert(bytes, (high >> i) & 0xFF)
  end
  return bytes
end

local function get_word(bytes, i)
  return (bytes[i] << 24) | (bytes[i+1] << 16) | (bytes[i+2] << 8) | bytes[i+3]
end

local function compress(msg_bytes, h)
  local W = {}
  for t = 0, 63 do
    if t < 16 then
      W[t] = get_word(msg_bytes, t * 4 + 1)
    else
      local s0 = rrot(W[t-15], 7) ~ rrot(W[t-15], 18) ~ rshift(W[t-15], 3)
      local s1 = rrot(W[t-2], 17) ~ rrot(W[t-2], 19) ~ rshift(W[t-2], 10)
      W[t] = (W[t-16] + s0 + W[t-7] + s1) & 0xFFFFFFFF
    end
  end
  
  local a, b, c, d, e, f, g, hh = h[1], h[2], h[3], h[4], h[5], h[6], h[7], h[8]
  
  for t = 0, 63 do
    local S1 = rrot(e, 6) ~ rrot(e, 11) ~ rrot(e, 25)
    local ch = (e & f) ~ ((0xFFFFFFFF ~ e) & g)
    local temp1 = (hh + S1 + ch + K[t+1] + W[t]) & 0xFFFFFFFF
    local S0 = rrot(a, 2) ~ rrot(a, 13) ~ rrot(a, 22)
    local maj = (a & b) ~ (a & c) ~ (b & c)
    local temp2 = (S0 + maj) & 0xFFFFFFFF
    
    hh = g; g = f; f = e; e = (d + temp1) & 0xFFFFFFFF
    d = c; c = b; b = a; a = (temp1 + temp2) & 0xFFFFFFFF
  end
  
  return {
    (h[1] + a) & 0xFFFFFFFF,
    (h[2] + b) & 0xFFFFFFFF,
    (h[3] + c) & 0xFFFFFFFF,
    (h[4] + d) & 0xFFFFFFFF,
    (h[5] + e) & 0xFFFFFFFF,
    (h[6] + f) & 0xFFFFFFFF,
    (h[7] + g) & 0xFFFFFFFF,
    (h[8] + hh) & 0xFFFFFFFF
  }
end

function sha256.sum256(data)
  local msg_bytes = pad_message(data)
  local h = {table.unpack(H0)}
  
  for i = 1, #msg_bytes, 64 do
    local chunk = {}
    for j = i, i + 63 do
      chunk[j - i + 1] = msg_bytes[j]
    end
    h = compress(chunk, h)
  end
  
  local result = {}
  for i = 1, 8 do
    local word = h[i]
    table.insert(result, string.char(
      (word >> 24) & 0xFF,
      (word >> 16) & 0xFF,
      (word >> 8) & 0xFF,
      word & 0xFF
    ))
  end
  
  return table.concat(result)
end

sha256.sum256a = sha256.sum256

function sha256.hex(data)
  local bin = sha256.sum256(data)
  local hex_str = ""
  for i = 1, #bin do
    hex_str = hex_str .. string.format("%02x", string.byte(bin, i))
  end
  return hex_str
end

return sha256
