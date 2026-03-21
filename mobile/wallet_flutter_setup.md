# Flutter Wallet Setup Guide

This guide covers setting up a Flutter mobile wallet app for Rustchain with balance checking, transaction history, and QR code functionality.

## Project Structure

```
mobile_wallet/
├── lib/
│   ├── main.dart
│   ├── screens/
│   │   ├── home_screen.dart
│   │   ├── balance_screen.dart
│   │   ├── transactions_screen.dart
│   │   └── receive_screen.dart
│   ├── services/
│   │   └── api_service.dart
│   └── models/
│       ├── balance.dart
│       └── transaction.dart
└── pubspec.yaml
```

## pubspec.yaml Dependencies

```yaml
name: rustchain_wallet
description: Mobile wallet for Rustchain cryptocurrency
version: 1.0.0+1

environment:
  sdk: '>=3.0.0 <4.0.0'
  flutter: ">=3.10.0"

dependencies:
  flutter:
    sdk: flutter
  http: ^1.1.0
  qr_flutter: ^4.1.0
  qr_code_scanner: ^1.0.1
  shared_preferences: ^2.2.0
  flutter_secure_storage: ^9.0.0
  crypto: ^3.0.3
  json_annotation: ^4.8.1
  cupertino_icons: ^1.0.6

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^3.0.0
  json_serializable: ^6.7.1
  build_runner: ^2.4.6

flutter:
  uses-material-design: true
  assets:
    - assets/images/
```

## main.dart Structure

```dart
import 'package:flutter/material.dart';
import 'screens/home_screen.dart';

void main() {
  runApp(RustchainWalletApp());
}

class RustchainWalletApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Rustchain Wallet',
      theme: ThemeData(
        primarySwatch: Colors.orange,
        visualDensity: VisualDensity.adaptivePlatformDensity,
      ),
      home: HomeScreen(),
    );
  }
}
```

## API Service

```dart
// lib/services/api_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/balance.dart';
import '../models/transaction.dart';

class ApiService {
  static const String baseUrl = 'http://localhost:8000';

  static Future<Balance> getBalance(String address) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/balance/$address'),
      headers: {'Content-Type': 'application/json'},
    );

    if (response.statusCode == 200) {
      return Balance.fromJson(json.decode(response.body));
    }
    throw Exception('Failed to load balance');
  }

  static Future<List<Transaction>> getTransactions(String address) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/transactions/$address'),
      headers: {'Content-Type': 'application/json'},
    );

    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((json) => Transaction.fromJson(json)).toList();
    }
    throw Exception('Failed to load transactions');
  }

  static Future<String> sendTransaction(String from, String to, double amount) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/send'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode({
        'from': from,
        'to': to,
        'amount': amount,
      }),
    );

    if (response.statusCode == 200) {
      final data = json.decode(response.body);
      return data['txid'];
    }
    throw Exception('Failed to send transaction');
  }
}
```

## Data Models

```dart
// lib/models/balance.dart
class Balance {
  final double confirmed;
  final double pending;
  final String address;

  Balance({
    required this.confirmed,
    required this.pending,
    required this.address,
  });

  factory Balance.fromJson(Map<String, dynamic> json) {
    return Balance(
      confirmed: json['confirmed']?.toDouble() ?? 0.0,
      pending: json['pending']?.toDouble() ?? 0.0,
      address: json['address'] ?? '',
    );
  }
}

// lib/models/transaction.dart
class Transaction {
  final String txid;
  final String from;
  final String to;
  final double amount;
  final DateTime timestamp;
  final bool confirmed;

  Transaction({
    required this.txid,
    required this.from,
    required this.to,
    required this.amount,
    required this.timestamp,
    required this.confirmed,
  });

  factory Transaction.fromJson(Map<String, dynamic> json) {
    return Transaction(
      txid: json['txid'] ?? '',
      from: json['from'] ?? '',
      to: json['to'] ?? '',
      amount: json['amount']?.toDouble() ?? 0.0,
      timestamp: DateTime.parse(json['timestamp'] ?? DateTime.now().toIso8601String()),
      confirmed: json['confirmed'] ?? false,
    );
  }
}
```

