/**
 * AlertDashboard — Screen 1
 * Real-time fall alerts with FCM push, severity badges, timestamps, one-tap call.
 * Polls active alerts every 10s as fallback; FCM push updates within 20s of event.
 */
import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  RefreshControl,
  ActivityIndicator,
  TouchableOpacity,
  Platform,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

import { AlertCard } from '../components/AlertCard';
import { getActiveAlerts, getEmergencyContacts } from '../services/api';
import { setForegroundAlertHandler } from '../services/notificationService';
import { useAppStore } from '../store/appStore';
import type { FallAlert, EmergencyContact } from '../types';
import { ALERT_POLL_INTERVAL_MS } from '../constants';

export default function AlertDashboard() {
  const { alerts, setAlerts, upsertAlert } = useAppStore((s) => ({
    alerts: s.alerts,
    setAlerts: s.setAlerts,
    upsertAlert: s.upsertAlert,
  }));

  const [primaryContacts, setPrimaryContacts] = useState<Record<string, EmergencyContact>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);

  // Load alerts from API
  const loadAlerts = useCallback(async (silent = false) => {
    if (!silent) setIsLoading(true);
    setError(null);
    try {
      const active = await getActiveAlerts();
      if (!mountedRef.current) return;
      setAlerts(active);

      // Prefetch primary emergency contacts for visible patients
      const patientIds = [...new Set(active.map((a) => a.patientId))];
      const contactsMap: Record<string, EmergencyContact> = {};
      await Promise.allSettled(
        patientIds.map(async (pid) => {
          const contacts = await getEmergencyContacts(pid);
          const primary = contacts.find((c) => c.isPrimary) ?? contacts[0];
          if (primary) contactsMap[pid] = primary;
        })
      );
      if (mountedRef.current) setPrimaryContacts(contactsMap);
    } catch (err: any) {
      if (mountedRef.current) setError(err?.message ?? 'Failed to load alerts');
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [setAlerts]);

  // FCM foreground push handler — immediately insert new alert
  useEffect(() => {
    const unsubscribe = setForegroundAlertHandler(async (payload) => {
      // Fetch the full alert object and insert at top
      try {
        const { getAlertById } = await import('../services/api');
        const fullAlert = await getAlertById(payload.alertId);
        upsertAlert(fullAlert);
      } catch {
        // Minimal alert from push payload
        upsertAlert({
          id: payload.alertId,
          deviceId: '',
          patientId: '',
          patientName: payload.patientName,
          severity: payload.severity as any,
          status: 'active',
          timestamp: payload.timestamp,
          location: { latitude: 0, longitude: 0, timestamp: Date.now() },
        });
      }
    });
    return unsubscribe;
  }, [upsertAlert]);

  // Poll as fallback
  useFocusEffect(
    useCallback(() => {
      mountedRef.current = true;
      loadAlerts();
      pollIntervalRef.current = setInterval(() => loadAlerts(true), ALERT_POLL_INTERVAL_MS);
      return () => {
        mountedRef.current = false;
        if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
      };
    }, [loadAlerts])
  );

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await loadAlerts(true);
    setIsRefreshing(false);
  }, [loadAlerts]);

  const activeAlerts = alerts.filter((a) => a.status === 'active');
  const otherAlerts = alerts.filter((a) => a.status !== 'active');

  const renderItem = ({ item }: { item: FallAlert }) => (
    <AlertCard
      alert={item}
      primaryContact={primaryContacts[item.patientId]}
      onAcknowledge={() => loadAlerts(true)}
    />
  );

  const renderHeader = () => (
    <View style={styles.listHeader}>
      {activeAlerts.length > 0 ? (
        <View style={styles.activeBanner}>
          <Icon name="alert-circle" size={18} color="#ef4444" />
          <Text style={styles.activeBannerText}>
            {activeAlerts.length} active alert{activeAlerts.length !== 1 ? 's' : ''} require attention
          </Text>
        </View>
      ) : (
        <View style={styles.clearBanner}>
          <Icon name="check-circle" size={18} color="#22c55e" />
          <Text style={styles.clearBannerText}>No active alerts</Text>
        </View>
      )}
      {otherAlerts.length > 0 && activeAlerts.length > 0 && (
        <Text style={styles.sectionLabel}>RECENT</Text>
      )}
    </View>
  );

  if (isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#ef4444" />
        <Text style={styles.loadingText}>Loading alerts…</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.centered}>
        <Icon name="alert-circle-outline" size={48} color="#ef4444" />
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.retryButton} onPress={() => loadAlerts()}>
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={alerts}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        ListHeaderComponent={renderHeader}
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Icon name="bell-off" size={48} color="#374151" />
            <Text style={styles.emptyText}>No alerts yet</Text>
          </View>
        }
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={handleRefresh}
            tintColor="#ef4444"
          />
        }
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#111827',
  },
  listContent: {
    padding: 16,
    paddingBottom: 32,
  },
  listHeader: {
    marginBottom: 16,
  },
  activeBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#7f1d1d22',
    borderColor: '#ef444444',
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    gap: 8,
    marginBottom: 16,
  },
  activeBannerText: {
    color: '#fca5a5',
    fontSize: 14,
    fontWeight: '500',
  },
  clearBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#14532d22',
    borderColor: '#22c55e44',
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    gap: 8,
    marginBottom: 16,
  },
  clearBannerText: {
    color: '#86efac',
    fontSize: 14,
    fontWeight: '500',
  },
  sectionLabel: {
    color: '#6b7280',
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 1,
    marginBottom: 8,
  },
  centered: {
    flex: 1,
    backgroundColor: '#111827',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  loadingText: {
    color: '#9ca3af',
    fontSize: 14,
  },
  errorText: {
    color: '#f87171',
    fontSize: 14,
    textAlign: 'center',
    paddingHorizontal: 32,
  },
  retryButton: {
    backgroundColor: '#1f2937',
    paddingHorizontal: 24,
    paddingVertical: 10,
    borderRadius: 8,
  },
  retryText: {
    color: '#ef4444',
    fontWeight: '600',
  },
  emptyState: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 80,
    gap: 12,
  },
  emptyText: {
    color: '#4b5563',
    fontSize: 16,
  },
});
