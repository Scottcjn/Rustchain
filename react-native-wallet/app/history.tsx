/**
 * Transaction History Screen
 *
 * Displays transfer history for the active wallet using the RustChain node API.
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
import { useLocalSearchParams } from 'expo-router';
import {
  RustChainClient,
  Network,
  type TransferHistoryItem,
} from '../src/api/rustchain';
import { WalletStorage } from '../src/storage/secure';

const HISTORY_LIMIT = 50;
const client = new RustChainClient(Network.Mainnet);

export default function HistoryScreen() {
  const { walletName, address } = useLocalSearchParams<{
    walletName?: string;
    address?: string;
  }>();

  const [walletAddress, setWalletAddress] = useState('');
  const [transactions, setTransactions] = useState<TransferHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<'all' | 'sent' | 'received'>('all');
  const [errorMessage, setErrorMessage] = useState('');

  const loadTransactions = useCallback(async () => {
    try {
      setErrorMessage('');

      let resolvedAddress = typeof address === 'string' ? address : address?.[0] || '';
      const resolvedWalletName =
        typeof walletName === 'string' ? walletName : walletName?.[0] || '';

      if (!resolvedAddress && resolvedWalletName) {
        const metadata = await WalletStorage.getMetadata(resolvedWalletName);
        resolvedAddress = metadata?.address || '';
      }

      setWalletAddress(resolvedAddress);

      if (!resolvedAddress) {
        setTransactions([]);
        setErrorMessage('Open history from a wallet to load transactions.');
        return;
      }

      const history = await client.getTransferHistory(resolvedAddress, HISTORY_LIMIT);
      setTransactions(history);
    } catch (error) {
      console.error('Failed to load wallet history:', error);
      setTransactions([]);
      setErrorMessage('Failed to load transaction history from the RustChain network.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [address, walletName]);

  useEffect(() => {
    loadTransactions();
  }, [loadTransactions]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadTransactions();
  }, [loadTransactions]);

  const filteredTransactions = transactions.filter((tx) => {
    if (filter === 'all') return true;
    return tx.direction === filter;
  });

  const formatAmount = (amount: number): string => {
    const fixed = amount.toFixed(6);
    return fixed.replace(/\.?0+$/, '') || '0';
  };

  const formatDate = (timestamp?: number | null): string => {
    if (!timestamp) return 'Unknown';
    const date = new Date(timestamp * 1000);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  const formatAddress = (value: string): string => {
    if (!value) return 'Unknown';
    if (value.length <= 24) return value;
    return `${value.slice(0, 12)}...${value.slice(-8)}`;
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'confirmed':
        return '#00ff88';
      case 'pending':
        return '#ffaa00';
      case 'failed':
        return '#ff6b6b';
      default:
        return '#888';
    }
  };

  const renderConfirmations = (item: TransferHistoryItem): string => {
    if (item.status === 'confirmed') {
      return 'Confirmed';
    }
    if (item.status === 'pending') {
      return item.confirms_at
        ? `Expected ${formatDate(item.confirms_at)}`
        : 'Awaiting confirmation';
    }
    return item.status_reason || 'Transfer voided';
  };

  const renderTransactionItem = ({ item }: { item: TransferHistoryItem }) => (
    <TouchableOpacity
      style={styles.transactionCard}
      activeOpacity={0.7}
    >
      <View style={styles.transactionHeader}>
        <View style={styles.transactionType}>
          <View
            style={[
              styles.typeIcon,
              item.direction === 'sent' ? styles.sentIcon : styles.receivedIcon,
            ]}
          >
            <Text style={styles.typeIconText}>
              {item.direction === 'sent' ? '↑' : '↓'}
            </Text>
          </View>
          <Text style={styles.typeText}>
            {item.direction === 'sent' ? 'Sent' : 'Received'}
          </Text>
        </View>
        <Text
          style={[
            styles.amountText,
            item.direction === 'sent' ? styles.sentAmount : styles.receivedAmount,
          ]}
        >
          {item.direction === 'sent' ? '-' : '+'}
          {formatAmount(item.amount_rtc)} RTC
        </Text>
      </View>

      <View style={styles.transactionDetails}>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Counterparty:</Text>
          <Text style={styles.detailValue} selectable>
            {formatAddress(item.counterparty)}
          </Text>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Date:</Text>
          <Text style={styles.detailValue}>{formatDate(item.timestamp)}</Text>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Tx:</Text>
          <Text style={styles.detailValue} selectable>
            {formatAddress(item.tx_hash)}
          </Text>
        </View>
        {item.memo && (
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Memo:</Text>
            <Text style={styles.detailValue}>{item.memo}</Text>
          </View>
        )}
      </View>

      <View style={styles.transactionFooter}>
        <Text
          style={[styles.statusText, { color: getStatusColor(item.status) }]}
        >
          {item.status.toUpperCase()}
        </Text>
        <Text style={styles.confirmationsText}>
          {renderConfirmations(item)}
        </Text>
      </View>
    </TouchableOpacity>
  );

  const renderEmptyList = () => (
    <View style={styles.emptyContainer}>
      <Text style={styles.emptyTitle}>No Transactions</Text>
      <Text style={styles.emptyText}>
        {errorMessage || (filter === 'all'
          ? 'Your transfer history will appear here'
          : `No ${filter} transactions found`)}
      </Text>
    </View>
  );

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#00d4ff" />
        <Text style={styles.loadingText}>Loading history...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.filterContainer}>
        <TouchableOpacity
          style={[styles.filterButton, filter === 'all' && styles.filterButtonActive]}
          onPress={() => setFilter('all')}
          activeOpacity={0.7}
        >
          <Text
            style={[
              styles.filterButtonText,
              filter === 'all' && styles.filterButtonTextActive,
            ]}
          >
            All
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.filterButton, filter === 'sent' && styles.filterButtonActive]}
          onPress={() => setFilter('sent')}
          activeOpacity={0.7}
        >
          <Text
            style={[
              styles.filterButtonText,
              filter === 'sent' && styles.filterButtonTextActive,
            ]}
          >
            Sent
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.filterButton, filter === 'received' && styles.filterButtonActive]}
          onPress={() => setFilter('received')}
          activeOpacity={0.7}
        >
          <Text
            style={[
              styles.filterButtonText,
              filter === 'received' && styles.filterButtonTextActive,
            ]}
          >
            Received
          </Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={filteredTransactions}
        renderItem={renderTransactionItem}
        keyExtractor={(item) => item.tx_id}
        contentContainerStyle={
          filteredTransactions.length === 0 ? styles.emptyList : styles.list
        }
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor="#00d4ff"
          />
        }
        ListEmptyComponent={renderEmptyList}
      />

      <View style={styles.infoBox}>
        <Text style={styles.infoText}>
          {walletAddress
            ? `Showing up to ${HISTORY_LIMIT} transfers for ${formatAddress(walletAddress)}. Pull down to refresh.`
            : 'Open history from a wallet screen to load live transfers.'}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1a1a2e',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#1a1a2e',
  },
  loadingText: {
    color: '#888',
    marginTop: 10,
  },
  filterContainer: {
    flexDirection: 'row',
    padding: 15,
    gap: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#0f3460',
  },
  filterButton: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: 'center',
    backgroundColor: '#0f3460',
  },
  filterButtonActive: {
    backgroundColor: '#00d4ff',
  },
  filterButtonText: {
    color: '#888',
    fontSize: 14,
    fontWeight: 'bold',
  },
  filterButtonTextActive: {
    color: '#fff',
  },
  list: {
    padding: 15,
  },
  emptyList: {
    flex: 1,
  },
  transactionCard: {
    backgroundColor: '#16213e',
    borderRadius: 12,
    padding: 15,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#0f3460',
  },
  transactionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  transactionType: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  typeIcon: {
    width: 28,
    height: 28,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sentIcon: {
    backgroundColor: '#ff6b6b33',
  },
  receivedIcon: {
    backgroundColor: '#00ff8833',
  },
  typeIconText: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  typeText: {
    fontSize: 14,
    color: '#888',
  },
  amountText: {
    fontSize: 18,
    fontWeight: 'bold',
  },
  sentAmount: {
    color: '#ff6b6b',
  },
  receivedAmount: {
    color: '#00ff88',
  },
  transactionDetails: {
    gap: 5,
    marginBottom: 10,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
  },
  detailLabel: {
    fontSize: 12,
    color: '#666',
  },
  detailValue: {
    flex: 1,
    fontSize: 12,
    color: '#ccc',
    textAlign: 'right',
    fontFamily: 'monospace',
  },
  transactionFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#0f3460',
  },
  statusText: {
    fontSize: 12,
    fontWeight: 'bold',
  },
  confirmationsText: {
    flex: 1,
    fontSize: 12,
    color: '#666',
    textAlign: 'right',
    marginLeft: 12,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#888',
    marginBottom: 10,
  },
  emptyText: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
  },
  infoBox: {
    backgroundColor: '#16213e',
    padding: 15,
    margin: 15,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#0f3460',
  },
  infoText: {
    fontSize: 13,
    color: '#888',
    textAlign: 'center',
  },
});