## Home Screen

```dart
// lib/screens/home_screen.dart
import 'package:flutter/material.dart';
import 'balance_screen.dart';
import 'transactions_screen.dart';
import 'receive_screen.dart';

class HomeScreen extends StatefulWidget {
  @override
  _HomeScreenState createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;

  final List<Widget> _screens = [
    BalanceScreen(),
    TransactionsScreen(),
    ReceiveScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Rustchain Wallet'),
        backgroundColor: Colors.orange,
      ),
      body: _screens[_currentIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (index) => setState(() => _currentIndex = index),
        items: [
          BottomNavigationBarItem(
            icon: Icon(Icons.account_balance_wallet),
            label: 'Balance',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.history),
            label: 'Transactions',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.qr_code),
            label: 'Receive',
          ),
        ],
      ),
    );
  }
}
```

## Balance Screen

```dart
// lib/screens/balance_screen.dart
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../models/balance.dart';

class BalanceScreen extends StatefulWidget {
  @override
  _BalanceScreenState createState() => _BalanceScreenState();
}

class _BalanceScreenState extends State<BalanceScreen> {
  Balance? balance;
  bool isLoading = true;
  String walletAddress = 'your_wallet_address_here';

  @override
  void initState() {
    super.initState();
    loadBalance();
  }

  Future<void> loadBalance() async {
    try {
      final result = await ApiService.getBalance(walletAddress);
      setState(() {
        balance = result;
        isLoading = false;
      });
    } catch (e) {
      setState(() => isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to load balance: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Card(
            child: Padding(
              padding: EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Wallet Balance',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  SizedBox(height: 16),
                  if (isLoading)
                    CircularProgressIndicator()
                  else if (balance != null) ...[
                    Text(
                      'Confirmed: ${balance!.confirmed.toStringAsFixed(8)} RTC',
                      style: TextStyle(fontSize: 16),
                    ),
                    SizedBox(height: 8),
                    Text(
                      'Pending: ${balance!.pending.toStringAsFixed(8)} RTC',
                      style: TextStyle(fontSize: 16, color: Colors.orange),
                    ),
                  ] else
                    Text('Failed to load balance'),
                ],
              ),
            ),
          ),
          SizedBox(height: 20),
          ElevatedButton(
            onPressed: loadBalance,
            child: Text('Refresh Balance'),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.orange),
          ),
        ],
      ),
    );
  }
}
```

## Transactions Screen

```dart
// lib/screens/transactions_screen.dart
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../models/transaction.dart';

class TransactionsScreen extends StatefulWidget {
  @override
  _TransactionsScreenState createState() => _TransactionsScreenState();
}

class _TransactionsScreenState extends State<TransactionsScreen> {
  List<Transaction> transactions = [];
  bool isLoading = true;
  String walletAddress = 'your_wallet_address_here';

  @override
  void initState() {
    super.initState();
    loadTransactions();
  }

  Future<void> loadTransactions() async {
    try {
      final result = await ApiService.getTransactions(walletAddress);
      setState(() {
        transactions = result;
        isLoading = false;
      });
    } catch (e) {
      setState(() => isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to load transactions: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Transaction History',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
              IconButton(
                onPressed: loadTransactions,
                icon: Icon(Icons.refresh),
              ),
            ],
          ),
          SizedBox(height: 16),
          Expanded(
            child: isLoading
                ? Center(child: CircularProgressIndicator())
                : transactions.isEmpty
                    ? Center(child: Text('No transactions found'))
                    : ListView.builder(
                        itemCount: transactions.length,
                        itemBuilder: (context, index) {
                          final tx = transactions[index];
                          final isReceived = tx.to == walletAddress;
                          return Card(
                            child: ListTile(
                              leading: Icon(
                                isReceived ? Icons.arrow_downward : Icons.arrow_upward,
                                color: isReceived ? Colors.green : Colors.red,
                              ),
                              title: Text(
                                '${isReceived ? '+' : '-'}${tx.amount.toStringAsFixed(8)} RTC',
                                style: TextStyle(
                                  fontWeight: FontWeight.bold,
                                  color: isReceived ? Colors.green : Colors.red,
                                ),
                              ),
                              subtitle: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text('${isReceived ? 'From' : 'To'}: ${isReceived ? tx.from : tx.to}'),
                                  Text('${tx.timestamp.toString().substring(0, 16)}'),
                                ],
                              ),
                              trailing: Icon(
                                tx.confirmed ? Icons.check_circle : Icons.schedule,
                                color: tx.confirmed ? Colors.green : Colors.orange,
                              ),
                            ),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }
}
```

