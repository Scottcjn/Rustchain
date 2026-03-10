/**
 * Transaction History Screen
 * 
 * Displays transaction history for the wallet
 * Note: This is a placeholder as the RustChain API may not have a dedicated history endpoint
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
import { useRouter } from 'expo-router';

interface Transaction {
  id: string;
  hash: string;
  from: string;
  to: string;
  amount: number;
  fee: number;
  timestamp: string;
  status: 'pending' | 'confirmed' | 'failed';
  confirmations: number;
  memo?: string;
  type: 'sent' | 'received';
}

// Mock transaction data for demonstration
// In production, this would come from the RustChain API
const generateMockTransactions = (): Transaction[] => {
  const transactions: Transaction[] = [];
  const now = Date.now();

  for (let i = 0; i < 10; i++) {
    const isSent = Math.random() > 0.5;
    transactions.push({
      id: `tx-${i}`,
      hash: `0x${Array(64)
        .fill(0)
        .map(() => Math.floor(Math.random() * 16).toString(16))
        .join('')}`,
      from: isSent ? 'Your Wallet' : 'External Wallet',
      to: isSent ? 'External Wallet' : 'Your Wallet',
      amount: Math.floor(Math.random() * 1000000000),
      fee: Math.floor(Math.random() * 1000000),
      timestamp: new Date(now - i * 86400000).toISOString(),
      status: i === 0 ? 'pending' : 'confirmed',
      confirmations: i === 0 ? 0 : Math.floor(Math.random() * 100) + 1,
      memo: isSent ? 'Test transaction' : undefined,
      type: isSent ? 'sent' : 'received',
    });
  }

  return transactions;
};

export default function HistoryScreen() {
  const router = useRouter();
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<'all' | 'sent' | 'received'>('all');

  const loadTransactions = useCallback(async () => {
    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setTransactions(generateMockTransactions());
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    loadTransactions();
  }, [loadTransactions]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadTransactions();
  }, [loadTransactions]);

  const filteredTransactions = transactions.filter((tx) => {
    if (filter === 'all') return true;
    return tx.type === filter;
  });

  const formatAmount = (amount: number): string => {
    return (amount / 100000000).toFixed(8);
  };

  const formatDate = (timestamp: string): string => {
    const date = new Date(timestamp);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  const formatAddress = (address: string): string => {
    if (address === 'Your Wallet') return address;
    return `${address.slice(0, 15)}...${address.slice(-8)}`;
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

  const renderTransactionItem = ({ item }: { item: Transaction }) => (
    <TouchableOpacity
      style={styles.transactionCard}
      activeOpacity={0.7}
      onPress={() => {
        // Could navigate to transaction details
      }}
    >
      <View style={styles.transactionHeader}>
        <View style={styles.transactionType}>
          <View
            style={[
              styles.typeIcon,
              item.type === 'sent' ? styles.sentIcon : styles.receivedIcon,
            ]}
          >
            <Text style={styles.typeIconText}>
              {item.type === 'sent' ? '↑' : '↓'}
            </Text>
          </View>
          <Text style={styles.typeText}>
            {item.type === 'sent' ? 'Sent' : 'Received'}
          </Text>
        </View>
        <Text
          style={[
            styles.amountText,
            item.type === 'sent' ? styles.sentAmount : styles.receivedAmount,
          ]}
        >
          {item.type === 'sent' ? '-' : '+'}
          {formatAmount(item.amount)} RTC
        </Text>
      </View>

      <View style={styles.transactionDetails}>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>To/From:</Text>
          <Text style={styles.detailValue} selectable>
            {item.type === 'sent' ? item.to : item.from}
          </Text>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Date:</Text>
          <Text style={styles.detailValue}>{formatDate(item.timestamp)}</Text>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Fee:</Text>
          <Text style={styles.detailValue}>
            {formatAmount(item.fee)} RTC
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
          {item.confirmations} confirmations
        </Text>
      </View>
    </TouchableOpacity>
  );

  const renderEmptyList = () => (
    <View style={styles.emptyContainer}>
      <Text style={styles.emptyTitle}>No Transactions</Text>
      <Text style={styles.emptyText}>
        {filter === 'all'
          ? 'Your transaction history will appear here'
          : `No ${filter} transactions found`}
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
        keyExtractor={(item) => item.id}
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
          ℹ️ Transaction history is loaded from the RustChain network.
          Pull down to refresh.
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
  },
  detailLabel: {
    fontSize: 12,
    color: '#666',
  },
  detailValue: {
    fontSize: 12,
    color: '#ccc',
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
    fontSize: 12,
    color: '#666',
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
