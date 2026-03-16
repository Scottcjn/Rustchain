/**
 * QR Code Scanner Component
 *
 * Camera-based QR scanning with strict payload validation.
 * Accepts RTC addresses and payment request URIs.
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
import { isValidAddress, isValidChainId, parseRtcAmountToMicrounits } from '../services/wallet';
import type { QRPayload, QRPayloadType, PaymentRequest } from '../types';

const MAX_QR_LENGTH = 2048;
const MAX_MEMO_LENGTH = 280;

// ── Payload Parsing ─────────────────────────────────────────────────────────

export function parseQRPayload(data: string): QRPayload {
  const warnings: string[] = [];
  const trimmed = data.trim();

  if (!trimmed) {
    return { type: 'unknown', data: '', raw: data, validated: false, warnings: ['Empty payload'] };
  }
  if (trimmed.length > MAX_QR_LENGTH) {
    return { type: 'unknown', data: trimmed.slice(0, MAX_QR_LENGTH), raw: data, validated: false, warnings: ['Payload too large'] };
  }
  if (/[\u0000-\u001F\u007F]/.test(trimmed)) {
    return { type: 'unknown', data: trimmed, raw: data, validated: false, warnings: ['Contains control characters'] };
  }

  // URI scheme (rustchain: or rtc:)
  const uriMatch = trimmed.match(/^([a-zA-Z][a-zA-Z0-9+.-]*):(\/\/)?(.*)$/);
  if (uriMatch) {
    const scheme = uriMatch[1].toLowerCase();
    const rest = uriMatch[3];
    if (!['rustchain', 'rtc'].includes(scheme)) {
      warnings.push(`Unknown URI scheme: ${scheme}`);
    }
    try {
      const req = parsePaymentRequest(rest);
      if (req) {
        const v = validatePaymentRequest(req);
        return {
          type: req.amount !== undefined ? 'payment_request' : 'address',
          data: JSON.stringify(req),
          raw: data,
          validated: v.valid,
          warnings: warnings.concat(v.errors),
        };
      }
    } catch {
      warnings.push('Failed to parse payment request');
    }
    const addr = rest.split('?')[0];
    if (isValidAddress(addr)) {
      return { type: 'address', data: addr, raw: data, validated: true, warnings };
    }
  }

  // JSON payload
  if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
    try {
      const json = JSON.parse(trimmed);
      if (json?.address) {
        const req: PaymentRequest = {
          address: String(json.address),
          amount: typeof json.amount === 'number' ? json.amount : undefined,
          memo: typeof json.memo === 'string' ? json.memo : undefined,
          chain_id: typeof json.chain_id === 'string' ? json.chain_id : undefined,
        };
        const v = validatePaymentRequest(req);
        return {
          type: req.amount !== undefined ? 'payment_request' : 'address',
          data: JSON.stringify(req),
          raw: data,
          validated: v.valid,
          warnings: warnings.concat(v.errors),
        };
      }
      return { type: 'unknown', data: trimmed, raw: data, validated: false, warnings: ['Unrecognized JSON'] };
    } catch {
      warnings.push('Invalid JSON');
    }
  }

  // Plain address
  if (isValidAddress(trimmed)) {
    return { type: 'address', data: trimmed, raw: data, validated: true, warnings };
  }

  return { type: 'unknown', data: trimmed, raw: data, validated: false, warnings: ['Unrecognized format'] };
}

function parsePaymentRequest(uri: string): PaymentRequest | null {
  const [address, qs] = uri.split('?');
  if (!address) return null;
  const result: PaymentRequest = { address };
  if (qs) {
    const params = new URLSearchParams(qs);
    const amt = params.get('amount');
    if (amt) {
      const v = parseRtcAmountToMicrounits(amt);
      if (v.valid && v.value !== undefined) result.amount = v.value;
    }
    const memo = params.get('memo') || params.get('label');
    if (memo) result.memo = memo.slice(0, MAX_MEMO_LENGTH);
    const cid = params.get('chain_id');
    if (cid && isValidChainId(cid)) result.chain_id = cid;
  }
  return result;
}

export function validatePaymentRequest(req: PaymentRequest): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  if (!isValidAddress(req.address)) errors.push('Invalid recipient address');
  if (req.amount !== undefined) {
    if (req.amount <= 0) errors.push('Amount must be > 0');
    if (!Number.isFinite(req.amount)) errors.push('Amount must be finite');
  }
  if (req.memo && req.memo.length > MAX_MEMO_LENGTH) errors.push('Memo too long');
  if (req.chain_id && !isValidChainId(req.chain_id)) errors.push('Invalid chain_id');
  return { valid: errors.length === 0, errors };
}

// ── Scanner Component ───────────────────────────────────────────────────────

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
}: QRScannerProps): React.JSX.Element {
  const [permission, requestPermission] = useCameraPermissions();
  const [scanned, setScanned] = useState(false);
  const [torchOn, setTorchOn] = useState(false);

  useEffect(() => {
    if (visible && !permission) requestPermission();
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
        Alert.alert('Error', 'Empty QR code');
        setScanned(false);
        return;
      }

      const payload = parseQRPayload(data);

      if (strictValidation && !payload.validated) {
        Alert.alert(
          'Invalid QR Code',
          payload.warnings.join('\n') || 'Not a valid RTC address or payment request',
          [{ text: 'OK', onPress: () => setScanned(false) }]
        );
        return;
      }

      if (!acceptedTypes.includes(payload.type)) {
        Alert.alert('Unsupported QR Code', `Expected ${acceptedTypes.join(' or ')}, got ${payload.type}`, [
          { text: 'OK', onPress: () => setScanned(false) },
        ]);
        return;
      }

      if (payload.type === 'payment_request') {
        try {
          const req: PaymentRequest = JSON.parse(payload.data);
          if (req.amount) {
            Alert.alert(
              'Payment Request',
              `Address: ${req.address.slice(0, 20)}...\nAmount: ${req.amount} RTC`,
              [
                { text: 'Cancel', style: 'cancel', onPress: () => setScanned(false) },
                { text: 'Continue', onPress: () => { onScan(req.address); onClose(); } },
              ]
            );
            return;
          }
        } catch {
          Alert.alert('Error', 'Failed to parse payment request', [{ text: 'OK', onPress: () => setScanned(false) }]);
          return;
        }
      }

      onScan(payload.data);
      onClose();
    },
    [scanned, onScan, onClose, strictValidation, acceptedTypes]
  );

  const handleClose = () => { setScanned(false); setTorchOn(false); onClose(); };

  if (!permission) {
    return (
      <Modal visible={visible} transparent animationType="fade">
        <View style={styles.overlay}>
          <View style={styles.centered}>
            <ActivityIndicator size="large" color="#00d4ff" />
            <Text style={styles.permText}>Requesting camera permission...</Text>
          </View>
        </View>
      </Modal>
    );
  }

  if (!permission.granted) {
    return (
      <Modal visible={visible} transparent animationType="fade">
        <View style={styles.overlay}>
          <View style={styles.permBox}>
            <Text style={styles.permTitle}>Camera Permission Required</Text>
            <Text style={styles.permDesc}>Camera is needed to scan QR codes.</Text>
            <TouchableOpacity style={styles.permBtn} onPress={requestPermission}>
              <Text style={styles.permBtnText}>Grant Permission</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.permBtn, styles.cancelBtn]} onPress={handleClose}>
              <Text style={styles.cancelBtnText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    );
  }

  return (
    <Modal visible={visible} transparent animationType="slide">
      <View style={styles.overlay}>
        <View style={styles.scanner}>
          <View style={styles.headerRow}>
            <Text style={styles.title}>{title}</Text>
            <TouchableOpacity onPress={handleClose}>
              <Text style={styles.closeBtn}>{'\u2715'}</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.cameraBox}>
            <CameraView
              style={styles.camera}
              barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
              enableTorch={torchOn}
              onBarcodeScanned={scanned ? undefined : handleBarCodeScanned}
            />
            <View style={styles.frameOverlay}>
              <View style={styles.scanFrame} />
            </View>
          </View>

          <Text style={styles.desc}>{description}</Text>

          <View style={styles.controls}>
            <TouchableOpacity style={styles.ctrlBtn} onPress={() => setTorchOn(!torchOn)}>
              <Text style={styles.ctrlBtnText}>{torchOn ? 'Flash On' : 'Flash Off'}</Text>
            </TouchableOpacity>
            {scanned && (
              <TouchableOpacity style={[styles.ctrlBtn, styles.retryBtn]} onPress={() => setScanned(false)}>
                <Text style={styles.ctrlBtnText}>Scan Again</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.95)', justifyContent: 'center', alignItems: 'center' },
  centered: { backgroundColor: '#1a1a2e', padding: 30, borderRadius: 15, alignItems: 'center' },
  permText: { color: '#888', marginTop: 15 },
  permBox: { backgroundColor: '#16213e', padding: 30, borderRadius: 15, alignItems: 'center', maxWidth: '85%' },
  permTitle: { fontSize: 18, fontWeight: 'bold', color: '#fff', marginBottom: 10 },
  permDesc: { fontSize: 14, color: '#888', textAlign: 'center', marginBottom: 20 },
  permBtn: { backgroundColor: '#00d4ff', paddingVertical: 12, paddingHorizontal: 30, borderRadius: 10, marginBottom: 10, width: '100%', alignItems: 'center' },
  permBtnText: { color: '#fff', fontSize: 16, fontWeight: 'bold' },
  cancelBtn: { backgroundColor: 'transparent', borderWidth: 1, borderColor: '#666' },
  cancelBtnText: { color: '#888', fontSize: 16, fontWeight: 'bold' },
  scanner: { flex: 1, width: '100%', backgroundColor: '#1a1a2e', paddingTop: Platform.OS === 'ios' ? 60 : 40 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 20, paddingBottom: 20 },
  title: { fontSize: 20, fontWeight: 'bold', color: '#fff' },
  closeBtn: { fontSize: 28, color: '#fff', fontWeight: '300' },
  cameraBox: { flex: 1, marginHorizontal: 20, borderRadius: 15, overflow: 'hidden', backgroundColor: '#000' },
  camera: { flex: 1 },
  frameOverlay: { ...StyleSheet.absoluteFillObject, justifyContent: 'center', alignItems: 'center' },
  scanFrame: { width: 250, height: 250, borderWidth: 2, borderColor: '#00d4ff', borderRadius: 15, backgroundColor: 'transparent' },
  desc: { fontSize: 14, color: '#888', textAlign: 'center', padding: 20 },
  controls: { flexDirection: 'row', justifyContent: 'center', gap: 15, padding: 20 },
  ctrlBtn: { backgroundColor: '#16213e', paddingVertical: 12, paddingHorizontal: 20, borderRadius: 10, borderWidth: 1, borderColor: '#00d4ff' },
  ctrlBtnText: { color: '#00d4ff', fontSize: 14, fontWeight: 'bold' },
  retryBtn: { borderColor: '#ff6b6b' },
});

export default QRScanner;
