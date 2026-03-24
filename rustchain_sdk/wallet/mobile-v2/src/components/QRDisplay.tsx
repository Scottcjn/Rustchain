/**
 * QRDisplay Component
 *
 * Renders a QR code for the wallet address using react-native-qrcode-svg.
 * Falls back to text display if SVG rendering is unavailable.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

// Conditional import: react-native-qrcode-svg requires react-native-svg
let QRCode: any = null;
try {
  QRCode = require('react-native-qrcode-svg').default;
} catch {
  // Library not installed — fall back to text
}

interface QRDisplayProps {
  value: string;
  size?: number;
  label?: string;
}

export function QRDisplay({ value, size = 200, label }: QRDisplayProps): React.JSX.Element {
  return (
    <View style={styles.container}>
      {label && <Text style={styles.label}>{label}</Text>}
      <View style={styles.qrBox}>
        {QRCode ? (
          <QRCode
            value={value}
            size={size}
            color="#1a1a2e"
            backgroundColor="#ffffff"
          />
        ) : (
          <View style={[styles.fallback, { width: size, height: size }]}>
            <Text style={styles.fallbackIcon}>QR</Text>
            <Text style={styles.fallbackHint}>
              Install react-native-qrcode-svg{'\n'}for QR code display
            </Text>
          </View>
        )}
      </View>
      <Text style={styles.address} selectable numberOfLines={2}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
  },
  label: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#00d4ff',
    marginBottom: 16,
  },
  qrBox: {
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
  },
  fallback: {
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f0f0f0',
    borderRadius: 8,
  },
  fallbackIcon: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#1a1a2e',
    marginBottom: 8,
  },
  fallbackHint: {
    fontSize: 11,
    color: '#666',
    textAlign: 'center',
  },
  address: {
    fontSize: 12,
    color: '#888',
    fontFamily: 'monospace',
    textAlign: 'center',
    maxWidth: 280,
  },
});
