import nacl from 'tweetnacl';

export function getKeysFromBIP39Seed(seed: Uint8Array) {
  if (seed.length !== 32) {
    throw new Error("Seed must be exactly 32 bytes for ed25519 derivation");
  }
  // Fix: Replaced fromSecretKey with fromSeed to handle 32-byte BIP39 seeds correctly
  const keyPair = nacl.sign.keyPair.fromSeed(seed);
  return {
    publicKey: keyPair.publicKey,
    secretKey: keyPair.secretKey
  };
}