/**
 * RustChain Wallet — App Entry Point
 *
 * Cross-platform React Native wallet for RustChain (RTC).
 * BIP39 mnemonic, Ed25519 signing, AES-256-GCM storage,
 * biometric auth, QR scanning, transaction history.
 */

import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { StyleSheet } from 'react-native';
import AppNavigator from './src/navigation/AppNavigator';

export default function App(): React.JSX.Element {
  return (
    <GestureHandlerRootView style={styles.root}>
      <StatusBar style="light" />
      <AppNavigator />
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#0a0a1a',
  },
});
