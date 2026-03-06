/* global nacl */
(() => {
  "use strict";

  const el = (id) => document.getElementById(id);
  const nodeOriginPill = el("nodeOriginPill");
  const mnemonicEl = el("mnemonic");
  const addrEl = el("addr");
  const pubEl = el("pub");
  const balancePill = el("balancePill");
  const balanceLog = el("balanceLog");
  const sendLog = el("sendLog");
  const toEl = el("to");
  const amountEl = el("amount");
  const memoEl = el("memo");

  nodeOriginPill.textContent = location.origin;

  let state = {
    mnemonic: "",
    wordlist: null,
    publicKey: null, // Uint8Array
    secretKey: null, // Uint8Array (64 bytes for nacl)
    address: "",
  };

  function setLog(target, msg) {
    target.textContent = msg || "";
  }

  function bytesToHex(bytes) {
    let out = "";
    for (let i = 0; i < bytes.length; i++) out += bytes[i].toString(16).padStart(2, "0");
    return out;
  }

  function hexToBytes(hex) {
    const s = String(hex || "").trim();
    if (s.length % 2 !== 0) throw new Error("hex_len");
    const out = new Uint8Array(s.length / 2);
    for (let i = 0; i < out.length; i++) out[i] = parseInt(s.slice(i * 2, i * 2 + 2), 16);
    return out;
  }

  function concatBytes(a, b) {
    const out = new Uint8Array(a.length + b.length);
    out.set(a, 0);
    out.set(b, a.length);
    return out;
  }

  async function sha256(bytes) {
    const buf = await crypto.subtle.digest("SHA-256", bytes);
    return new Uint8Array(buf);
  }

  async function pbkdf2Sha512(passwordUtf8, saltUtf8, iterations, outLenBytes) {
    const key = await crypto.subtle.importKey("raw", passwordUtf8, "PBKDF2", false, ["deriveBits"]);
    const bits = await crypto.subtle.deriveBits(
      {
        name: "PBKDF2",
        hash: "SHA-512",
        salt: saltUtf8,
        iterations,
      },
      key,
      outLenBytes * 8
    );
    return new Uint8Array(bits);
  }

  async function loadWordlistEnglish() {
    if (state.wordlist) return state.wordlist;
    const resp = await fetch("/light-client/assets/bip39_english.txt", { cache: "no-cache" });
    if (!resp.ok) throw new Error(`wordlist_http_${resp.status}`);
    const text = await resp.text();
    const words = text
      .split(/\r?\n/g)
      .map((w) => w.trim())
      .filter((w) => w.length > 0);
    if (words.length !== 2048) throw new Error(`wordlist_len_${words.length}`);
    state.wordlist = words;
    return words;
  }

  // BIP39 (English) implementation, using WebCrypto for SHA-256 + PBKDF2-HMAC-SHA512.
  async function entropyToMnemonic(entropyBytes, wordlist) {
    if (!(entropyBytes instanceof Uint8Array)) throw new Error("entropy_type");
    const entBits = entropyBytes.length * 8;
    if (![128, 160, 192, 224, 256].includes(entBits)) throw new Error("entropy_bits");

    const hash = await sha256(entropyBytes);
    const csBits = entBits / 32;
    const totalBits = entBits + csBits;

    // Build bit string for ENT || CS
    let bits = "";
    for (let i = 0; i < entropyBytes.length; i++) bits += entropyBytes[i].toString(2).padStart(8, "0");
    const csByte = hash[0];
    bits += (csByte >>> (8 - csBits)).toString(2).padStart(csBits, "0");

    if (bits.length !== totalBits) throw new Error("bits_len");
    const words = [];
    for (let i = 0; i < totalBits / 11; i++) {
      const chunk = bits.slice(i * 11, i * 11 + 11);
      const idx = parseInt(chunk, 2);
      words.push(wordlist[idx]);
    }
    return words.join(" ");
  }

  async function mnemonicToEntropy(mnemonic, wordlist) {
    const m = String(mnemonic || "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, " ");
    const parts = m.split(" ").filter(Boolean);
    if (![12, 15, 18, 21, 24].includes(parts.length)) throw new Error("mnemonic_words");

    let bits = "";
    for (const w of parts) {
      const idx = wordlist.indexOf(w);
      if (idx < 0) throw new Error("mnemonic_word_unknown");
      bits += idx.toString(2).padStart(11, "0");
    }

    const totalBits = bits.length;
    const csBits = totalBits / 33;
    const entBits = totalBits - csBits;
    if (entBits % 32 !== 0) throw new Error("mnemonic_entbits");

    const entBytes = entBits / 8;
    const entropy = new Uint8Array(entBytes);
    for (let i = 0; i < entBytes; i++) {
      entropy[i] = parseInt(bits.slice(i * 8, i * 8 + 8), 2);
    }

    const hash = await sha256(entropy);
    const expected = (hash[0] >>> (8 - csBits)).toString(2).padStart(csBits, "0");
    const got = bits.slice(entBits);
    if (expected !== got) throw new Error("mnemonic_checksum");

    return entropy;
  }

  async function mnemonicToSeed(mnemonic, passphrase) {
    // BIP39: PBKDF2(HMAC-SHA512, 2048, password=mnemonic(NFKD), salt="mnemonic"+passphrase(NFKD), dkLen=64)
    // Browser normalization is supported via String.normalize.
    const m = String(mnemonic || "").normalize("NFKD");
    const p = String(passphrase || "").normalize("NFKD");
    const enc = new TextEncoder();
    const password = enc.encode(m);
    const salt = enc.encode("mnemonic" + p);
    return pbkdf2Sha512(password, salt, 2048, 64);
  }

  async function addressFromPubkeyHex(pubHex) {
    const pubBytes = hexToBytes(pubHex);
    const h = await sha256(pubBytes);
    return "RTC" + bytesToHex(h).slice(0, 40);
  }

  async function deriveWalletFromMnemonic(mnemonic) {
    await loadWordlistEnglish();
    // Will throw if invalid.
    await mnemonicToEntropy(mnemonic, state.wordlist);

    const seed64 = await mnemonicToSeed(mnemonic, "");
    const seed32 = (await sha256(seed64)).slice(0, 32);

    const kp = nacl.sign.keyPair.fromSeed(seed32);
    const pubHex = bytesToHex(kp.publicKey);
    const addr = await addressFromPubkeyHex(pubHex);

    state.mnemonic = mnemonic;
    state.publicKey = kp.publicKey;
    state.secretKey = kp.secretKey;
    state.address = addr;

    addrEl.textContent = addr;
    pubEl.textContent = pubHex;
  }

  function pyJsonNumber(n) {
    // RustChain server uses Python float() then json.dumps.
    // Key mismatch edge case: Python prints 1.0, JS prints "1".
    if (!Number.isFinite(n)) throw new Error("amount_not_finite");
    if (Math.trunc(n) === n) return `${n}.0`;
    const s = n.toString(); // shortest round-trip in JS; close to Python repr for non-integers
    if (!/[eE]/.test(s)) return s;
    const m = s.match(/^([+-]?\d+(?:\.\d+)?)[eE]([+-]?)(\d+)$/);
    if (!m) return s;
    const base = m[1];
    const sign = m[2] === "-" ? "-" : "+";
    const exp = m[3].padStart(2, "0");
    return `${base}e${sign}${exp}`;
  }

  function canonicalSignedMessage(fromAddress, toAddress, amountRtc, memo, nonceStr) {
    // Python: json.dumps(tx_data, sort_keys=True, separators=(",", ":"))
    const amountStr = pyJsonNumber(amountRtc);
    const memoStr = String(memo ?? "");
    const nonceS = String(nonceStr ?? "");
    // keys sorted: amount, from, memo, nonce, to
    return `{"amount":${amountStr},"from":${JSON.stringify(fromAddress)},"memo":${JSON.stringify(
      memoStr
    )},"nonce":${JSON.stringify(nonceS)},"to":${JSON.stringify(toAddress)}}`;
  }

  async function refreshBalance() {
    if (!state.address) throw new Error("no_wallet_loaded");
    setLog(balanceLog, "loading...");
    const resp = await fetch(`/wallet/balance?miner_id=${encodeURIComponent(state.address)}`, {
      cache: "no-cache",
    });
    const text = await resp.text();
    let data = null;
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error(`balance_bad_json: ${text.slice(0, 120)}`);
    }
    if (!resp.ok) throw new Error(`balance_http_${resp.status}: ${text}`);
    const amt = Number(data.amount_rtc ?? 0);
    balancePill.textContent = `${amt.toFixed(6)} RTC`;
    setLog(balanceLog, JSON.stringify(data, null, 2));
  }

  async function signAndSend() {
    if (!state.secretKey || !state.publicKey || !state.address) throw new Error("no_wallet_loaded");
    if (!nacl || !nacl.sign || !nacl.sign.detached) throw new Error("nacl_missing");

    const to = String(toEl.value || "").trim();
    const memo = String(memoEl.value || "");
    const amount = Number(String(amountEl.value || "").trim());
    if (!to.startsWith("RTC") || to.length !== 43) throw new Error("invalid_to_address");
    if (!Number.isFinite(amount) || amount <= 0) throw new Error("invalid_amount");

    // Replay protection is per (from_address, nonce). Use ms to avoid collisions.
    const nonceInt = Date.now();
    const nonceStr = String(nonceInt);

    // Signed message must match server reconstruction exactly.
    const msgStr = canonicalSignedMessage(state.address, to, amount, memo, nonceStr);
    const msgBytes = new TextEncoder().encode(msgStr);

    const sig = nacl.sign.detached(msgBytes, state.secretKey);
    const sigHex = bytesToHex(sig);
    const pubHex = bytesToHex(state.publicKey);

    const body = {
      from_address: state.address,
      to_address: to,
      amount_rtc: amount,
      nonce: nonceInt,
      signature: sigHex,
      public_key: pubHex,
      memo,
    };

    setLog(sendLog, `message=${msgStr}\n\nposting...`);
    const resp = await fetch("/wallet/transfer/signed", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    const text = await resp.text();
    setLog(sendLog, `message=${msgStr}\n\nresponse_http=${resp.status}\n${text}`);
  }

  async function generateMnemonic24() {
    const wordlist = await loadWordlistEnglish();
    const entropy = new Uint8Array(32);
    crypto.getRandomValues(entropy);
    const m = await entropyToMnemonic(entropy, wordlist);
    mnemonicEl.value = m;
    return m;
  }

  function lockWallet() {
    state.mnemonic = "";
    state.publicKey = null;
    state.secretKey = null;
    state.address = "";
    mnemonicEl.value = "";
    addrEl.textContent = "-";
    pubEl.textContent = "-";
    balancePill.textContent = "- RTC";
    setLog(balanceLog, "");
    setLog(sendLog, "");
  }

  async function loadWalletFromTextarea() {
    const m = String(mnemonicEl.value || "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, " ");
    if (!m) throw new Error("empty_mnemonic");
    await deriveWalletFromMnemonic(m);
  }

  async function copyAddress() {
    if (!state.address) throw new Error("no_wallet_loaded");
    await navigator.clipboard.writeText(state.address);
  }

  async function main() {
    setLog(balanceLog, "");
    setLog(sendLog, "");

    el("btnGenerate").addEventListener("click", async () => {
      try {
        await generateMnemonic24();
      } catch (e) {
        setLog(sendLog, `generate_error: ${String(e && e.message ? e.message : e)}`);
      }
    });

    el("btnLoad").addEventListener("click", async () => {
      try {
        await loadWalletFromTextarea();
        setLog(sendLog, "wallet_loaded");
      } catch (e) {
        setLog(sendLog, `load_error: ${String(e && e.message ? e.message : e)}`);
      }
    });

    el("btnLock").addEventListener("click", () => lockWallet());

    el("btnCopyAddress").addEventListener("click", async () => {
      try {
        await copyAddress();
        setLog(sendLog, "copied_address");
      } catch (e) {
        setLog(sendLog, `copy_error: ${String(e && e.message ? e.message : e)}`);
      }
    });

    el("btnBalance").addEventListener("click", async () => {
      try {
        await refreshBalance();
      } catch (e) {
        setLog(balanceLog, `balance_error: ${String(e && e.message ? e.message : e)}`);
      }
    });

    el("btnSend").addEventListener("click", async () => {
      try {
        await signAndSend();
      } catch (e) {
        setLog(sendLog, `send_error: ${String(e && e.message ? e.message : e)}`);
      }
    });
  }

  window.addEventListener("load", () => {
    main().catch((e) => setLog(sendLog, `boot_error: ${String(e && e.message ? e.message : e)}`));
  });
})();

