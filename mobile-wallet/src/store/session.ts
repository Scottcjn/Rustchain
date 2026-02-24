export type WalletSession = {
  minerId: string;
  mnemonic?: string;
  publicKeyHex?: string;
};

let inMemory: WalletSession | null = null;

export function setSession(s: WalletSession | null) {
  inMemory = s;
}

export function getSession(): WalletSession | null {
  return inMemory;
}

// persistence hooks placeholder for AsyncStorage integration
export async function loadSession(): Promise<WalletSession | null> {
  return inMemory;
}

export async function saveSession(s: WalletSession | null): Promise<void> {
  inMemory = s;
}
