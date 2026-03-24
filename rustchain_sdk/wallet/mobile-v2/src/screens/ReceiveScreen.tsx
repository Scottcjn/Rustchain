/**
 * Receive Screen
 *
 * Displays wallet address as QR code with copy functionality.
 */

import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Alert,
  ScrollView,
} from 'react-native';
import * as Clipboard from 'expo-clipboard';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/AppNavigator';
import { QRDisplay } from '../components/QRDisplay';

type Props = NativeStackScreenProps<RootStackParamList, 'Receive'>;

export default function ReceiveScreen({ route }: Props): React.JSX.Element {
  const { walletName, address } = route.params;

  const handleCopy = async () => {
    await Clipboard.setStringAsync(address);
    Alert.alert('Copied', 'Address copied to clipboard');
  };

  const handleCopyUri = async () => {
    const uri = `rustchain:${address}`;
    await Clipboard.setStringAsync(uri);
    Alert.alert('Copied', 'Payment URI copied to clipboard');
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.qrCard}>
        <QRDisplay value={address} size={220} label="Scan to send RTC" />
      </View>

      <View style={styles.addressCard}>
        <Text style={styles.addressLabel}>Your RTC Address</Text>
        <TouchableOpacity style={styles.addressBox} onPress={handleCopy} activeOpacity={0.7}>
          <Text style={styles.addressText} selectable>{address}</Text>
        </TouchableOpacity>
        <Text style={styles.hint}>Tap to copy</Text>
      </View>

      <View style={styles.actions}>
        <TouchableOpacity style={styles.actionBtn} onPress={handleCopy} activeOpacity={0.7}>
          <Text style={styles.actionBtnText}>Copy Address</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.actionBtn, styles.secondaryBtn]} onPress={handleCopyUri} activeOpacity={0.7}>
          <Text style={styles.secondaryBtnText}>Copy Payment URI</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.warningBox}>
        <Text style={styles.warningTitle}>Important</Text>
        <Text style={styles.warningText}>
          Only send RTC (RustChain) to this address.{'\n'}
          Sending other assets may result in permanent loss.
        </Text>
      </View>

      <View style={styles.infoBox}>
        <Text style={styles.infoLabel}>Wallet:</Text>
        <Text style={styles.infoValue}>{walletName}</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a1a' },
  content: { padding: 20, alignItems: 'center' },
  qrCard: { backgroundColor: '#12122a', borderRadius: 20, padding: 24, marginBottom: 20, borderWidth: 1, borderColor: '#1a1a3e', alignItems: 'center', width: '100%' },
  addressCard: { backgroundColor: '#12122a', borderRadius: 12, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: '#1a1a3e', width: '100%' },
  addressLabel: { fontSize: 13, color: '#888', marginBottom: 8 },
  addressBox: { backgroundColor: '#0f3460', borderRadius: 8, padding: 14 },
  addressText: { fontSize: 13, color: '#00ff88', fontFamily: 'monospace', textAlign: 'center' },
  hint: { fontSize: 11, color: '#666', marginTop: 6, textAlign: 'center' },
  actions: { flexDirection: 'row', gap: 10, marginBottom: 20, width: '100%' },
  actionBtn: { flex: 1, backgroundColor: '#00d4ff', paddingVertical: 14, borderRadius: 12, alignItems: 'center' },
  actionBtnText: { color: '#fff', fontSize: 14, fontWeight: 'bold' },
  secondaryBtn: { backgroundColor: 'transparent', borderWidth: 1, borderColor: '#00d4ff' },
  secondaryBtnText: { color: '#00d4ff', fontSize: 14, fontWeight: 'bold' },
  warningBox: { backgroundColor: '#1a1008', borderRadius: 12, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: '#ff6b6b44', width: '100%' },
  warningTitle: { fontSize: 14, fontWeight: 'bold', color: '#ff6b6b', marginBottom: 6 },
  warningText: { fontSize: 13, color: '#ccc', lineHeight: 20 },
  infoBox: { backgroundColor: '#12122a', borderRadius: 10, padding: 14, flexDirection: 'row', justifyContent: 'space-between', width: '100%', borderWidth: 1, borderColor: '#1a1a3e' },
  infoLabel: { fontSize: 14, color: '#888' },
  infoValue: { fontSize: 14, color: '#fff' },
});
