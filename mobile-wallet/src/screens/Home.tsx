import React, {useEffect, useState} from 'react';
import History from './History';
import Send from './Send';
import Security from './Security';
import Receive from './Receive';
import Stats from './Stats';
import Onboarding from './Onboarding';
import BiometricGate from './BiometricGate';
import QrScanner from './QrScanner';
import { getSession, saveSession } from '../store/session';
import {SafeAreaView, Text, TextInput, Pressable} from 'react-native';
import {createMnemonic, deriveEd25519FromMnemonic} from '../crypto/wallet';

export default function Home() {
  const [mnemonic, setMnemonic] = useState('');
  const [pub, setPub] = useState('');
  const [minerId, setMinerId] = useState('');
  const [showHistory, setShowHistory] = useState(false);
  const [showSend, setShowSend] = useState(false);
  const [showSecurity, setShowSecurity] = useState(false);
  const [showReceive, setShowReceive] = useState(false);
  const [showStats, setShowStats] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [showBiometric, setShowBiometric] = useState(false);
  const [showQrScanner, setShowQrScanner] = useState(false);

  useEffect(() => {
    const s = getSession();
    if (s?.minerId) setMinerId(s.minerId);
  }, []);

  if (showHistory && minerId) return <History minerId={minerId} />;
  if (showSend && minerId) return <Send from={minerId} />;
  if (showSecurity) return <Security />;
  if (showReceive) return <Receive minerId={minerId} />;
  if (showStats) return <Stats />;
  if (showOnboarding) return <Onboarding />;
  if (showBiometric) return <BiometricGate />;
  if (showQrScanner) return <QrScanner />;

  return <SafeAreaView style={{flex:1,padding:16,backgroundColor:'#111'}}>
    <Text style={{color:'#fff',fontSize:24,fontWeight:'700'}}>RustChain Wallet</Text>
    <Pressable onPress={async()=>{const m=await createMnemonic(); setMnemonic(m); const k=await deriveEd25519FromMnemonic(m); setPub(k.publicKeyHex);}} style={{backgroundColor:'#2d8cff',padding:10,borderRadius:8,marginTop:12}}>
      <Text>Generate Wallet</Text>
    </Pressable>
    <TextInput value={mnemonic} onChangeText={setMnemonic} multiline style={{color:'#fff',marginTop:12,borderWidth:1,borderColor:'#333',padding:8}} />
    <Text style={{color:'#9aa',marginTop:8}}>Public key: {pub.slice(0,32)}...</Text>
    <TextInput value={minerId} onChangeText={setMinerId} placeholder='miner_id for history' placeholderTextColor='#777' style={{color:'#fff',marginTop:10,borderWidth:1,borderColor:'#333',padding:8}} />
    <Pressable onPress={async () => { await saveSession({ minerId }); }} style={{backgroundColor:'#444',padding:10,borderRadius:8,marginTop:10}}><Text>Save Session</Text></Pressable>
    <Pressable onPress={() => setShowHistory(true)} style={{backgroundColor:'#2d8cff',padding:10,borderRadius:8,marginTop:10}}><Text>Open History</Text></Pressable>
    <Pressable onPress={() => setShowSend(true)} style={{backgroundColor:'#31c46d',padding:10,borderRadius:8,marginTop:10}}><Text>Send RTC</Text></Pressable>
    <Pressable onPress={() => setShowSecurity(true)} style={{backgroundColor:'#7a5cff',padding:10,borderRadius:8,marginTop:10}}><Text>Security / QR</Text></Pressable>
    <Pressable onPress={() => setShowReceive(true)} style={{backgroundColor:'#f0b429',padding:10,borderRadius:8,marginTop:10}}><Text>Receive RTC</Text></Pressable>
    <Pressable onPress={() => setShowStats(true)} style={{backgroundColor:'#1fa2ff',padding:10,borderRadius:8,marginTop:10}}><Text>Price / Stats</Text></Pressable>
    <Pressable onPress={() => setShowOnboarding(true)} style={{backgroundColor:'#ff6b6b',padding:10,borderRadius:8,marginTop:10}}><Text>Onboarding</Text></Pressable>
    <Pressable onPress={() => setShowBiometric(true)} style={{backgroundColor:'#4f8a10',padding:10,borderRadius:8,marginTop:10}}><Text>Biometric Gate</Text></Pressable>
    <Pressable onPress={() => setShowQrScanner(true)} style={{backgroundColor:'#8e44ad',padding:10,borderRadius:8,marginTop:10}}><Text>QR Scanner</Text></Pressable>
    <Text style={{color:'#9aa',marginTop:16}}>QR Scan hook: TODO (expo-camera / barcode-scanner)</Text>
    <Text style={{color:'#9aa',marginTop:4}}>Biometric hook: TODO (expo-local-authentication)</Text>
  </SafeAreaView>
}
