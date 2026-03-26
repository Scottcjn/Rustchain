--[[
  NET.LUA - mTCP HTTP Client for FreeDOS
  RustChain Intel 386 Miner
]]

local net = {}

function net.json_encode(obj)
  local function escape_str(s)
    s = s or ""
    s = s:gsub("\\", "\\\\")
    s = s:gsub('"', '\\"')
    s = s:gsub("\n", "\\n")
    s = s:gsub("\r", "\\r")
    s = s:gsub("\t", "\\t")
    return '"' .. s .. '"'
  end
  
  local function encode_value(v)
    local t = type(v)
    if t == "nil" then return "null"
    elseif t == "number" then return string.format("%.17g", v)
    elseif t == "boolean" then return tostring(v)
    elseif t == "string" then return escape_str(v)
    elseif t == "table" then
      local is_array = #v > 0 or next(v) == nil
      local parts = {}
      if is_array then
        for i, val in ipairs(v) do table.insert(parts, encode_value(val)) end
        return "[" .. table.concat(parts, ",") .. "]"
      else
        for key, val in pairs(v) do
          if type(key) == "string" then
            table.insert(parts, escape_str(key) .. ":" .. encode_value(val))
          end
        end
        return "{" .. table.concat(parts, ",") .. "}"
      end
    else return "null" end
  end
  
  return encode_value(obj)
end

function net.http_get(url)
  local handle = io.popen('curl.exe -sk "' .. url .. '" 2>NUL', "r")
  if handle then
    local response = handle:read("*a")
    handle:close()
    if response and response ~= "" then return response end
  end
  
  local handle2 = io.popen('wget.exe -q -O - "' .. url .. '" 2>NUL', "r")
  if handle2 then
    local response = handle2:read("*a")
    handle2:close()
    if response and response ~= "" then return response end
  end
  
  return nil
end

function net.http_post(url, body)
  body = body or ""
  local handle = io.popen(
    'curl.exe -sk -X POST -H "Content-Type: application/json" -d "' ..
    body:gsub('"', '\\"') .. '" "' .. url .. '" 2>NUL', "r"
  )
  if handle then
    local response = handle:read("*a")
    handle:close()
    if response and response ~= "" then return response end
  end
  
  local handle2 = io.popen(
    'wget.exe -q -O - --post-data="' .. body:gsub('"', '\\"') .. '" "' .. url .. '" 2>NUL', "r"
  )
  if handle2 then
    local response = handle2:read("*a")
    handle2:close()
    if response and response ~= "" then return response end
  end
  
  return nil
end

return net
