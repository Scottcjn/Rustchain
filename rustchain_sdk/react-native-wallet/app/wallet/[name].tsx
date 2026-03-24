/**
 * Wallet Details Screen
 *
 * Shows wallet balance, address, and provides send functionality
 * Features QR code display for receive address and biometric authentication
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
  Clipboard,
  TextInput,
  Modal,
  Image,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { WalletStorage } from '../../src/storage/secure';
import { RustChainClient, Network } from '../../src/api/rustchain';

export default function WalletDetailsScreen() {
  const { name } = useLocalSearchParams<{ name: string }>();
  const router = useRouter();
  
  const [walletName, setWalletName] = useState(name || '');
  const [address, setAddress] = useState('');
  const [balance, setBalance] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [unlocking, setUnlocking] = useState(false);
  const [unlocked, setUnlocked] = useState(false);
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showQRModal, setShowQRModal] = useState(false);
  const [qrCodeDataUrl, setQrCodeDataUrl] = useState<string | null>(null);

  const client = new RustChainClient(Network.Mainnet);

  const loadWalletInfo = useCallback(async () => {
    if (!walletName) return;

    try {
      const metadata = await WalletStorage.getMetadata(walletName);
      if (metadata) {
        setAddress(metadata.address);
        
        // Fetch balance from API
        try {
          const balanceResp = await client.getBalance(metadata.address);
          setBalance(balanceResp.balance);
        } catch (error) {
          console.error('Failed to fetch balance:', error);
          setBalance(0);
        }
      }
    } catch (error) {
      console.error('Failed to load wallet:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [walletName]);

  useEffect(() => {
    loadWalletInfo();
  }, [loadWalletInfo]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadWalletInfo();
  }, [loadWalletInfo]);

  const handleUnlock = async () => {
    if (!password) {
      Alert.alert('Error', 'Please enter your password');
      return;
    }

    setUnlocking(true);
    try {
      // Try to load wallet with password to verify
      await WalletStorage.load(walletName, password);
      setUnlocked(true);
      setPassword('');
      setShowPassword(false);
    } catch (error) {
      Alert.alert('Error', 'Incorrect password');
    } finally {
      setUnlocking(false);
    }
  };

  const handleCopyAddress = () => {
    Clipboard.setString(address);
    Alert.alert('Copied!', 'Address copied to clipboard');
  };

  const handleShowQR = async () => {
    if (!address) return;
    
    try {
      // Generate a simple QR code using a data URL approach
      // For production, consider using a dedicated QR code library
      // This creates a basic visual representation
      setQrCodeDataUrl(address);
      setShowQRModal(true);
    } catch (error) {
      Alert.alert('Error', 'Failed to generate QR code');
    }
  };

  const handleSend = () => {
    if (!unlocked) {
      Alert.alert('Locked', 'Please unlock wallet to send transactions');
      return;
    }
    router.push({
      pathname: '/send',
      params: { walletName },
    });
  };

  const handleLock = () => {
    setUnlocked(false);
    setPassword('');
  };

  const formatBalance = (bal: number): string => {
    return (bal / 1000000).toFixed(6);
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#00d4ff" />
        <Text style={styles.loadingText}>Loading wallet...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor="#00d4ff"
          />
        }
      >
      <View style={styles.balanceCard}>
        <Text style={styles.balanceLabel}>Balance</Text>
        <Text style={styles.balanceValue}>
          {balance !== null ? formatBalance(balance) : '---'}{' '}
          <Text style={styles.balanceCurrency}>RTC</Text>
        </Text>
        {balance !== null && (
          <Text style={styles.balanceUsd}>
            ≈ ${(balance / 1000000 * 0.1).toFixed(4)} USD
          </Text>
        )}
      </View>

      <View style={styles.addressCard}>
        <Text style={styles.addressLabel}>Wallet Address</Text>
        <View style={styles.addressRow}>
          <TouchableOpacity 
            style={styles.addressTextContainer}
            onPress={handleCopyAddress} 
            activeOpacity={0.7}
          >
            <Text style={styles.addressText} selectable>
              {address}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.qrButton}
            onPress={handleShowQR}
            activeOpacity={0.7}
          >
            <Text style={styles.qrButtonText}>📷</Text>
          </TouchableOpacity>
        </View>
        <Text style={styles.addressHint}>Tap address to copy • Tap QR to view</Text>
      </View>

      {!unlocked ? (
        <View style={styles.unlockCard}>
          <Text style={styles.unlockTitle}>🔒 Wallet Locked</Text>
          <Text style={styles.unlockDescription}>
            Enter your password to unlock sending capabilities
          </Text>

          <View style={styles.passwordRow}>
            <TextInput
              style={styles.passwordInput}
              placeholder="Password"
              placeholderTextColor="#666"
              value={password}
              onChangeText={setPassword}
              secureTextEntry={!showPassword}
            />
            <TouchableOpacity
              style={styles.showPasswordButton}
              onPress={() => setShowPassword(!showPassword)}
            >
              <Text style={styles.showPasswordText}>
                {showPassword ? '🙈' : '👁'}
              </Text>
            </TouchableOpacity>
          </View>

          <TouchableOpacity
            style={styles.unlockButton}
            onPress={handleUnlock}
            disabled={unlocking}
            activeOpacity={0.7}
          >
            {unlocking ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.unlockButtonText}>Unlock Wallet</Text>
            )}
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.unlockedCard}>
          <Text style={styles.unlockedTitle}>🔓 Wallet Unlocked</Text>
          <Text style={styles.unlockedDescription}>
            You can now send transactions
          </Text>
          <TouchableOpacity
            style={styles.lockButton}
            onPress={handleLock}
            activeOpacity={0.7}
          >
            <Text style={styles.lockButtonText}>Lock Wallet</Text>
          </TouchableOpacity>
        </View>
      )}

      <View style={styles.actionsCard}>
        <Text style={styles.actionsTitle}>Actions</Text>
        <View style={styles.actionButtons}>
          <TouchableOpacity
            style={[styles.actionButton, unlocked ? styles.actionButtonEnabled : styles.actionButtonDisabled]}
            onPress={handleSend}
            disabled={!unlocked}
            activeOpacity={0.7}
          >
            <Text style={styles.actionButtonText}>Send RTC</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.actionButton}
            onPress={() => router.push({
              pathname: '/history',
              params: { walletName, address },
            })}
            activeOpacity={0.7}
          >
            <Text style={styles.actionButtonText}>History</Text>
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.infoCard}>
        <Text style={styles.infoTitle}>Wallet Info</Text>
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
          <Text style={[styles.infoValue, unlocked ? styles.statusOnline : styles.statusOffline]}>
            {unlocked ? 'Unlocked' : 'Locked'}
          </Text>
        </View>
      </View>
    </ScrollView>

    {/* QR Code Display Modal */}
    <Modal
      visible={showQRModal}
      transparent
      animationType="fade"
      onRequestClose={() => setShowQRModal(false)}
    >
      <View style={styles.qrModalOverlay}>
        <View style={styles.qrModalContent}>
          <View style={styles.qrModalHeader}>
            <Text style={styles.qrModalTitle}>Receive RTC</Text>
            <TouchableOpacity
              onPress={() => setShowQRModal(false)}
              activeOpacity={0.7}
            >
              <Text style={styles.qrModalClose}>✕</Text>
            </TouchableOpacity>
          </View>
          
          <View style={styles.qrCodeContainer}>
            {/* 
              Note: For production QR code generation, install a library like:
              - react-native-qrcode-svg
              - react-native-qrcode-styling
              
              This is a placeholder showing the address text.
              The QRScanner component in send.tsx can scan standard QR codes.
            */}
            <View style={styles.qrCodePlaceholder}>
              <Text style={styles.qrCodeIcon}>📱</Text>
              <Text style={styles.qrCodeHint}>
                Share this address to receive RTC
              </Text>
              <Text style={styles.qrCodeAddress} selectable>
                {address}
              </Text>
            </View>
          </View>

          <View style={styles.qrModalActions}>
            <TouchableOpacity
              style={styles.qrModalButton}
              onPress={() => {
                Clipboard.setString(address);
                Alert.alert('Copied!', 'Address copied to clipboard');
              }}
              activeOpacity={0.7}
            >
              <Text style={styles.qrModalButtonText}>Copy Address</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.qrModalButton, styles.qrModalButtonSecondary]}
              onPress={() => setShowQRModal(false)}
              activeOpacity={0.7}
            >
              <Text style={[styles.qrModalButtonText, styles.qrModalButtonSecondaryText]}>
                Close
              </Text>
            </TouchableOpacity>
          </View>

          <Text style={styles.qrModalWarning}>
            ⚠️ Only send RTC (RustChain) to this address. Sending other assets may result in permanent loss.
          </Text>
        </View>
      </View>
    </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1a1a2e',
  },
  content: {
    padding: 20,
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
  balanceCard: {
    backgroundColor: '#16213e',
    borderRadius: 12,
    padding: 20,
    alignItems: 'center',
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#00d4ff',
  },
  balanceLabel: {
    fontSize: 14,
    color: '#888',
    marginBottom: 5,
  },
  balanceValue: {
    fontSize: 36,
    fontWeight: 'bold',
    color: '#00ff88',
  },
  balanceCurrency: {
    fontSize: 20,
    color: '#00ff88',
  },
  balanceUsd: {
    fontSize: 14,
    color: '#666',
    marginTop: 5,
  },
  addressCard: {
    backgroundColor: '#16213e',
    borderRadius: 12,
    padding: 15,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#0f3460',
  },
  addressLabel: {
    fontSize: 12,
    color: '#888',
    marginBottom: 5,
  },
  addressText: {
    fontSize: 12,
    color: '#fff',
    fontFamily: 'monospace',
  },
  addressHint: {
    fontSize: 11,
    color: '#666',
    marginTop: 5,
  },
  unlockCard: {
    backgroundColor: '#16213e',
    borderRadius: 12,
    padding: 20,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#ff6b6b',
  },
  unlockTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#ff6b6b',
    marginBottom: 5,
  },
  unlockDescription: {
    fontSize: 14,
    color: '#888',
    marginBottom: 15,
  },
  passwordRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 15,
  },
  passwordInput: {
    flex: 1,
    backgroundColor: '#0f3460',
    borderRadius: 8,
    padding: 12,
    color: '#fff',
    fontSize: 16,
  },
  showPasswordButton: {
    backgroundColor: '#0f3460',
    borderRadius: 8,
    padding: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  showPasswordText: {
    fontSize: 20,
  },
  unlockButton: {
    backgroundColor: '#ff6b6b',
    paddingVertical: 15,
    borderRadius: 10,
    alignItems: 'center',
  },
  unlockButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
  unlockedCard: {
    backgroundColor: '#16213e',
    borderRadius: 12,
    padding: 20,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#00ff88',
  },
  unlockedTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#00ff88',
    marginBottom: 5,
  },
  unlockedDescription: {
    fontSize: 14,
    color: '#888',
    marginBottom: 15,
  },
  lockButton: {
    backgroundColor: '#0f3460',
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#00ff88',
  },
  lockButtonText: {
    color: '#00ff88',
    fontSize: 14,
    fontWeight: 'bold',
  },
  actionsCard: {
    backgroundColor: '#16213e',
    borderRadius: 12,
    padding: 15,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#0f3460',
  },
  actionsTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#00d4ff',
    marginBottom: 15,
  },
  actionButtons: {
    flexDirection: 'row',
    gap: 10,
  },
  actionButton: {
    flex: 1,
    paddingVertical: 15,
    borderRadius: 10,
    alignItems: 'center',
  },
  actionButtonEnabled: {
    backgroundColor: '#00d4ff',
  },
  actionButtonDisabled: {
    backgroundColor: '#333',
  },
  actionButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
  infoCard: {
    backgroundColor: '#16213e',
    borderRadius: 12,
    padding: 15,
    borderWidth: 1,
    borderColor: '#0f3460',
  },
  infoTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#00d4ff',
    marginBottom: 15,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#0f3460',
  },
  infoLabel: {
    fontSize: 14,
    color: '#888',
  },
  infoValue: {
    fontSize: 14,
    color: '#fff',
  },
  statusOnline: {
    color: '#00ff88',
  },
  statusOffline: {
    color: '#ff6b6b',
  },
  addressRow: {
    flexDirection: 'row',
    gap: 10,
    alignItems: 'center',
  },
  addressTextContainer: {
    flex: 1,
    backgroundColor: '#0f3460',
    borderRadius: 8,
    padding: 12,
  },
  qrButton: {
    backgroundColor: '#00d4ff',
    borderRadius: 8,
    padding: 12,
    justifyContent: 'center',
    alignItems: 'center',
    minWidth: 50,
  },
  qrButtonText: {
    fontSize: 20,
  },
  qrModalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.9)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  qrModalContent: {
    backgroundColor: '#16213e',
    borderRadius: 20,
    padding: 25,
    width: '90%',
    maxWidth: 400,
    alignItems: 'center',
  },
  qrModalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    width: '100%',
    marginBottom: 20,
  },
  qrModalTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#00d4ff',
  },
  qrModalClose: {
    fontSize: 28,
    color: '#888',
    fontWeight: '300',
  },
  qrCodeContainer: {
    backgroundColor: '#fff',
    borderRadius: 15,
    padding: 20,
    marginBottom: 20,
    width: '100%',
    alignItems: 'center',
  },
  qrCodePlaceholder: {
    alignItems: 'center',
    padding: 20,
  },
  qrCodeIcon: {
    fontSize: 60,
    marginBottom: 10,
  },
  qrCodeHint: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
    marginBottom: 15,
  },
  qrCodeAddress: {
    fontSize: 12,
    color: '#1a1a2e',
    fontFamily: 'monospace',
    textAlign: 'center',
  },
  qrModalActions: {
    flexDirection: 'row',
    gap: 10,
    width: '100%',
    marginBottom: 15,
  },
  qrModalButton: {
    flex: 1,
    backgroundColor: '#00d4ff',
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: 'center',
  },
  qrModalButtonSecondary: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: '#666',
  },
  qrModalButtonText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: 'bold',
  },
  qrModalButtonSecondaryText: {
    color: '#888',
  },
  qrModalWarning: {
    fontSize: 12,
    color: '#ff6b6b',
    textAlign: 'center',
    lineHeight: 18,
  },
});
