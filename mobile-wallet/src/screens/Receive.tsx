import React from 'react';
import { SafeAreaView, Text, View } from 'react-native';

export default function Receive({ minerId }: { minerId: string }) {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#111', padding: 14 }}>
      <Text style={{ color: '#fff', fontSize: 22, fontWeight: '700' }}>Receive RTC</Text>
      <Text style={{ color: '#9aa', marginTop: 10 }}>Wallet / miner id:</Text>
      <Text style={{ color: '#fff', marginTop: 6 }}>{minerId || '(set miner_id on Home)'}</Text>
      <View style={{ marginTop: 18, backgroundColor: '#1b1e25', borderWidth: 1, borderColor: '#2a3140', borderRadius: 10, padding: 16 }}>
        <Text style={{ color: '#cfd6e5' }}>QR display hook (TODO): generate QR for wallet address</Text>
        <Text style={{ color: '#8ea0c2', marginTop: 8 }}>Suggested integration: `react-native-qrcode-svg`</Text>
      </View>
    </SafeAreaView>
  );
}
