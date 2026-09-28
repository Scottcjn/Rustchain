/*
 * RustChain light client: canonical signed-transfer message builder.
 *
 * Pure functions only (no DOM, no network) so the exact bytes the browser signs
 * can be checked against the node's verifier in tests
 * (tests/test_signed_transfer_clients_chain_id.py).
 *
 * The node reconstructs the signed message for POST /wallet/transfer/signed as
 * (node/rustchain_v2_integrated_v2.2.1_rip200.py, _wallet_transfer_signed_messages):
 *
 *   json.dumps({"amount": float, "chain_id": str, "from": str, "memo": str,
 *               "nonce": str(nonce), "to": str}, sort_keys=True, separators=(",", ":"))
 *
 * This is the fee-less ("legacy") form, which the node accepts when fee_rtc is 0.
 * chain_id binds the signature to one network so it cannot be replayed on
 * another (testnet <-> mainnet, forks). It must be the node's CHAIN_ID, which the
 * node publishes at GET /network/info.
 */
(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.RustChainLightSigning = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const CHAIN_ID_RE = /^[A-Za-z0-9._-]{1,64}$/;

  function isValidChainId(chainId) {
    return typeof chainId === "string" && CHAIN_ID_RE.test(chainId);
  }

  // Python's repr(float) for a finite number, as produced by json.dumps.
  // JS and Python agree on the shortest round-trip DIGITS, but not on layout:
  // Python prints 1.0 (JS "1") and switches to exponent form when the decimal
  // exponent is < -4 or >= 16 (JS: < -6 or >= 21), e.g. 1e-05 vs "0.00001".
  function pyJsonNumber(n) {
    if (typeof n !== "number" || !Number.isFinite(n)) throw new Error("amount_not_finite");
    if (n === 0) return Object.is(n, -0) ? "-0.0" : "0.0";
    const sign = n < 0 ? "-" : "";
    const m = Math.abs(n).toExponential().match(/^(\d)(?:\.(\d+))?e([+-]\d+)$/);
    if (!m) throw new Error("amount_format");
    const digits = m[1] + (m[2] || "");
    const exp = parseInt(m[3], 10);
    if (exp < -4 || exp >= 16) {
      const mant = digits.length > 1 ? `${digits[0]}.${digits.slice(1)}` : digits;
      const e = Math.abs(exp).toString().padStart(2, "0");
      return `${sign}${mant}e${exp < 0 ? "-" : "+"}${e}`;
    }
    if (exp < 0) return `${sign}0.${"0".repeat(-exp - 1)}${digits}`;
    const intLen = exp + 1;
    if (digits.length <= intLen) return `${sign}${digits}${"0".repeat(intLen - digits.length)}.0`;
    return `${sign}${digits.slice(0, intLen)}.${digits.slice(intLen)}`;
  }

  function canonicalSignedMessage(fromAddress, toAddress, amountRtc, memo, nonceStr, chainId) {
    if (!isValidChainId(chainId)) throw new Error("invalid_chain_id");
    // keys sorted: amount, chain_id, from, memo, nonce, to
    return (
      `{"amount":${pyJsonNumber(amountRtc)}` +
      `,"chain_id":${JSON.stringify(chainId)}` +
      `,"from":${JSON.stringify(String(fromAddress))}` +
      `,"memo":${JSON.stringify(String(memo ?? ""))}` +
      `,"nonce":${JSON.stringify(String(nonceStr ?? ""))}` +
      `,"to":${JSON.stringify(String(toAddress))}}`
    );
  }

  function bytesToHex(bytes) {
    let out = "";
    for (let i = 0; i < bytes.length; i++) out += bytes[i].toString(16).padStart(2, "0");
    return out;
  }

  // Build the signed request body for POST /wallet/transfer/signed.
  // `nacl` is tweetnacl; `secretKey`/`publicKey` are nacl Uint8Arrays.
  function buildSignedTransfer(nacl, opts) {
    const { secretKey, publicKey, fromAddress, toAddress, amountRtc, memo, nonce, chainId } = opts;
    if (!Number.isSafeInteger(nonce) || nonce <= 0) throw new Error("invalid_nonce");
    const memoStr = String(memo ?? "");
    const message = canonicalSignedMessage(fromAddress, toAddress, amountRtc, memoStr, String(nonce), chainId);
    const sig = nacl.sign.detached(new TextEncoder().encode(message), secretKey);
    return {
      message,
      body: {
        from_address: fromAddress,
        to_address: toAddress,
        amount_rtc: amountRtc,
        nonce,
        signature: bytesToHex(sig),
        public_key: bytesToHex(publicKey),
        memo: memoStr,
        chain_id: chainId,
      },
    };
  }

  return { isValidChainId, pyJsonNumber, canonicalSignedMessage, buildSignedTransfer };
});
