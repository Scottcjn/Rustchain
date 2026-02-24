import React from 'react';
import { SafeAreaView, Text, Pressable } from 'react-native';

export default function TransferReview({ from, to, amount, onConfirm }: { from: string; to: string; amount: number; onConfirm: () => void }) {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#111', padding: 14 }}>
      <Text style={{ color: '#fff', fontSize: 22, fontWeight: '700' }}>Transfer Review</Text>
      <Text style={{ color: '#cdd3df', marginTop: 12 }}>From: {from}</Text>
      <Text style={{ color: '#cdd3df', marginTop: 8 }}>To: {to}</Text>
      <Text style={{ color: '#cdd3df', marginTop: 8 }}>Amount: {amount} RTC</Text>
      <Text style={{ color: '#8ea0c2', marginTop: 14 }}>
        Final preflight hook: biometric gate + Ed25519 signed payload before submit.
      </Text>
      <Pressable onPress={onConfirm} style={{ backgroundColor: '#31c46d', padding: 10, borderRadius: 8, marginTop: 14 }}>
        <Text>Confirm Transfer</Text>
      </Pressable>
    </SafeAreaView>
  );
}
