/**
 * BalanceCard Component
 *
 * Displays wallet balance with RTC and approximate USD value.
 */

import React from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { MICRO_RTC_PER_RTC } from '../types';

interface BalanceCardProps {
  balance: number | null;
  loading?: boolean;
}

export function BalanceCard({ balance, loading }: BalanceCardProps): React.JSX.Element {
  const formatBalance = (bal: number): string => {
    return (bal / MICRO_RTC_PER_RTC).toFixed(6);
  };

  return (
    <View style={styles.card}>
      <Text style={styles.label}>Balance</Text>
      {loading ? (
        <ActivityIndicator size="large" color="#00d4ff" style={styles.loader} />
      ) : (
        <>
          <Text style={styles.value}>
            {balance !== null ? formatBalance(balance) : '---'}{' '}
            <Text style={styles.currency}>RTC</Text>
          </Text>
          {balance !== null && (
            <Text style={styles.usd}>
              ~${((balance / MICRO_RTC_PER_RTC) * 0.1).toFixed(4)} USD
            </Text>
          )}
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#16213e',
    borderRadius: 16,
    padding: 24,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#00d4ff',
  },
  label: {
    fontSize: 14,
    color: '#888',
    marginBottom: 8,
  },
  value: {
    fontSize: 36,
    fontWeight: 'bold',
    color: '#00ff88',
  },
  currency: {
    fontSize: 20,
    color: '#00ff88',
  },
  usd: {
    fontSize: 14,
    color: '#666',
    marginTop: 4,
  },
  loader: {
    marginVertical: 16,
  },
});
