/**
 * Wallet Detail Screen
 *
 * Balance display, address copy, unlock/lock, send/receive/history actions.
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  ScrollView,
  RefreshControl,
  Alert,
  TextInput,
} from 'react-native';
import * as Clipboard from 'expo-clipboard';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/AppNavigator';
import { WalletStorage } from '../services/storage';
import { RustChainClient } from '../services/api';
import { BalanceCard } from '../components/BalanceCard';

type Props = NativeStackScreenProps<RootStackParamList, 'WalletDetail'>;

export default function WalletDetailScreen({ route, navigation }: Props): React.JSX.Element {
  const { walletName } = route.params;
  const [address, setAddress] = useState('');
  const [balance, setBalance] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [unlocked, setUnlocked] = useState(false);
  const [password, setPassword] = useState('');
  const [unlocking, setUnlocking] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const client = new RustChainClient();

  const loadInfo = useCallback(async () => {
    try {
      const meta = await WalletStorage.getMetadata(walletName);
      if (meta) {
        setAddress(meta.address);
        try {
          const bal = await client.getBalance(meta.address);
          setBalance(bal.balance);
        } catch {
          setBalance(0);
        }
      }
    } catch (err) {
      console.error('Failed to load wallet:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [walletName]);

  useEffect(() => { loadInfo(); }, [loadInfo]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadInfo();
  }, [loadInfo]);

  const handleUnlock = async () => {
    if (!password) { Alert.alert('Error', 'Enter your password'); return; }
    setUnlocking(true);
    try {
      await WalletStorage.load(walletName, password);
      setUnlocked(true);
      setPassword('');
      setShowPassword(false);
    } catch {
      Alert.alert('Error', 'Incorrect password');
    } finally {
      setUnlocking(false);
    }
  };

  const handleCopy = async () => {
    await Clipboard.setStringAsync(address);
    Alert.alert('Copied', 'Address copied to clipboard');
  };

  if (loading) {
    return (
      <View style={styles.loadingBox}>
        <ActivityIndicator size="large" color="#00d4ff" />
        <Text style={styles.loadingText}>Loading wallet...</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#00d4ff" />}
    >
      <BalanceCard balance={balance} />

      {/* Address */}
      <View style={styles.card}>
        <Text style={styles.cardLabel}>Wallet Address</Text>
        <TouchableOpacity style={styles.addressRow} onPress={handleCopy} activeOpacity={0.7}>
          <Text style={styles.addressText} selectable>{address}</Text>
        </TouchableOpacity>
        <Text style={styles.hint}>Tap to copy</Text>
      </View>

      {/* Unlock / Lock */}
      {!unlocked ? (
        <View style={styles.lockCard}>
          <Text style={styles.lockTitle}>Wallet Locked</Text>
          <Text style={styles.lockDesc}>Enter password to unlock send capabilities</Text>
          <View style={styles.passwordRow}>
            <TextInput
              style={styles.passwordInput}
              placeholder="Password"
              placeholderTextColor="#666"
              value={password}
              onChangeText={setPassword}
              secureTextEntry={!showPassword}
              onSubmitEditing={handleUnlock}
            />
            <TouchableOpacity style={styles.togglePw} onPress={() => setShowPassword(!showPassword)}>
              <Text style={styles.togglePwText}>{showPassword ? 'Hide' : 'Show'}</Text>
            </TouchableOpacity>
          </View>
          <TouchableOpacity style={styles.unlockBtn} onPress={handleUnlock} disabled={unlocking} activeOpacity={0.7}>
            {unlocking ? <ActivityIndicator color="#fff" /> : <Text style={styles.unlockBtnText}>Unlock</Text>}
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.unlockedCard}>
          <Text style={styles.unlockedTitle}>Wallet Unlocked</Text>
          <TouchableOpacity style={styles.lockBtn} onPress={() => setUnlocked(false)} activeOpacity={0.7}>
            <Text style={styles.lockBtnText}>Lock Wallet</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Actions */}
      <View style={styles.card}>
        <Text style={styles.cardLabel}>Actions</Text>
        <View style={styles.actionRow}>
          <TouchableOpacity
            style={[styles.actionBtn, unlocked ? styles.actionEnabled : styles.actionDisabled]}
            onPress={() => navigation.navigate('Send', { walletName })}
            disabled={!unlocked}
            activeOpacity={0.7}
          >
            <Text style={styles.actionBtnText}>Send</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.actionBtn, styles.actionEnabled]}
            onPress={() => navigation.navigate('Receive', { walletName, address })}
            activeOpacity={0.7}
          >
            <Text style={styles.actionBtnText}>Receive</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.actionBtn, styles.actionEnabled]}
            onPress={() => navigation.navigate('History', { walletName, address })}
            activeOpacity={0.7}
          >
            <Text style={styles.actionBtnText}>History</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Info */}
      <View style={styles.card}>
        <Text style={styles.cardLabel}>Wallet Info</Text>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>Name:</Text>
          <Text style={styles.infoValue}>{walletName}</Text>
        </View>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>Network:</Text>
          <Text style={styles.infoValue}>Mainnet</Text>
        </View>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>Status:</Text>
          <Text style={[styles.infoValue, unlocked ? styles.online : styles.offline]}>
            {unlocked ? 'Unlocked' : 'Locked'}
          </Text>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a1a' },
  content: { padding: 20, gap: 16 },
  loadingBox: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0a0a1a' },
  loadingText: { color: '#888', marginTop: 10 },
  card: { backgroundColor: '#12122a', borderRadius: 12, padding: 16, borderWidth: 1, borderColor: '#1a1a3e' },
  cardLabel: { fontSize: 13, color: '#888', marginBottom: 8 },
  addressRow: { backgroundColor: '#0f3460', borderRadius: 8, padding: 12 },
  addressText: { fontSize: 12, color: '#fff', fontFamily: 'monospace' },
  hint: { fontSize: 11, color: '#666', marginTop: 4 },
  lockCard: { backgroundColor: '#12122a', borderRadius: 12, padding: 20, borderWidth: 1, borderColor: '#ff6b6b44' },
  lockTitle: { fontSize: 18, fontWeight: 'bold', color: '#ff6b6b', marginBottom: 4 },
  lockDesc: { fontSize: 14, color: '#888', marginBottom: 16 },
  passwordRow: { flexDirection: 'row', gap: 10, marginBottom: 16 },
  passwordInput: { flex: 1, backgroundColor: '#0f3460', borderRadius: 8, padding: 12, color: '#fff', fontSize: 16 },
  togglePw: { backgroundColor: '#0f3460', borderRadius: 8, padding: 12, justifyContent: 'center' },
  togglePwText: { color: '#00d4ff', fontSize: 13, fontWeight: 'bold' },
  unlockBtn: { backgroundColor: '#ff6b6b', paddingVertical: 14, borderRadius: 12, alignItems: 'center' },
  unlockBtnText: { color: '#fff', fontSize: 16, fontWeight: 'bold' },
  unlockedCard: { backgroundColor: '#12122a', borderRadius: 12, padding: 20, borderWidth: 1, borderColor: '#00ff8844' },
  unlockedTitle: { fontSize: 18, fontWeight: 'bold', color: '#00ff88', marginBottom: 12 },
  lockBtn: { backgroundColor: '#0f3460', paddingVertical: 12, borderRadius: 8, alignItems: 'center', borderWidth: 1, borderColor: '#00ff88' },
  lockBtnText: { color: '#00ff88', fontSize: 14, fontWeight: 'bold' },
  actionRow: { flexDirection: 'row', gap: 10 },
  actionBtn: { flex: 1, paddingVertical: 14, borderRadius: 10, alignItems: 'center' },
  actionEnabled: { backgroundColor: '#00d4ff' },
  actionDisabled: { backgroundColor: '#333' },
  actionBtnText: { color: '#fff', fontSize: 14, fontWeight: 'bold' },
  infoRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#1a1a3e' },
  infoLabel: { fontSize: 14, color: '#888' },
  infoValue: { fontSize: 14, color: '#fff' },
  online: { color: '#00ff88' },
  offline: { color: '#ff6b6b' },
});
