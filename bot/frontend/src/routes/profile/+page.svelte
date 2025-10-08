<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import {
		user,
		isAuthenticated,
		requestAccountLinking,
		checkLinkedAccounts,
		unlinkAccount,
		syncSteamData,
		checkAuth
	} from '$lib/stores/auth';

	let linkingProvider: 'steam' | 'discord' | null = null;
	let unlinkingProvider: 'steam' | 'discord' | null = null;
	let syncingSteam = false; // New state to track sync operation
	let unlinkError = '';
	let syncMessage = ''; // New state to show sync result message
	let authChecked = false;
	let showSteamDetails = false; // Toggle for showing/hiding additional Steam details
	let copiedField: string | null = null; // Track which field was copied

	// Handle linking account with specific provider
	async function handleLinkAccount(provider: 'steam' | 'discord') {
		linkingProvider = provider;
		const linkUrl = await requestAccountLinking(provider);
		if (linkUrl) {
			window.location.href = linkUrl;
		} else {
			unlinkError = `Failed to initiate account linking with ${provider}`;
			linkingProvider = null;
		}
	}

	// Handle unlinking account with specific provider
	async function handleUnlinkAccount(provider: 'steam' | 'discord') {
		unlinkingProvider = provider;
		unlinkError = '';

		try {
			// Check if this is the only linked provider
			const currentUser = $user;
			if (currentUser) {
				const linkedProviders = currentUser.auth_providers.filter((p) => p.linked);
				if (linkedProviders.length === 1 && linkedProviders[0].provider === provider) {
					if (
						!confirm(
							'This is your only linked account. Unlinking it will log you out completely. Continue?'
						)
					) {
						unlinkingProvider = null;
						return;
						// If user confirms, the unlinkAccount function will automatically log them out
						// when they unlink their only authentication method
					}
				}
			}

			try {
				await unlinkAccount(provider);
				// If we get here and haven't been redirected due to logout,
				// it means the unlinking was successful but didn't require logout
			} catch (error: unknown) {
				// Get the specific error message from the backend
				unlinkError =
					error instanceof Error ? error.message : `Failed to unlink ${provider} account`;
			}
		} catch (e: unknown) {
			console.error('Error unlinking account:', e);
			unlinkError = `Error unlinking account: ${e instanceof Error ? e.message : 'Unknown error'}`;
		} finally {
			unlinkingProvider = null;
		}
	}

	// Handle syncing Steam data
	async function handleSyncSteam() {
		syncingSteam = true;
		syncMessage = '';
		unlinkError = ''; // Clear any previous errors

		try {
			await syncSteamData();
			syncMessage = 'Steam data synced successfully!';
			// Message will disappear after 3 seconds
			setTimeout(() => {
				syncMessage = '';
			}, 3000);
		} catch (error: unknown) {
			unlinkError = error instanceof Error ? error.message : 'Failed to sync Steam data';
		} finally {
			syncingSteam = false;
		}
	}

	// Copy text to clipboard function
	function copyToClipboard(text: string, field: string) {
		if (!browser) return;

		navigator.clipboard.writeText(text).then(
			() => {
				// Success - show feedback
				copiedField = field;
				// Reset after 2 seconds
				setTimeout(() => {
					copiedField = null;
				}, 2000);
			},
			(err) => {
				console.error('Could not copy text: ', err);
			}
		);
	}

	// Check authentication on mount and properly handle auth state
	onMount(async () => {
		// First check local storage for token and verify with backend
		if (browser) {
			const isLoggedIn = await checkAuth();
			authChecked = true;

			// Only redirect if definitely not authenticated after checking
			if (!isLoggedIn) {
				goto('/');
				return;
			}

			// If authenticated, fetch linked accounts info
			await checkLinkedAccounts();
		}
	});

	// Get provider link status
	$: steamLinked =
		$user &&
		'steam_id64' in $user &&
		$user.steam_id64 !== undefined &&
		$user.steam_id64 !== null &&
		$user.steam_id64 !== '';

	$: discordLinked =
		$user &&
		'discord_id' in $user &&
		$user.discord_id !== undefined &&
		$user.discord_id !== null &&
		$user.discord_id !== '';

	// Only redirect if authentication is definitely false AND we've already checked storage
	$: if ($isAuthenticated === false && authChecked && browser) {
		goto('/');
	}
</script>

