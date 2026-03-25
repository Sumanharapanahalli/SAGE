import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

import AlertDashboard from '../screens/AlertDashboard';
import LiveMapScreen from '../screens/LiveMapScreen';
import DeviceStatusScreen from '../screens/DeviceStatusScreen';
import EmergencyContactsScreen from '../screens/EmergencyContactsScreen';
import AlertHistoryScreen from '../screens/AlertHistoryScreen';
import DevicePairingScreen from '../screens/DevicePairingScreen';
import SettingsScreen from '../screens/SettingsScreen';
import LockScreen from '../screens/LockScreen';

import type { RootStackParamList, MainTabParamList } from '../types';
import { useAppStore } from '../store/appStore';
import { SEVERITY_COLORS } from '../constants';

const Stack = createStackNavigator<RootStackParamList>();
const Tab = createBottomTabNavigator<MainTabParamList>();

function MainTabs() {
  const alertCount = useAppStore((s) => s.alerts.filter((a) => a.status === 'active').length);

  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ color, size }) => {
          const icons: Record<string, string> = {
            AlertDashboard: 'bell-alert',
            LiveMap: 'map-marker-radius',
            DeviceStatus: 'devices',
            EmergencyContacts: 'account-group',
            AlertHistory: 'history',
            Settings: 'cog',
          };
          return <Icon name={icons[route.name] ?? 'circle'} size={size} color={color} />;
        },
        tabBarActiveTintColor: SEVERITY_COLORS.critical,
        tabBarInactiveTintColor: '#6b7280',
        tabBarStyle: { backgroundColor: '#111827', borderTopColor: '#1f2937' },
        tabBarLabelStyle: { fontSize: 10 },
        headerStyle: { backgroundColor: '#111827' },
        headerTintColor: '#f9fafb',
      })}
    >
      <Tab.Screen
        name="AlertDashboard"
        component={AlertDashboard}
        options={{
          title: 'Alerts',
          tabBarBadge: alertCount > 0 ? alertCount : undefined,
          tabBarBadgeStyle: { backgroundColor: SEVERITY_COLORS.critical },
        }}
      />
      <Tab.Screen
        name="LiveMap"
        component={LiveMapScreen}
        options={{ title: 'Live Map' }}
      />
      <Tab.Screen
        name="DeviceStatus"
        component={DeviceStatusScreen}
        options={{ title: 'Device' }}
      />
      <Tab.Screen
        name="EmergencyContacts"
        component={EmergencyContactsScreen}
        options={{ title: 'Contacts' }}
      />
      <Tab.Screen
        name="AlertHistory"
        component={AlertHistoryScreen}
        options={{ title: 'History' }}
      />
      <Tab.Screen
        name="Settings"
        component={SettingsScreen}
        options={{ title: 'Settings' }}
      />
    </Tab.Navigator>
  );
}

export default function AppNavigator() {
  const isLocked = useAppStore((s) => s.auth.isLocked);
  const isAuthenticated = useAppStore((s) => s.auth.isAuthenticated);

  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        {!isAuthenticated ? (
          <Stack.Screen name="Auth" component={LockScreen} />
        ) : isLocked ? (
          <Stack.Screen name="LockScreen" component={LockScreen} />
        ) : (
          <>
            <Stack.Screen name="MainTabs" component={MainTabs} />
            <Stack.Screen
              name="DevicePairing"
              component={DevicePairingScreen}
              options={{ headerShown: true, title: 'Pair Device', presentation: 'modal' }}
            />
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}
