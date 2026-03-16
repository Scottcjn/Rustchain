/**
 * Settings Screen
 *
 * Network selection, biometric toggle, wallet management, and about info.
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Alert,
  ScrollView,
  Switch,
  TextInput,
  Modal,
} from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/AppNavigator';
import { WalletStorage } from '../services/storage';
import { RustChainClient } from '../services/api';
import { isBiometricAvailable, getBiometricType, getBiometricTypeName } from '../services/biometric';
import type { NetworkId, BiometricType } from '../types';

type Props = NativeStackScreenProps<RootStackParamList, 'Settings'>;

export default function SettingsScreen({ navigation }: Props): React.JSX.Element {
  const [bioAvailable, setBioAvailable] = useState(false);
  const [bioEnabled, setBioEnabled] = useState(true);
  const [bioType, setBioType] = useState<BiometricType>('NONE');
  const [network, setNetwork] = useState<NetworkId>('mainnet');
  const [nodeHealth, setNodeHealth] = useState<boolean | null>(null);
  const [walletCount, setWalletCount] = useState(0);
  const [showChangePw, setShowChangePw] = useState(false);
  const [changePwWallet, setChangePwWallet] = useState('');
  const [oldPw, setOldPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');

  useEffect(() => {
    (async () => {
      const avail = await isBiometricAvailable();
      setBioAvailable(avail);
      if (avail) {
        const type = await getBiometricType();
        setBioType(type);
      }
      const wallets = await WalletStorage.list();
      setWalletCount(wallets.length);
    })();
  }, []);

  const checkHealth = async () => {
    setNodeHealth(null);
    const client = new RustChainClient(network);
    const healthy = await client.healthCheck();
    setNodeHealth(healthy);
    Alert.alert(
      healthy ? 'Node Online' : 'Node Offline',
      healthy ? 'Successfully connected to the RustChain node.' : 'Could not reach the node. Check your network.'
    );
  };

  const handleChangePw = async () => {
    if (!changePwWallet) { Alert.alert('Error', 'Select a wallet'); return; }
    if (newPw.length < 8) { Alert.alert('Error', 'New password must be at least 8 characters'); return; }
    if (newPw !== confirmPw) { Alert.alert('Error', 'Passwords do not match'); return; }

    try {
      await WalletStorage.changePassword(changePwWallet, oldPw, newPw);
      Alert.alert('Success', 'Password changed successfully');
      setShowChangePw(false);
      setOldPw('');
      setNewPw('');
      setConfirmPw('');
    } catch (err: any) {
      Alert.alert('Error', err.message || 'Failed to change password');
    }
  };

  const handleExportWallet = async () => {
    const wallets = await WalletStorage.list();
    if (wallets.length === 0) { Alert.alert('No Wallets', 'Create a wallet first'); return; }

    Alert.alert('Export Wallet', 'Select a wallet to export', [
      ...wallets.map((name) => ({
        text: name,
        onPress: () => {
          Alert.prompt?.(
            'Enter Password',
            `Password for "${name}":`,
            async (pw: string) => {
              try {
                const backup = await WalletStorage.export(name, pw);
                Alert.alert('Backup', `Backup data (${backup.length} chars) ready. In production, this would be shared via secure channel.`);
              } catch {
                Alert.alert('Error', 'Invalid password');
              }
            },
            'secure-text'
          );
        },
      })),
      { text: 'Cancel', style: 'cancel' },
    ]);
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Network */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Network</Text>
        <View style={styles.networkRow}>
          {(['mainnet', 'testnet', 'devnet'] as NetworkId[]).map((n) => (
            <TouchableOpacity
              key={n}
              style={[styles.netBtn, network === n && styles.netBtnActive]}
              onPress={() => setNetwork(n)}
              activeOpacity={0.7}
            >
              <Text style={[styles.netBtnText, network === n && styles.netBtnTextActive]}>
                {n.charAt(0).toUpperCase() + n.slice(1)}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
        <TouchableOpacity style={styles.healthBtn} onPress={checkHealth} activeOpacity={0.7}>
          <Text style={styles.healthBtnText}>Check Node Health</Text>
        </TouchableOpacity>
        {nodeHealth !== null && (
          <Text style={[styles.healthStatus, { color: nodeHealth ? '#00ff88' : '#ff6b6b' }]}>
            {nodeHealth ? 'Node is online' : 'Node unreachable'}
          </Text>
        )}
      </View>

      {/* Security */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Security</Text>
        <View style={styles.settingRow}>
          <View>
            <Text style={styles.settingLabel}>Biometric Authentication</Text>
            <Text style={styles.settingDesc}>
              {bioAvailable ? getBiometricTypeName(bioType) : 'Not available on this device'}
            </Text>
          </View>
          <Switch
            value={bioEnabled && bioAvailable}
            onValueChange={setBioEnabled}
            disabled={!bioAvailable}
            trackColor={{ false: '#333', true: '#00d4ff' }}
            thumbColor="#fff"
          />
        </View>
      </View>

      {/* Wallet Management */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Wallet Management</Text>
        <Text style={styles.settingDesc}>{walletCount} wallet(s) stored</Text>

        <TouchableOpacity style={styles.mgmtBtn} onPress={() => {
          WalletStorage.list().then((wallets) => {
            if (wallets.length === 0) { Alert.alert('No Wallets'); return; }
            Alert.alert('Change Password', 'Select a wallet', [
              ...wallets.map((name) => ({
                text: name,
                onPress: () => { setChangePwWallet(name); setShowChangePw(true); },
              })),
              { text: 'Cancel', style: 'cancel' },
            ]);
          });
        }} activeOpacity={0.7}>
          <Text style={styles.mgmtBtnText}>Change Password</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.mgmtBtn} onPress={handleExportWallet} activeOpacity={0.7}>
          <Text style={styles.mgmtBtnText}>Export Wallet Backup</Text>
        </TouchableOpacity>
      </View>

      {/* About */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>About</Text>
        <View style={styles.aboutRow}>
          <Text style={styles.aboutLabel}>App Version</Text>
          <Text style={styles.aboutValue}>1.0.0</Text>
        </View>
        <View style={styles.aboutRow}>
          <Text style={styles.aboutLabel}>Encryption</Text>
          <Text style={styles.aboutValue}>AES-256-GCM</Text>
        </View>
        <View style={styles.aboutRow}>
          <Text style={styles.aboutLabel}>Key Derivation</Text>
          <Text style={styles.aboutValue}>PBKDF2-SHA256 (600k)</Text>
        </View>
        <View style={styles.aboutRow}>
          <Text style={styles.aboutLabel}>Signing</Text>
          <Text style={styles.aboutValue}>Ed25519</Text>
        </View>
        <View style={styles.aboutRow}>
          <Text style={styles.aboutLabel}>Mnemonic</Text>
          <Text style={styles.aboutValue}>BIP39 (12 words)</Text>
        </View>
      </View>

      {/* Change Password Modal */}
      <Modal visible={showChangePw} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.pwModal}>
            <Text style={styles.pwTitle}>Change Password</Text>
            <Text style={styles.pwWallet}>{changePwWallet}</Text>
            <TextInput style={styles.pwInput} placeholder="Current Password" placeholderTextColor="#666" value={oldPw} onChangeText={setOldPw} secureTextEntry />
            <TextInput style={styles.pwInput} placeholder="New Password (min 8 chars)" placeholderTextColor="#666" value={newPw} onChangeText={setNewPw} secureTextEntry />
            <TextInput style={styles.pwInput} placeholder="Confirm New Password" placeholderTextColor="#666" value={confirmPw} onChangeText={setConfirmPw} secureTextEntry />
            <View style={styles.pwBtns}>
              <TouchableOpacity style={[styles.pwBtn, styles.pwCancel]} onPress={() => { setShowChangePw(false); setOldPw(''); setNewPw(''); setConfirmPw(''); }}>
                <Text style={styles.pwCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.pwBtn, styles.pwConfirm]} onPress={handleChangePw}>
                <Text style={styles.pwConfirmText}>Change</Text>
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
  section: { backgroundColor: '#12122a', borderRadius: 12, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: '#1a1a3e' },
  sectionTitle: { fontSize: 16, fontWeight: 'bold', color: '#00d4ff', marginBottom: 12 },
  networkRow: { flexDirection: 'row', gap: 10, marginBottom: 12 },
  netBtn: { flex: 1, paddingVertical: 10, borderRadius: 8, alignItems: 'center', backgroundColor: '#0f3460' },
  netBtnActive: { backgroundColor: '#00d4ff' },
  netBtnText: { color: '#888', fontSize: 14, fontWeight: 'bold' },
  netBtnTextActive: { color: '#fff' },
  healthBtn: { backgroundColor: '#0f3460', paddingVertical: 12, borderRadius: 8, alignItems: 'center', borderWidth: 1, borderColor: '#00d4ff' },
  healthBtnText: { color: '#00d4ff', fontSize: 14, fontWeight: 'bold' },
  healthStatus: { fontSize: 13, marginTop: 8, textAlign: 'center' },
  settingRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  settingLabel: { fontSize: 15, color: '#fff', marginBottom: 2 },
  settingDesc: { fontSize: 13, color: '#888' },
  mgmtBtn: { backgroundColor: '#0f3460', paddingVertical: 12, borderRadius: 8, alignItems: 'center', marginTop: 10, borderWidth: 1, borderColor: '#1a1a3e' },
  mgmtBtnText: { color: '#00d4ff', fontSize: 14, fontWeight: 'bold' },
  aboutRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#1a1a3e' },
  aboutLabel: { fontSize: 14, color: '#888' },
  aboutValue: { fontSize: 14, color: '#fff' },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.8)', justifyContent: 'center', alignItems: 'center' },
  pwModal: { backgroundColor: '#12122a', padding: 24, borderRadius: 16, width: '85%', borderWidth: 1, borderColor: '#00d4ff' },
  pwTitle: { fontSize: 18, fontWeight: 'bold', color: '#fff', textAlign: 'center', marginBottom: 4 },
  pwWallet: { fontSize: 14, color: '#00d4ff', textAlign: 'center', marginBottom: 16 },
  pwInput: { backgroundColor: '#0f3460', borderRadius: 8, padding: 12, color: '#fff', fontSize: 16, marginBottom: 12 },
  pwBtns: { flexDirection: 'row', gap: 10 },
  pwBtn: { flex: 1, paddingVertical: 12, borderRadius: 8, alignItems: 'center' },
  pwCancel: { backgroundColor: '#0f3460', borderWidth: 1, borderColor: '#666' },
  pwCancelText: { color: '#888', fontSize: 15, fontWeight: 'bold' },
  pwConfirm: { backgroundColor: '#00d4ff' },
  pwConfirmText: { color: '#fff', fontSize: 15, fontWeight: 'bold' },
});
