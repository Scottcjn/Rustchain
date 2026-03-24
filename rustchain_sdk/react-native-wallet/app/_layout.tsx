/**
 * Root Layout
 * 
 * Main navigation layout for the RustChain Wallet app
 */

import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

export default function RootLayout() {
  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: {
            backgroundColor: '#1a1a2e',
          },
          headerTintColor: '#00d4ff',
          headerTitleStyle: {
            fontWeight: 'bold',
          },
          contentStyle: {
            backgroundColor: '#1a1a2e',
          },
        }}
      >
        <Stack.Screen 
          name="index" 
          options={{ 
            title: 'RustChain Wallet',
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="wallet/create" 
          options={{ 
            title: 'Create Wallet',
          }} 
        />
        <Stack.Screen 
          name="wallet/import" 
          options={{ 
            title: 'Import Wallet',
          }} 
        />
        <Stack.Screen 
          name="wallet/[name]" 
          options={{ 
            title: 'Wallet Details',
          }} 
        />
        <Stack.Screen 
          name="send" 
          options={{ 
            title: 'Send RTC',
          }} 
        />
        <Stack.Screen 
          name="history" 
          options={{ 
            title: 'Transaction History',
          }} 
        />
      </Stack>
    </>
  );
}
