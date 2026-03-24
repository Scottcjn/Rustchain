/**
 * Create Wallet Screen
 *
 * BIP39 mnemonic generation with Ed25519 key derivation.
 * User must write down the mnemonic before proceeding.
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  ScrollView,
} from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/AppNavigator';
import {
  generateMnemonic,
  keyPairFromMnemonic,
  publicKeyToHex,
  publicKeyToRtcAddress,
} from '../services/wallet';
import { WalletStorage } from '../services/storage';
import type { KeyPair } from '../types';

type Props = NativeStackScreenProps<RootStackParamList, 'CreateWallet'>;

export default function CreateWalletScreen({ navigation }: Props): React.JSX.Element {
  const [step, setStep] = useState<'generate' | 'confirm' | 'save'>('generate');
  const [mnemonic, setMnemonic] = useState('');
  const [keyPair, setKeyPair] = useState<KeyPair | null>(null);
  const [address, setAddress] = useState('');
  const [pubKeyHex, setPubKeyHex] = useState('');
  const [walletName, setWalletName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [confirmInput, setConfirmInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleGenerate = async () => {
    try {
      const m = generateMnemonic();
      setMnemonic(m);
      const kp = await keyPairFromMnemonic(m);
      setKeyPair(kp);
      const addr = await publicKeyToRtcAddress(kp.publicKey);
      setAddress(addr);
      setPubKeyHex(publicKeyToHex(kp.publicKey));
      setStep('confirm');
    } catch (err) {
      Alert.alert('Error', 'Failed to generate wallet');
    }
  };

  const handleConfirmMnemonic = () => {
    const normalizedInput = confirmInput.trim().toLowerCase().replace(/\s+/g, ' ');
    const normalizedMnemonic = mnemonic.trim().toLowerCase();
    if (normalizedInput !== normalizedMnemonic) {
      Alert.alert('Mismatch', 'The mnemonic you entered does not match. Please try again.');
      return;
    }
    setStep('save');
  };

  const handleCreate = async () => {
    if (!walletName.trim()) {
      Alert.alert('Error', 'Enter a wallet name');
      return;
    }
    if (password.length < 8) {
      Alert.alert('Error', 'Password must be at least 8 characters');
      return;
    }
    if (password !== confirmPassword) {
      Alert.alert('Error', 'Passwords do not match');
      return;
    }
    if (!keyPair) {
      Alert.alert('Error', 'Generate a wallet first');
      return;
    }

    setLoading(true);
    try {
      const exists = await WalletStorage.exists(walletName.trim());
      if (exists) {
        Alert.alert('Error', 'A wallet with this name already exists');
        setLoading(false);
        return;
      }

      await WalletStorage.save(walletName.trim(), keyPair, password, 'pbkdf2', mnemonic);
      Alert.alert('Wallet Created', `"${walletName}" created successfully.`, [
        { text: 'OK', onPress: () => navigation.goBack() },
      ]);
    } catch (err: any) {
      Alert.alert('Error', err.message || 'Failed to save wallet');
    } finally {
      setLoading(false);
    }
  };

  // ── Step 1: Generate ───────────────────────────────────────────────────

  if (step === 'generate') {
    return (
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <View style={styles.section}>
          <Text style={styles.stepLabel}>Step 1 of 3</Text>
          <Text style={styles.sectionTitle}>Generate Recovery Phrase</Text>
          <Text style={styles.desc}>
            A 12-word BIP39 mnemonic will be generated. This is the only way to
            recover your wallet if you lose your device.
          </Text>
          <TouchableOpacity style={styles.primaryBtn} onPress={handleGenerate} activeOpacity={0.7}>
            <Text style={styles.primaryBtnText}>Generate Mnemonic</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.warningBox}>
          <Text style={styles.warningTitle}>Security Notice</Text>
          <Text style={styles.warningText}>
            {'\u2022'} Write down your recovery phrase on paper{'\n'}
            {'\u2022'} Never share it with anyone{'\n'}
            {'\u2022'} Never store it digitally (no screenshots){'\n'}
            {'\u2022'} Keep it in a safe place
          </Text>
        </View>
      </ScrollView>
    );
  }

  // ── Step 2: Confirm Mnemonic ──────────────────────────────────────────

  if (step === 'confirm') {
    const words = mnemonic.split(' ');
    return (
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <View style={styles.section}>
          <Text style={styles.stepLabel}>Step 2 of 3</Text>
          <Text style={styles.sectionTitle}>Write Down Your Recovery Phrase</Text>
          <View style={styles.mnemonicGrid}>
            {words.map((word, i) => (
              <View key={i} style={styles.wordBox}>
                <Text style={styles.wordNum}>{i + 1}</Text>
                <Text style={styles.wordText}>{word}</Text>
              </View>
            ))}
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Confirm Recovery Phrase</Text>
          <Text style={styles.desc}>
            Type all 12 words in order to confirm you wrote them down.
          </Text>
          <TextInput
            style={[styles.input, styles.mnemonicInput]}
            placeholder="Enter all 12 words separated by spaces"
            placeholderTextColor="#666"
            value={confirmInput}
            onChangeText={setConfirmInput}
            autoCapitalize="none"
            autoCorrect={false}
            multiline
            numberOfLines={3}
          />
          <TouchableOpacity style={styles.primaryBtn} onPress={handleConfirmMnemonic} activeOpacity={0.7}>
            <Text style={styles.primaryBtnText}>Verify & Continue</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.infoBox}>
          <Text style={styles.infoTitle}>Wallet Preview</Text>
          <Text style={styles.infoLabel}>Address:</Text>
          <Text style={styles.infoValue} selectable>{address}</Text>
          <Text style={styles.infoLabel}>Public Key:</Text>
          <Text style={styles.infoValue} selectable>{pubKeyHex}</Text>
        </View>
      </ScrollView>
    );
  }

  // ── Step 3: Save ──────────────────────────────────────────────────────

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.section}>
        <Text style={styles.stepLabel}>Step 3 of 3</Text>
        <Text style={styles.sectionTitle}>Name & Secure Your Wallet</Text>

        <TextInput
          style={styles.input}
          placeholder="Wallet Name (e.g., Main Wallet)"
          placeholderTextColor="#666"
          value={walletName}
          onChangeText={setWalletName}
          autoCapitalize="words"
          editable={!loading}
        />
        <TextInput
          style={styles.input}
          placeholder="Password (min 8 characters)"
          placeholderTextColor="#666"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          editable={!loading}
        />
        <TextInput
          style={styles.input}
          placeholder="Confirm Password"
          placeholderTextColor="#666"
          value={confirmPassword}
          onChangeText={setConfirmPassword}
          secureTextEntry
          editable={!loading}
        />
      </View>

      <View style={styles.warningBox}>
        <Text style={styles.warningTitle}>Encryption</Text>
        <Text style={styles.warningText}>
          {'\u2022'} Private key encrypted with AES-256-GCM{'\n'}
          {'\u2022'} PBKDF2-SHA256 with 600,000 iterations{'\n'}
          {'\u2022'} Password cannot be recovered if lost{'\n'}
          {'\u2022'} Mnemonic is also encrypted and stored securely
        </Text>
      </View>

      <TouchableOpacity
        style={[styles.primaryBtn, loading && styles.disabledBtn]}
        onPress={handleCreate}
        disabled={loading}
        activeOpacity={0.7}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.primaryBtnText}>Create Wallet</Text>
        )}
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a1a' },
  content: { padding: 20 },
  section: { backgroundColor: '#12122a', borderRadius: 12, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: '#1a1a3e' },
  stepLabel: { fontSize: 12, color: '#00d4ff', fontWeight: 'bold', marginBottom: 8 },
  sectionTitle: { fontSize: 18, fontWeight: 'bold', color: '#fff', marginBottom: 8 },
  desc: { fontSize: 14, color: '#888', marginBottom: 16, lineHeight: 20 },
  mnemonicGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  wordBox: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#0f3460', borderRadius: 8, paddingVertical: 8, paddingHorizontal: 12, gap: 6, width: '30%', flexGrow: 1 },
  wordNum: { fontSize: 11, color: '#666', fontWeight: 'bold', minWidth: 16 },
  wordText: { fontSize: 14, color: '#00ff88', fontWeight: '600' },
  input: { backgroundColor: '#0f3460', borderRadius: 10, padding: 14, color: '#fff', fontSize: 16, marginBottom: 12 },
  mnemonicInput: { height: 80, textAlignVertical: 'top', fontSize: 14 },
  primaryBtn: { backgroundColor: '#00d4ff', paddingVertical: 16, borderRadius: 12, alignItems: 'center', marginTop: 4 },
  primaryBtnText: { color: '#fff', fontSize: 16, fontWeight: 'bold' },
  disabledBtn: { backgroundColor: '#444', opacity: 0.5 },
  warningBox: { backgroundColor: '#1a1008', borderRadius: 12, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: '#ff6b6b44' },
  warningTitle: { fontSize: 15, fontWeight: 'bold', color: '#ff6b6b', marginBottom: 8 },
  warningText: { fontSize: 13, color: '#ccc', lineHeight: 22 },
  infoBox: { backgroundColor: '#12122a', borderRadius: 12, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: '#1a1a3e' },
  infoTitle: { fontSize: 15, fontWeight: 'bold', color: '#00d4ff', marginBottom: 12 },
  infoLabel: { fontSize: 12, color: '#888', marginBottom: 2 },
  infoValue: { fontSize: 11, color: '#00ff88', fontFamily: 'monospace', marginBottom: 10 },
});
