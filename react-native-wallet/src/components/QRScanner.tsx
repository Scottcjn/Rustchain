/**
 * QR Code Scanner Component (Hardened)
 *
 * Provides QR code scanning functionality with strict payload validation
 *
 * Issue #785: Security hardening
 * - Strict QR payload validation
 * - Schema validation for scanned data
 * - Prevent malicious payload injection
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
import {
  isValidAddress,
  isValidChainId,
  parseRtcAmountToMicrounits,
} from '../utils/crypto';

const MAX_QR_PAYLOAD_LENGTH = 2048;
const MAX_MEMO_LENGTH = 280;

/**
 * QR Payload types
 */
export type QRPayloadType = 
  | 'address'
  | 'transaction'
  | 'payment_request'
  | 'unknown';

/**
 * Validated QR payload
 */
export interface QRPayload {
  type: QRPayloadType;
  data: string;
  raw: string;
  validated: boolean;
  warnings: string[];
}

/**
 * Transaction request payload (BIP21-like)
 */
export interface PaymentRequest {
  address: string;
  amount?: number;
  memo?: string;
  chain_id?: string;
}

/**
 * Parse and validate QR payload
 * Issue #785: Strict validation to prevent malicious payloads
 */
export function parseQRPayload(data: string): QRPayload {
  const warnings: string[] = [];
  const trimmedData = data.trim();

  // Check for empty payload
  if (!trimmedData) {
    return {
      type: 'unknown',
      data: '',
      raw: data,
      validated: false,
      warnings: ['Empty payload'],
    };
  }

  if (trimmedData.length > MAX_QR_PAYLOAD_LENGTH) {
    return {
      type: 'unknown',
      data: trimmedData.slice(0, MAX_QR_PAYLOAD_LENGTH),
      raw: data,
      validated: false,
      warnings: ['Payload is too large'],
    };
  }

  if (/[\u0000-\u001F\u007F]/.test(trimmedData)) {
    return {
      type: 'unknown',
      data: trimmedData,
      raw: data,
      validated: false,
      warnings: ['Payload contains unsupported control characters'],
    };
  }

  // Check for URI scheme (rustchain:, rtc:, etc.)
  const uriMatch = trimmedData.match(/^([a-zA-Z][a-zA-Z0-9+.-]*):(\/\/)?(.*)$/);
  
  if (uriMatch) {
    const scheme = uriMatch[1].toLowerCase();
    const rest = uriMatch[3];

    // Validate scheme
    const validSchemes = ['rustchain', 'rtc'];
    if (!validSchemes.includes(scheme)) {
      warnings.push(`Unknown URI scheme: ${scheme}`);
    }

    // Parse as payment request
    try {
      const paymentRequest = parsePaymentRequest(scheme, rest);
      if (paymentRequest) {
        const validation = validatePaymentRequest(paymentRequest);
        // Only return payment_request if there's an amount, otherwise just address
        return {
          type: paymentRequest.amount !== undefined ? 'payment_request' : 'address',
          data: JSON.stringify(paymentRequest),
          raw: data,
          validated: validation.valid,
          warnings: warnings.concat(validation.errors),
        };
      }
    } catch (e) {
      warnings.push('Failed to parse payment request');
    }

    // Try to extract address from URI
    const addressFromUri = rest.split('?')[0];
    if (isValidAddress(addressFromUri)) {
      return {
        type: 'address',
        data: addressFromUri,
        raw: data,
        validated: true,
        warnings,
      };
    }
  }

  // Check for JSON payload
  if (trimmedData.startsWith('{') && trimmedData.endsWith('}')) {
    try {
      const json = JSON.parse(trimmedData);
      if (json && typeof json === 'object' && json.address) {
        const request: PaymentRequest = {
          address: String(json.address),
          amount: typeof json.amount === 'number' ? json.amount : undefined,
          memo: typeof json.memo === 'string' ? json.memo : typeof json.label === 'string' ? json.label : undefined,
          chain_id: typeof json.chain_id === 'string' ? json.chain_id : undefined,
        };
        const validation = validatePaymentRequest(request);
        return {
          type: request.amount !== undefined ? 'payment_request' : 'address',
          data: JSON.stringify(request),
          raw: data,
          validated: validation.valid,
          warnings: warnings.concat(validation.errors),
        };
      }
      
      // Unknown JSON structure
      warnings.push('Unrecognized JSON format');
      return {
        type: 'unknown',
        data: trimmedData,
        raw: data,
        validated: false,
        warnings,
      };
    } catch (e) {
      warnings.push('Invalid JSON format');
    }
  }

  // Plain address
  if (isValidAddress(trimmedData)) {
    return {
      type: 'address',
      data: trimmedData,
      raw: data,
      validated: true,
      warnings,
    };
  }

  // Check if it looks like a transaction hash
  if (/^[0-9a-fA-F]{64}$/.test(trimmedData)) {
    warnings.push('This appears to be a transaction hash, not an address');
    return {
      type: 'unknown',
      data: trimmedData,
      raw: data,
      validated: false,
      warnings,
    };
  }

  // Unknown format
  return {
    type: 'unknown',
    data: trimmedData,
    raw: data,
    validated: false,
    warnings: ['Unrecognized format'],
  };
}

