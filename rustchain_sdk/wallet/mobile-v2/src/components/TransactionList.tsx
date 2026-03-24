/**
 * TransactionList Component
 *
 * Renders a list of transfer history items with direction indicators,
 * amounts, counterparty, and status.
 */

import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import type { TransferHistoryItem } from '../types';

interface TransactionListProps {
  transactions: TransferHistoryItem[];
  onPress?: (tx: TransferHistoryItem) => void;
}

export function TransactionList({
  transactions,
  onPress,
}: TransactionListProps): React.JSX.Element {
  const formatAmount = (amount: number): string => {
    const fixed = amount.toFixed(6);
    return fixed.replace(/\.?0+$/, '') || '0';
  };

  const formatDate = (ts?: number | null): string => {
    if (!ts) return 'Unknown';
    const d = new Date(ts * 1000);
    return `${d.toLocaleDateString()} ${d.toLocaleTimeString()}`;
  };

  const formatAddr = (addr: string): string => {
    if (!addr) return 'Unknown';
    if (addr.length <= 24) return addr;
    return `${addr.slice(0, 12)}...${addr.slice(-8)}`;
  };

  const statusColor = (status: string): string => {
    switch (status) {
      case 'confirmed': return '#00ff88';
      case 'pending':   return '#ffaa00';
      case 'failed':    return '#ff6b6b';
      default:          return '#888';
    }
  };

  if (transactions.length === 0) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyTitle}>No Transactions</Text>
        <Text style={styles.emptyText}>Your transfer history will appear here</Text>
      </View>
    );
  }

  return (
    <View>
      {transactions.map((tx) => (
        <TouchableOpacity
          key={tx.tx_id}
          style={styles.card}
          onPress={() => onPress?.(tx)}
          activeOpacity={0.7}
        >
          <View style={styles.header}>
            <View style={styles.typeRow}>
              <View
                style={[
                  styles.icon,
                  tx.direction === 'sent' ? styles.sentIcon : styles.receivedIcon,
                ]}
              >
                <Text style={styles.iconText}>
                  {tx.direction === 'sent' ? '\u2191' : '\u2193'}
                </Text>
              </View>
              <Text style={styles.typeText}>
                {tx.direction === 'sent' ? 'Sent' : 'Received'}
              </Text>
            </View>
            <Text
              style={[
                styles.amount,
                tx.direction === 'sent' ? styles.sentAmt : styles.receivedAmt,
              ]}
            >
              {tx.direction === 'sent' ? '-' : '+'}
              {formatAmount(tx.amount_rtc)} RTC
            </Text>
          </View>

          <View style={styles.details}>
            <View style={styles.row}>
              <Text style={styles.detailLabel}>To/From:</Text>
              <Text style={styles.detailValue} selectable>
                {formatAddr(tx.counterparty)}
              </Text>
            </View>
            <View style={styles.row}>
              <Text style={styles.detailLabel}>Date:</Text>
              <Text style={styles.detailValue}>{formatDate(tx.timestamp)}</Text>
            </View>
            {tx.memo ? (
              <View style={styles.row}>
                <Text style={styles.detailLabel}>Memo:</Text>
                <Text style={styles.detailValue}>{tx.memo}</Text>
              </View>
            ) : null}
          </View>

          <View style={styles.footer}>
            <Text style={[styles.status, { color: statusColor(tx.status) }]}>
              {tx.status.toUpperCase()}
            </Text>
            <Text style={styles.txHash}>{formatAddr(tx.tx_hash)}</Text>
          </View>
        </TouchableOpacity>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#16213e',
    borderRadius: 12,
    padding: 15,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#0f3460',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  typeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  icon: {
    width: 28,
    height: 28,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sentIcon: { backgroundColor: '#ff6b6b33' },
  receivedIcon: { backgroundColor: '#00ff8833' },
  iconText: { fontSize: 16, fontWeight: 'bold', color: '#fff' },
  typeText: { fontSize: 14, color: '#888' },
  amount: { fontSize: 18, fontWeight: 'bold' },
  sentAmt: { color: '#ff6b6b' },
  receivedAmt: { color: '#00ff88' },
  details: { gap: 4, marginBottom: 10 },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
  },
  detailLabel: { fontSize: 12, color: '#666' },
  detailValue: { flex: 1, fontSize: 12, color: '#ccc', textAlign: 'right', fontFamily: 'monospace' },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#0f3460',
  },
  status: { fontSize: 12, fontWeight: 'bold' },
  txHash: { fontSize: 11, color: '#555', fontFamily: 'monospace' },
  empty: {
    alignItems: 'center',
    padding: 40,
  },
  emptyTitle: { fontSize: 20, fontWeight: 'bold', color: '#888', marginBottom: 8 },
  emptyText: { fontSize: 14, color: '#666', textAlign: 'center' },
});
