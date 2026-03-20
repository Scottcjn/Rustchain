# React Native Wallet Setup Guide

## Prerequisites

- Node.js 18+ and npm/yarn
- React Native development environment
- Android Studio (for Android) or Xcode (for iOS)
- Rustchain node running locally or remote access

## Installation

```bash
npx react-native init RustchainWallet
cd RustchainWallet
npm install @react-native-async-storage/async-storage
npm install react-native-qrcode-svg
npm install react-native-qrcode-scanner
npm install react-native-vector-icons
```

### iOS Setup
```bash
cd ios && pod install && cd ..
```

### Android Setup
Add to `android/app/build.gradle`:
```gradle
android {
    ...
    packagingOptions {
        pickFirst '**/libc++_shared.so'
        pickFirst '**/libjsc.so'
    }
}
```

## Core API Integration

Create `src/api/rustchain.js`:

```javascript
const API_BASE = 'http://localhost:8000'; // Adjust for your node

class RustchainAPI {
  async getBalance(address) {
    try {
      const response = await fetch(`${API_BASE}/balance/${address}`);
      const data = await response.json();
      return data.balance || 0;
    } catch (error) {
      console.error('Balance fetch error:', error);
      return 0;
    }
  }

  async getTransactions(address, limit = 50) {
    try {
      const response = await fetch(`${API_BASE}/transactions/${address}?limit=${limit}`);
      const data = await response.json();
      return data.transactions || [];
    } catch (error) {
      console.error('Transaction fetch error:', error);
      return [];
    }
  }

  async sendTransaction(fromAddress, toAddress, amount, privateKey) {
    try {
      const response = await fetch(`${API_BASE}/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          from: fromAddress,
          to: toAddress,
          amount: amount,
          private_key: privateKey
        })
      });
      return await response.json();
    } catch (error) {
      console.error('Send transaction error:', error);
      throw error;
    }
  }
}

export default new RustchainAPI();
```

## Wallet Components

### Balance Display Component

Create `src/components/BalanceCard.js`:

```javascript
import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, RefreshControl, ScrollView } from 'react-native';
import RustchainAPI from '../api/rustchain';

const BalanceCard = ({ address }) => {
  const [balance, setBalance] = useState(0);
  const [loading, setLoading] = useState(true);

  const fetchBalance = async () => {
    setLoading(true);
    const bal = await RustchainAPI.getBalance(address);
    setBalance(bal);
    setLoading(false);
  };

  useEffect(() => {
    if (address) {
      fetchBalance();
      const interval = setInterval(fetchBalance, 30000); // Update every 30s
      return () => clearInterval(interval);
    }
  }, [address]);

  return (
    <ScrollView
      refreshControl={
        <RefreshControl refreshing={loading} onRefresh={fetchBalance} />
      }
    >
      <View style={styles.container}>
        <Text style={styles.title}>Balance</Text>
        <Text style={styles.balance}>
          {balance.toFixed(8)} RTC
        </Text>
        <Text style={styles.address}>
          {address ? `${address.slice(0, 8)}...${address.slice(-8)}` : 'No address'}
        </Text>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#2c3e50',
    padding: 20,
    margin: 15,
    borderRadius: 12,
    alignItems: 'center',
  },
  title: {
    color: '#ecf0f1',
    fontSize: 16,
    marginBottom: 10,
  },
  balance: {
    color: '#f39c12',
    fontSize: 32,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  address: {
    color: '#95a5a6',
    fontSize: 12,
    fontFamily: 'monospace',
  },
});

export default BalanceCard;
```

### Transaction List Component

Create `src/components/TransactionList.js`:

```javascript
import React, { useState, useEffect } from 'react';
import { View, Text, FlatList, StyleSheet, RefreshControl } from 'react-native';
import RustchainAPI from '../api/rustchain';

