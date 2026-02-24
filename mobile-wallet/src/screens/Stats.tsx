import React, { useEffect, useState } from 'react';
import { SafeAreaView, Text } from 'react-native';

export default function Stats() {
  const [activeMiners, setActiveMiners] = useState<number>(0);
  const [epochPot, setEpochPot] = useState<number>(0);

  useEffect(() => {
    (async () => {
      try {
        const em = await fetch('https://50.28.86.131/epoch');
        if (em.ok) {
          const e = await em.json();
          setEpochPot(Number(e.pot || e.reward_pool || 0));
        }
      } catch {}
      try {
        const mm = await fetch('https://50.28.86.131/api/miners');
        if (mm.ok) {
          const m = await mm.json();
          const arr = Array.isArray(m) ? m : (m.miners || m.items || []);
          setActiveMiners(arr.length);
        }
      } catch {}
    })();
  }, []);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#111', padding: 14 }}>
      <Text style={{ color: '#fff', fontSize: 22, fontWeight: '700' }}>Network Stats / Price</Text>
      <Text style={{ color: '#cdd3df', marginTop: 12 }}>RTC reference: $0.10</Text>
      <Text style={{ color: '#cdd3df', marginTop: 8 }}>Active miners: {activeMiners}</Text>
      <Text style={{ color: '#cdd3df', marginTop: 8 }}>Epoch pot: {epochPot.toFixed(2)} RTC</Text>
    </SafeAreaView>
  );
}
