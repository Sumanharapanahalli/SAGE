import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { SEVERITY_COLORS, SEVERITY_LABELS } from '../constants';
import type { FallSeverity } from '../types';

interface Props {
  severity: FallSeverity;
  size?: 'sm' | 'md' | 'lg';
}

export function SeverityBadge({ severity, size = 'md' }: Props) {
  const color = SEVERITY_COLORS[severity] ?? '#6b7280';
  const label = SEVERITY_LABELS[severity] ?? severity;

  const textSize = size === 'sm' ? 10 : size === 'lg' ? 14 : 12;
  const paddingH = size === 'sm' ? 6 : size === 'lg' ? 12 : 8;
  const paddingV = size === 'sm' ? 2 : size === 'lg' ? 6 : 4;

  return (
    <View
      style={[
        styles.badge,
        {
          backgroundColor: `${color}22`,
          borderColor: color,
          paddingHorizontal: paddingH,
          paddingVertical: paddingV,
        },
      ]}
    >
      <Text style={[styles.text, { color, fontSize: textSize }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    borderRadius: 999,
    borderWidth: 1,
    alignSelf: 'flex-start',
  },
  text: {
    fontWeight: '600',
    letterSpacing: 0.5,
  },
});
