import { writable, get } from 'svelte/store';
import type { Writable } from 'svelte/store';

export interface AuthProvider {
    provider: 'steam' | 'discord';
    provider_id: string;
    linked: boolean;
}

export interface UserInfo {
    id?: number;
    steam_id?: string;
    steam_id64?: string;
    steam_id3?: string;
    steam_profile_url?: string;
    discord_id?: string;
    name?: string;
    avatar?: string;
    auth_providers: AuthProvider[];
}

// API configuration
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const IS_USING_NGROK = import.meta.env.VITE_USING_NGROK === 'true' || API_URL.includes('ngrok');

export const user: Writable<UserInfo | null> = writable(null);
export const isAuthenticated = writable(false);
export const authToken: Writable<string | null> = writable(null);

// Function to get default headers for API requests
const getHeaders = (): HeadersInit => {
    const headers: HeadersInit = {
        'Content-Type': 'application/json'
    };

    // Add ngrok header to bypass the browser warning
    if (IS_USING_NGROK) {
        headers['ngrok-skip-browser-warning'] = 'true';
    }

    return headers;
};

// Function to handle login with a specific provider
export const login = (provider: 'steam' | 'discord' = 'discord') => {
    // Redirect to backend authentication endpoint
    window.location.href = `${API_URL}/auth/${provider}/login`;
};

// Function to handle logout
export const logout = async () => {
    const token = localStorage.getItem('auth_token');
    if (token) {
        try {
            await fetch(`${API_URL}/auth/logout`, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify({ token })
            });
        } catch (error) {
            console.error('Error logging out:', error);
        }
    }

    user.set(null);
    isAuthenticated.set(false);
    authToken.set(null);
    localStorage.removeItem('auth_token');

    // Use direct window navigation instead of goto for more reliable redirect
    console.log('Redirecting to home page after logout...');
    window.location.href = '/';
};

// Function to verify token with the backend
export const verifyToken = async (token: string): Promise<boolean> => {
    try {
        console.log(`Verifying token: ${token.substring(0, 10)}...`);
        const response = await fetch(
            `${API_URL}/auth/verify-token?token=${encodeURIComponent(token)}`,
            { headers: getHeaders() }
        );

        if (response.ok) {
            const userData = await response.json();
            user.set(userData);
            isAuthenticated.set(true);
            authToken.set(token);
            localStorage.setItem('auth_token', token);
            return true;
        } else {
            // Better error handling - log the specific error
            const errorText = await response.text();
            console.error(`Token verification failed (${response.status}):`, errorText);

            // Clear invalid token
            localStorage.removeItem('auth_token');
            return false;
        }
    } catch (error) {
        console.error('Error verifying token:', error);
        // Clear invalid token on error
        localStorage.removeItem('auth_token');
        return false;
    }
};

// Function to check if user has a saved token and verify it
export const checkAuth = async (): Promise<boolean> => {
    const token = localStorage.getItem('auth_token');
    if (token) {
        authToken.set(token);
        return await verifyToken(token);
    }
    return false;
};

// Function to request account linking
export const requestAccountLinking = async (provider: 'steam' | 'discord'): Promise<string | null> => {
    const token = get(authToken);
    if (!token) {
        console.error('Cannot link account: No authentication token available');
        return null;
    }

    const url = `${API_URL}/auth/link/request`;
    const requestBody = { token, provider };

    console.log(`Making link account request to: ${url}`);
    console.log('Request body:', requestBody);
    console.log('Headers:', getHeaders());

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify(requestBody)
        });

        console.log(`Response status: ${response.status}`);

        if (response.ok) {
            const data = await response.json();
            console.log('Response data:', data);
            return data.message; // Contains the URL to redirect to
        } else {
            // Try to get error details
            let errorText;
            try {
                errorText = await response.text();
            } catch (error) {
                errorText = `Could not read error response: ${error instanceof Error ? error.message : String(error)}`;
            }
            console.error(`Error response (${response.status}):`, errorText);
        }
        return null;
    } catch (error) {
        console.error('Error requesting account linking:', error);
        return null;
    }
};

