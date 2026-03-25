import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Image,
} from 'react-native';
import { authenticateUser, isBiometricAvailable, getBiometricType } from '../services/hipaaService';
import { useAppStore } from '../store/appStore';

export default function LockScreen() {
  const [biometricType, setBiometricType] = useState('Biometric');
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [biometricAvailable, setBiometricAvailable] = useState(false);
  const setLocked = useAppStore((s) => s.setLocked);

  useEffect(() => {
    (async () => {
      const available = await isBiometricAvailable();
      setBiometricAvailable(available);
      if (available) {
        const type = await getBiometricType();
        setBiometricType(type);
        // Auto-prompt on load
        handleUnlock();
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleUnlock = async () => {
    if (isAuthenticating) return;
    setIsAuthenticating(true);
    setError(null);
    try {
      const success = await authenticateUser('Unlock SAGE Caregiver');
      if (success) {
        setLocked(false);
      } else {
        setError('Authentication failed. Please try again.');
      }
    } catch (err: any) {
      setError(err?.message ?? 'Authentication error');
    } finally {
      setIsAuthenticating(false);
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.logoContainer}>
        <Text style={styles.logo}>🔒</Text>
        <Text style={styles.appName}>SAGE Caregiver</Text>
        <Text style={styles.subtitle}>Tap to unlock</Text>
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <TouchableOpacity
        style={[styles.unlockButton, isAuthenticating && styles.unlockButtonDisabled]}
        onPress={handleUnlock}
        disabled={isAuthenticating}
        accessibilityLabel={`Unlock with ${biometricType}`}
        accessibilityRole="button"
      >
        {isAuthenticating ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.unlockButtonText}>
            {biometricAvailable ? `Unlock with ${biometricType}` : 'Unlock'}
          </Text>
        )}
      </TouchableOpacity>

      <Text style={styles.hipaaNotice}>
        Protected health information — HIPAA compliant
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f172a',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  logoContainer: {
    alignItems: 'center',
    marginBottom: 48,
  },
  logo: {
    fontSize: 64,
    marginBottom: 16,
  },
  appName: {
    fontSize: 28,
    fontWeight: '700',
    color: '#f9fafb',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: '#9ca3af',
  },
  error: {
    color: '#ef4444',
    fontSize: 14,
    marginBottom: 16,
    textAlign: 'center',
  },
  unlockButton: {
    backgroundColor: '#ef4444',
    paddingVertical: 16,
    paddingHorizontal: 48,
    borderRadius: 12,
    marginBottom: 32,
    minWidth: 220,
    alignItems: 'center',
  },
  unlockButtonDisabled: {
    opacity: 0.6,
  },
  unlockButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  hipaaNotice: {
    position: 'absolute',
    bottom: 32,
    color: '#4b5563',
    fontSize: 12,
    textAlign: 'center',
  },
});
