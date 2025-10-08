/**
 * Steam ID utilities for converting between different Steam ID formats
 */

const STEAM_ID64_BASE = '76561197960265728'; // This is the base that is added to get a SteamID64

/**
 * Converts a SteamID64 to the original SteamID format (STEAM_0:X:YYYYY)
 * @param steamId64 The 64-bit Steam ID (e.g., 76561197960287930)
 * @returns The original Steam ID format (e.g., STEAM_0:0:11101)
 */
export function convertSteamID64ToSteamID(steamId64: string): string {
    try {
        // Convert to bigint to handle large numbers properly
        const id64 = BigInt(steamId64);
        const base = BigInt(STEAM_ID64_BASE);

        // Calculate the account ID by subtracting the base
        const accountId = id64 - base;

        // The universe is always 0 for public accounts
        const universe = 0;

        // The last bit determines if it's 0 or 1
        const authServer = Number(accountId % 2n);

        // The account number is the ID divided by 2
        const accountNumber = accountId / 2n;

        return `STEAM_${universe}:${authServer}:${accountNumber}`;
    } catch (error) {
        console.error('Error converting SteamID64 to SteamID:', error);
        return 'Invalid SteamID';
    }
}

/**
 * Converts a SteamID64 to the SteamID3 format [U:1:XXXXX]
 * @param steamId64 The 64-bit Steam ID (e.g., 76561197960287930)
 * @returns The SteamID3 format (e.g., [U:1:22202])
 */
export function convertSteamID64ToSteamID3(steamId64: string): string {
    try {
        // Convert to bigint to handle large numbers properly
        const id64 = BigInt(steamId64);
        const base = BigInt(STEAM_ID64_BASE);

        // Calculate the account ID by subtracting the base
        const accountId = id64 - base;

        // The format is [U:1:accountId]
        return `[U:1:${accountId}]`;
    } catch (error) {
        console.error('Error converting SteamID64 to SteamID3:', error);
        return 'Invalid SteamID';
    }
}

/**
 * Validates if a string is a valid SteamID64
 * @param steamId64 The 64-bit Steam ID to validate
 * @returns True if the ID is a valid SteamID64
 */
export function isValidSteamID64(steamId64: string): boolean {
    // SteamID64 should be a 17-digit number starting with 7656
    const steamId64Regex = /^7656\d{13}$/;
    return steamId64Regex.test(steamId64);
}