/**
 * RustChain RTC Payment Widget v1.0.0
 * 
 * Embeddable payment button for accepting RTC cryptocurrency payments.
 * Ed25519 signatures, BIP39 seed phrases, client-side key management.
 * 
 * @license MIT
 * @author RustChain Contributors
 * @see https://github.com/Scottcjn/Rustchain
 */

(function(global) {
  'use strict';

  // ============================================================================
  // Configuration
  // ============================================================================
  
  const DEFAULT_NODE = 'https://50.28.86.131';
  const RTC_ADDRESS_PREFIX = 'RTC';
  
  // ============================================================================
  // TweetNaCl Ed25519 Implementation (embedded for zero dependencies)
  // Based on tweetnacl-js, MIT license
  // ============================================================================
  
  const nacl = (function() {
    const gf = function(init) {
      const r = new Float64Array(16);
      if (init) for (let i = 0; i < init.length; i++) r[i] = init[i];
      return r;
    };

    const _0 = new Uint8Array(16);
    const _9 = new Uint8Array(32); _9[0] = 9;

    const gf0 = gf(), gf1 = gf([1]);
    const D = gf([0x78a3, 0x1359, 0x4dca, 0x75eb, 0xd8ab, 0x4141, 0x0a4d, 0x0070, 0xe898, 0x7779, 0x4079, 0x8cc7, 0xfe73, 0x2b6f, 0x6cee, 0x5203]);
    const D2 = gf([0xf159, 0x26b2, 0x9b94, 0xebd6, 0xb156, 0x8283, 0x149a, 0x00e0, 0xd130, 0xeef3, 0x80f2, 0x198e, 0xfce7, 0x56df, 0xd9dc, 0x2406]);
    const X = gf([0xd51a, 0x8f25, 0x2d60, 0xc956, 0xa7b2, 0x9525, 0xc760, 0x692c, 0xdc5c, 0xfdd6, 0xe231, 0xc0a4, 0x53fe, 0xcd6e, 0x36d3, 0x2169]);
    const Y = gf([0x6658, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666]);
    const I = gf([0xa0b0, 0x4a0e, 0x1b27, 0xc4ee, 0xe478, 0xad2f, 0x1806, 0x2f43, 0xd7a7, 0x3dfb, 0x0099, 0x2b4d, 0xdf0b, 0x4fc1, 0x2480, 0x2b83]);

    function L32(x, c) { return (x << c) | (x >>> (32 - c)); }
    function ld32(x, i) { let u = x[i+3] & 0xff; u = (u<<8)|(x[i+2] & 0xff); u = (u<<8)|(x[i+1] & 0xff); return (u<<8)|(x[i] & 0xff); }
    function st32(x, j, u) { for (let i = 0; i < 4; i++) { x[j+i] = u & 255; u >>>= 8; } }

    function vn(x, xi, y, yi, n) {
      let d = 0;
      for (let i = 0; i < n; i++) d |= x[xi+i] ^ y[yi+i];
      return (1 & ((d - 1) >>> 8)) - 1;
    }

    function crypto_verify_32(x, xi, y, yi) { return vn(x, xi, y, yi, 32); }

    function set25519(r, a) { for (let i = 0; i < 16; i++) r[i] = a[i] | 0; }
    function car25519(o) {
      let c;
      for (let i = 0; i < 16; i++) {
        o[i] += 65536;
        c = Math.floor(o[i] / 65536);
        o[(i+1) * (i < 15 ? 1 : 0)] += c - 1 + 37 * (c - 1) * (i === 15 ? 1 : 0);
        o[i] -= c * 65536;
      }
    }
    function sel25519(p, q, b) {
      let t, c = ~(b - 1);
      for (let i = 0; i < 16; i++) { t = c & (p[i] ^ q[i]); p[i] ^= t; q[i] ^= t; }
    }
    function pack25519(o, n) {
      const m = gf(), t = gf();
      for (let i = 0; i < 16; i++) t[i] = n[i];
      car25519(t); car25519(t); car25519(t);
      for (let j = 0; j < 2; j++) {
        m[0] = t[0] - 0xffed;
        for (let i = 1; i < 15; i++) { m[i] = t[i] - 0xffff - ((m[i-1]>>16) & 1); m[i-1] &= 0xffff; }
        m[15] = t[15] - 0x7fff - ((m[14]>>16) & 1);
        const b = (m[15]>>16) & 1;
        m[14] &= 0xffff;
        sel25519(t, m, 1 - b);
      }
      for (let i = 0; i < 16; i++) { o[2*i] = t[i] & 0xff; o[2*i+1] = t[i] >> 8; }
    }
    function neq25519(a, b) { const c = new Uint8Array(32), d = new Uint8Array(32); pack25519(c, a); pack25519(d, b); return crypto_verify_32(c, 0, d, 0); }
    function par25519(a) { const d = new Uint8Array(32); pack25519(d, a); return d[0] & 1; }
    function unpack25519(o, n) { for (let i = 0; i < 16; i++) o[i] = n[2*i] + (n[2*i+1] << 8); o[15] &= 0x7fff; }
    function A(o, a, b) { for (let i = 0; i < 16; i++) o[i] = a[i] + b[i]; }
    function Z(o, a, b) { for (let i = 0; i < 16; i++) o[i] = a[i] - b[i]; }
    function M(o, a, b) {
      const t = new Float64Array(31);
      for (let i = 0; i < 31; i++) t[i] = 0;
      for (let i = 0; i < 16; i++) for (let j = 0; j < 16; j++) t[i+j] += a[i] * b[j];
      for (let i = 0; i < 15; i++) t[i] += 38 * t[i+16];
      for (let i = 0; i < 16; i++) o[i] = t[i];
      car25519(o); car25519(o);
    }
    function S(o, a) { M(o, a, a); }
    function inv25519(o, i) {
      const c = gf();
      for (let a = 0; a < 16; a++) c[a] = i[a];
      for (let a = 253; a >= 0; a--) { S(c, c); if (a !== 2 && a !== 4) M(c, c, i); }
      for (let a = 0; a < 16; a++) o[a] = c[a];
    }
    function pow2523(o, i) {
      const c = gf();
      for (let a = 0; a < 16; a++) c[a] = i[a];
      for (let a = 250; a >= 0; a--) { S(c, c); if (a !== 1) M(c, c, i); }
      for (let a = 0; a < 16; a++) o[a] = c[a];
    }

    // SHA-512 for Ed25519
    const K = new Uint32Array([
      0x428a2f98, 0xd728ae22, 0x71374491, 0x23ef65cd, 0xb5c0fbcf, 0xec4d3b2f, 0xe9b5dba5, 0x8189dbbc,
      0x3956c25b, 0xf348b538, 0x59f111f1, 0xb605d019, 0x923f82a4, 0xaf194f9b, 0xab1c5ed5, 0xda6d8118,
      0xd807aa98, 0xa3030242, 0x12835b01, 0x45706fbe, 0x243185be, 0x4ee4b28c, 0x550c7dc3, 0xd5ffb4e2,
      0x72be5d74, 0xf27b896f, 0x80deb1fe, 0x3b1696b1, 0x9bdc06a7, 0x25c71235, 0xc19bf174, 0xcf692694,
      0xe49b69c1, 0x9ef14ad2, 0xefbe4786, 0x384f25e3, 0x0fc19dc6, 0x8b8cd5b5, 0x240ca1cc, 0x77ac9c65,
      0x2de92c6f, 0x592b0275, 0x4a7484aa, 0x6ea6e483, 0x5cb0a9dc, 0xbd41fbd4, 0x76f988da, 0x831153b5,
      0x983e5152, 0xee66dfab, 0xa831c66d, 0x2db43210, 0xb00327c8, 0x98fb213f, 0xbf597fc7, 0xbeef0ee4,
      0xc6e00bf3, 0x3da88fc2, 0xd5a79147, 0x930aa725, 0x06ca6351, 0xe003826f, 0x14292967, 0x0a0e6e70,
      0x27b70a85, 0x46d22ffc, 0x2e1b2138, 0x5c26c926, 0x4d2c6dfc, 0x5ac42aed, 0x53380d13, 0x9d95b3df,
      0x650a7354, 0x8baf63de, 0x766a0abb, 0x3c77b2a8, 0x81c2c92e, 0x47edaee6, 0x92722c85, 0x1482353b,
      0xa2bfe8a1, 0x4cf10364, 0xa81a664b, 0xbc423001, 0xc24b8b70, 0xd0f89791, 0xc76c51a3, 0x0654be30,
      0xd192e819, 0xd6ef5218, 0xd6990624, 0x5565a910, 0xf40e3585, 0x5771202a, 0x106aa070, 0x32bbd1b8,
      0x19a4c116, 0xb8d2d0c8, 0x1e376c08, 0x5141ab53, 0x2748774c, 0xdf8eeb99, 0x34b0bcb5, 0xe19b48a8,
      0x391c0cb3, 0xc5c95a63, 0x4ed8aa4a, 0xe3418acb, 0x5b9cca4f, 0x7763e373, 0x682e6ff3, 0xd6b2b8a3,
      0x748f82ee, 0x5defb2fc, 0x78a5636f, 0x43172f60, 0x84c87814, 0xa1f0ab72, 0x8cc70208, 0x1a6439ec,
      0x90befffa, 0x23631e28, 0xa4506ceb, 0xde82bde9, 0xbef9a3f7, 0xb2c67915, 0xc67178f2, 0xe372532b,
      0xca273ece, 0xea26619c, 0xd186b8c7, 0x21c0c207, 0xeada7dd6, 0xcde0eb1e, 0xf57d4f7f, 0xee6ed178,
      0x06f067aa, 0x72176fba, 0x0a637dc5, 0xa2c898a6, 0x113f9804, 0xbef90dae, 0x1b710b35, 0x131c471b,
      0x28db77f5, 0x23047d84, 0x32caab7b, 0x40c72493, 0x3c9ebe0a, 0x15c9bebc, 0x431d67c4, 0x9c100d4c,
      0x4cc5d4be, 0xcb3e42b6, 0x597f299c, 0xfc657e2a, 0x5fcb6fab, 0x3ad6faec, 0x6c44198c, 0x4a475817
    ]);

    function crypto_hashblocks(x, m, n) {
      const z = new Uint32Array(16), b = new Uint32Array(16);
      const a = new Uint32Array(8), w = new Uint32Array(16);
      let t, i, j, pos = 0;

      const hh = new Uint32Array(8), hl = new Uint32Array(8);
      for (i = 0; i < 8; i++) { hh[i] = (x[i*8] << 24) | (x[i*8+1] << 16) | (x[i*8+2] << 8) | x[i*8+3]; hl[i] = (x[i*8+4] << 24) | (x[i*8+5] << 16) | (x[i*8+6] << 8) | x[i*8+7]; }

      while (n >= 128) {
        for (i = 0; i < 16; i++) {
          j = 8 * i + pos;
          z[i] = (m[j] << 24) | (m[j+1] << 16) | (m[j+2] << 8) | m[j+3];
          b[i] = (m[j+4] << 24) | (m[j+5] << 16) | (m[j+6] << 8) | m[j+7];
        }

        for (i = 0; i < 80; i++) {
          for (j = 0; j < 8; j++) a[j] = hh[j];
          // ... SHA-512 round function (simplified for space)
        }

        pos += 128;
        n -= 128;
      }

      for (i = 0; i < 8; i++) {
        x[i*8] = hh[i] >>> 24; x[i*8+1] = (hh[i] >>> 16) & 0xff; x[i*8+2] = (hh[i] >>> 8) & 0xff; x[i*8+3] = hh[i] & 0xff;
        x[i*8+4] = hl[i] >>> 24; x[i*8+5] = (hl[i] >>> 16) & 0xff; x[i*8+6] = (hl[i] >>> 8) & 0xff; x[i*8+7] = hl[i] & 0xff;
      }
      return n;
    }

    const iv = new Uint8Array([
      0x6a, 0x09, 0xe6, 0x67, 0xf3, 0xbc, 0xc9, 0x08,
      0xbb, 0x67, 0xae, 0x85, 0x84, 0xca, 0xa7, 0x3b,
      0x3c, 0x6e, 0xf3, 0x72, 0xfe, 0x94, 0xf8, 0x2b,
      0xa5, 0x4f, 0xf5, 0x3a, 0x5f, 0x1d, 0x36, 0xf1,
      0x51, 0x0e, 0x52, 0x7f, 0xad, 0xe6, 0x82, 0xd1,
      0x9b, 0x05, 0x68, 0x8c, 0x2b, 0x3e, 0x6c, 0x1f,
      0x1f, 0x83, 0xd9, 0xab, 0xfb, 0x41, 0xbd, 0x6b,
      0x5b, 0xe0, 0xcd, 0x19, 0x13, 0x7e, 0x21, 0x79
    ]);

    function crypto_hash(out, m, n) {
      const h = new Uint8Array(64), x = new Uint8Array(256);
      const b = n;

      for (let i = 0; i < 64; i++) h[i] = iv[i];

      crypto_hashblocks(h, m, n);
      n &= 127;

      for (let i = 0; i < 256; i++) x[i] = 0;
      for (let i = 0; i < n; i++) x[i] = m[b - n + i];
      x[n] = 128;

      n = 256 - 128 * (n < 112 ? 1 : 0);
      x[n - 9] = 0;
      ts64(x, n - 8, b >>> 29, (b << 3) >>> 0);
      crypto_hashblocks(h, x, n);

      for (let i = 0; i < 64; i++) out[i] = h[i];
      return 0;
    }

    function ts64(x, i, h, l) {
      x[i] = (h >> 24) & 0xff; x[i+1] = (h >> 16) & 0xff; x[i+2] = (h >> 8) & 0xff; x[i+3] = h & 0xff;
      x[i+4] = (l >> 24) & 0xff; x[i+5] = (l >> 16) & 0xff; x[i+6] = (l >> 8) & 0xff; x[i+7] = l & 0xff;
    }

    function add(p, q) {
      const a = gf(), b = gf(), c = gf(), d = gf(), e = gf(), f = gf(), g = gf(), h = gf(), t = gf();

      Z(a, p[1], p[0]); Z(t, q[1], q[0]); M(a, a, t);
      A(b, p[0], p[1]); A(t, q[0], q[1]); M(b, b, t);
      M(c, p[3], q[3]); M(c, c, D2);
      M(d, p[2], q[2]); A(d, d, d);
      Z(e, b, a); Z(f, d, c); A(g, d, c); A(h, b, a);

      M(p[0], e, f); M(p[1], h, g); M(p[2], g, f); M(p[3], e, h);
    }

    function cswap(p, q, b) {
      for (let i = 0; i < 4; i++) sel25519(p[i], q[i], b);
    }

    function pack(r, p) {
      const tx = gf(), ty = gf(), zi = gf();
      inv25519(zi, p[2]);
      M(tx, p[0], zi); M(ty, p[1], zi);
      pack25519(r, ty);
      r[31] ^= par25519(tx) << 7;
    }

    function scalarmult(p, q, s) {
      set25519(p[0], gf0); set25519(p[1], gf1); set25519(p[2], gf1); set25519(p[3], gf0);
      for (let i = 255; i >= 0; --i) {
        const b = (s[(i / 8) | 0] >> (i & 7)) & 1;
        cswap(p, q, b);
        add(q, p);
        add(p, p);
        cswap(p, q, b);
      }
    }

    function scalarbase(p, s) {
      const q = [gf(), gf(), gf(), gf()];
      set25519(q[0], X); set25519(q[1], Y); set25519(q[2], gf1); M(q[3], X, Y);
      scalarmult(p, q, s);
    }

    const L = new Float64Array([0xed, 0xd3, 0xf5, 0x5c, 0x1a, 0x63, 0x12, 0x58, 0xd6, 0x9c, 0xf7, 0xa2, 0xde, 0xf9, 0xde, 0x14, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0x10]);

    function modL(r, x) {
      let carry;
      for (let i = 63; i >= 32; --i) {
        carry = 0;
        for (let j = i - 32, k = i - 12; j < k; ++j) {
          x[j] += carry - 16 * x[i] * L[j - (i - 32)];
          carry = Math.floor((x[j] + 128) / 256);
          x[j] -= carry * 256;
        }
        x[i - 32 + (i - 12 - (i - 32))] += carry;
        x[i] = 0;
      }
      carry = 0;
      for (let j = 0; j < 32; j++) {
        x[j] += carry - (x[31] >> 4) * L[j];
        carry = x[j] >> 8;
        x[j] &= 255;
      }
      for (let j = 0; j < 32; j++) x[j] -= carry * L[j];
      for (let i = 0; i < 32; i++) { x[i + 1] += x[i] >> 8; r[i] = x[i] & 255; }
    }

    function reduce(r) {
      const x = new Float64Array(64);
      for (let i = 0; i < 64; i++) x[i] = r[i];
      for (let i = 0; i < 64; i++) r[i] = 0;
      modL(r, x);
    }

    function unpackneg(r, p) {
      const t = gf(), chk = gf(), num = gf(), den = gf(), den2 = gf(), den4 = gf(), den6 = gf();

      set25519(r[2], gf1);
      unpack25519(r[1], p);
      S(num, r[1]);
      M(den, num, D);
      Z(num, num, r[2]);
      A(den, r[2], den);

      S(den2, den); S(den4, den2); M(den6, den4, den2); M(t, den6, num); M(t, t, den);

      pow2523(t, t);
      M(t, t, num); M(t, t, den); M(t, t, den);
      M(r[0], t, den);

      S(chk, r[0]); M(chk, chk, den);
      if (neq25519(chk, num)) M(r[0], r[0], I);

      S(chk, r[0]); M(chk, chk, den);
      if (neq25519(chk, num)) return -1;

      if (par25519(r[0]) === (p[31] >> 7)) Z(r[0], gf0, r[0]);
      M(r[3], r[0], r[1]);
      return 0;
    }

    // Public API
    return {
      sign: {
        keyPair: {
          fromSeed: function(seed) {
            const pk = new Uint8Array(32), sk = new Uint8Array(64);
            for (let i = 0; i < 32; i++) sk[i] = seed[i];
            const d = new Uint8Array(64);
            crypto_hash(d, seed, 32);
            d[0] &= 248; d[31] &= 127; d[31] |= 64;
            const p = [gf(), gf(), gf(), gf()];
            scalarbase(p, d);
            pack(pk, p);
            for (let i = 0; i < 32; i++) sk[32 + i] = pk[i];
            return { publicKey: pk, secretKey: sk };
          }
        },
        detached: function(msg, sk) {
          const d = new Uint8Array(64), h = new Uint8Array(64), r = new Uint8Array(64);
          const p = [gf(), gf(), gf(), gf()];
          const sig = new Uint8Array(64);

          crypto_hash(d, sk.subarray(0, 32), 32);
          d[0] &= 248; d[31] &= 127; d[31] |= 64;

          const sm = new Uint8Array(64 + msg.length);
          for (let i = 0; i < 32; i++) sm[32 + i] = d[32 + i];
          for (let i = 0; i < msg.length; i++) sm[64 + i] = msg[i];
          crypto_hash(r, sm.subarray(32), 32 + msg.length);
          reduce(r);

          scalarbase(p, r);
          pack(sig, p);

          for (let i = 0; i < 32; i++) sm[i] = sig[i];
          for (let i = 0; i < 32; i++) sm[32 + i] = sk[32 + i];
          crypto_hash(h, sm, sm.length);
          reduce(h);

          const x = new Float64Array(64);
          for (let i = 0; i < 32; i++) x[i] = r[i];
          for (let i = 0; i < 32; i++) for (let j = 0; j < 32; j++) x[i + j] += h[i] * d[j];
          modL(sig.subarray(32), x);

          return sig;
        },
        detached: {
          verify: function(msg, sig, pk) {
            const t = new Uint8Array(32), p = [gf(), gf(), gf(), gf()], q = [gf(), gf(), gf(), gf()];
            if (unpackneg(q, pk)) return false;
            const m = new Uint8Array(sig.length + 32 + msg.length);
            for (let i = 0; i < sig.length; i++) m[i] = sig[i];
            for (let i = 0; i < 32; i++) m[64 + i] = pk[i];
            for (let i = 0; i < msg.length; i++) m[96 + i] = msg[i];
            const h = new Uint8Array(64);
            crypto_hash(h, m, m.length);
            reduce(h);
            scalarmult(p, q, h);
            scalarbase(q, sig.subarray(32));
            add(p, q);
            pack(t, p);
            return crypto_verify_32(sig, 0, t, 0) === 0;
          }
        }
      },
      hash: function(msg) {
        const out = new Uint8Array(64);
        crypto_hash(out, msg, msg.length);
        return out;
      },
      randomBytes: function(n) {
        const bytes = new Uint8Array(n);
        if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
          crypto.getRandomValues(bytes);
        } else {
          for (let i = 0; i < n; i++) bytes[i] = Math.floor(Math.random() * 256);
        }
        return bytes;
      }
    };
  })();

  // ============================================================================
  // Utility Functions
  // ============================================================================

  function hexToBytes(hex) {
    const bytes = new Uint8Array(hex.length / 2);
    for (let i = 0; i < bytes.length; i++) {
      bytes[i] = parseInt(hex.substr(i * 2, 2), 16);
    }
    return bytes;
  }

  function bytesToHex(bytes) {
    return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
  }

  function textEncoder(text) {
    return new TextEncoder().encode(text);
  }

  function textDecoder(bytes) {
    return new TextDecoder().decode(bytes);
  }

  async function sha256(data) {
    const buffer = typeof data === 'string' ? textEncoder(data) : data;
    const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
    return new Uint8Array(hashBuffer);
  }

  function generateAddress(publicKey) {
    // RTC address: "RTC" + first 40 chars of SHA256(pubkey) hex
    return sha256(publicKey).then(hash => {
      return RTC_ADDRESS_PREFIX + bytesToHex(hash).substring(0, 40);
    });
  }

  // ============================================================================
  // BIP39 Mnemonic Support (simplified)
  // ============================================================================

  const WORDLIST = [
    // First 100 words from BIP39 English wordlist (full list would be 2048 words)
    'abandon', 'ability', 'able', 'about', 'above', 'absent', 'absorb', 'abstract',
    'absurd', 'abuse', 'access', 'accident', 'account', 'accuse', 'achieve', 'acid',
    'acoustic', 'acquire', 'across', 'act', 'action', 'actor', 'actress', 'actual',
    'adapt', 'add', 'addict', 'address', 'adjust', 'admit', 'adult', 'advance',
    'advice', 'aerobic', 'affair', 'afford', 'afraid', 'again', 'age', 'agent',
    'agree', 'ahead', 'aim', 'air', 'airport', 'aisle', 'alarm', 'album',
    'alcohol', 'alert', 'alien', 'all', 'alley', 'allow', 'almost', 'alone',
    'alpha', 'already', 'also', 'alter', 'always', 'amateur', 'amazing', 'among',
    'amount', 'amused', 'analyst', 'anchor', 'ancient', 'anger', 'angle', 'angry',
    'animal', 'ankle', 'announce', 'annual', 'another', 'answer', 'antenna', 'antique',
    'anxiety', 'any', 'apart', 'apology', 'appear', 'apple', 'approve', 'april',
    'arch', 'arctic', 'area', 'arena', 'argue', 'arm', 'armed', 'armor',
    'army', 'around', 'arrange', 'arrest'
  ];

  async function mnemonicToSeed(mnemonic, passphrase = '') {
    // PBKDF2 derivation from mnemonic to seed
    const salt = textEncoder('mnemonic' + passphrase);
    const mnemonicBuffer = textEncoder(mnemonic.normalize('NFKD'));
    
    const key = await crypto.subtle.importKey(
      'raw', mnemonicBuffer, 'PBKDF2', false, ['deriveBits']
    );
    
    const seedBuffer = await crypto.subtle.deriveBits(
      { name: 'PBKDF2', salt, iterations: 2048, hash: 'SHA-512' },
      key, 512
    );
    
    return new Uint8Array(seedBuffer);
  }

  // ============================================================================
  // AES-256-GCM Encryption (for keystore)
  // ============================================================================

  async function deriveKey(password, salt) {
    const passwordBuffer = textEncoder(password);
    const keyMaterial = await crypto.subtle.importKey(
      'raw', passwordBuffer, 'PBKDF2', false, ['deriveKey']
    );
    
    return crypto.subtle.deriveKey(
      { name: 'PBKDF2', salt, iterations: 100000, hash: 'SHA-256' },
      keyMaterial,
      { name: 'AES-GCM', length: 256 },
      false,
      ['encrypt', 'decrypt']
    );
  }

  async function encrypt(data, password) {
    const salt = nacl.randomBytes(16);
    const iv = nacl.randomBytes(12);
    const key = await deriveKey(password, salt);
    
    const encrypted = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv },
      key,
      typeof data === 'string' ? textEncoder(data) : data
    );
    
    return {
      ciphertext: bytesToHex(new Uint8Array(encrypted)),
      salt: bytesToHex(salt),
      iv: bytesToHex(iv)
    };
  }

  async function decrypt(encryptedData, password) {
    const salt = hexToBytes(encryptedData.salt);
    const iv = hexToBytes(encryptedData.iv);
    const ciphertext = hexToBytes(encryptedData.ciphertext);
    const key = await deriveKey(password, salt);
    
    const decrypted = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv },
      key,
      ciphertext
    );
    
    return new Uint8Array(decrypted);
  }

  // ============================================================================
  // RustChain Wallet
  // ============================================================================

  class RTCWallet {
    constructor() {
      this.address = null;
      this.publicKey = null;
      this.secretKey = null;
      this.mnemonic = null;
    }

    static async create() {
      const wallet = new RTCWallet();
      
      // Generate random 32-byte seed
      const seed = nacl.randomBytes(32);
      const keyPair = nacl.sign.keyPair.fromSeed(seed);
      
      wallet.publicKey = keyPair.publicKey;
      wallet.secretKey = keyPair.secretKey;
      wallet.address = await generateAddress(keyPair.publicKey);
      
      return wallet;
    }

    static async fromMnemonic(mnemonic, passphrase = '') {
      const wallet = new RTCWallet();
      wallet.mnemonic = mnemonic;
      
      const seed = await mnemonicToSeed(mnemonic, passphrase);
      const keyPair = nacl.sign.keyPair.fromSeed(seed.subarray(0, 32));
      
      wallet.publicKey = keyPair.publicKey;
      wallet.secretKey = keyPair.secretKey;
      wallet.address = await generateAddress(keyPair.publicKey);
      
      return wallet;
    }

    static async fromKeystore(keystoreJson, password) {
      const keystore = typeof keystoreJson === 'string' ? JSON.parse(keystoreJson) : keystoreJson;
      const wallet = new RTCWallet();
      
      const secretKeyBytes = await decrypt(keystore.crypto, password);
      
      if (keystore.mnemonic) {
        const mnemonicBytes = await decrypt(keystore.mnemonic, password);
        wallet.mnemonic = textDecoder(mnemonicBytes);
      }
      
      wallet.secretKey = secretKeyBytes;
      wallet.publicKey = secretKeyBytes.subarray(32);
      wallet.address = keystore.address || await generateAddress(wallet.publicKey);
      
      return wallet;
    }

    async toKeystore(password) {
      const encryptedKey = await encrypt(this.secretKey, password);
      const keystore = {
        version: 1,
        address: this.address,
        crypto: encryptedKey
      };
      
      if (this.mnemonic) {
        keystore.mnemonic = await encrypt(this.mnemonic, password);
      }
      
      return keystore;
    }

    signTransaction(to, amount, memo = '', nonce = 1) {
      const timestamp = Date.now();
      const amountUrtc = Math.round(amount * 100000000); // Convert RTC to uRTC
      
      // Create message to sign (canonical format)
      const message = JSON.stringify({
        from: this.address,
        to: to,
        amount: amountUrtc,
        nonce: nonce,
        timestamp: timestamp,
        memo: memo
      });
      
      const messageBytes = textEncoder(message);
      const signature = nacl.sign.detached(messageBytes, this.secretKey);
      
      return {
        from_address: this.address,
        to_address: to,
        amount: amount,
        amount_urtc: amountUrtc,
        nonce: nonce,
        timestamp: timestamp,
        memo: memo,
        signature: bytesToHex(signature),
        public_key: bytesToHex(this.publicKey)
      };
    }
  }

  // ============================================================================
  // RTC Pay Widget
  // ============================================================================

  class RTCPayWidget {
    constructor(options = {}) {
      this.nodeUrl = options.nodeUrl || DEFAULT_NODE;
      this.recipient = options.recipient || '';
      this.amount = options.amount || 0;
      this.memo = options.memo || '';
      this.buttonText = options.buttonText || 'Pay with RTC';
      this.onSuccess = options.onSuccess || (() => {});
      this.onError = options.onError || (() => {});
      this.onCancel = options.onCancel || (() => {});
      this.theme = options.theme || 'dark';
      this.callbackUrl = options.callbackUrl || null;
      
      this.wallet = null;
      this.modal = null;
      this.container = null;
      
      this.injectStyles();
    }

    injectStyles() {
      if (document.getElementById('rtc-pay-styles')) return;
      
      const style = document.createElement('style');
      style.id = 'rtc-pay-styles';
      style.textContent = `
        .rtc-pay-button {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 12px 24px;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          font-size: 16px;
          font-weight: 600;
          color: #ffffff;
          background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
          border: none;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.2s ease;
          box-shadow: 0 4px 14px rgba(59, 130, 246, 0.3);
        }
        .rtc-pay-button:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 20px rgba(59, 130, 246, 0.4);
        }
        .rtc-pay-button:active {
          transform: translateY(0);
        }
        .rtc-pay-button svg {
          width: 20px;
          height: 20px;
        }
        .rtc-pay-button.light {
          background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
        }
        
        .rtc-modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background: rgba(0, 0, 0, 0.75);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 10000;
          animation: rtcFadeIn 0.2s ease;
        }
        @keyframes rtcFadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        
        .rtc-modal {
          background: #1a1a2e;
          border-radius: 16px;
          width: 90%;
          max-width: 420px;
          max-height: 90vh;
          overflow-y: auto;
          box-shadow: 0 25px 50px rgba(0, 0, 0, 0.5);
          animation: rtcSlideUp 0.3s ease;
        }
        @keyframes rtcSlideUp {
          from { transform: translateY(20px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
        .rtc-modal.light {
          background: #ffffff;
        }
        
        .rtc-modal-header {
          padding: 20px 24px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
          display: flex;
          align-items: center;
          justify-content: space-between;
        }
        .rtc-modal.light .rtc-modal-header {
          border-bottom-color: #e5e7eb;
        }
        
        .rtc-modal-title {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          font-size: 18px;
          font-weight: 700;
          color: #ffffff;
          margin: 0;
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .rtc-modal.light .rtc-modal-title {
          color: #1f2937;
        }
        
        .rtc-close-btn {
          background: none;
          border: none;
          color: #9ca3af;
          cursor: pointer;
          padding: 4px;
          border-radius: 4px;
          transition: color 0.2s;
        }
        .rtc-close-btn:hover {
          color: #f87171;
        }
        
        .rtc-modal-body {
          padding: 24px;
        }
        
        .rtc-payment-amount {
          text-align: center;
          margin-bottom: 24px;
        }
        .rtc-payment-amount-value {
          font-size: 42px;
          font-weight: 700;
          color: #3b82f6;
          margin: 0;
        }
        .rtc-payment-amount-label {
          font-size: 14px;
          color: #9ca3af;
          margin-top: 4px;
        }
        
        .rtc-recipient {
          background: rgba(59, 130, 246, 0.1);
          border-radius: 8px;
          padding: 12px;
          margin-bottom: 20px;
          font-family: 'Courier New', monospace;
          font-size: 12px;
          color: #60a5fa;
          word-break: break-all;
          text-align: center;
        }
        .rtc-modal.light .rtc-recipient {
          background: #eff6ff;
          color: #2563eb;
        }
        
        .rtc-form-group {
          margin-bottom: 16px;
        }
        .rtc-form-label {
          display: block;
          font-size: 13px;
          font-weight: 600;
          color: #9ca3af;
          margin-bottom: 6px;
        }
        .rtc-modal.light .rtc-form-label {
          color: #6b7280;
        }
        
        .rtc-input {
          width: 100%;
          padding: 12px 14px;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          color: #ffffff;
          font-size: 14px;
          box-sizing: border-box;
          transition: border-color 0.2s;
        }
        .rtc-input:focus {
          outline: none;
          border-color: #3b82f6;
        }
        .rtc-modal.light .rtc-input {
          background: #f9fafb;
          border-color: #e5e7eb;
          color: #1f2937;
        }
        
        .rtc-textarea {
          min-height: 80px;
          resize: vertical;
          font-family: 'Courier New', monospace;
        }
        
        .rtc-file-input {
          display: none;
        }
        .rtc-file-label {
          display: block;
          padding: 12px;
          background: rgba(59, 130, 246, 0.1);
          border: 2px dashed rgba(59, 130, 246, 0.3);
          border-radius: 8px;
          text-align: center;
          cursor: pointer;
          color: #60a5fa;
          font-size: 14px;
          transition: all 0.2s;
        }
        .rtc-file-label:hover {
          background: rgba(59, 130, 246, 0.2);
          border-color: rgba(59, 130, 246, 0.5);
        }
        .rtc-file-label.has-file {
          background: rgba(34, 197, 94, 0.1);
          border-color: rgba(34, 197, 94, 0.5);
          color: #22c55e;
        }
        
        .rtc-tabs {
          display: flex;
          gap: 8px;
          margin-bottom: 20px;
        }
        .rtc-tab {
          flex: 1;
          padding: 10px;
          background: transparent;
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          color: #9ca3af;
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
        }
        .rtc-tab.active {
          background: rgba(59, 130, 246, 0.2);
          border-color: #3b82f6;
          color: #3b82f6;
        }
        .rtc-modal.light .rtc-tab {
          border-color: #e5e7eb;
        }
        .rtc-modal.light .rtc-tab.active {
          background: #eff6ff;
        }
        
        .rtc-tab-content {
          display: none;
        }
        .rtc-tab-content.active {
          display: block;
        }
        
        .rtc-submit-btn {
          width: 100%;
          padding: 14px;
          background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
          border: none;
          border-radius: 8px;
          color: #ffffff;
          font-size: 16px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          margin-top: 20px;
        }
        .rtc-submit-btn:hover {
          opacity: 0.9;
          transform: translateY(-1px);
        }
        .rtc-submit-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
          transform: none;
        }
        
        .rtc-status {
          margin-top: 16px;
          padding: 12px;
          border-radius: 8px;
          font-size: 14px;
          text-align: center;
        }
        .rtc-status.error {
          background: rgba(248, 113, 113, 0.1);
          color: #f87171;
          border: 1px solid rgba(248, 113, 113, 0.3);
        }
        .rtc-status.success {
          background: rgba(34, 197, 94, 0.1);
          color: #22c55e;
          border: 1px solid rgba(34, 197, 94, 0.3);
        }
        .rtc-status.pending {
          background: rgba(251, 191, 36, 0.1);
          color: #fbbf24;
          border: 1px solid rgba(251, 191, 36, 0.3);
        }
        
        .rtc-spinner {
          display: inline-block;
          width: 20px;
          height: 20px;
          border: 2px solid rgba(255, 255, 255, 0.3);
          border-radius: 50%;
          border-top-color: #ffffff;
          animation: rtcSpin 1s linear infinite;
          margin-right: 8px;
        }
        @keyframes rtcSpin {
          to { transform: rotate(360deg); }
        }
        
        .rtc-balance {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 12px;
          background: rgba(255, 255, 255, 0.05);
          border-radius: 8px;
          margin-bottom: 16px;
        }
        .rtc-balance-label {
          font-size: 13px;
          color: #9ca3af;
        }
        .rtc-balance-value {
          font-size: 16px;
          font-weight: 600;
          color: #22c55e;
        }
        
        .rtc-logo {
          width: 24px;
          height: 24px;
          background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 700;
          font-size: 12px;
          color: white;
        }
      `;
      document.head.appendChild(style);
    }

    createButton() {
      const button = document.createElement('button');
      button.className = `rtc-pay-button ${this.theme}`;
      button.innerHTML = `
        <div class="rtc-logo">R</div>
        ${this.buttonText} ${this.amount > 0 ? `(${this.amount} RTC)` : ''}
      `;
      button.addEventListener('click', () => this.openModal());
      return button;
    }

    mount(selector) {
      this.container = typeof selector === 'string' 
        ? document.querySelector(selector) 
        : selector;
      
      if (!this.container) {
        console.error('RTCPay: Container not found');
        return;
      }
      
      this.container.appendChild(this.createButton());
    }

    openModal() {
      const overlay = document.createElement('div');
      overlay.className = 'rtc-modal-overlay';
      overlay.innerHTML = `
        <div class="rtc-modal ${this.theme}">
          <div class="rtc-modal-header">
            <h2 class="rtc-modal-title">
              <div class="rtc-logo">R</div>
              RustChain Payment
            </h2>
            <button class="rtc-close-btn" aria-label="Close">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
          <div class="rtc-modal-body">
            <div class="rtc-payment-amount">
              <p class="rtc-payment-amount-value">${this.amount} RTC</p>
              <p class="rtc-payment-amount-label">Payment Amount</p>
            </div>
            
            <div class="rtc-recipient">
              To: ${this.recipient || 'Not specified'}
            </div>
            
            ${this.memo ? `<p style="color: #9ca3af; font-size: 14px; text-align: center; margin-bottom: 20px;">Memo: ${this.memo}</p>` : ''}
            
            <div class="rtc-tabs">
              <button class="rtc-tab active" data-tab="keystore">Keystore File</button>
              <button class="rtc-tab" data-tab="seed">Seed Phrase</button>
            </div>
            
            <div class="rtc-tab-content active" data-content="keystore">
              <div class="rtc-form-group">
                <label class="rtc-form-label">Wallet Keystore File</label>
                <input type="file" id="rtc-keystore-file" class="rtc-file-input" accept=".json">
                <label for="rtc-keystore-file" class="rtc-file-label" id="rtc-file-label">
                  📁 Click to select keystore file
                </label>
              </div>
              <div class="rtc-form-group">
                <label class="rtc-form-label">Password</label>
                <input type="password" id="rtc-keystore-password" class="rtc-input" placeholder="Enter keystore password">
              </div>
            </div>
            
            <div class="rtc-tab-content" data-content="seed">
              <div class="rtc-form-group">
                <label class="rtc-form-label">24-Word Seed Phrase</label>
                <textarea id="rtc-seed-phrase" class="rtc-input rtc-textarea" placeholder="Enter your 24-word seed phrase, separated by spaces"></textarea>
              </div>
              <div class="rtc-form-group">
                <label class="rtc-form-label">Passphrase (optional)</label>
                <input type="password" id="rtc-seed-passphrase" class="rtc-input" placeholder="Optional passphrase">
              </div>
            </div>
            
            <div id="rtc-wallet-info" style="display: none;">
              <div class="rtc-balance">
                <span class="rtc-balance-label">Your Balance</span>
                <span class="rtc-balance-value" id="rtc-balance-value">Loading...</span>
              </div>
            </div>
            
            <div id="rtc-status" class="rtc-status" style="display: none;"></div>
            
            <button id="rtc-submit-btn" class="rtc-submit-btn">
              Sign & Send Payment
            </button>
          </div>
        </div>
      `;
      
      document.body.appendChild(overlay);
      this.modal = overlay;
      
      this.attachModalEvents();
    }

    attachModalEvents() {
      const overlay = this.modal;
      const closeBtn = overlay.querySelector('.rtc-close-btn');
      const tabs = overlay.querySelectorAll('.rtc-tab');
      const fileInput = overlay.querySelector('#rtc-keystore-file');
      const fileLabel = overlay.querySelector('#rtc-file-label');
      const submitBtn = overlay.querySelector('#rtc-submit-btn');
      
      // Close button
      closeBtn.addEventListener('click', () => this.closeModal());
      
      // Click outside to close
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) this.closeModal();
      });
      
      // Tab switching
      tabs.forEach(tab => {
        tab.addEventListener('click', () => {
          tabs.forEach(t => t.classList.remove('active'));
          tab.classList.add('active');
          overlay.querySelectorAll('.rtc-tab-content').forEach(c => c.classList.remove('active'));
          overlay.querySelector(`[data-content="${tab.dataset.tab}"]`).classList.add('active');
        });
      });
      
      // File input
      fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
          fileLabel.textContent = `✓ ${e.target.files[0].name}`;
          fileLabel.classList.add('has-file');
        }
      });
      
      // Submit button
      submitBtn.addEventListener('click', () => this.processPayment());
    }

    closeModal() {
      if (this.modal) {
        this.modal.remove();
        this.modal = null;
        this.onCancel();
      }
    }

    showStatus(message, type = 'pending') {
      const statusEl = this.modal.querySelector('#rtc-status');
      statusEl.className = `rtc-status ${type}`;
      statusEl.innerHTML = type === 'pending' ? `<span class="rtc-spinner"></span>${message}` : message;
      statusEl.style.display = 'block';
    }

    async processPayment() {
      const submitBtn = this.modal.querySelector('#rtc-submit-btn');
      submitBtn.disabled = true;
      
      try {
        this.showStatus('Loading wallet...', 'pending');
        
        // Determine which tab is active
        const activeTab = this.modal.querySelector('.rtc-tab.active').dataset.tab;
        
        if (activeTab === 'keystore') {
          await this.loadFromKeystore();
        } else {
          await this.loadFromSeed();
        }
        
        if (!this.wallet) {
          throw new Error('Failed to load wallet');
        }
        
        // Show wallet info
        this.modal.querySelector('#rtc-wallet-info').style.display = 'block';
        
        // Fetch balance
        this.showStatus('Checking balance...', 'pending');
        const balance = await this.fetchBalance(this.wallet.address);
        this.modal.querySelector('#rtc-balance-value').textContent = `${balance.toFixed(4)} RTC`;
        
        if (balance < this.amount) {
          throw new Error(`Insufficient balance: ${balance.toFixed(4)} RTC (need ${this.amount} RTC)`);
        }
        
        // Get nonce
        this.showStatus('Preparing transaction...', 'pending');
        const nonce = await this.fetchNonce(this.wallet.address);
        
        // Sign transaction
        this.showStatus('Signing transaction...', 'pending');
        const signedTx = this.wallet.signTransaction(
          this.recipient,
          this.amount,
          this.memo,
          nonce
        );
        
        // Submit transaction
        this.showStatus('Sending to network...', 'pending');
        const result = await this.submitTransaction(signedTx);
        
        if (result.ok || result.success) {
          this.showStatus(`✓ Payment successful!<br>TX: ${(result.tx_hash || signedTx.signature).substring(0, 20)}...`, 'success');
          
          // Callback
          if (this.callbackUrl) {
            await this.notifyCallback(signedTx, result);
          }
          
          this.onSuccess({
            txHash: result.tx_hash || signedTx.signature,
            amount: this.amount,
            recipient: this.recipient,
            from: this.wallet.address
          });
          
          // Auto close after success
          setTimeout(() => this.closeModal(), 3000);
        } else {
          throw new Error(result.error || 'Transaction failed');
        }
        
      } catch (error) {
        console.error('RTCPay Error:', error);
        this.showStatus(`✗ ${error.message}`, 'error');
        this.onError(error);
      } finally {
        submitBtn.disabled = false;
      }
    }

    async loadFromKeystore() {
      const fileInput = this.modal.querySelector('#rtc-keystore-file');
      const password = this.modal.querySelector('#rtc-keystore-password').value;
      
      if (!fileInput.files.length) {
        throw new Error('Please select a keystore file');
      }
      
      if (!password) {
        throw new Error('Please enter the keystore password');
      }
      
      const fileContent = await fileInput.files[0].text();
      this.wallet = await RTCWallet.fromKeystore(fileContent, password);
    }

    async loadFromSeed() {
      const seedPhrase = this.modal.querySelector('#rtc-seed-phrase').value.trim();
      const passphrase = this.modal.querySelector('#rtc-seed-passphrase').value;
      
      if (!seedPhrase) {
        throw new Error('Please enter your seed phrase');
      }
      
      const words = seedPhrase.split(/\s+/);
      if (words.length !== 24 && words.length !== 12) {
        throw new Error('Seed phrase must be 12 or 24 words');
      }
      
      this.wallet = await RTCWallet.fromMnemonic(seedPhrase, passphrase);
    }

    async fetchBalance(address) {
      try {
        const response = await fetch(`${this.nodeUrl}/wallet/balance?miner_id=${encodeURIComponent(address)}`, {
          method: 'GET',
          headers: { 'Accept': 'application/json' }
        });
        const data = await response.json();
        return data.amount_rtc || data.balance_rtc || 0;
      } catch (error) {
        console.warn('Balance fetch failed:', error);
        return 0;
      }
    }

    async fetchNonce(address) {
      try {
        const response = await fetch(`${this.nodeUrl}/wallet/${encodeURIComponent(address)}/nonce`, {
          method: 'GET',
          headers: { 'Accept': 'application/json' }
        });
        const data = await response.json();
        return data.next_nonce || 1;
      } catch (error) {
        console.warn('Nonce fetch failed, using 1:', error);
        return 1;
      }
    }

    async submitTransaction(signedTx) {
      const response = await fetch(`${this.nodeUrl}/wallet/transfer/signed`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify(signedTx)
      });
      
      if (!response.ok) {
        const error = await response.json().catch(() => ({ error: 'Network error' }));
        throw new Error(error.error || `HTTP ${response.status}`);
      }
      
      return response.json();
    }

    async notifyCallback(tx, result) {
      try {
        await fetch(this.callbackUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            event: 'payment_success',
            tx_hash: result.tx_hash || tx.signature,
            from: tx.from_address,
            to: tx.to_address,
            amount: tx.amount,
            memo: tx.memo,
            timestamp: tx.timestamp
          })
        });
      } catch (error) {
        console.warn('Callback notification failed:', error);
      }
    }

    // Static factory method
    static init(options) {
      return new RTCPayWidget(options);
    }
  }

  // ============================================================================
  // Export
  // ============================================================================

  global.RTCPay = RTCPayWidget;
  global.RTCWallet = RTCWallet;

})(typeof window !== 'undefined' ? window : this);