// Function to check the status of linked accounts
export const checkLinkedAccounts = async (): Promise<void> => {
    const token = get(authToken);
    if (!token) {
        console.warn('Cannot check linked accounts: No authentication token available');
        return;
    }

    try {
        const response = await fetch(
            `${API_URL}/auth/link/status?token=${encodeURIComponent(token)}`,
            { headers: getHeaders() }
        );

        if (response.ok) {
            const userData = await response.json();
            user.set(userData);
        }
    } catch (error) {
        console.error('Error checking linked accounts:', error);
    }
};

// Check if a specific provider is linked
export const isProviderLinked = (provider: 'steam' | 'discord'): boolean => {
    const currentUser = get(user);
    if (!currentUser) {
        // User not logged in or data not available yet
        return false;
    }

    const providerInfo = currentUser.auth_providers?.find((p: AuthProvider) => p.provider === provider);
    return !!providerInfo?.linked;
};

// Function to unlink an authentication provider
export const unlinkAccount = async (provider: 'steam' | 'discord'): Promise<boolean> => {
    const token = get(authToken);
    if (!token) {
        console.error('Cannot unlink account: No authentication token available');
        return false;
    }

    const url = `${API_URL}/auth/unlink`;
    const requestBody = { token, provider };

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify(requestBody)
        });

        if (response.ok) {
            const userData = await response.json();

            // Debug output to check the response
            console.log('Unlink response:', userData);

            // Check if we need to logout (either by explicit flag or by checking auth providers)
            const shouldLogout = userData.requires_logout ||
                (userData.auth_providers && userData.auth_providers.length === 0) ||
                (!userData.steam_id && !userData.discord_id);

            if (shouldLogout) {
                console.log('Account unlinking requires logout (no auth methods left), performing forced logout...');

                try {
                    // Notify backend about logout
                    await fetch(`${API_URL}/auth/logout`, {
                        method: 'POST',
                        headers: getHeaders(),
                        body: JSON.stringify({ token })
                    });
                    console.log("Backend logout successful");
                } catch (error) {
                    console.error('Error during logout API call:', error);
                } finally {
                    // Force a complete logout by clearing everything
                    console.log('Forcing complete logout');

                    // Clear all auth state
                    user.set(null);
                    isAuthenticated.set(false);
                    authToken.set(null);

                    // Remove from storage
                    localStorage.removeItem('auth_token');

                    // Force a hard redirect to the home page
                    console.log('Redirecting to home...');
                    window.location.replace('/');

                    // Return immediately without doing anything else
                    return true;
                }
            }

            // If no logout required, update the user data with the new state
            user.set(userData);
            return true;
        }

        // Extract the specific error message from the response
        const errorText = await response.text();
        let errorMessage = `Error unlinking ${provider} account`;

        try {
            // Try to parse the error as JSON
            const errorJson = JSON.parse(errorText);
            if (errorJson && errorJson.detail) {
                errorMessage = errorJson.detail;
            }
        } catch (_) {
            // If not valid JSON, use the raw text if available
            if (errorText) {
                errorMessage = errorText;
            }
        }

        console.error(`Error unlinking account (${response.status}):`, errorMessage);
        throw new Error(errorMessage);
    } catch (error) {
        console.error('Error unlinking account:', error);
        throw error;
    }
};

// Function to sync Steam data from Steam API
export const syncSteamData = async (): Promise<boolean> => {
    const token = get(authToken);
    if (!token) {
        console.error('Cannot sync Steam data: No authentication token available');
        return false;
    }

    try {
        const response = await fetch(`${API_URL}/auth/sync-steam`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({ token })
        });

        if (response.ok) {
            const userData = await response.json();
            // Update the user store with the fresh data
            user.set(userData);
            return true;
        } else {
            // Try to get error details
            let errorMessage = 'Failed to sync Steam data';
            try {
                const errorData = await response.json();
                if (errorData.detail) {
                    errorMessage = errorData.detail;
                }
            } catch (error) {
                console.error('Error parsing sync error response:', error);
            }
            console.error(`Error syncing Steam data (${response.status}):`, errorMessage);
            throw new Error(errorMessage);
        }
    } catch (error) {
        console.error('Error syncing Steam data:', error);
        throw error;
    }
};