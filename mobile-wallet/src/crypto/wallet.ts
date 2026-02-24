import * as bip39 from 'bip39';
import * as ed from '@noble/ed25519';

export async function createMnemonic(): Promise<string> {
  return bip39.generateMnemonic(256);
}

export async function importMnemonic(mnemonic: string): Promise<boolean> {
  return bip39.validateMnemonic(mnemonic);
}

export async function deriveEd25519FromMnemonic(mnemonic: string) {
  const seed = await bip39.mnemonicToSeed(mnemonic);
  const priv = seed.slice(0, 32);
  const pub = await ed.getPublicKey(priv);
  return { privateKeyHex: Buffer.from(priv).toString('hex'), publicKeyHex: Buffer.from(pub).toString('hex') };
}

export async function signMessage(privateKeyHex: string, message: string) {
  const priv = Uint8Array.from(Buffer.from(privateKeyHex, 'hex'));
  const msg = new TextEncoder().encode(message);
  const sig = await ed.sign(msg, priv);
  return Buffer.from(sig).toString('hex');
}
