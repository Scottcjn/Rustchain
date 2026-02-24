import React, { useEffect, useState } from 'react';
import { SafeAreaView, Text, ScrollView } from 'react-native';
import { txHistory } from '../api/client';

export default function History({ minerId }: { minerId: string }) {
  const [rows, setRows] = useState<any[]>([]);
  const [err, setErr] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const data = await txHistory(minerId);
        setRows(data.history || data.items || []);
      } catch (e:any) {
        setErr(e?.message || 'history load failed');
      }
    })();
  }, [minerId]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#111', padding: 12 }}>
      <Text style={{ color: '#fff', fontSize: 20, fontWeight: '700' }}>Transaction History</Text>
      {err ? <Text style={{ color: '#ff7a7a', marginTop: 8 }}>{err}</Text> : null}
      <ScrollView style={{ marginTop: 10 }}>
        {rows.map((r, i) => (
          <Text key={i} style={{ color: '#cdd3df', marginBottom: 8 }}>
            {(r.ts || r.created_at || '')} | {(r.type || 'tx')} | {(r.amount_rtc || r.amount || 0)} RTC
          </Text>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}
