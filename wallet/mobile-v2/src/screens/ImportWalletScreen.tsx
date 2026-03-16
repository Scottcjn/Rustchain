/**
 * Import Wallet Screen
 *
 * Import via BIP39 mnemonic, hex private key, or Base58 key.
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
  validateMnemonic,
  keyPairFromMnemonic,
  keyPairFromHex,
  keyPairFromBase58,
  publicKeyToRtcAddress,
} from '../services/wallet';
import { WalletStorage } from '../services/storage';
import type { KeyPair } from '../types';

type Props = NativeStackScreenProps<RootStackParamList, 'ImportWallet'>;
type ImportMethod = 'mnemonic' | 'hex' | 'base58';

const METHODS: { value: ImportMethod; label: string }[] = [
  { value: 'mnemonic', label: 'BIP39 Mnemonic (12 words)' },
  { value: 'hex', label: 'Hex Private Key (64/128 chars)' },
  { value: 'base58', label: 'Base58 Private Key' },
];

export default function ImportWalletScreen({ navigation }: Props): React.JSX.Element {
  const [method, setMethod] = useState<ImportMethod>('mnemonic');
  const [keyInput, setKeyInput] = useState('');
  const [walletName, setWalletName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [validatedAddress, setValidatedAddress] = useState<string | null>(null);
  const [validatedKeyPair, setValidatedKeyPair] = useState<KeyPair | null>(null);
  const [validatedMnemonic, setValidatedMnemonic] = useState<string | null>(null);

  const handleValidate = async () => {
    try {
      let kp: KeyPair;
      let mnemonic: string | null = null;

      if (method === 'mnemonic') {
        const normalized = keyInput.trim().toLowerCase();
        if (!validateMnemonic(normalized)) {
          Alert.alert('Error', 'Invalid BIP39 mnemonic. Check your words and try again.');
          return;
        }
        kp = await keyPairFromMnemonic(normalized);
        mnemonic = normalized;
      } else if (method === 'hex') {
        const clean = keyInput.trim().replace(/^0x/, '');
        if (!/^[0-9a-fA-F]{64}$/.test(clean) && !/^[0-9a-fA-F]{128}$/.test(clean)) {
          Alert.alert('Error', 'Expected 64 or 128 hex characters.');
          return;
        }
        kp = keyPairFromHex(clean);
      } else {
        kp = keyPairFromBase58(keyInput.trim());
      }

      const addr = await publicKeyToRtcAddress(kp.publicKey);
      setValidatedAddress(addr);
      setValidatedKeyPair(kp);
      setValidatedMnemonic(mnemonic);
      Alert.alert('Valid Key', `Address: ${addr.slice(0, 20)}...`);
    } catch (err: any) {
      Alert.alert('Error', err.message || 'Invalid key format');
      setValidatedAddress(null);
      setValidatedKeyPair(null);
      setValidatedMnemonic(null);
    }
  };

  const handleImport = async () => {
    if (!walletName.trim()) { Alert.alert('Error', 'Enter a wallet name'); return; }
    if (password.length < 8) { Alert.alert('Error', 'Password must be at least 8 characters'); return; }
    if (password !== confirmPassword) { Alert.alert('Error', 'Passwords do not match'); return; }
    if (!validatedKeyPair || !validatedAddress) { Alert.alert('Error', 'Validate your key first'); return; }

    setLoading(true);
    try {
      const exists = await WalletStorage.exists(walletName.trim());
      if (exists) {
        Alert.alert('Error', 'A wallet with this name already exists');
        setLoading(false);
        return;
      }

      await WalletStorage.save(
        walletName.trim(),
        validatedKeyPair,
        password,
        'pbkdf2',
        validatedMnemonic ?? undefined
      );

      Alert.alert('Imported', `"${walletName}" imported successfully.`, [
        { text: 'OK', onPress: () => navigation.goBack() },
      ]);
    } catch (err: any) {
      Alert.alert('Error', err.message || 'Failed to import wallet');
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Import Method</Text>
        <View style={styles.methods}>
          {METHODS.map((m) => (
            <TouchableOpacity
              key={m.value}
              style={[styles.methodBtn, method === m.value && styles.methodBtnActive]}
              onPress={() => {
                setMethod(m.value);
                setValidatedAddress(null);
                setValidatedKeyPair(null);
                setValidatedMnemonic(null);
                setKeyInput('');
              }}
              activeOpacity={0.7}
            >
              <Text style={[styles.methodText, method === m.value && styles.methodTextActive]}>
                {m.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>
          {method === 'mnemonic' ? 'Recovery Phrase' : 'Private Key'}
        </Text>
        <Text style={styles.desc}>
          {method === 'mnemonic'
            ? 'Enter your 12-word BIP39 mnemonic, separated by spaces'
            : method === 'hex'
              ? 'Enter 64-char seed or 128-char private key in hex'
              : 'Enter Base58-encoded private key'}
        </Text>
        <TextInput
          style={[styles.input, styles.keyInput]}
          placeholder={
            method === 'mnemonic'
              ? 'word1 word2 word3 ...'
              : method === 'hex'
                ? 'a1b2c3d4...'
                : '5KQwrPbwdL6...'
          }
          placeholderTextColor="#666"
          value={keyInput}
          onChangeText={setKeyInput}
          secureTextEntry={method !== 'mnemonic'}
          multiline
          numberOfLines={3}
          autoCapitalize="none"
          autoCorrect={false}
          editable={!loading}
        />
        <TouchableOpacity style={styles.validateBtn} onPress={handleValidate} disabled={loading} activeOpacity={0.7}>
          <Text style={styles.validateBtnText}>Validate Key</Text>
        </TouchableOpacity>

        {validatedAddress && (
          <View style={styles.addressBox}>
            <Text style={styles.addressLabel}>Derived Address:</Text>
            <Text style={styles.addressValue} selectable>{validatedAddress}</Text>
          </View>
        )}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Wallet Details</Text>
        <TextInput
          style={styles.input}
          placeholder="Wallet Name"
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
        <Text style={styles.warningTitle}>Security Warning</Text>
        <Text style={styles.warningText}>
          {'\u2022'} Never share your private key or mnemonic{'\n'}
          {'\u2022'} Only import keys from trusted sources{'\n'}
          {'\u2022'} Keys are encrypted locally with AES-256-GCM
        </Text>
      </View>

      <TouchableOpacity
        style={[styles.importBtn, (!validatedAddress || loading) && styles.disabledBtn]}
        onPress={handleImport}
        disabled={!validatedAddress || loading}
        activeOpacity={0.7}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.importBtnText}>Import Wallet</Text>
        )}
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a1a' },
  content: { padding: 20 },
  section: { backgroundColor: '#12122a', borderRadius: 12, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: '#1a1a3e' },
  sectionTitle: { fontSize: 16, fontWeight: 'bold', color: '#00d4ff', marginBottom: 8 },
  desc: { fontSize: 14, color: '#888', marginBottom: 12 },
  methods: { gap: 8 },
  methodBtn: { backgroundColor: '#0f3460', paddingVertical: 12, paddingHorizontal: 14, borderRadius: 8, borderWidth: 1, borderColor: '#0f3460' },
  methodBtnActive: { backgroundColor: '#00d4ff', borderColor: '#00d4ff' },
  methodText: { color: '#888', fontSize: 14 },
  methodTextActive: { color: '#fff', fontWeight: 'bold' },
  input: { backgroundColor: '#0f3460', borderRadius: 10, padding: 14, color: '#fff', fontSize: 16, marginBottom: 12 },
  keyInput: { fontFamily: 'monospace', fontSize: 13, height: 80, textAlignVertical: 'top' },
  validateBtn: { backgroundColor: '#0f3460', paddingVertical: 12, borderRadius: 10, alignItems: 'center', borderWidth: 1, borderColor: '#00d4ff' },
  validateBtnText: { color: '#00d4ff', fontSize: 14, fontWeight: 'bold' },
  addressBox: { backgroundColor: '#0f3460', padding: 12, borderRadius: 8, marginTop: 12 },
  addressLabel: { fontSize: 12, color: '#888', marginBottom: 4 },
  addressValue: { fontSize: 12, color: '#00ff88', fontFamily: 'monospace' },
  warningBox: { backgroundColor: '#1a1008', borderRadius: 12, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: '#ff6b6b44' },
  warningTitle: { fontSize: 15, fontWeight: 'bold', color: '#ff6b6b', marginBottom: 8 },
  warningText: { fontSize: 13, color: '#ccc', lineHeight: 22 },
  importBtn: { backgroundColor: '#00d4ff', paddingVertical: 16, borderRadius: 12, alignItems: 'center' },
  importBtnText: { color: '#fff', fontSize: 16, fontWeight: 'bold' },
  disabledBtn: { backgroundColor: '#444', opacity: 0.5 },
});
