/**
 * Home Screen
 *
 * Wallet list with create/import actions. Pull-to-refresh. Long-press to delete.
 */

import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  FlatList,
  RefreshControl,
  Alert,
} from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/AppNavigator';
import { WalletStorage } from '../services/storage';
import type { WalletMetadata } from '../types';

type Props = NativeStackScreenProps<RootStackParamList, 'Home'>;

interface WalletItem {
  name: string;
  metadata: WalletMetadata;
}

export default function HomeScreen({ navigation }: Props): React.JSX.Element {
  const [wallets, setWallets] = useState<WalletItem[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const loadWallets = useCallback(async () => {
    try {
      const names = await WalletStorage.list();
      const items: WalletItem[] = [];
      for (const name of names) {
        const metadata = await WalletStorage.getMetadata(name);
        if (metadata) items.push({ name, metadata });
      }
      setWallets(items);
    } catch (err) {
      console.error('Failed to load wallets:', err);
    }
  }, []);

  React.useEffect(() => {
    const unsub = navigation.addListener('focus', loadWallets);
    return unsub;
  }, [navigation, loadWallets]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadWallets();
    setRefreshing(false);
  }, [loadWallets]);

  const handleDelete = (name: string) => {
    Alert.alert(
      'Delete Wallet',
      `Delete "${name}"? This cannot be undone.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            await WalletStorage.delete(name);
            await loadWallets();
          },
        },
      ]
    );
  };

  const renderItem = ({ item }: { item: WalletItem }) => (
    <TouchableOpacity
      style={styles.card}
      onPress={() => navigation.navigate('WalletDetail', { walletName: item.name })}
      onLongPress={() => handleDelete(item.name)}
      activeOpacity={0.7}
    >
      <View style={styles.cardHeader}>
        <Text style={styles.cardName}>{item.metadata.name}</Text>
        <Text style={styles.cardAddr}>
          {item.metadata.address.slice(0, 20)}...{item.metadata.address.slice(-10)}
        </Text>
      </View>
      <View style={styles.cardFooter}>
        <Text style={styles.cardDate}>
          Created: {new Date(item.metadata.createdAt).toLocaleDateString()}
        </Text>
        <Text style={styles.cardNetwork}>{item.metadata.network ?? 'mainnet'}</Text>
      </View>
    </TouchableOpacity>
  );

  const renderEmpty = () => (
    <View style={styles.empty}>
      <Text style={styles.emptyTitle}>No Wallets Yet</Text>
      <Text style={styles.emptyText}>
        Create a new wallet or import an existing one to get started
      </Text>
    </View>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>RustChain Wallet</Text>
        <Text style={styles.subtitle}>Manage your RTC tokens</Text>
      </View>

      <View style={styles.buttonRow}>
        <TouchableOpacity
          style={[styles.actionBtn, styles.createBtn]}
          onPress={() => navigation.navigate('CreateWallet')}
          activeOpacity={0.7}
        >
          <Text style={styles.actionBtnText}>Create New</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.actionBtn, styles.importBtn]}
          onPress={() => navigation.navigate('ImportWallet')}
          activeOpacity={0.7}
        >
          <Text style={styles.actionBtnText}>Import</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={wallets}
        renderItem={renderItem}
        keyExtractor={(item) => item.name}
        contentContainerStyle={wallets.length === 0 ? styles.emptyList : styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#00d4ff" />
        }
        ListEmptyComponent={renderEmpty}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a1a' },
  header: { padding: 20, paddingTop: 60, backgroundColor: '#12122a', borderBottomWidth: 1, borderBottomColor: '#1a1a3e' },
  title: { fontSize: 28, fontWeight: 'bold', color: '#00d4ff', marginBottom: 4 },
  subtitle: { fontSize: 14, color: '#888' },
  buttonRow: { flexDirection: 'row', padding: 16, gap: 10 },
  actionBtn: { flex: 1, paddingVertical: 14, borderRadius: 12, alignItems: 'center' },
  createBtn: { backgroundColor: '#00d4ff' },
  importBtn: { backgroundColor: '#12122a', borderWidth: 1, borderColor: '#00d4ff' },
  actionBtnText: { color: '#fff', fontSize: 16, fontWeight: 'bold' },
  list: { padding: 16 },
  emptyList: { flex: 1 },
  card: { backgroundColor: '#12122a', borderRadius: 12, padding: 16, marginBottom: 10, borderWidth: 1, borderColor: '#1a1a3e' },
  cardHeader: { marginBottom: 10 },
  cardName: { fontSize: 18, fontWeight: 'bold', color: '#fff', marginBottom: 4 },
  cardAddr: { fontSize: 12, color: '#888', fontFamily: 'monospace' },
  cardFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cardDate: { fontSize: 12, color: '#666' },
  cardNetwork: { fontSize: 12, color: '#00ff88', fontWeight: 'bold' },
  empty: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 40 },
  emptyTitle: { fontSize: 20, fontWeight: 'bold', color: '#888', marginBottom: 8 },
  emptyText: { fontSize: 14, color: '#666', textAlign: 'center' },
});
