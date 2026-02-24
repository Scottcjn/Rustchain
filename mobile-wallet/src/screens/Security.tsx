import React from 'react';
import { SafeAreaView, Text, Pressable } from 'react-native';

export default function Security() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#111', padding: 14 }}>
      <Text style={{ color: '#fff', fontSize: 22, fontWeight: '700' }}>Security Hooks</Text>
      <Text style={{ color: '#9aa', marginTop: 10 }}>
        Biometric auth integration placeholder (expo-local-authentication):
      </Text>
      <Pressable style={{ marginTop: 10, backgroundColor: '#2d8cff', padding: 10, borderRadius: 8 }}>
        <Text>Enable Biometric Lock (TODO)</Text>
      </Pressable>
      <Text style={{ color: '#9aa', marginTop: 20 }}>
        QR scan integration placeholder (expo-camera / barcode scanner):
      </Text>
      <Pressable style={{ marginTop: 10, backgroundColor: '#31c46d', padding: 10, borderRadius: 8 }}>
        <Text>Open QR Scanner (TODO)</Text>
      </Pressable>
    </SafeAreaView>
  );
}
