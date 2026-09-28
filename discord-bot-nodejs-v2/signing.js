'use strict';
/**
 * Chain-bound request builder for POST /wallet/transfer/signed.
 *
 * The node rebuilds the signed message as (node/rustchain_v2_integrated_v2.2.1_rip200.py,
 * _wallet_transfer_signed_messages):
 *
 *   json.dumps({"amount": float, "chain_id": str, "from": str, "memo": str,
 *               "nonce": str(nonce), "to": str}, sort_keys=True, separators=(",", ":"))
 *
 * i.e. the fee-less form, accepted when fee_rtc is 0. chain_id binds the
 * signature to one network so it cannot be replayed on another; it must equal
 * the node's CHAIN_ID (GET /network/info). Checked against the node's verifier in
 * tests/test_signed_transfer_clients_chain_id.py.
 */
const crypto = require('crypto');

const CHAIN_ID_RE = /^[A-Za-z0-9._-]{1,64}$/;

function isValidChainId(chainId) {
  return typeof chainId === 'string' && CHAIN_ID_RE.test(chainId);
}

// Python's repr(float) (what json.dumps writes). JS and Python agree on the
// shortest round-trip digits but not on layout: Python prints 1.0 (JS "1") and
// uses exponent form when the decimal exponent is < -4 or >= 16 (1e-05).
function pyJsonNumber(n) {
  if (typeof n !== 'number' || !Number.isFinite(n)) throw new Error('amount_not_finite');
  if (n === 0) return Object.is(n, -0) ? '-0.0' : '0.0';
  const sign = n < 0 ? '-' : '';
  const m = Math.abs(n).toExponential().match(/^(\d)(?:\.(\d+))?e([+-]\d+)$/);
  if (!m) throw new Error('amount_format');
  const digits = m[1] + (m[2] || '');
  const exp = parseInt(m[3], 10);
  if (exp < -4 || exp >= 16) {
    const mant = digits.length > 1 ? `${digits[0]}.${digits.slice(1)}` : digits;
    return `${sign}${mant}e${exp < 0 ? '-' : '+'}${String(Math.abs(exp)).padStart(2, '0')}`;
  }
  if (exp < 0) return `${sign}0.${'0'.repeat(-exp - 1)}${digits}`;
  const intLen = exp + 1;
  if (digits.length <= intLen) return `${sign}${digits}${'0'.repeat(intLen - digits.length)}.0`;
  return `${sign}${digits.slice(0, intLen)}.${digits.slice(intLen)}`;
}

// Python json.dumps(ensure_ascii=True) string encoding. JSON.stringify already
// escapes quotes, backslashes, control chars (\b \t \n \f \r, else \u00xx)
// and lone surrogates exactly as Python does; Python additionally escapes every
// UTF-16 code unit outside 0x20-0x7e (so DEL, accents, emoji surrogate pairs)
// as lowercase \uxxxx. Without this, any non-ASCII memo fails verification.
function pyJsonString(value) {
  return JSON.stringify(String(value)).replace(
    /[\u007f-\uffff]/g,
    (c) => '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0')
  );
}

function canonicalSignedMessage(fromAddress, toAddress, amountRtc, memo, nonce, chainId) {
  if (!isValidChainId(chainId)) throw new Error('invalid_chain_id');
  // keys sorted: amount, chain_id, from, memo, nonce, to
  return (
    `{"amount":${pyJsonNumber(amountRtc)}` +
    `,"chain_id":${pyJsonString(chainId)}` +
    `,"from":${pyJsonString(String(fromAddress))}` +
    `,"memo":${pyJsonString(String(memo ?? ''))}` +
    `,"nonce":${pyJsonString(String(nonce))}` +
    `,"to":${pyJsonString(String(toAddress))}}`
  );
}

// RTC address = "RTC" + first 40 hex chars of sha256(public key).
function addressFromPublicKey(publicKey) {
  return 'RTC' + crypto.createHash('sha256').update(Buffer.from(publicKey)).digest('hex').slice(0, 40);
}

// secretKey: 64-byte tweetnacl secret key (seed || public key).
function buildSignedTransfer(nacl, { secretKey, toAddress, amountRtc, memo = '', nonce, chainId }) {
  if (!(secretKey instanceof Uint8Array) || secretKey.length !== 64) throw new Error('bad_secret_key');
  if (!Number.isSafeInteger(nonce) || nonce <= 0) throw new Error('invalid_nonce');
  const publicKey = secretKey.slice(32);
  const fromAddress = addressFromPublicKey(publicKey);
  const memoStr = String(memo ?? '');
  const message = canonicalSignedMessage(fromAddress, toAddress, amountRtc, memoStr, nonce, chainId);
  const signature = nacl.sign.detached(new TextEncoder().encode(message), secretKey);
  return {
    message,
    body: {
      from_address: fromAddress,
      to_address: toAddress,
      amount_rtc: amountRtc,
      memo: memoStr,
      nonce,
      chain_id: chainId,
      public_key: Buffer.from(publicKey).toString('hex'),
      signature: Buffer.from(signature).toString('hex'),
    },
  };
}

module.exports = {
  isValidChainId,
  pyJsonNumber,
  pyJsonString,
  canonicalSignedMessage,
  addressFromPublicKey,
  buildSignedTransfer,
};
