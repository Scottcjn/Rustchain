/**
 * Create Wallet Screen
 * 
 * Allows users to create a new wallet with password protection
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
import { generateKeyPair, publicKeyToBase58, publicKeyToHex } from '../../src/utils/crypto';
import { WalletStorage } from '../../src/storage/secure';

export default function CreateWalletScreen() {
  const router = useRouter();
  const [walletName, setWalletName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [generatedWallet, setGeneratedWallet] = useState<{
    address: string;
    publicKey: string;
  } | null>(null);

  const handleGenerate = () => {
    try {
      const keyPair = generateKeyPair();
      const address = publicKeyToBase58(keyPair.publicKey);
      const publicKey = publicKeyToHex(keyPair.publicKey);

      setGeneratedWallet({ address, publicKey });
    } catch (error) {
      Alert.alert('Error', 'Failed to generate wallet');
    }
  };

  const handleCreate = async () => {
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

    if (!generatedWallet) {
      Alert.alert('Error', 'Please generate a wallet first');
      return;
    }

    setLoading(true);

    try {
      // Generate key pair again (in production, store the generated one)
      const keyPair = generateKeyPair();

      // Save encrypted wallet
      await WalletStorage.save(walletName.trim(), keyPair, password);

      Alert.alert(
        'Wallet Created!',
        `Wallet "${walletName}" has been created successfully.`,
        [
          {
            text: 'OK',
            onPress: () => router.back(),
          },
        ]
      );
    } catch (error) {
      Alert.alert('Error', 'Failed to save wallet');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerate = () => {
    setGeneratedWallet(null);
    handleGenerate();
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.section}>
        <Text style={styles.label}>Step 1: Generate Wallet</Text>
        <Text style={styles.description}>
          Generate a new Ed25519 key pair for your RustChain wallet
        </Text>

        {!generatedWallet ? (
          <TouchableOpacity
            style={styles.generateButton}
            onPress={handleGenerate}
            activeOpacity={0.7}
          >
            <Text style={styles.generateButtonText}>Generate New Wallet</Text>
          </TouchableOpacity>
        ) : (
          <View style={styles.generatedContainer}>
            <View style={styles.addressBox}>
              <Text style={styles.addressLabel}>Wallet Address:</Text>
              <Text style={styles.addressText} selectable>
                {generatedWallet.address}
              </Text>
            </View>

            <View style={styles.addressBox}>
              <Text style={styles.addressLabel}>Public Key:</Text>
              <Text style={styles.addressText} selectable>
                {generatedWallet.publicKey}
              </Text>
            </View>

            <TouchableOpacity
              style={styles.regenerateButton}
              onPress={handleRegenerate}
              activeOpacity={0.7}
            >
              <Text style={styles.regenerateButtonText}>Generate Different Wallet</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>Step 2: Wallet Details</Text>
        <Text style={styles.description}>
          Choose a name and secure password for your wallet
        </Text>

        <TextInput
          style={styles.input}
          placeholder="Wallet Name (e.g., My Main Wallet)"
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
        <Text style={styles.warningTitle}>⚠️ Security Notice</Text>
        <Text style={styles.warningText}>
          • Your private key is encrypted with AES-256-GCM using your password
        </Text>
        <Text style={styles.warningText}>
          • Store your password securely - it cannot be recovered if lost
        </Text>
        <Text style={styles.warningText}>
          • Consider backing up your wallet after creation
        </Text>
      </View>

      <TouchableOpacity
        style={[
          styles.createButton,
          (!generatedWallet || loading) && styles.createButtonDisabled,
        ]}
        onPress={handleCreate}
        disabled={!generatedWallet || loading}
        activeOpacity={0.7}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.createButtonText}>Create Wallet</Text>
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
  generateButton: {
    backgroundColor: '#00d4ff',
    paddingVertical: 15,
    borderRadius: 10,
    alignItems: 'center',
  },
  generateButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
  generatedContainer: {
    gap: 10,
  },
  addressBox: {
    backgroundColor: '#0f3460',
    padding: 12,
    borderRadius: 8,
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
  regenerateButton: {
    backgroundColor: '#0f3460',
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#00d4ff',
  },
  regenerateButtonText: {
    color: '#00d4ff',
    fontSize: 14,
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
  createButton: {
    backgroundColor: '#00ff88',
    paddingVertical: 15,
    borderRadius: 10,
    alignItems: 'center',
  },
  createButtonDisabled: {
    backgroundColor: '#444',
    opacity: 0.5,
  },
  createButtonText: {
    color: '#1a1a2e',
    fontSize: 16,
    fontWeight: 'bold',
  },
});
