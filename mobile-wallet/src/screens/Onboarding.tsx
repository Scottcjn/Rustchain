import React from 'react';
import { SafeAreaView, Text, View } from 'react-native';

export default function Onboarding() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#111', padding: 14 }}>
      <Text style={{ color: '#fff', fontSize: 22, fontWeight: '700' }}>Wallet Onboarding Checklist</Text>
      <View style={{ marginTop: 14 }}>
        <Text style={{ color: '#cdd3df', marginBottom: 8 }}>1. Create/import BIP39 mnemonic ✅</Text>
        <Text style={{ color: '#cdd3df', marginBottom: 8 }}>2. Derive Ed25519 keypair ✅</Text>
        <Text style={{ color: '#cdd3df', marginBottom: 8 }}>3. Save encrypted session (hook) ✅</Text>
        <Text style={{ color: '#cdd3df', marginBottom: 8 }}>4. Enable biometric gate (TODO integration)</Text>
        <Text style={{ color: '#cdd3df', marginBottom: 8 }}>5. Verify receive QR + send test transfer</Text>
      </View>
      <Text style={{ color: '#8ea0c2', marginTop: 20 }}>This screen is a UX scaffold for first-run wallet flow and acceptance checks.</Text>
    </SafeAreaView>
  );
}