{#if $isAuthenticated || !browser || !authChecked}
	<div class="mx-auto max-w-md p-4">
		{#if !$isAuthenticated && browser && !authChecked}
			<div class="py-8 text-center">
				<div
					class="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-current border-r-transparent"
					role="status"
				>
					<span class="sr-only">Loading...</span>
				</div>
				<p class="mt-2 text-gray-600">Checking authentication...</p>
			</div>
		{:else}
			<h1 class="mb-8 text-center text-3xl font-bold">User Profile</h1>

			<div class="mb-6 rounded-lg border border-green-200 bg-green-50 p-4">
				<div class="mb-4 flex items-center justify-center">
					<div class="text-center">
						{#if $user?.avatar}
							<img
								src={$user.avatar}
								alt="User Avatar"
								class="mx-auto mb-2 h-20 w-20 rounded-full"
							/>
						{/if}
						<span class="block text-xl font-semibold">{$user?.name ?? 'User'}</span>
					</div>
				</div>

				{#if unlinkError}
					<div class="mb-3 rounded border border-red-400 bg-red-100 px-3 py-2 text-sm text-red-700">
						{unlinkError}
					</div>
				{/if}

				{#if syncMessage}
					<div
						class="mb-3 rounded border border-green-400 bg-green-100 px-3 py-2 text-sm text-green-700"
					>
						{syncMessage}
					</div>
				{/if}

				<div class="space-y-4">
					<h3 class="font-semibold">Linked Accounts:</h3>

					<div class="flex items-center justify-between">
						<span>
							<span class="font-medium">Discord:</span>
							{#if discordLinked}
								<span class="text-green-600">✓ Linked</span>
								<span class="block text-xs text-gray-600">ID: {$user?.discord_id}</span>
							{:else}
								<span class="text-red-600">✗ Not Linked</span>
							{/if}
						</span>
						{#if !discordLinked}
							<button
								on:click={() => handleLinkAccount('discord')}
								class="rounded bg-indigo-500 px-3 py-1 text-sm text-white hover:bg-indigo-600"
								disabled={linkingProvider === 'discord'}
							>
								{linkingProvider === 'discord' ? 'Linking...' : 'Link Discord Account'}
							</button>
						{:else}
							<div class="text-xs text-gray-600">
								<span class="font-medium text-indigo-600">Primary Account</span>
								<span class="block italic">(Cannot be unlinked)</span>
							</div>
						{/if}
					</div>

					<div class="flex items-center justify-between">
						<span>
							<span class="font-medium">Steam:</span>
							{#if steamLinked}
								<span class="text-green-600">✓ Linked</span>
								<span class="block text-xs text-gray-600">ID: {$user?.steam_id64}</span>
								<button
									on:click={() => (showSteamDetails = !showSteamDetails)}
									class="mt-1 text-xs text-blue-600 hover:underline"
								>
									{showSteamDetails ? 'Hide details' : 'Show details'}
								</button>

								{#if showSteamDetails}
									<div class="mt-2 rounded border border-gray-200 bg-gray-50 p-2 text-xs">
										{#if $user?.steam_profile_url}
											<div class="mb-1 flex items-center justify-between">
												<div>
													<strong>Steam Profile:</strong>
													<a
														href={$user?.steam_profile_url}
														target="_blank"
														rel="noopener noreferrer"
														class="text-blue-600 hover:underline"
													>
														View Profile
													</a>
												</div>
											</div>
										{/if}
										<div class="mb-1 flex items-center justify-between">
											<div><strong>Steam ID64:</strong> {$user?.steam_id64}</div>
											<button
												on:click={() => copyToClipboard($user?.steam_id64 || '', 'steam_id64')}
												class="ml-2 rounded bg-gray-200 px-1.5 py-0.5 text-xs hover:bg-gray-300"
												title="Copy to clipboard"
											>
												{#if copiedField === 'steam_id64'}
													✓
												{:else}
													Copy
												{/if}
											</button>
										</div>

										{#if $user?.steam_id}
											<div class="mb-1 flex items-center justify-between">
												<div><strong>Steam ID:</strong> {$user?.steam_id}</div>
												<button
													on:click={() => copyToClipboard($user?.steam_id || '', 'steam_id')}
													class="ml-2 rounded bg-gray-200 px-1.5 py-0.5 text-xs hover:bg-gray-300"
													title="Copy to clipboard"
												>
													{#if copiedField === 'steam_id'}
														✓
													{:else}
														Copy
													{/if}
												</button>
											</div>
										{/if}

										{#if $user?.steam_id3}
											<div class="mb-1 flex items-center justify-between">
												<div><strong>Steam ID3:</strong> {$user?.steam_id3}</div>
												<button
													on:click={() => copyToClipboard($user?.steam_id3 || '', 'steam_id3')}
													class="ml-2 rounded bg-gray-200 px-1.5 py-0.5 text-xs hover:bg-gray-300"
													title="Copy to clipboard"
												>
													{#if copiedField === 'steam_id3'}
														✓
													{:else}
														Copy
													{/if}
												</button>
											</div>
										{/if}
									</div>
								{/if}
							{:else}
								<span class="text-red-600">✗ Not Linked</span>
							{/if}
						</span>
						<div class="flex space-x-2">
							{#if !steamLinked}
								<button
									on:click={() => handleLinkAccount('steam')}
									class="rounded bg-indigo-500 px-3 py-1 text-sm text-white hover:bg-indigo-600"
									disabled={linkingProvider === 'steam'}
								>
									{linkingProvider === 'steam' ? 'Linking...' : 'Link Steam Account'}
								</button>
							{:else}
								<button
									on:click={handleSyncSteam}
									class="rounded bg-blue-400 px-2 py-1 text-sm text-white hover:bg-blue-500"
									disabled={syncingSteam}
								>
									{#if syncingSteam}
										<span class="flex items-center">
											<svg class="mr-1 h-3 w-3 animate-spin" viewBox="0 0 24 24">
												<circle
													class="opacity-25"
													cx="12"
													cy="12"
													r="10"
													stroke="currentColor"
													stroke-width="4"
													fill="none"
												></circle>
												<path
													class="opacity-75"
													fill="currentColor"
													d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
												></path>
											</svg>
											Syncing
										</span>
									{:else}
										Sync
									{/if}
								</button>
								<button
									on:click={() => handleUnlinkAccount('steam')}
									class="rounded bg-red-400 px-2 py-1 text-sm text-white hover:bg-red-500"
									disabled={unlinkingProvider === 'steam'}
								>
									{unlinkingProvider === 'steam' ? 'Unlinking...' : 'Unlink'}
								</button>
							{/if}
						</div>
					</div>
				</div>
			</div>

			<div class="mt-4 text-center">
				<button
					on:click={() => {
						if (browser) window.location.href = '/';
					}}
					class="text-blue-600 hover:underline"
				>
					Back to Home
				</button>
			</div>
		{/if}
	</div>
{/if}
