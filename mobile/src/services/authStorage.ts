/**
 * Secure token storage using the iOS Keychain / Android Keystore via react-native-keychain.
 * Never uses AsyncStorage for credentials (HIPAA requirement).
 */
import * as Keychain from 'react-native-keychain';

const TOKEN_SERVICE = 'com.sagecare.caregiver.tokens';

export async function storeTokens(accessToken: string, refreshToken: string): Promise<void> {
  await Keychain.setGenericPassword(
    'tokens',
    JSON.stringify({ accessToken, refreshToken }),
    {
      service: TOKEN_SERVICE,
      accessible: Keychain.ACCESSIBLE.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
    }
  );
}

export async function getStoredTokens(): Promise<{
  accessToken: string | null;
  refreshToken: string | null;
}> {
  try {
    const credentials = await Keychain.getGenericPassword({ service: TOKEN_SERVICE });
    if (!credentials) return { accessToken: null, refreshToken: null };
    const parsed = JSON.parse(credentials.password);
    return { accessToken: parsed.accessToken, refreshToken: parsed.refreshToken };
  } catch {
    return { accessToken: null, refreshToken: null };
  }
}

export async function clearTokens(): Promise<void> {
  await Keychain.resetGenericPassword({ service: TOKEN_SERVICE });
}
