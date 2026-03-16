/**
 * App Navigator
 *
 * Stack navigator for the RustChain Wallet app.
 */

import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

import HomeScreen from '../screens/HomeScreen';
import CreateWalletScreen from '../screens/CreateWalletScreen';
import ImportWalletScreen from '../screens/ImportWalletScreen';
import WalletDetailScreen from '../screens/WalletDetailScreen';
import SendScreen from '../screens/SendScreen';
import ReceiveScreen from '../screens/ReceiveScreen';
import HistoryScreen from '../screens/HistoryScreen';
import SettingsScreen from '../screens/SettingsScreen';

export type RootStackParamList = {
  Home: undefined;
  CreateWallet: undefined;
  ImportWallet: undefined;
  WalletDetail: { walletName: string };
  Send: { walletName: string };
  Receive: { walletName: string; address: string };
  History: { walletName: string; address?: string };
  Settings: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();

const SCREEN_OPTIONS = {
  headerStyle: { backgroundColor: '#0a0a1a' },
  headerTintColor: '#00d4ff',
  headerTitleStyle: { fontWeight: 'bold' as const },
  contentStyle: { backgroundColor: '#0a0a1a' },
};

export default function AppNavigator(): React.JSX.Element {
  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={SCREEN_OPTIONS}>
        <Stack.Screen
          name="Home"
          component={HomeScreen}
          options={{ headerShown: false }}
        />
        <Stack.Screen
          name="CreateWallet"
          component={CreateWalletScreen}
          options={{ title: 'Create Wallet' }}
        />
        <Stack.Screen
          name="ImportWallet"
          component={ImportWalletScreen}
          options={{ title: 'Import Wallet' }}
        />
        <Stack.Screen
          name="WalletDetail"
          component={WalletDetailScreen}
          options={{ title: 'Wallet' }}
        />
        <Stack.Screen
          name="Send"
          component={SendScreen}
          options={{ title: 'Send RTC' }}
        />
        <Stack.Screen
          name="Receive"
          component={ReceiveScreen}
          options={{ title: 'Receive RTC' }}
        />
        <Stack.Screen
          name="History"
          component={HistoryScreen}
          options={{ title: 'Transaction History' }}
        />
        <Stack.Screen
          name="Settings"
          component={SettingsScreen}
          options={{ title: 'Settings' }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