/**
 * Parse BIP21-like payment request
 */
function parsePaymentRequest(scheme: string, uri: string): PaymentRequest | null {
  const [address, queryString] = uri.split('?');
  
  if (!address) {
    return null;
  }

  const result: PaymentRequest = {
    address,
  };

  if (queryString) {
    const params = new URLSearchParams(queryString);
    
    // Parse amount
    const amountStr = params.get('amount');
    if (amountStr) {
      const amountValidation = parseRtcAmountToMicrounits(amountStr);
      if (amountValidation.valid && amountValidation.value !== undefined) {
        result.amount = amountValidation.value;
      }
    }

    // Parse memo/label
    const memo = params.get('memo') || params.get('label') || undefined;
    result.memo = memo ? memo.slice(0, MAX_MEMO_LENGTH) : undefined;

    // Parse chain_id
    const chainId = params.get('chain_id') || undefined;
    result.chain_id = chainId && isValidChainId(chainId) ? chainId : undefined;
  }

  return result;
}

/**
 * Validate payment request
 */
export function validatePaymentRequest(request: PaymentRequest): {
  valid: boolean;
  errors: string[];
} {
  const errors: string[] = [];

  // Validate address
  if (!isValidAddress(request.address)) {
    errors.push('Invalid recipient address');
  }

  // Validate amount if present
  if (request.amount !== undefined) {
    if (request.amount <= 0) {
      errors.push('Amount must be greater than 0');
    }
    if (!Number.isFinite(request.amount)) {
      errors.push('Amount must be finite');
    }
    if (request.amount > Number.MAX_SAFE_INTEGER) {
      errors.push('Amount too large');
    }
  }

  if (request.memo && request.memo.length > MAX_MEMO_LENGTH) {
    errors.push('Memo is too long');
  }

  if (request.chain_id && !isValidChainId(request.chain_id)) {
    errors.push('Invalid chain_id');
  }

  return { valid: errors.length === 0, errors };
}

interface QRScannerProps {
  visible: boolean;
  onScan: (data: string) => void;
  onClose: () => void;
  title?: string;
  description?: string;
  acceptedTypes?: QRPayloadType[];
  strictValidation?: boolean;
}

export function QRScanner({
  visible,
  onScan,
  onClose,
  title = 'Scan QR Code',
  description = 'Position the QR code within the frame',
  acceptedTypes = ['address', 'payment_request'],
  strictValidation = true,
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
        Alert.alert('Error', 'Invalid QR code: empty payload');
        setScanned(false);
        return;
      }

      // Parse and validate payload
      const payload = parseQRPayload(data);

      // Check for warnings
      if (payload.warnings.length > 0) {
        console.warn('QR Scan warnings:', payload.warnings);
      }

      // Strict validation mode
      if (strictValidation && !payload.validated) {
        Alert.alert(
          'Invalid QR Code',
          `This QR code does not contain a valid ${acceptedTypes.join(' or ')}.\n\nWarnings:\n${payload.warnings.join('\n')}`,
          [
            { text: 'OK', onPress: () => setScanned(false) },
          ]
        );
        return;
      }

      // Check payload type
      if (!acceptedTypes.includes(payload.type)) {
        Alert.alert(
          'Unsupported QR Code',
          `This QR code contains ${payload.type} data, but only ${acceptedTypes.join(' or ')} is accepted.`,
          [
            { text: 'OK', onPress: () => setScanned(false) },
          ]
        );
        return;
      }

      // Additional validation for payment requests
      if (payload.type === 'payment_request') {
        try {
          const request: PaymentRequest = JSON.parse(payload.data);
          const validation = validatePaymentRequest(request);
          
          if (!validation.valid) {
            Alert.alert(
              'Invalid Payment Request',
              validation.errors.join('\n'),
              [
                { text: 'OK', onPress: () => setScanned(false) },
              ]
            );
            return;
          }

          // Warn about amount
          if (request.amount) {
            Alert.alert(
              'Payment Request',
              `Address: ${request.address.slice(0, 20)}...\nAmount: ${request.amount} RTC\n\nContinue?`,
              [
                { text: 'Cancel', style: 'cancel', onPress: () => setScanned(false) },
                {
                  text: 'Continue',
                  onPress: () => {
                    onScan(request.address);
                    onClose();
                  },
                },
              ]
            );
            return;
          }
        } catch (e) {
          Alert.alert(
            'Error',
            'Failed to parse payment request',
            [
              { text: 'OK', onPress: () => setScanned(false) },
            ]
          );
          return;
        }
      }

      // Valid address
      onScan(payload.data);
      onClose();
    },
    [scanned, onScan, onClose, strictValidation, acceptedTypes]
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

          {strictValidation && (
            <View style={styles.validationBadge}>
              <Text style={styles.validationBadgeText}>🔒 Strict Validation Enabled</Text>
            </View>
          )}

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
  validationBadge: {
    backgroundColor: '#16213e',
    paddingVertical: 8,
    paddingHorizontal: 15,
    borderRadius: 20,
    marginHorizontal: 20,
    marginTop: 10,
    borderWidth: 1,
    borderColor: '#00ff88',
  },
  validationBadgeText: {
    fontSize: 12,
    color: '#00ff88',
    fontWeight: 'bold',
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
