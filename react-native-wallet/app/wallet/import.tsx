/**
 * Import Wallet Screen
 * 
 * Allows users to import an existing wallet using private key or mnemonic
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
import { useRouter } from 'expo-router';
import { keyPairFromHex, keyPairFromBase58, publicKeyToBase58 } from '../../src/utils/crypto';
import { WalletStorage } from '../../src/storage/secure';

type ImportMethod = 'privateKey' | 'base58';

const IMPORT_METHODS: { value: ImportMethod; label: string }[] = [
  { value: 'privateKey', label: 'Hex-encoded Private Key (64 chars)' },
  { value: 'base58', label: 'Base58-encoded Private Key' },
];

export default function ImportWalletScreen() {
  const router = useRouter();
  const [walletName, setWalletName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [importMethod, setImportMethod] = useState<ImportMethod>('privateKey');
  const [privateKey, setPrivateKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [importedAddress, setImportedAddress] = useState<string | null>(null);

  const handleValidateKey = () => {
    try {
      let keyPair;
      
      if (importMethod === 'privateKey') {
        // Validate hex format
        const cleanKey = privateKey.trim().replace(/^0x/, '');
        if (!/^[0-9a-fA-F]{64}$/.test(cleanKey)) {
          Alert.alert('Error', 'Invalid private key format. Expected 64 hex characters.');
          return;
        }
        keyPair = keyPairFromHex(cleanKey);
      } else {
        // Base58 format
        keyPair = keyPairFromBase58(privateKey.trim());
      }

      const address = publicKeyToBase58(keyPair.publicKey);
      setImportedAddress(address);
      Alert.alert('Success', `Valid key! Address: ${address.slice(0, 20)}...`);
    } catch (error) {
      Alert.alert('Error', 'Invalid private key. Please check and try again.');
      setImportedAddress(null);
    }
  };

  const handleImport = async () => {
    // Validation
    if (!walletName.trim()) {
      Alert.alert('Error', 'Please enter a wallet name');
      return;
    }

    if (!password) {
      Alert.alert('Error', 'Please enter a password');
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

    if (!importedAddress) {
      Alert.alert('Error', 'Please validate your private key first');
      return;
    }

    setLoading(true);

    try {
      let keyPair;
      const cleanKey = privateKey.trim().replace(/^0x/, '');
      
      if (importMethod === 'privateKey') {
        keyPair = keyPairFromHex(cleanKey);
      } else {
        keyPair = keyPairFromBase58(cleanKey);
      }

      // Check if wallet name already exists
      const exists = await WalletStorage.exists(walletName.trim());
      if (exists) {
        Alert.alert('Error', 'A wallet with this name already exists');
        setLoading(false);
        return;
      }

      // Save encrypted wallet
      await WalletStorage.save(walletName.trim(), keyPair, password);

      Alert.alert(
        'Wallet Imported!',
        `Wallet "${walletName}" has been imported successfully.`,
        [
          {
            text: 'OK',
            onPress: () => router.back(),
          },
        ]
      );
    } catch (error) {
      Alert.alert('Error', 'Failed to import wallet');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.section}>
        <Text style={styles.label}>Step 1: Select Import Method</Text>
        
        <View style={styles.methodSelector}>
          {IMPORT_METHODS.map((method) => (
            <TouchableOpacity
              key={method.value}
              style={[
                styles.methodButton,
                importMethod === method.value && styles.methodButtonActive,
              ]}
              onPress={() => {
                setImportMethod(method.value);
                setImportedAddress(null);
                setPrivateKey('');
              }}
              activeOpacity={0.7}
            >
              <Text
                style={[
                  styles.methodButtonText,
                  importMethod === method.value && styles.methodButtonTextActive,
                ]}
              >
                {method.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>Step 2: Enter Private Key</Text>
        <Text style={styles.description}>
          {importMethod === 'privateKey'
            ? 'Enter your 64-character hex-encoded private key'
            : 'Enter your Base58-encoded private key'}
        </Text>

        <TextInput
          style={[styles.input, styles.keyInput]}
          placeholder={
            importMethod === 'privateKey'
              ? 'e.g., a1b2c3d4e5f6... (64 hex chars)'
              : 'e.g., 5KQwrPbwdL6PhXujxW...'
          }
          placeholderTextColor="#666"
          value={privateKey}
          onChangeText={setPrivateKey}
          secureTextEntry
          multiline
          numberOfLines={3}
          autoCapitalize="none"
          autoCorrect={false}
          editable={!loading}
        />

        <TouchableOpacity
          style={styles.validateButton}
          onPress={handleValidateKey}
          disabled={loading}
          activeOpacity={0.7}
        >
          <Text style={styles.validateButtonText}>Validate Key</Text>
        </TouchableOpacity>

        {importedAddress && (
          <View style={styles.addressBox}>
            <Text style={styles.addressLabel}>Imported Address:</Text>
            <Text style={styles.addressText} selectable>
              {importedAddress}
            </Text>
          </View>
        )}
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>Step 3: Wallet Details</Text>
        <Text style={styles.description}>
          Choose a name and secure password for this wallet
        </Text>

        <TextInput
          style={styles.input}
          placeholder="Wallet Name (e.g., Imported Wallet)"
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
        <Text style={styles.warningTitle}>⚠️ Security Warning</Text>
        <Text style={styles.warningText}>
          • Never share your private key with anyone
        </Text>
        <Text style={styles.warningText}>
          • Only import keys from trusted sources
        </Text>
        <Text style={styles.warningText}>
          • This app encrypts your key locally - the password cannot be recovered
        </Text>
      </View>

      <TouchableOpacity
        style={[
          styles.importButton,
          (!importedAddress || loading) && styles.importButtonDisabled,
        ]}
        onPress={handleImport}
        disabled={!importedAddress || loading}
        activeOpacity={0.7}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.importButtonText}>Import Wallet</Text>
        )}
      </TouchableOpacity>
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
  section: {
    backgroundColor: '#16213e',
    borderRadius: 12,
    padding: 15,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#0f3460',
  },
  label: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#00d4ff',
    marginBottom: 5,
  },
  description: {
    fontSize: 14,
    color: '#888',
    marginBottom: 15,
  },
  methodSelector: {
    gap: 10,
  },
  methodButton: {
    backgroundColor: '#0f3460',
    paddingVertical: 12,
    paddingHorizontal: 15,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#0f3460',
  },
  methodButtonActive: {
    backgroundColor: '#00d4ff',
    borderColor: '#00d4ff',
  },
  methodButtonText: {
    color: '#888',
    fontSize: 14,
  },
  methodButtonTextActive: {
    color: '#fff',
    fontWeight: 'bold',
  },
  input: {
    backgroundColor: '#0f3460',
    borderRadius: 8,
    padding: 12,
    color: '#fff',
    fontSize: 16,
    marginBottom: 15,
    borderWidth: 1,
    borderColor: '#1a1a2e',
  },
  keyInput: {
    fontFamily: 'monospace',
    fontSize: 12,
  },
  validateButton: {
    backgroundColor: '#0f3460',
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#00d4ff',
  },
  validateButtonText: {
    color: '#00d4ff',
    fontSize: 14,
    fontWeight: 'bold',
  },
  addressBox: {
    backgroundColor: '#0f3460',
    padding: 12,
    borderRadius: 8,
    marginTop: 10,
  },
  addressLabel: {
    fontSize: 12,
    color: '#888',
    marginBottom: 5,
  },
  addressText: {
    fontSize: 12,
    color: '#00ff88',
    fontFamily: 'monospace',
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
  importButton: {
    backgroundColor: '#00d4ff',
    paddingVertical: 15,
    borderRadius: 10,
    alignItems: 'center',
  },
  importButtonDisabled: {
    backgroundColor: '#444',
    opacity: 0.5,
  },
  importButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
});