## Receive Screen with QR Code

```dart
// lib/screens/receive_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:qr_flutter/qr_flutter.dart';

class ReceiveScreen extends StatefulWidget {
  @override
  _ReceiveScreenState createState() => _ReceiveScreenState();
}

class _ReceiveScreenState extends State<ReceiveScreen> {
  String walletAddress = 'your_wallet_address_here';

  void copyToClipboard() {
    Clipboard.setData(ClipboardData(text: walletAddress));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Address copied to clipboard')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Text(
            'Receive RTC',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
          ),
          SizedBox(height: 32),
          Container(
            padding: EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.grey.shade300),
            ),
            child: QrImageView(
              data: walletAddress,
              version: QrVersions.auto,
              size: 200.0,
            ),
          ),
          SizedBox(height: 32),
          Text(
            'Your Wallet Address:',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
          ),
          SizedBox(height: 8),
          Container(
            padding: EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.grey.shade300),
            ),
            child: Text(
              walletAddress,
              style: TextStyle(fontSize: 14, fontFamily: 'monospace'),
              textAlign: TextAlign.center,
            ),
          ),
          SizedBox(height: 16),
          ElevatedButton.icon(
            onPressed: copyToClipboard,
            icon: Icon(Icons.copy),
            label: Text('Copy Address'),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.orange),
          ),
          SizedBox(height: 16),
          Text(
            'Share this address or QR code to receive RTC payments',
            style: TextStyle(color: Colors.grey.shade600),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
```

## Setup Instructions

1. **Create Flutter Project:**
   ```bash
   flutter create rustchain_wallet
   cd rustchain_wallet
   ```

2. **Replace pubspec.yaml** with the dependencies above

3. **Install Dependencies:**
   ```bash
   flutter pub get
   ```

4. **Add Platform Permissions:**

   For **android/app/src/main/AndroidManifest.xml:**
   ```xml
   <uses-permission android:name="android.permission.INTERNET" />
   <uses-permission android:name="android.permission.CAMERA" />
   ```

   For **ios/Runner/Info.plist:**
   ```xml
   <key>NSCameraUsageDescription</key>
   <string>Camera access needed for QR code scanning</string>
   ```

5. **Update API Base URL** in `api_service.dart` to match your Rustchain node

6. **Set Wallet Address** in each screen to use your actual wallet address

7. **Run the App:**
   ```bash
   flutter run
   ```

## Features Implemented

- **Balance Display:** Shows confirmed and pending RTC balance
- **Transaction History:** Lists incoming/outgoing transactions with status
- **QR Code Generation:** Creates QR code for wallet address
- **Address Sharing:** Copy wallet address to clipboard
- **HTTP Integration:** Connects to Rustchain node API
- **Material Design:** Clean, responsive UI for Android/iOS

## Next Steps

- Implement secure key storage
- Add transaction sending functionality
- Include QR code scanning for payments
- Add wallet creation/import features
- Implement push notifications for incoming transactions
