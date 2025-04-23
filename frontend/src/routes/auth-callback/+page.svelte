<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { verifyToken, authToken } from '$lib/stores/auth';

	let message = 'Verifying your authentication...';
	let error = false;
	let linkError: any = null;
	let isForceLoading = false;
	
	// Function to directly force-link a Steam account without re-authentication
	async function handleForceLinkClick() {
		let steamId = null;
		
		// Try to get the Steam ID from the error object - it might be in different formats
		if (linkError) {
			if (linkError.steam_id) {
				steamId = linkError.steam_id;
			} else if (linkError.auth_id) {
				steamId = linkError.auth_id;
			} else {
				// Try to extract Steam ID from the error message using regex
				const steamIdRegex = /\b\d{17,}\b/; // Steam IDs are typically 17-digit numbers
				let match;
				
				if (linkError.message && (match = linkError.message.match(steamIdRegex))) {
					steamId = match[0];
				} else if (linkError.detail && (match = linkError.detail.match(steamIdRegex))) {
					steamId = match[0];
				}
			}
		}
		
		if (!steamId) {
			message = 'Could not determine the Steam ID to link';
			error = true;
			return;
		}
		
		isForceLoading = true;
		message = 'Force linking your Steam account...';
		
		try {
			// Use the stored auth token and Steam ID to force link directly
			const token = localStorage.getItem('auth_token');
			if (!token) {
				message = 'Authentication token not found';
				error = true;
				return;
			}
			
			const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
			const IS_USING_NGROK = import.meta.env.VITE_USING_NGROK === 'true' || API_URL.includes('ngrok');
			
			const headers = {
				'Content-Type': 'application/json'
			};
			
			// Add ngrok header to bypass the browser warning if needed
			if (IS_USING_NGROK) {
				headers['ngrok-skip-browser-warning'] = 'true';
			}
			
			console.log('Sending force-link request with Steam ID:', steamId);
			const response = await fetch(`${API_URL}/auth/force-link-steam`, {
				method: 'POST',
				headers,
				body: JSON.stringify({
					token,
					steam_id: steamId
				})
			});
			
			if (!response.ok) {
				const errorData = await response.text();
				throw new Error(`Force link failed: ${errorData}`);
			}
			
			const userData = await response.json();
			message = 'Account successfully linked! Redirecting...';
			console.log('Force link successful, user data:', userData);
			
			// Redirect to home page after a short delay
			setTimeout(() => {
				goto('/');
			}, 1500);
			
		} catch (e) {
			console.error('Error force linking account:', e);
			message = `Error linking account: ${e.message}`;
			error = true;
		} finally {
			isForceLoading = false;
		}
	}

	onMount(async () => {
		try {
			// Get the token or error from URL
			const url = new URL(window.location.href);
			const token = url.searchParams.get('token');
			const errorParam = url.searchParams.get('error');

			// Check if there's an error parameter (like for Steam account linking)
			if (errorParam) {
				try {
					linkError = JSON.parse(decodeURIComponent(errorParam));
					message = linkError.message || 'Error during account linking';
					error = true;
					return;
				} catch (e) {
					console.error('Failed to parse error parameter:', e);
				}
			}

			if (!token) {
				message = 'Authentication failed: No token received';
				error = true;
				return;
			}

			// Verify the token with our backend
			const success = await verifyToken(token);

			if (success) {
				message = 'Authentication successful! Redirecting...';
				// Redirect to home page after a short delay
				setTimeout(() => {
					goto('/');
				}, 1500);
			} else {
				message = 'Authentication failed: Invalid token';
				error = true;
			}
		} catch (e) {
			console.error('Error during authentication:', e);
			message = 'Authentication error occurred';
			error = true;
		}
	});
</script>

<div class="flex min-h-screen items-center justify-center bg-gray-100">
	<div class="w-full max-w-md rounded-lg bg-white p-8 shadow-lg">
		<div class="text-center">
			{#if error}
				{#if linkError && (linkError.error_code === "steam_account_already_linked" || 
              (linkError.message && linkError.message.includes("already linked to a different user")) ||
              (linkError.detail && linkError.detail.includes("already linked to a different user")))}
					<div class="mb-4 text-2xl font-bold text-amber-600">Steam Account Already Linked</div>
					<p class="text-gray-600 mb-4">{linkError.message}</p>
					<div class="flex flex-col space-y-3">
						<button
							on:click={handleForceLinkClick}
							class="rounded bg-amber-500 px-4 py-2 font-bold text-white hover:bg-amber-600 disabled:opacity-50"
							disabled={isForceLoading}
						>
							{#if isForceLoading}
								<span class="inline-flex items-center">
									<svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
										<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
										<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
									</svg>
									Linking...
								</span>
							{:else}
								Force Link Steam Account
							{/if}
						</button>
						<p class="text-xs text-gray-500 italic mt-1">
							This will unlink this Steam account from the other user and link it to your current account.
						</p>
						<a
							href="/"
							class="rounded bg-blue-500 px-4 py-2 font-bold text-white hover:bg-blue-600"
						>
							Return to Home
						</a>
					</div>
				{:else}
					<div class="mb-4 text-2xl font-bold text-red-600">Authentication Failed</div>
					<p class="text-gray-600">{message}</p>
					<a
						href="/"
						class="mt-4 inline-block rounded bg-blue-500 px-4 py-2 font-bold text-white hover:bg-blue-600"
					>
						Return to Home
					</a>
				{/if}
			{:else}
				<div class="mb-4 text-2xl font-bold text-blue-600">Authentication Processing</div>
				<p class="text-gray-600">{message}</p>
				<div class="mt-4 flex justify-center">
					<div
						class="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"
					></div>
				</div>
			{/if}
		</div>
	</div>
</div>
