import React, { useState } from 'react';
import { SafeAreaView, Text, Pressable } from 'react-native';

export default function BiometricGate() {
  const [status, setStatus] = useState('Not verified');

  async function verify() {
    // TODO: integrate expo-local-authentication here
    setStatus('Verified (mock)');
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#111', padding: 14 }}>
      <Text style={{ color: '#fff', fontSize: 22, fontWeight: '700' }}>Biometric Gate</Text>
      <Text style={{ color: '#cdd3df', marginTop: 12 }}>Status: {status}</Text>
      <Pressable onPress={verify} style={{ backgroundColor: '#2d8cff', padding: 10, borderRadius: 8, marginTop: 12 }}>
        <Text>Verify Now</Text>
      </Pressable>
      <Text style={{ color: '#8ea0c2', marginTop: 18 }}>
        Integration note: replace mock with `expo-local-authentication` before production.
      </Text>
    </SafeAreaView>
  );
}
