/**
 * Send Transaction Screen (Hardened)
 *
 * Allows users to send RTC with dry-run validation
 * Features QR code scanning and biometric authentication
 *
 * Issue #785: Security hardening
 * - Password NOT passed via router params
 * - Secure re-authentication for export
 * - Numeric validation hardening
 * - chain_id in signed payload
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  ScrollView,
  Switch,
  Modal,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { WalletStorage } from '../src/storage/secure';
import {
  RustChainClient,
  Network,
  dryRunTransfer,
  DryRunResult,
  validateTransactionInput,
} from '../src/api/rustchain';
import { KeyPair, isValidAddress } from '../src/utils/crypto';
import { QRScanner } from '../src/components/QRScanner';
import {
  authenticateWithBiometricsOrFallback,
  isBiometricAvailable,
  getBiometricTypeName,
} from '../src/utils/biometric';

export default function SendScreen() {
  // Issue #785: Only get walletName from params, NOT password
  const { walletName } = useLocalSearchParams<{
    walletName: string;
  }>();
  const router = useRouter();

  const [recipient, setRecipient] = useState('');
  const [amount, setAmount] = useState('');
  const [memo, setMemo] = useState('');
  const [fee, setFee] = useState('');
  const [loading, setLoading] = useState(false);
  const [dryRunResult, setDryRunResult] = useState<DryRunResult | null>(null);
  const [dryRunLoading, setDryRunLoading] = useState(false);
  const [dryRunEnabled, setDryRunEnabled] = useState(true);
  const [keyPair, setKeyPair] = useState<KeyPair | null>(null);
  const [walletAddress, setWalletAddress] = useState<string>('');

  // QR Scanner state
  const [showQRScanner, setShowQRScanner] = useState(false);

  // Biometric authentication state
  const [biometricAvailable, setBiometricAvailable] = useState(false);
  const [biometricVerified, setBiometricVerified] = useState(false);
  const [biometricLoading, setBiometricLoading] = useState(false);

  // Password input modal for re-authentication
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [passwordInput, setPasswordInput] = useState('');

  const client = new RustChainClient(Network.Mainnet);

  useEffect(() => {
    // Check biometric availability on mount
    const checkBiometric = async () => {
      const bioAvailable = await isBiometricAvailable();
      setBiometricAvailable(bioAvailable);
    };
    checkBiometric();
  }, []);

  // Issue #785: Load wallet only when user initiates send, not on mount
  // This prevents keeping sensitive data in memory unnecessarily
  const loadWalletKeyPair = async (password: string): Promise<boolean> => {
    try {
      const kp = await WalletStorage.load(walletName, password);
      const metadata = await WalletStorage.getMetadata(walletName);
      if (metadata) {
        setKeyPair(kp);
        setWalletAddress(metadata.address);
        return true;
      }
      return false;
    } catch (error) {
      Alert.alert('Error', 'Failed to load wallet. Please check your password.');
      return false;
    }
  };

  const handleDryRun = async () => {
    if (!keyPair || !recipient || !amount) {
      Alert.alert('Error', 'Please fill in recipient and amount');
      return;
    }

    // Validate input with hardened numeric validation
    const validation = validateTransactionInput(amount, fee || undefined);
    if (!validation.valid) {
      Alert.alert('Validation Error', validation.errors.join('\n'));
      return;
    }

    const amountNum = (validation.parsedAmount || 0) * 100000000; // Convert to satoshis
    const feeNum = validation.parsedFee ? validation.parsedFee * 100000000 : undefined;

    setDryRunLoading(true);
    try {
      const result = await dryRunTransfer(
        client,
        keyPair,
        recipient,
        amountNum,
        feeNum ? { fee: feeNum, memo: memo || undefined } : { memo: memo || undefined }
      );
      setDryRunResult(result);

      if (!result.valid) {
        Alert.alert(
          'Validation Failed',
          result.errors.join('\n'),
          [{ text: 'OK' }]
        );
      }
    } catch (error) {
      Alert.alert('Error', 'Dry run failed. Check network connection.');
    } finally {
      setDryRunLoading(false);
    }
  };

  const handleSend = async () => {
    if (!recipient || !amount) {
      Alert.alert('Error', 'Please fill in recipient and amount');
      return;
    }

    // Validate recipient address
    if (!isValidAddress(recipient)) {
      Alert.alert('Error', 'Invalid recipient address format');
      return;
    }

    // Validate amount
    const amountValidation = validateTransactionAmount(amount);
    if (!amountValidation.valid) {
      Alert.alert('Error', `Invalid amount: ${amountValidation.error}`);
      return;
    }

    // Issue #785: Require re-authentication before sending
    // If biometric is available and verified, proceed
    // Otherwise, show password input modal
    if (biometricAvailable && biometricVerified) {
      // Already verified, proceed with send
      proceedWithSend();
      return;
    }

    if (biometricAvailable) {
      // Try biometric first
      setBiometricLoading(true);
      try {
        const result = await authenticateWithBiometricsOrFallback(
          'Authenticate to send transaction'
        );

        if (result.success) {
          setBiometricVerified(true);
          proceedWithSend();
          return;
        }

        if (!result.available) {
          // Fall through to password
        } else {
          // Biometric failed/cancelled
          Alert.alert(
            'Authentication Required',
            result.error || 'Please authenticate to send',
            [{ text: 'OK' }]
          );
          return;
        }
      } catch (error: any) {
        Alert.alert('Error', error.message || 'Authentication failed');
        setBiometricLoading(false);
        return;
      } finally {
        setBiometricLoading(false);
      }
    }

    // Show password input modal for re-authentication
    setShowPasswordModal(true);
  };

  const handlePasswordSubmit = async () => {
    if (!passwordInput) {
      Alert.alert('Error', 'Please enter your password');
      return;
    }

    setLoading(true);
    setShowPasswordModal(false);

    const loaded = await loadWalletKeyPair(passwordInput);
    setPasswordInput('');
    setLoading(false);

    if (loaded) {
      proceedWithSend();
    }
  };

  const proceedWithSend = async () => {
    if (!keyPair) {
      // Try to load wallet (should have been loaded already)
      setShowPasswordModal(true);
      return;
    }

    // Final confirmation
    const amountNum = parseFloat(amount) * 100000000;
    const feeNum = fee ? parseFloat(fee) * 100000000 : await client.estimateFee(amountNum);

    Alert.alert(
      'Confirm Transaction',
      `Send ${amount} RTC to:\n${recipient.slice(0, 20)}...\n\nFee: ${(feeNum / 100000000).toFixed(8)} RTC\nMemo: ${memo || 'None'}`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Confirm',
          style: 'destructive',
          onPress: async () => {
            setLoading(true);
            try {
              const result = await client.transfer(
                keyPair,
                recipient,
                amountNum,
                {
                  fee: feeNum,
                  memo: memo || undefined,
                }
              );

              Alert.alert(
                'Transaction Submitted!',
                `Transaction Hash:\n${result.tx_hash}`,
                [
                  {
                    text: 'OK',
                    onPress: () => {
                      // Clear sensitive data from memory
                      setKeyPair(null);
                      router.back();
                    },
                  },
                ]
              );
            } catch (error: any) {
              Alert.alert(
                'Transaction Failed',
                error.message || 'Failed to submit transaction'
              );
            } finally {
              setLoading(false);
            }
          },
        },
      ]
    );
  };

  const formatAddress = (addr: string): string => {
    return `${addr.slice(0, 20)}...${addr.slice(-10)}`;
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.dryRunToggle}>
        <Text style={styles.dryRunLabel}>Dry-run validation:</Text>
        <Switch
          value={dryRunEnabled}
          onValueChange={setDryRunEnabled}
          trackColor={{ false: '#333', true: '#00d4ff' }}
          thumbColor="#fff"
        />
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>Recipient Address</Text>
        <View style={styles.inputRow}>
          <TextInput
            style={[styles.input, styles.inputFlex]}
            placeholder="RTC wallet address"
            placeholderTextColor="#666"
            value={recipient}
            onChangeText={setRecipient}
            autoCapitalize="none"
            autoCorrect={false}
            editable={!loading}
          />
          <TouchableOpacity
            style={styles.qrButton}
            onPress={() => setShowQRScanner(true)}
            disabled={loading}
            activeOpacity={0.7}
          >
            <Text style={styles.qrButtonText}>📷</Text>
          </TouchableOpacity>
        </View>
        {recipient && (
          <Text style={styles.addressPreview}>{formatAddress(recipient)}</Text>
        )}
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>Amount (RTC)</Text>
        <TextInput
          style={styles.input}
          placeholder="0.00000000"
          placeholderTextColor="#666"
          value={amount}
          onChangeText={setAmount}
          keyboardType="decimal-pad"
          editable={!loading}
        />
        {amount && (
          <Text style={styles.amountPreview}>
            ≈ ${(parseFloat(amount) * 0.1).toFixed(4)} USD
          </Text>
        )}
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>Fee (RTC) - Optional</Text>
        <TextInput
          style={styles.input}
          placeholder="Auto-calculated if empty"
          placeholderTextColor="#666"
          value={fee}
          onChangeText={setFee}
          keyboardType="decimal-pad"
          editable={!loading}
        />
        <Text style={styles.hint}>
          Leave empty for automatic fee estimation
        </Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>Memo - Optional</Text>
        <TextInput
          style={[styles.input, styles.memoInput]}
          placeholder="Add a note to this transaction"
          placeholderTextColor="#666"
          value={memo}
          onChangeText={setMemo}
          multiline
          numberOfLines={3}
          editable={!loading}
        />
      </View>

      {dryRunEnabled && (
        <View style={styles.dryRunSection}>
          <Text style={styles.dryRunTitle}>🔍 Dry-run Validation</Text>
          <Text style={styles.dryRunDescription}>
            Validate transaction before submitting to the network
          </Text>

          <TouchableOpacity
            style={styles.dryRunButton}
            onPress={handleDryRun}
            disabled={dryRunLoading || !recipient || !amount}
            activeOpacity={0.7}
          >
            {dryRunLoading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.dryRunButtonText}>Run Validation</Text>
            )}
          </TouchableOpacity>

          {dryRunResult && (
            <View
              style={[
                styles.dryRunResult,
                dryRunResult.valid
                  ? styles.dryRunSuccess
                  : styles.dryRunError,
              ]}
            >
              <Text
                style={[
                  styles.dryRunResultTitle,
                  dryRunResult.valid
                    ? styles.dryRunSuccessTitle
                    : styles.dryRunErrorTitle,
                ]}
              >
                {dryRunResult.valid ? '✓ Validation Passed' : '✗ Validation Failed'}
              </Text>

              {!dryRunResult.valid &&
                dryRunResult.errors.map((error, index) => (
                  <Text key={index} style={styles.dryRunErrorText}>
                    • {error}
                  </Text>
                ))}

              {dryRunResult.valid && (
                <>
                  <Text style={styles.dryRunDetail}>
                    Estimated Fee: {(dryRunResult.estimatedFee / 100000000).toFixed(8)} RTC
                  </Text>
                  <Text style={styles.dryRunDetail}>
                    Total Cost: {(dryRunResult.totalCost / 100000000).toFixed(8)} RTC
                  </Text>
                  <Text style={styles.dryRunDetail}>
                    Your Balance: {(dryRunResult.senderBalance ?? 0 / 100000000).toFixed(8)} RTC
                  </Text>
                </>
              )}
            </View>
          )}
        </View>
      )}

      {biometricAvailable && (
        <View style={styles.biometricStatus}>
          {biometricVerified ? (
            <View style={[styles.biometricBadge, styles.biometricVerified]}>
              <Text style={styles.biometricBadgeIcon}>✓</Text>
              <Text style={styles.biometricBadgeText}>Biometric Verified</Text>
            </View>
          ) : (
            <View style={[styles.biometricBadge, styles.biometricPending]}>
              <Text style={styles.biometricBadgeIcon}>🔒</Text>
              <Text style={styles.biometricBadgeText}>
                Authentication required to send
              </Text>
            </View>
          )}
        </View>
      )}

      <View style={styles.warningBox}>
        <Text style={styles.warningTitle}>⚠️ Important</Text>
        <Text style={styles.warningText}>
          • Double-check the recipient address before sending
        </Text>
        <Text style={styles.warningText}>
          • Transactions cannot be reversed once confirmed
        </Text>
        <Text style={styles.warningText}>
          • Ensure you have sufficient balance for amount + fee
        </Text>
        <Text style={styles.warningText}>
          • Your signature is bound to the chain_id to prevent replay attacks
        </Text>
      </View>

      <TouchableOpacity
        style={[
          styles.sendButton,
          (loading || !recipient || !amount) && styles.sendButtonDisabled,
        ]}
        onPress={handleSend}
        disabled={loading || !recipient || !amount}
        activeOpacity={0.7}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.sendButtonText}>Send Transaction</Text>
        )}
      </TouchableOpacity>

      {/* QR Code Scanner Modal */}
      <QRScanner
        visible={showQRScanner}
        onScan={(data) => {
          setRecipient(data);
          setShowQRScanner(false);
        }}
        onClose={() => setShowQRScanner(false)}
        title="Scan Recipient Address"
        description="Position the QR code within the frame to scan the wallet address"
        strictValidation={true}
      />

      {/* Password Re-authentication Modal */}
      <Modal visible={showPasswordModal} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.passwordModal}>
            <Text style={styles.passwordModalTitle}>Re-authenticate Required</Text>
            <Text style={styles.passwordModalDescription}>
              For security, please enter your password to confirm this transaction
            </Text>
            <TextInput
              style={styles.passwordInput}
              placeholder="Enter password"
              placeholderTextColor="#666"
              value={passwordInput}
              onChangeText={setPasswordInput}
              secureTextEntry
              autoFocus
              onSubmitEditing={handlePasswordSubmit}
            />
            <View style={styles.passwordModalButtons}>
              <TouchableOpacity
                style={[styles.passwordModalButton, styles.cancelButton]}
                onPress={() => {
                  setShowPasswordModal(false);
                  setPasswordInput('');
                }}
              >
                <Text style={styles.cancelButtonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.passwordModalButton, styles.confirmButton]}
                onPress={handlePasswordSubmit}
              >
                <Text style={styles.confirmButtonText}>Confirm</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
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
  dryRunToggle: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#16213e',
    padding: 15,
    borderRadius: 10,
    marginBottom: 20,
  },
  dryRunLabel: {
    fontSize: 16,
    color: '#fff',
  },
  section: {
    backgroundColor: '#16213e',
    borderRadius: 12,
    padding: 15,
    marginBottom: 15,
    borderWidth: 1,
    borderColor: '#0f3460',
  },
  label: {
    fontSize: 14,
    color: '#00d4ff',
    fontWeight: 'bold',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#0f3460',
    borderRadius: 8,
    padding: 12,
    color: '#fff',
    fontSize: 16,
  },
  inputFlex: {
    flex: 1,
  },
  inputRow: {
    flexDirection: 'row',
    gap: 10,
    alignItems: 'center',
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
  memoInput: {
    height: 80,
    textAlignVertical: 'top',
  },
  hint: {
    fontSize: 12,
    color: '#666',
    marginTop: 5,
  },
  addressPreview: {
    fontSize: 12,
    color: '#888',
    fontFamily: 'monospace',
    marginTop: 5,
  },
  amountPreview: {
    fontSize: 12,
    color: '#00ff88',
    marginTop: 5,
  },
  dryRunSection: {
    backgroundColor: '#16213e',
    borderRadius: 12,
    padding: 15,
    marginBottom: 15,
    borderWidth: 1,
    borderColor: '#00d4ff',
  },
  dryRunTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#00d4ff',
    marginBottom: 5,
  },
  dryRunDescription: {
    fontSize: 13,
    color: '#888',
    marginBottom: 15,
  },
  dryRunButton: {
    backgroundColor: '#00d4ff',
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  dryRunButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
  dryRunResult: {
    marginTop: 15,
    padding: 12,
    borderRadius: 8,
  },
  dryRunSuccess: {
    backgroundColor: '#1a3d2e',
    borderWidth: 1,
    borderColor: '#00ff88',
  },
  dryRunError: {
    backgroundColor: '#3d1a1a',
    borderWidth: 1,
    borderColor: '#ff6b6b',
  },
  dryRunResultTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  dryRunSuccessTitle: {
    color: '#00ff88',
  },
  dryRunErrorTitle: {
    color: '#ff6b6b',
  },
  dryRunErrorText: {
    fontSize: 13,
    color: '#ff6b6b',
    marginBottom: 4,
  },
  dryRunDetail: {
    fontSize: 13,
    color: '#ccc',
    marginBottom: 4,
  },
  warningBox: {
    backgroundColor: '#2d1f1f',
    borderRadius: 12,
    padding: 15,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#ff6b6b',
  },
  warningTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#ff6b6b',
    marginBottom: 10,
  },
  warningText: {
    fontSize: 13,
    color: '#ccc',
    marginBottom: 5,
  },
  sendButton: {
    backgroundColor: '#00ff88',
    paddingVertical: 15,
    borderRadius: 10,
    alignItems: 'center',
  },
  sendButtonDisabled: {
    backgroundColor: '#444',
    opacity: 0.5,
  },
  sendButtonText: {
    color: '#1a1a2e',
    fontSize: 16,
    fontWeight: 'bold',
  },
  biometricStatus: {
    marginBottom: 20,
  },
  biometricBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 12,
    borderRadius: 10,
    gap: 8,
  },
  biometricVerified: {
    backgroundColor: '#1a3d2e',
    borderWidth: 1,
    borderColor: '#00ff88',
  },
  biometricPending: {
    backgroundColor: '#3d2e1a',
    borderWidth: 1,
    borderColor: '#ffaa00',
  },
  biometricBadgeIcon: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  biometricBadgeText: {
    fontSize: 14,
    color: '#fff',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  passwordModal: {
    backgroundColor: '#16213e',
    padding: 25,
    borderRadius: 15,
    width: '85%',
    borderWidth: 1,
    borderColor: '#00d4ff',
  },
  passwordModalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 10,
    textAlign: 'center',
  },
  passwordModalDescription: {
    fontSize: 14,
    color: '#888',
    textAlign: 'center',
    marginBottom: 20,
  },
  passwordInput: {
    backgroundColor: '#0f3460',
    borderRadius: 8,
    padding: 12,
    color: '#fff',
    fontSize: 16,
    marginBottom: 15,
  },
  passwordModalButtons: {
    flexDirection: 'row',
    gap: 10,
  },
  passwordModalButton: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  cancelButton: {
    backgroundColor: '#0f3460',
    borderWidth: 1,
    borderColor: '#666',
  },
  cancelButtonText: {
    color: '#888',
    fontSize: 16,
    fontWeight: 'bold',
  },
  confirmButton: {
    backgroundColor: '#00d4ff',
  },
  confirmButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
});
