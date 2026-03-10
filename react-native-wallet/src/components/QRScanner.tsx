/**
 * QR Code Scanner Component
 *
 * Provides QR code scanning functionality for wallet addresses
 * using expo-camera with graceful fallback for unsupported devices
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Modal,
  ActivityIndicator,
  Alert,
  Platform,
} from 'react-native';
import { CameraView, useCameraPermissions, BarcodeScanningResult } from 'expo-camera';

interface QRScannerProps {
  visible: boolean;
  onScan: (data: string) => void;
  onClose: () => void;
  title?: string;
  description?: string;
}

export function QRScanner({
  visible,
  onScan,
  onClose,
  title = 'Scan QR Code',
  description = 'Position the QR code within the frame',
}: QRScannerProps) {
  const [permission, requestPermission] = useCameraPermissions();
  const [scanned, setScanned] = useState(false);
  const [torchOn, setTorchOn] = useState(false);

  useEffect(() => {
    if (visible && !permission) {
      requestPermission();
    }
    if (!visible) {
      setScanned(false);
      setTorchOn(false);
    }
  }, [visible, permission]);

  const handleBarCodeScanned = useCallback(
    (result: BarcodeScanningResult) => {
      if (scanned) return;
      setScanned(true);

      const data = result.data?.trim();
      if (!data) {
        Alert.alert('Error', 'Invalid QR code');
        setScanned(false);
        return;
      }

      // Validate it looks like a wallet address (basic validation)
      if (data.startsWith('RTC') || data.length >= 40) {
        onScan(data);
        onClose();
      } else {
        Alert.alert(
          'Warning',
          'Scanned content may not be a valid wallet address. Continue?',
          [
            { text: 'Cancel', style: 'cancel', onPress: () => setScanned(false) },
            {
              text: 'Use Anyway',
              onPress: () => {
                onScan(data);
                onClose();
              },
            },
          ]
        );
      }
    },
    [scanned, onScan, onClose]
  );

  const handleClose = () => {
    setScanned(false);
    setTorchOn(false);
    onClose();
  };

  const handleRetry = () => {
    setScanned(false);
  };

  const toggleTorch = () => {
    setTorchOn(!torchOn);
  };

  if (!permission) {
    return (
      <Modal visible={visible} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.container}>
            <ActivityIndicator size="large" color="#00d4ff" />
            <Text style={styles.permissionText}>Requesting camera permission...</Text>
          </View>
        </View>
      </Modal>
    );
  }

  if (!permission.granted) {
    return (
      <Modal visible={visible} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.permissionContainer}>
            <Text style={styles.permissionTitle}>Camera Permission Required</Text>
            <Text style={styles.permissionDescription}>
              To scan QR codes, we need permission to use your camera.
            </Text>
            <TouchableOpacity
              style={styles.permissionButton}
              onPress={requestPermission}
              activeOpacity={0.7}
            >
              <Text style={styles.permissionButtonText}>Grant Permission</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.permissionButton, styles.cancelButton]}
              onPress={handleClose}
              activeOpacity={0.7}
            >
              <Text style={styles.cancelButtonText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    );
  }

  return (
    <Modal visible={visible} transparent animationType="slide">
      <View style={styles.modalOverlay}>
        <View style={styles.scannerContainer}>
          <View style={styles.header}>
            <Text style={styles.title}>{title}</Text>
            <TouchableOpacity onPress={handleClose} activeOpacity={0.7}>
              <Text style={styles.closeButton}>✕</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.cameraContainer}>
            <CameraView
              style={styles.camera}
              barcodeScannerSettings={{
                barcodeTypes: ['qr'],
              }}
              enableTorch={torchOn}
              onBarcodeScanned={scanned ? undefined : handleBarCodeScanned}
            />
            
            <View style={styles.overlay}>
              <View style={styles.scanFrame} />
            </View>
          </View>

          <Text style={styles.description}>{description}</Text>

          <View style={styles.controls}>
            <TouchableOpacity
              style={styles.controlButton}
              onPress={toggleTorch}
              activeOpacity={0.7}
            >
              <Text style={styles.controlButtonText}>
                {torchOn ? '🔦 Flash On' : '💡 Flash Off'}
              </Text>
            </TouchableOpacity>

            {scanned && (
              <TouchableOpacity
                style={[styles.controlButton, styles.retryButton]}
                onPress={handleRetry}
                activeOpacity={0.7}
              >
                <Text style={styles.controlButtonText}>🔄 Scan Again</Text>
              </TouchableOpacity>
            )}
          </View>

          <View style={styles.fallbackSection}>
            <Text style={styles.fallbackText}>Can't scan?</Text>
            <Text style={styles.fallbackHint}>
              Make sure the QR code is well-lit and fully visible
            </Text>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.95)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  container: {
    backgroundColor: '#1a1a2e',
    padding: 30,
    borderRadius: 15,
    alignItems: 'center',
  },
  permissionContainer: {
    backgroundColor: '#16213e',
    padding: 30,
    borderRadius: 15,
    alignItems: 'center',
    maxWidth: '85%',
  },
  permissionText: {
    color: '#888',
    marginTop: 15,
    textAlign: 'center',
  },
  permissionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 10,
    textAlign: 'center',
  },
  permissionDescription: {
    fontSize: 14,
    color: '#888',
    textAlign: 'center',
    marginBottom: 20,
    lineHeight: 20,
  },
  permissionButton: {
    backgroundColor: '#00d4ff',
    paddingVertical: 12,
    paddingHorizontal: 30,
    borderRadius: 10,
    marginBottom: 10,
    width: '100%',
    alignItems: 'center',
  },
  permissionButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
  cancelButton: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: '#666',
  },
  cancelButtonText: {
    color: '#888',
  },
  scannerContainer: {
    flex: 1,
    width: '100%',
    backgroundColor: '#1a1a2e',
    paddingTop: Platform.OS === 'ios' ? 60 : 40,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingBottom: 20,
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#fff',
  },
  closeButton: {
    fontSize: 28,
    color: '#fff',
    fontWeight: '300',
  },
  cameraContainer: {
    flex: 1,
    marginHorizontal: 20,
    borderRadius: 15,
    overflow: 'hidden',
    backgroundColor: '#000',
  },
  camera: {
    flex: 1,
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scanFrame: {
    width: 250,
    height: 250,
    borderWidth: 2,
    borderColor: '#00d4ff',
    borderRadius: 15,
    backgroundColor: 'transparent',
  },
  description: {
    fontSize: 14,
    color: '#888',
    textAlign: 'center',
    padding: 20,
  },
  controls: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 15,
    padding: 20,
  },
  controlButton: {
    backgroundColor: '#16213e',
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#00d4ff',
  },
  controlButtonText: {
    color: '#00d4ff',
    fontSize: 14,
    fontWeight: 'bold',
  },
  retryButton: {
    borderColor: '#ff6b6b',
  },
  fallbackSection: {
    paddingHorizontal: 20,
    paddingBottom: 20,
  },
  fallbackText: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
    marginBottom: 5,
  },
  fallbackHint: {
    fontSize: 12,
    color: '#444',
    textAlign: 'center',
  },
});

export default QRScanner;
