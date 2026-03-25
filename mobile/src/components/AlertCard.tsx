import React, { useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Linking,
  Alert,
} from 'react-native';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { formatDistanceToNow } from 'date-fns';
import ReactNativeHapticFeedback from 'react-native-haptic-feedback';
import { SeverityBadge } from './SeverityBadge';
import type { FallAlert, EmergencyContact } from '../types';
import { acknowledgeAlert } from '../services/api';

interface Props {
  alert: FallAlert;
  primaryContact?: EmergencyContact;
  onAcknowledge?: (alertId: string) => void;
  onViewDetails?: (alertId: string) => void;
}

export function AlertCard({ alert, primaryContact, onAcknowledge, onViewDetails }: Props) {
  const timeAgo = formatDistanceToNow(new Date(alert.timestamp), { addSuffix: true });

  const handleCall = useCallback(() => {
    if (!primaryContact?.phone) {
      Alert.alert('No Contact', 'No emergency contact phone number available.');
      return;
    }
    ReactNativeHapticFeedback.trigger('notificationSuccess');
    const uri = `tel:${primaryContact.phone}`;
    Linking.canOpenURL(uri)
      .then((supported) => {
        if (supported) return Linking.openURL(uri);
        Alert.alert('Error', 'Unable to make calls from this device.');
      })
      .catch(() => Alert.alert('Error', 'Call failed.'));
  }, [primaryContact]);

  const handleAcknowledge = useCallback(async () => {
    try {
      await acknowledgeAlert(alert.id);
      onAcknowledge?.(alert.id);
    } catch {
      Alert.alert('Error', 'Could not acknowledge alert. Please try again.');
    }
  }, [alert.id, onAcknowledge]);

  const isCritical = alert.severity === 'critical' || alert.severity === 'high';

  return (
    <View
      style={[styles.card, isCritical && styles.cardCritical]}
      accessible
      accessibilityLabel={`Fall alert for ${alert.patientName}, ${alert.severity} severity, ${timeAgo}`}
    >
      {/* Header row */}
      <View style={styles.headerRow}>
        <View style={styles.headerLeft}>
          <Icon name="account-circle" size={20} color="#9ca3af" />
          <Text style={styles.patientName}>{alert.patientName}</Text>
        </View>
        <SeverityBadge severity={alert.severity} />
      </View>

      {/* Timestamp */}
      <View style={styles.metaRow}>
        <Icon name="clock-outline" size={14} color="#6b7280" />
        <Text style={styles.timestamp}>{timeAgo}</Text>
        <Text style={styles.timestampFull}>
          {'  ·  '}
          {new Date(alert.timestamp).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </Text>
      </View>

      {/* Location */}
      {alert.location && (
        <View style={styles.metaRow}>
          <Icon name="map-marker" size={14} color="#6b7280" />
          <Text style={styles.locationText}>
            {alert.location.latitude.toFixed(5)}, {alert.location.longitude.toFixed(5)}
          </Text>
        </View>
      )}

      {/* Actions */}
      <View style={styles.actionsRow}>
        {/* One-tap call to primary emergency contact */}
        <TouchableOpacity
          style={styles.callButton}
          onPress={handleCall}
          accessibilityLabel={`Call ${primaryContact?.name ?? 'emergency contact'}`}
          accessibilityRole="button"
        >
          <Icon name="phone" size={16} color="#fff" />
          <Text style={styles.callButtonText}>
            Call {primaryContact?.name ?? 'Contact'}
          </Text>
        </TouchableOpacity>

        {alert.status === 'active' && (
          <TouchableOpacity
            style={styles.ackButton}
            onPress={handleAcknowledge}
            accessibilityLabel="Acknowledge alert"
            accessibilityRole="button"
          >
            <Icon name="check" size={16} color="#22c55e" />
            <Text style={styles.ackButtonText}>Acknowledge</Text>
          </TouchableOpacity>
        )}

        <TouchableOpacity
          style={styles.detailButton}
          onPress={() => onViewDetails?.(alert.id)}
          accessibilityLabel="View alert details"
          accessibilityRole="button"
        >
          <Icon name="chevron-right" size={20} color="#6b7280" />
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#1f2937',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 3,
    borderLeftColor: '#374151',
  },
  cardCritical: {
    borderLeftColor: '#ef4444',
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  patientName: {
    color: '#f9fafb',
    fontSize: 16,
    fontWeight: '600',
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: 4,
  },
  timestamp: {
    color: '#9ca3af',
    fontSize: 13,
  },
  timestampFull: {
    color: '#6b7280',
    fontSize: 12,
  },
  locationText: {
    color: '#6b7280',
    fontSize: 12,
    fontFamily: 'monospace',
  },
  actionsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 12,
  },
  callButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#ef4444',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    gap: 6,
    flex: 1,
    justifyContent: 'center',
  },
  callButtonText: {
    color: '#fff',
    fontSize: 13,
    fontWeight: '600',
  },
  ackButton: {
    flexDirection: 'row',
    alignItems: 'center',
    borderColor: '#22c55e',
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    gap: 4,
  },
  ackButtonText: {
    color: '#22c55e',
    fontSize: 13,
    fontWeight: '500',
  },
  detailButton: {
    padding: 8,
  },
});
