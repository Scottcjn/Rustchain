import React, { useState } from 'react';
import { SafeAreaView, Text, TextInput, Pressable } from 'react-native';
import { sendRtc } from '../api/client';

export default function Send({ from }: { from: string }) {
  const [to, setTo] = useState('');
  const [amount, setAmount] = useState('');
  const [msg, setMsg] = useState('');

  async function submit() {
    try {
      const amt = Number(amount);
      if (!to || !Number.isFinite(amt) || amt <= 0) {
        setMsg('Invalid recipient/amount');
        return;
      }
      await sendRtc({ from, to, amount: amt });
      setMsg(`Sent ${amt} RTC to ${to}`);
    } catch (e:any) {
      setMsg(e?.message || 'send failed');
    }
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#111', padding: 14 }}>
      <Text style={{ color: '#fff', fontSize: 22, fontWeight: '700' }}>Send RTC</Text>
      <Text style={{ color: '#9aa', marginTop: 8 }}>From: {from}</Text>
      <TextInput value={to} onChangeText={setTo} placeholder='to wallet' placeholderTextColor='#777' style={{ color:'#fff', borderWidth:1, borderColor:'#333', padding:8, marginTop:10 }} />
      <TextInput value={amount} onChangeText={setAmount} placeholder='amount' placeholderTextColor='#777' keyboardType='decimal-pad' style={{ color:'#fff', borderWidth:1, borderColor:'#333', padding:8, marginTop:10 }} />
      <Pressable onPress={submit} style={{ backgroundColor:'#2d8cff', padding:10, borderRadius:8, marginTop:12 }}>
        <Text>Send</Text>
      </Pressable>
      {msg ? <Text style={{ color:'#cdd3df', marginTop:12 }}>{msg}</Text> : null}
      <Text style={{ color:'#9aa', marginTop:16 }}>Biometric confirmation hook: TODO (`expo-local-authentication`).</Text>
    </SafeAreaView>
  );
}
