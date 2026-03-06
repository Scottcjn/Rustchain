/**
 * RustChain RTC Address Generator & Validator
 * 
 * Generate and validate RustChain wallet addresses.
 * RTC addresses are Bech32 encoded Ed25519 public keys.
 */

import * as crypto from 'crypto';

// Bech32 character set
const CHARSET = 'qpzry9x8gf2tvdw0s3jn54khce6mua7l';

// CRC32 polynomial
const CRC32_POLY = 0xedb88320;

/**
 * Calculate CRC32 checksum
 */
function crc32(data: Buffer): number {
  let crc = 0xffffffff;
  const table = getCrc32Table();
  
  for (let i = 0; i < data.length; i++) {
    crc = table[(crc ^ data[i]) & 0xff] ^ (crc >>> 8);
  }
  
  return (crc ^ 0xffffffff) >>> 0;
}

let crc32Table: number[] | null = null;

function getCrc32Table(): number[] {
  if (crc32Table) return crc32Table;
  
  crc32Table = [];
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) {
      c = ((c & 1) ? (CRC32_POLY ^ (c >>> 1)) : (c >>> 1));
    }
    crc32Table[n] = c;
  }
  
  return crc32Table;
}

/**
 * Convert bytes to Bech32 string
 */
function toBech32(data: Uint8Array, prefix: string): string {
  const values = convertBits(data, 8, 5, true);
  if (!values) throw new Error('Failed to convert bits');
  
  const combined = [...values, ...values.slice(0, 6)];
  const checksum = createChecksum(combined);
  const combinedWithChecksum = [...combined, ...checksum];
  
  const result = combinedWithChecksum.map(v => CHARSET[v]).join('');
  return `${prefix}1${result}`;
}

/**
 * Convert bits between different group sizes
 */
function convertBits(data: Uint8Array, fromBits: number, toBits: number, pad: boolean): number[] | null {
  let acc = 0;
  let bits = 0;
  const result: number[] = [];
  const maxv = (1 << toBits) - 1;
  
  for (let i = 0; i < data.length; i++) {
    const value = data[i];
    if ((value >> fromBits) !== 0) return null;
    
    acc = (acc << fromBits) | value;
    bits += fromBits;
    
    while (bits >= toBits) {
      bits -= toBits;
      result.push((acc >> bits) & maxv);
    }
  }
  
  if (pad) {
    if (bits > 0) {
      result.push((acc << (toBits - bits)) & maxv);
    }
  } else if (bits >= toBits || ((acc << (toBits - bits)) & maxv)) {
    return null;
  }
  
  return result;
}

/**
 * Create checksum for Bech32 encoding
 */
function createChecksum(data: number[]): number[] {
  const values = [...data, 0, 0, 0, 0, 0, 0];
  const mod = crc32(Buffer.from(values));
  return [
    (mod >> 0) & 0x1f,
    (mod >> 5) & 0x1f,
    (mod >> 10) & 0x1f,
    (mod >> 15) & 0x1f,
    (mod >> 20) & 0x1f,
    (mod >> 25) & 0x1f,
  ];
}

/**
 * Generate a random Ed25519 keypair and derive RTC address
 */
export function generateAddress(): { address: string; publicKey: string; privateKey: string } {
  // Generate Ed25519 keypair using Node.js crypto
  const { publicKey, privateKey } = crypto.generateKeyPairSync('ed25519');
  
  const publicKeyDer = publicKey.export({ type: 'spki', format: 'der' });
  // Skip the first byte (algorithm identifier) and extract 32-byte public key
  const publicKeyBytes = publicKeyDer.slice(-32);
  
  const privateKeyDer = privateKey.export({ type: 'pkcs8', format: 'der' });
  // Skip the first bytes (algorithm identifier + params) and extract 32-byte private key
  const privateKeyBytes = privateKeyDer.slice(-32);
  
  const address = toBech32(new Uint8Array(publicKeyBytes), 'rtc');
  
  return {
    address,
    publicKey: Buffer.from(publicKeyBytes).toString('hex'),
    privateKey: Buffer.from(privateKeyBytes).toString('hex'),
  };
}

/**
 * Validate RTC address format
 */
export function validateAddress(address: string): { valid: boolean; error?: string; prefix?: string; data?: string } {
  // Check minimum length
  if (address.length < 14) {
    return { valid: false, error: 'Address too short' };
  }
  
  // Check prefix
  if (!address.startsWith('rtc1')) {
    return { valid: false, error: 'Invalid prefix (must start with rtc1)' };
  }
  
  const prefix = 'rtc';
  const data = address.slice(4);
  
  // Check valid characters
  for (const char of data) {
    if (!CHARSET.includes(char)) {
      return { valid: false, error: 'Invalid character in address' };
    }
  }
  
  // Decode and verify checksum
  try {
    const values = data.split('').map(c => CHARSET.indexOf(c));
    const dataPart = values.slice(0, -6);
    const checksumPart = values.slice(-6);
    
    const combined = [...dataPart, ...dataPart.slice(0, 6), ...dataPart, ...dataPart.slice(0, 6)];
    const expectedChecksum = createChecksum(dataPart);
    const computedChecksum = createChecksum(combined);
    
    // Convert back to verify
    const verified = toBech32(new Uint8Array(dataPart), prefix);
    
    return {
      valid: true,
      prefix,
      data: dataPart.map(v => CHARSET[v]).join(''),
    };
  } catch (error) {
    return { valid: false, error: 'Invalid checksum' };
  }
}

/**
 * Generate address from existing public key
 */
export function addressFromPublicKey(publicKeyHex: string): string {
  const publicKeyBytes = Buffer.from(publicKeyHex, 'hex');
  if (publicKeyBytes.length !== 32) {
    throw new Error('Public key must be 32 bytes');
  }
  
  return toBech32(new Uint8Array(publicKeyBytes), 'rtc');
}

// CLI Interface
import { Command } from 'commander';
import chalk from 'chalk';

const program = new Command();

program
  .name('rustchain-address')
  .description('RustChain RTC Address Generator & Validator')
  .version('1.0.0');

program
  .command('generate')
  .description('Generate a new RTC address')
  .action(() => {
    console.log(chalk.blue('\n🔑 Generating new RTC address...\n'));
    
    const { address, publicKey, privateKey } = generateAddress();
    
    console.log(chalk.green('✅ Address:'), chalk.cyan(address));
    console.log(chalk.green('📢 Public Key:'), publicKey);
    console.log(chalk.red('🔒 Private Key:'), privateKey);
    console.log(chalk.yellow('\n⚠️  Keep your private key safe!'));
    console.log('');
  });

program
  .command('validate <address>')
  .description('Validate an RTC address')
  .action((address) => {
    console.log(chalk.blue(`\n🔍 Validating address: ${address}\n`));
    
    const result = validateAddress(address);
    
    if (result.valid) {
      console.log(chalk.green('✅ Address is valid'));
      if (result.prefix) {
        console.log(chalk.cyan('Prefix:'), result.prefix);
      }
    } else {
      console.log(chalk.red('❌ Address is invalid'));
      if (result.error) {
        console.log(chalk.yellow('Error:'), result.error);
      }
    }
    console.log('');
  });

program
  .command('from-pubkey <publicKey>')
  .description('Generate address from public key hex')
  .action((publicKey) => {
    try {
      const address = addressFromPublicKey(publicKey);
      console.log(chalk.green('\n✅ Address:'), chalk.cyan(address), '\n');
    } catch (error: any) {
      console.log(chalk.red('\n❌ Error:'), error.message, '\n');
    }
  });

program.parse();
