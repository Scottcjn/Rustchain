/**
 * Home Screen
 * 
 * Main wallet list and selection screen
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
import { useRouter } from 'expo-router';
import { WalletStorage, WalletMetadata } from '../src/storage/secure';

interface WalletItem {
  name: string;
  metadata: WalletMetadata;
}

export default function HomeScreen() {
  const router = useRouter();
  const [wallets, setWallets] = useState<WalletItem[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const loadWallets = useCallback(async () => {
    try {
      const walletNames = await WalletStorage.list();
      const walletItems: WalletItem[] = [];

      for (const name of walletNames) {
        const metadata = await WalletStorage.getMetadata(name);
        if (metadata) {
          walletItems.push({ name, metadata });
        }
      }

      setWallets(walletItems);
    } catch (error) {
      console.error('Failed to load wallets:', error);
    }
  }, []);

  React.useEffect(() => {
    loadWallets();
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadWallets();
    setRefreshing(false);
  }, [loadWallets]);

  const handleCreateWallet = () => {
    router.push('/wallet/create');
  };

  const handleImportWallet = () => {
    router.push('/wallet/import');
  };

  const handleSelectWallet = (name: string) => {
    router.push(`/wallet/${encodeURIComponent(name)}`);
  };

  const handleDeleteWallet = (name: string) => {
    Alert.alert(
      'Delete Wallet',
      `Are you sure you want to delete "${name}"? This action cannot be undone.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await WalletStorage.delete(name);
              await loadWallets();
              Alert.alert('Success', 'Wallet deleted');
            } catch (error) {
              Alert.alert('Error', 'Failed to delete wallet');
            }
          },
        },
      ]
    );
  };

  const renderWalletItem = ({ item }: { item: WalletItem }) => (
    <TouchableOpacity
      style={styles.walletCard}
      onPress={() => handleSelectWallet(item.name)}
      onLongPress={() => handleDeleteWallet(item.name)}
      activeOpacity={0.7}
    >
      <View style={styles.walletHeader}>
        <Text style={styles.walletName}>{item.metadata.name}</Text>
        <Text style={styles.walletAddress}>
          {item.metadata.address.slice(0, 20)}...
          {item.metadata.address.slice(-10)}
        </Text>
      </View>
      <View style={styles.walletFooter}>
        <Text style={styles.walletDate}>
          Created: {new Date(item.metadata.createdAt).toLocaleDateString()}
        </Text>
        <Text style={styles.walletNetwork}>{item.metadata.network ?? 'mainnet'}</Text>
      </View>
    </TouchableOpacity>
  );

  const renderEmptyList = () => (
    <View style={styles.emptyContainer}>
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
          style={[styles.actionButton, styles.createButton]}
          onPress={handleCreateWallet}
          activeOpacity={0.7}
        >
          <Text style={styles.actionButtonText}>Create New</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.actionButton, styles.importButton]}
          onPress={handleImportWallet}
          activeOpacity={0.7}
        >
          <Text style={styles.actionButtonText}>Import</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={wallets}
        renderItem={renderWalletItem}
        keyExtractor={(item) => item.name}
        contentContainerStyle={wallets.length === 0 ? styles.emptyList : styles.list}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor="#00d4ff"
          />
        }
        ListEmptyComponent={renderEmptyList}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1a1a2e',
  },
  header: {
    padding: 20,
    paddingTop: 60,
    backgroundColor: '#16213e',
    borderBottomWidth: 1,
    borderBottomColor: '#0f3460',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#00d4ff',
    marginBottom: 5,
  },
  subtitle: {
    fontSize: 14,
    color: '#888',
  },
  buttonRow: {
    flexDirection: 'row',
    padding: 15,
    gap: 10,
  },
  actionButton: {
    flex: 1,
    paddingVertical: 15,
    borderRadius: 10,
    alignItems: 'center',
  },
  createButton: {
    backgroundColor: '#00d4ff',
  },
  importButton: {
    backgroundColor: '#0f3460',
    borderWidth: 1,
    borderColor: '#00d4ff',
  },
  actionButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
  list: {
    padding: 15,
  },
  emptyList: {
    flex: 1,
  },
  walletCard: {
    backgroundColor: '#16213e',
    borderRadius: 12,
    padding: 15,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#0f3460',
  },
  walletHeader: {
    marginBottom: 10,
  },
  walletName: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 5,
  },
  walletAddress: {
    fontSize: 12,
    color: '#888',
    fontFamily: 'monospace',
  },
  walletFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  walletDate: {
    fontSize: 12,
    color: '#666',
  },
  walletNetwork: {
    fontSize: 12,
    color: '#00ff88',
    fontWeight: 'bold',
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
});
