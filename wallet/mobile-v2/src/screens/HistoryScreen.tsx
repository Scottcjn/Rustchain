/**
 * History Screen
 *
 * Transaction history with sent/received filter and pull-to-refresh.
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/AppNavigator';
import { RustChainClient } from '../services/api';
import { WalletStorage } from '../services/storage';
import { TransactionList } from '../components/TransactionList';
import type { TransferHistoryItem } from '../types';

type Props = NativeStackScreenProps<RootStackParamList, 'History'>;
type Filter = 'all' | 'sent' | 'received';

const HISTORY_LIMIT = 50;

export default function HistoryScreen({ route }: Props): React.JSX.Element {
  const { walletName, address: paramAddress } = route.params;

  const [address, setAddress] = useState(paramAddress || '');
  const [transactions, setTransactions] = useState<TransferHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<Filter>('all');
  const [errorMsg, setErrorMsg] = useState('');

  const client = new RustChainClient();

  const loadHistory = useCallback(async () => {
    try {
      setErrorMsg('');
      let resolvedAddr = paramAddress || '';
      if (!resolvedAddr && walletName) {
        const meta = await WalletStorage.getMetadata(walletName);
        resolvedAddr = meta?.address || '';
      }
      setAddress(resolvedAddr);
      if (!resolvedAddr) {
        setTransactions([]);
        setErrorMsg('No wallet address available.');
        return;
      }
      const history = await client.getTransferHistory(resolvedAddr, HISTORY_LIMIT);
      setTransactions(history);
    } catch {
      setTransactions([]);
      setErrorMsg('Failed to load transaction history.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [paramAddress, walletName]);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadHistory();
  }, [loadHistory]);

  const filtered = transactions.filter((tx) => filter === 'all' || tx.direction === filter);

  const formatAddr = (a: string): string =>
    a.length <= 24 ? a : `${a.slice(0, 12)}...${a.slice(-8)}`;

  if (loading) {
    return (
      <View style={styles.loadingBox}>
        <ActivityIndicator size="large" color="#00d4ff" />
        <Text style={styles.loadingText}>Loading history...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Filters */}
      <View style={styles.filterRow}>
        {(['all', 'sent', 'received'] as Filter[]).map((f) => (
          <TouchableOpacity
            key={f}
            style={[styles.filterBtn, filter === f && styles.filterActive]}
            onPress={() => setFilter(f)}
            activeOpacity={0.7}
          >
            <Text style={[styles.filterText, filter === f && styles.filterTextActive]}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <FlatList
        data={filtered}
        renderItem={({ item }) => (
          <TransactionList transactions={[item]} />
        )}
        keyExtractor={(item) => item.tx_id}
        contentContainerStyle={filtered.length === 0 ? styles.emptyList : styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#00d4ff" />}
        ListEmptyComponent={
          <View style={styles.emptyBox}>
            <Text style={styles.emptyTitle}>No Transactions</Text>
            <Text style={styles.emptyText}>
              {errorMsg || (filter === 'all' ? 'History will appear here' : `No ${filter} transactions`)}
            </Text>
          </View>
        }
      />

      <View style={styles.infoBar}>
        <Text style={styles.infoText}>
          {address
            ? `Showing up to ${HISTORY_LIMIT} transfers for ${formatAddr(address)}`
            : 'Open from a wallet to load transfers'}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a1a' },
  loadingBox: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0a0a1a' },
  loadingText: { color: '#888', marginTop: 10 },
  filterRow: { flexDirection: 'row', padding: 16, gap: 10, borderBottomWidth: 1, borderBottomColor: '#1a1a3e' },
  filterBtn: { flex: 1, paddingVertical: 10, borderRadius: 8, alignItems: 'center', backgroundColor: '#12122a' },
  filterActive: { backgroundColor: '#00d4ff' },
  filterText: { color: '#888', fontSize: 14, fontWeight: 'bold' },
  filterTextActive: { color: '#fff' },
  list: { padding: 16 },
  emptyList: { flex: 1 },
  emptyBox: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 40 },
  emptyTitle: { fontSize: 20, fontWeight: 'bold', color: '#888', marginBottom: 8 },
  emptyText: { fontSize: 14, color: '#666', textAlign: 'center' },
  infoBar: { backgroundColor: '#12122a', padding: 14, margin: 16, borderRadius: 10, borderWidth: 1, borderColor: '#1a1a3e' },
  infoText: { fontSize: 13, color: '#888', textAlign: 'center' },
});
