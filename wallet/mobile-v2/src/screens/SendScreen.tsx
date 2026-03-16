/**
 * Send Screen
 *
 * Send RTC with QR scanning, dry-run validation, and biometric confirmation.
 * Password is NOT passed via navigation params.
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
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/AppNavigator';
import { WalletStorage } from '../services/storage';
import { RustChainClient, dryRunTransfer } from '../services/api';
import { isValidAddress, parseRtcAmountToMicrounits } from '../services/wallet';
import { QRScanner } from '../components/QRScanner';
import { authenticateOrFallback, isBiometricAvailable } from '../services/biometric';
import type { KeyPair, DryRunResult } from '../types';
import { MICRO_RTC_PER_RTC } from '../types';

type Props = NativeStackScreenProps<RootStackParamList, 'Send'>;

export default function SendScreen({ route, navigation }: Props): React.JSX.Element {
  const { walletName } = route.params;

  const [recipient, setRecipient] = useState('');
  const [amount, setAmount] = useState('');
  const [memo, setMemo] = useState('');
  const [loading, setLoading] = useState(false);
  const [dryResult, setDryResult] = useState<DryRunResult | null>(null);
  const [dryLoading, setDryLoading] = useState(false);
  const [dryEnabled, setDryEnabled] = useState(true);
  const [keyPair, setKeyPair] = useState<KeyPair | null>(null);
  const [walletAddress, setWalletAddress] = useState('');
  const [showQR, setShowQR] = useState(false);
  const [bioAvailable, setBioAvailable] = useState(false);
  const [bioVerified, setBioVerified] = useState(false);
  const [showPwModal, setShowPwModal] = useState(false);
  const [pwInput, setPwInput] = useState('');

  const client = new RustChainClient();

  useEffect(() => {
    (async () => {
      setBioAvailable(await isBiometricAvailable());
      const meta = await WalletStorage.getMetadata(walletName);
      if (meta) setWalletAddress(meta.address);
    })();
  }, [walletName]);

  useEffect(() => { setBioVerified(false); }, [recipient, amount, memo]);

  const loadKeyPair = async (pw: string): Promise<KeyPair | null> => {
    try {
      const kp = await WalletStorage.load(walletName, pw);
      setKeyPair(kp);
      return kp;
    } catch {
      Alert.alert('Error', 'Failed to load wallet. Check your password.');
      return null;
    }
  };

  const getDraft = (): { recipient: string; amountMicros: number; amountRtc: number; memo?: string } | null => {
    const r = recipient.trim();
    if (!r || !amount.trim()) { Alert.alert('Error', 'Fill in recipient and amount'); return null; }
    if (!isValidAddress(r)) { Alert.alert('Error', 'Invalid recipient address'); return null; }
    const v = parseRtcAmountToMicrounits(amount);
    if (!v.valid || v.units === undefined || v.value === undefined) {
      Alert.alert('Error', `Invalid amount: ${v.error}`);
      return null;
    }
    return { recipient: r, amountMicros: v.units, amountRtc: v.value, memo: memo.trim() || undefined };
  };

  const handleDryRun = async () => {
    const draft = getDraft();
    if (!draft || !walletAddress) return;
    setDryLoading(true);
    try {
      const res = await dryRunTransfer(client, walletAddress, draft.recipient, draft.amountMicros, { memo: draft.memo });
      setDryResult(res);
      if (!res.valid) Alert.alert('Validation Failed', res.errors.join('\n'));
    } catch {
      Alert.alert('Error', 'Dry run failed');
    } finally {
      setDryLoading(false);
    }
  };

  const handleSend = async () => {
    const draft = getDraft();
    if (!draft) return;

    if (bioAvailable && !bioVerified) {
      const res = await authenticateOrFallback('Authenticate to send transaction');
      if (res.success) {
        setBioVerified(true);
        if (keyPair) { proceedWithSend(keyPair, draft); return; }
        setShowPwModal(true);
        return;
      }
      if (res.available) {
        Alert.alert('Auth Required', res.error || 'Please authenticate');
        return;
      }
    }

    if (keyPair) { proceedWithSend(keyPair, draft); return; }
    setShowPwModal(true);
  };

  const handlePwSubmit = async () => {
    if (!pwInput) { Alert.alert('Error', 'Enter password'); return; }
    const draft = getDraft();
    if (!draft) { setShowPwModal(false); setPwInput(''); return; }
    setLoading(true);
    setShowPwModal(false);
    const kp = await loadKeyPair(pwInput);
    setPwInput('');
    setLoading(false);
    if (kp) proceedWithSend(kp, draft);
  };

  const proceedWithSend = (kp: KeyPair, draft: { recipient: string; amountMicros: number; amountRtc: number; memo?: string }) => {
    Alert.alert(
      'Confirm Transaction',
      `Send ${draft.amountRtc.toFixed(6)} RTC to:\n${draft.recipient.slice(0, 20)}...\n\nMemo: ${draft.memo || 'None'}`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Confirm',
          style: 'destructive',
          onPress: async () => {
            setLoading(true);
            try {
              const res = await client.transfer(kp, draft.recipient, draft.amountMicros, { memo: draft.memo });
              Alert.alert('Submitted', `Tx Hash: ${res.tx_hash}\nStatus: ${res.status}`, [
                { text: 'OK', onPress: () => { setKeyPair(null); setBioVerified(false); navigation.goBack(); } },
              ]);
            } catch (err: any) {
              Alert.alert('Failed', err.message || 'Transaction failed');
            } finally {
              setLoading(false);
            }
          },
        },
      ]
    );
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Dry-run toggle */}
      <View style={styles.toggleRow}>
        <Text style={styles.toggleLabel}>Dry-run validation</Text>
        <Switch value={dryEnabled} onValueChange={setDryEnabled} trackColor={{ false: '#333', true: '#00d4ff' }} thumbColor="#fff" />
      </View>

      {/* Recipient */}
      <View style={styles.section}>
        <Text style={styles.label}>Recipient Address</Text>
        <View style={styles.inputRow}>
          <TextInput style={[styles.input, { flex: 1 }]} placeholder="RTC address" placeholderTextColor="#666" value={recipient} onChangeText={setRecipient} autoCapitalize="none" autoCorrect={false} editable={!loading} />
          <TouchableOpacity style={styles.qrBtn} onPress={() => setShowQR(true)} disabled={loading}>
            <Text style={styles.qrBtnText}>Scan</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Amount */}
      <View style={styles.section}>
        <Text style={styles.label}>Amount (RTC)</Text>
        <TextInput style={styles.input} placeholder="0.000000" placeholderTextColor="#666" value={amount} onChangeText={setAmount} keyboardType="decimal-pad" editable={!loading} />
      </View>

      {/* Memo */}
      <View style={styles.section}>
        <Text style={styles.label}>Memo (optional)</Text>
        <TextInput style={[styles.input, styles.memoInput]} placeholder="Add a note" placeholderTextColor="#666" value={memo} onChangeText={setMemo} multiline numberOfLines={2} editable={!loading} />
      </View>

      {/* Dry-run */}
      {dryEnabled && (
        <View style={styles.drySection}>
          <TouchableOpacity style={styles.dryBtn} onPress={handleDryRun} disabled={dryLoading || !recipient || !amount} activeOpacity={0.7}>
            {dryLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.dryBtnText}>Run Validation</Text>}
          </TouchableOpacity>
          {dryResult && (
            <View style={[styles.dryResult, dryResult.valid ? styles.dryOk : styles.dryFail]}>
              <Text style={[styles.dryResultTitle, { color: dryResult.valid ? '#00ff88' : '#ff6b6b' }]}>
                {dryResult.valid ? 'Validation Passed' : 'Validation Failed'}
              </Text>
              {!dryResult.valid && dryResult.errors.map((e, i) => (
                <Text key={i} style={styles.dryError}>{'\u2022'} {e}</Text>
              ))}
              {dryResult.valid && (
                <>
                  <Text style={styles.dryDetail}>Total: {(dryResult.totalCost / MICRO_RTC_PER_RTC).toFixed(6)} RTC</Text>
                  <Text style={styles.dryDetail}>Balance: {((dryResult.senderBalance ?? 0) / MICRO_RTC_PER_RTC).toFixed(6)} RTC</Text>
                </>
              )}
            </View>
          )}
        </View>
      )}

      {/* Biometric status */}
      {bioAvailable && (
        <View style={[styles.bioBadge, bioVerified ? styles.bioOk : styles.bioPending]}>
          <Text style={styles.bioBadgeText}>
            {bioVerified ? 'Biometric Verified' : 'Authentication required to send'}
          </Text>
        </View>
      )}

      {/* Send button */}
      <TouchableOpacity
        style={[styles.sendBtn, (loading || !recipient || !amount) && styles.disabledBtn]}
        onPress={handleSend}
        disabled={loading || !recipient || !amount}
        activeOpacity={0.7}
      >
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.sendBtnText}>Send Transaction</Text>}
      </TouchableOpacity>

      {/* QR Scanner */}
      <QRScanner
        visible={showQR}
        onScan={(data) => { setRecipient(data); setShowQR(false); }}
        onClose={() => setShowQR(false)}
        title="Scan Recipient"
        strictValidation={true}
      />

      {/* Password Modal */}
      <Modal visible={showPwModal} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.pwModal}>
            <Text style={styles.pwTitle}>Enter Password</Text>
            <Text style={styles.pwDesc}>Authenticate to confirm this transaction</Text>
            <TextInput style={styles.pwInput} placeholder="Password" placeholderTextColor="#666" value={pwInput} onChangeText={setPwInput} secureTextEntry autoFocus onSubmitEditing={handlePwSubmit} />
            <View style={styles.pwBtns}>
              <TouchableOpacity style={[styles.pwBtn, styles.pwCancel]} onPress={() => { setShowPwModal(false); setPwInput(''); }}>
                <Text style={styles.pwCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.pwBtn, styles.pwConfirm]} onPress={handlePwSubmit}>
                <Text style={styles.pwConfirmText}>Confirm</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a1a' },
  content: { padding: 20 },
  toggleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#12122a', padding: 14, borderRadius: 10, marginBottom: 16 },
  toggleLabel: { fontSize: 15, color: '#fff' },
  section: { backgroundColor: '#12122a', borderRadius: 12, padding: 14, marginBottom: 14, borderWidth: 1, borderColor: '#1a1a3e' },
  label: { fontSize: 13, color: '#00d4ff', fontWeight: 'bold', marginBottom: 8 },
  input: { backgroundColor: '#0f3460', borderRadius: 8, padding: 12, color: '#fff', fontSize: 16 },
  inputRow: { flexDirection: 'row', gap: 10, alignItems: 'center' },
  qrBtn: { backgroundColor: '#00d4ff', borderRadius: 8, paddingVertical: 12, paddingHorizontal: 16 },
  qrBtnText: { color: '#fff', fontWeight: 'bold', fontSize: 14 },
  memoInput: { height: 60, textAlignVertical: 'top' },
  drySection: { backgroundColor: '#12122a', borderRadius: 12, padding: 14, marginBottom: 14, borderWidth: 1, borderColor: '#00d4ff44' },
  dryBtn: { backgroundColor: '#00d4ff', paddingVertical: 12, borderRadius: 8, alignItems: 'center' },
  dryBtnText: { color: '#fff', fontSize: 15, fontWeight: 'bold' },
  dryResult: { marginTop: 12, padding: 12, borderRadius: 8 },
  dryOk: { backgroundColor: '#0a2a1a', borderWidth: 1, borderColor: '#00ff88' },
  dryFail: { backgroundColor: '#2a0a0a', borderWidth: 1, borderColor: '#ff6b6b' },
  dryResultTitle: { fontSize: 14, fontWeight: 'bold', marginBottom: 6 },
  dryError: { fontSize: 13, color: '#ff6b6b', marginBottom: 2 },
  dryDetail: { fontSize: 13, color: '#ccc', marginBottom: 2 },
  bioBadge: { flexDirection: 'row', justifyContent: 'center', padding: 12, borderRadius: 10, marginBottom: 16 },
  bioOk: { backgroundColor: '#0a2a1a', borderWidth: 1, borderColor: '#00ff88' },
  bioPending: { backgroundColor: '#2a1a0a', borderWidth: 1, borderColor: '#ffaa00' },
  bioBadgeText: { fontSize: 14, color: '#fff' },
  sendBtn: { backgroundColor: '#00ff88', paddingVertical: 16, borderRadius: 12, alignItems: 'center' },
  sendBtnText: { color: '#0a0a1a', fontSize: 16, fontWeight: 'bold' },
  disabledBtn: { backgroundColor: '#444', opacity: 0.5 },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.8)', justifyContent: 'center', alignItems: 'center' },
  pwModal: { backgroundColor: '#12122a', padding: 24, borderRadius: 16, width: '85%', borderWidth: 1, borderColor: '#00d4ff' },
  pwTitle: { fontSize: 18, fontWeight: 'bold', color: '#fff', textAlign: 'center', marginBottom: 8 },
  pwDesc: { fontSize: 14, color: '#888', textAlign: 'center', marginBottom: 16 },
  pwInput: { backgroundColor: '#0f3460', borderRadius: 8, padding: 12, color: '#fff', fontSize: 16, marginBottom: 16 },
  pwBtns: { flexDirection: 'row', gap: 10 },
  pwBtn: { flex: 1, paddingVertical: 12, borderRadius: 8, alignItems: 'center' },
  pwCancel: { backgroundColor: '#0f3460', borderWidth: 1, borderColor: '#666' },
  pwCancelText: { color: '#888', fontSize: 15, fontWeight: 'bold' },
  pwConfirm: { backgroundColor: '#00d4ff' },
  pwConfirmText: { color: '#fff', fontSize: 15, fontWeight: 'bold' },
});
