import React from 'react';
import { SafeAreaView, Text, Pressable } from 'react-native';

export default function QrScanner() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#111', padding: 14 }}>
      <Text style={{ color: '#fff', fontSize: 22, fontWeight: '700' }}>QR Scanner</Text>
      <Text style={{ color: '#cdd3df', marginTop: 12 }}>
        Camera scan flow scaffold for recipient wallet QR.
      </Text>
      <Pressable style={{ backgroundColor: '#2d8cff', padding: 10, borderRadius: 8, marginTop: 12 }}>
        <Text>Start Scan (TODO)</Text>
      </Pressable>
      <Text style={{ color: '#8ea0c2', marginTop: 16 }}>
        Integration note: wire `expo-camera` + barcode parser and route result into Send screen recipient field.
      </Text>
    </SafeAreaView>
  );
}