const TransactionList = ({ address }) => {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchTransactions = async () => {
    setLoading(true);
    const txs = await RustchainAPI.getTransactions(address);
    setTransactions(txs);
    setLoading(false);
  };

  useEffect(() => {
    if (address) {
      fetchTransactions();
    }
  }, [address]);

  const renderTransaction = ({ item }) => {
    const isOutgoing = item.from === address;
    const amount = isOutgoing ? -item.amount : item.amount;
    const otherAddress = isOutgoing ? item.to : item.from;

    return (
      <View style={styles.txItem}>
        <View style={styles.txHeader}>
          <Text style={[styles.txAmount, isOutgoing ? styles.outgoing : styles.incoming]}>
            {amount > 0 ? '+' : ''}{amount.toFixed(8)} RTC
          </Text>
          <Text style={styles.txDate}>
            {new Date(item.timestamp * 1000).toLocaleDateString()}
          </Text>
        </View>
        <Text style={styles.txAddress}>
          {isOutgoing ? 'To: ' : 'From: '}
          {otherAddress ? `${otherAddress.slice(0, 12)}...${otherAddress.slice(-8)}` : 'Unknown'}
        </Text>
        <Text style={styles.txHash}>
          {item.hash ? `${item.hash.slice(0, 16)}...` : 'No hash'}
        </Text>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Recent Transactions</Text>
      <FlatList
        data={transactions}
        renderItem={renderTransaction}
        keyExtractor={(item, index) => item.hash || index.toString()}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={fetchTransactions} />
        }
        showsVerticalScrollIndicator={false}
        ListEmptyComponent={
          <Text style={styles.emptyText}>No transactions found</Text>
        }
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#ecf0f1',
    paddingHorizontal: 15,
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#2c3e50',
    marginVertical: 15,
  },
  txItem: {
    backgroundColor: '#fff',
    padding: 15,
    marginVertical: 4,
    borderRadius: 8,
    elevation: 2,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.22,
    shadowRadius: 2.22,
  },
  txHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  txAmount: {
    fontSize: 18,
    fontWeight: 'bold',
  },
  incoming: {
    color: '#27ae60',
  },
  outgoing: {
    color: '#e74c3c',
  },
  txDate: {
    color: '#7f8c8d',
    fontSize: 12,
  },
  txAddress: {
    color: '#34495e',
    fontSize: 14,
    marginBottom: 4,
    fontFamily: 'monospace',
  },
  txHash: {
    color: '#95a5a6',
    fontSize: 12,
    fontFamily: 'monospace',
  },
  emptyText: {
    textAlign: 'center',
    color: '#7f8c8d',
    fontSize: 16,
    marginTop: 50,
  },
});

export default TransactionList;
```

### QR Code Components

Create `src/components/QRGenerator.js`:

```javascript
import React from 'react';
import { View, Text, StyleSheet, Modal, TouchableOpacity } from 'react-native';
import QRCode from 'react-native-qrcode-svg';

const QRGenerator = ({ visible, address, onClose }) => {
  return (
    <Modal visible={visible} transparent animationType="slide">
      <View style={styles.overlay}>
        <View style={styles.container}>
          <Text style={styles.title}>Receive RTC</Text>
          <View style={styles.qrContainer}>
            {address ? (
              <QRCode
                value={address}
                size={200}
                backgroundColor="white"
                color="black"
              />
            ) : (
              <Text style={styles.noAddress}>No address available</Text>
            )}
          </View>
          <Text style={styles.address}>
            {address || 'No address'}
          </Text>
          <TouchableOpacity style={styles.closeButton} onPress={onClose}>
            <Text style={styles.closeText}>Close</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  container: {
    backgroundColor: 'white',
    padding: 30,
    borderRadius: 15,
    alignItems: 'center',
    maxWidth: '90%',
  },
  title: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#2c3e50',
    marginBottom: 20,
  },
  qrContainer: {
    padding: 20,
    backgroundColor: 'white',
    borderRadius: 10,
    marginBottom: 20,
  },
  address: {
    color: '#34495e',
    fontSize: 14,
    textAlign: 'center',
    fontFamily: 'monospace',
    marginBottom: 25,
    paddingHorizontal: 10,
  },
  closeButton: {
    backgroundColor: '#3498db',
    paddingHorizontal: 30,
    paddingVertical: 12,
    borderRadius: 8,
  },
  closeText: {
    color: 'white',
    fontSize: 16,
    fontWeight: 'bold',
  },
  noAddress: {
    fontSize: 16,
    color: '#e74c3c',
    textAlign: 'center',
    padding: 20,
  },
});

export default QRGenerator;
```

Create `src/components/QRScanner.js`:

```javascript
import React, { useState } from 'react';
import { View, Text, StyleSheet, Modal, TouchableOpacity, Alert } from 'react-native';
import QRCodeScanner from 'react-native-qrcode-scanner';

const QRScanner = ({ visible, onScan, onClose }) => {
  const [scanning, setScanning] = useState(true);

  const onSuccess = (e) => {
    setScanning(false);
    const scannedData = e.data;

    // Basic validation for Rustchain address format
    if (scannedData && scannedData.length >= 20) {
      onScan(scannedData);
    } else {
      Alert.alert('Invalid QR Code', 'This doesn\'t appear to be a valid Rustchain address.');
      setScanning(true);
    }
  };

  const handleClose = () => {
    setScanning(true);
    onClose();
  };

  return (
    <Modal visible={visible} animationType="slide">
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.title}>Scan QR Code</Text>
          <TouchableOpacity style={styles.closeButton} onPress={handleClose}>
            <Text style={styles.closeText}>✕</Text>
          </TouchableOpacity>
        </View>

        {scanning && (
          <QRCodeScanner
            onRead={onSuccess}
            showMarker={true}
            markerStyle={styles.marker}
            cameraStyle={styles.camera}
            topContent={
              <Text style={styles.instruction}>
                Point camera at QR code to scan address
              </Text>
            }
          />
        )}

        <View style={styles.footer}>
          <TouchableOpacity
            style={styles.rescanButton}
            onPress={() => setScanning(true)}
          >
            <Text style={styles.rescanText}>Rescan</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: 'black',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    paddingTop: 50,
    backgroundColor: 'rgba(0,0,0,0.8)',
  },
  title: {
    color: 'white',
    fontSize: 20,
    fontWeight: 'bold',
  },
  closeButton: {
    backgroundColor: 'rgba(255,255,255,0.2)',
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  closeText: {
    color: 'white',
    fontSize: 18,
    fontWeight: 'bold',
  },
  instruction: {
    color: 'white',
    fontSize: 16,
    textAlign: 'center',
    marginBottom: 20,
    paddingHorizontal: 20,
  },
  camera: {
    height: 400,
  },
  marker: {
    borderColor: '#f39c12',
    borderWidth: 2,
  },
  footer: {
    flex: 1,
    justifyContent: 'flex-end',
    alignItems: 'center',
    paddingBottom: 50,
    backgroundColor: 'rgba(0,0,0,0.8)',
  },
  rescanButton: {
    backgroundColor: '#3498db',
    paddingHorizontal: 30,
    paddingVertical: 15,
    borderRadius: 8,
  },
  rescanText: {
    color: 'white',
    fontSize: 16,
    fontWeight: 'bold',
  },
});

export default QRScanner;
```

## Main Wallet Screen

Create `src/screens/WalletScreen.js`:

```javascript
import React, { useState, useEffect } from 'react';
import { View, StyleSheet, TouchableOpacity, Text } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import BalanceCard from '../components/BalanceCard';
import TransactionList from '../components/TransactionList';
import QRGenerator from '../components/QRGenerator';
import QRScanner from '../components/QRScanner';

const WalletScreen = () => {
  const [address, setAddress] = useState('');
  const [showQRReceive, setShowQRReceive] = useState(false);
  const [showQRScan, setShowQRScan] = useState(false);

  useEffect(() => {
    loadAddress();
  }, []);

  const loadAddress = async () => {
    try {
      const savedAddress = await AsyncStorage.getItem('wallet_address');
      if (savedAddress) {
        setAddress(savedAddress);
      }
    } catch (error) {
      console.error('Error loading address:', error);
    }
  };

  const handleQRScan = (scannedAddress) => {
    console.log('Scanned address:', scannedAddress);
    setShowQRScan(false);
    // Here you would typically navigate to a send screen
    // or handle the scanned address appropriately
  };

  return (
    <View style={styles.container}>
      <BalanceCard address={address} />

      <View style={styles.buttonRow}>
        <TouchableOpacity
          style={[styles.actionButton, styles.receiveButton]}
          onPress={() => setShowQRReceive(true)}
        >
          <Text style={styles.buttonText}>Receive</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.actionButton, styles.sendButton]}
          onPress={() => setShowQRScan(true)}
        >
          <Text style={styles.buttonText}>Send</Text>
        </TouchableOpacity>
      </View>

      <TransactionList address={address} />

      <QRGenerator
        visible={showQRReceive}
        address={address}
        onClose={() => setShowQRReceive(false)}
      />

      <QRScanner
        visible={showQRScan}
        onScan={handleQRScan}
        onClose={() => setShowQRScan(false)}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#ecf0f1',
  },
  buttonRow: {
    flexDirection: 'row',
    paddingHorizontal: 15,
    marginBottom: 10,
  },
  actionButton: {
    flex: 1,
    paddingVertical: 15,
    marginHorizontal: 5,
    borderRadius: 8,
    alignItems: 'center',
  },
  receiveButton: {
    backgroundColor: '#27ae60',
  },
  sendButton: {
    backgroundColor: '#3498db',
  },
  buttonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: 'bold',
  },
});

export default WalletScreen;
```

## Usage

Replace your `App.js` with:

```javascript
import React from 'react';
import { StatusBar } from 'react-native';
import WalletScreen from './src/screens/WalletScreen';

const App = () => {
  return (
    <>
      <StatusBar barStyle="dark-content" backgroundColor="#ecf0f1" />
      <WalletScreen />
    </>
  );
};

export default App;
```

## Configuration Notes

1. Update `API_BASE` in `rustchain.js` to match your Rustchain node URL
2. Ensure your Rustchain node has CORS enabled for mobile requests
3. Store wallet private keys securely using KeyChain (iOS) or KeyStore (Android)
4. Test on both iOS and Android devices for platform-specific behavior
5. Consider implementing proper error handling and loading states
6. Add proper address generation and validation logic
7. Implement secure storage for sensitive data like private keys

This setup provides a basic but functional mobile wallet with balance display, transaction history, and QR code scanning/generation capabilities.
