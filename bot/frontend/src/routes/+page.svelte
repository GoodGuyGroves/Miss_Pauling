<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import {
		user,
		isAuthenticated,
		login,
		logout,
		requestAccountLinking,
		checkLinkedAccounts,
		isProviderLinked,
		unlinkAccount,
		checkAuth
	} from '$lib/stores/auth';

	let message = '';
	let loading = false;
	let error = '';
	let authChecking = true; 
	let linkingProvider: 'discord' | null = null;
	let unlinkingProvider: 'discord' | null = null;
	let unlinkError = '';

	// Function to fetch general hello world message
	async function fetchHelloWorld() {
		loading = true;
		error = '';
		try {
			const response = await fetch('http://localhost:8000/');
			if (!response.ok) throw new Error('API request failed');
			const data = await response.json();
			message = data.message;
		} catch (e) {
			error = 'Failed to fetch message. Is the API server running?';
			console.error(e);
		} finally {
			loading = false;
		}
	}

	// Handle login with Discord (only available login method)
	function handleLogin() {
		login('discord');
	}

	// Handle logout
	function handleLogout() {
		logout();
	}

	// Check authentication and fetch data when the component mounts
	onMount(async () => {
		if (browser) {
			// First check authentication status from localStorage
			await checkAuth();
			authChecking = false;
		}
		
		fetchHelloWorld();
	});
</script>

<div class="mx-auto max-w-md p-4">
	<h1 class="mb-8 text-center text-3xl font-bold">Miss Pauling</h1>

	{#if authChecking}
		<!-- Show loading spinner while checking authentication -->
		<div class="flex flex-col items-center justify-center py-8">
			<div class="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-500 border-r-transparent" role="status">
				<span class="sr-only">Loading...</span>
			</div>
			<p class="mt-2 text-gray-600">Checking authentication...</p>
		</div>
	{:else if !$isAuthenticated}
		<div class="mb-6 rounded-lg border border-gray-200 bg-gray-50 p-6">
			<h2 class="mb-4 text-2xl font-semibold text-center">Welcome!</h2>
			<p class="mb-6 text-center">Please sign in with Discord to access your profile</p>
			
			<div class="flex flex-col items-center">
				<button
					on:click={handleLogin}
					class="w-full rounded bg-indigo-600 px-4 py-3 font-semibold text-white hover:bg-indigo-700 flex items-center justify-center gap-2"
				>
					<!-- Discord logo SVG -->
					<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 16 16">
						<path d="M13.545 2.907a13.227 13.227 0 0 0-3.257-1.011.05.05 0 0 0-.052.025c-.141.25-.297.577-.406.833a12.19 12.19 0 0 0-3.658 0 8.258 8.258 0 0 0-.412-.833.051.051 0 0 0-.052-.025c-1.125.194-2.22.534-3.257 1.011a.041.041 0 0 0-.021.018C.356 6.024-.213 9.047.066 12.032c.001.014.01.028.021.037a13.276 13.276 0 0 0 3.995 2.02.05.05 0 0 0 .056-.019c.308-.42.582-.863.818-1.329a.05.05 0 0 0-.01-.059.051.051 0 0 0-.018-.011 8.875 8.875 0 0 1-1.248-.595.05.05 0 0 1-.02-.066.051.051 0 0 1 .015-.019c.084-.063.168-.129.248-.195a.05.05 0 0 1 .051-.007c2.619 1.196 5.454 1.196 8.041 0a.052.052 0 0 1 .053.007c.08.066.164.132.248.195a.051.051 0 0 1-.004.085 8.254 8.254 0 0 1-1.249.594.05.05 0 0 0-.03.03.052.052 0 0 0 .003.041c.24.465.515.909.817 1.329a.05.05 0 0 0 .056.019 13.235 13.235 0 0 0 4.001-2.02.049.049 0 0 0 .021-.037c.334-3.451-.559-6.449-2.366-9.106a.034.034 0 0 0-.02-.019Zm-8.198 7.307c-.789 0-1.438-.724-1.438-1.612 0-.889.637-1.613 1.438-1.613.807 0 1.45.73 1.438 1.613 0 .888-.637 1.612-1.438 1.612Zm5.316 0c-.788 0-1.438-.724-1.438-1.612 0-.889.637-1.613 1.438-1.613.807 0 1.451.73 1.438 1.613 0 .888-.631 1.612-1.438 1.612Z"/>
					</svg>
					Login with Discord
				</button>
			</div>

			<div class="mt-6 text-sm text-center text-gray-600">
				<p>Login to access your profile and manage your linked accounts</p>
			</div>
		</div>
	{:else}
		<div class="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
			<p class="text-xl mb-4">Welcome back, <span class="font-semibold">{$user?.name || 'User'}</span>!</p>
			<p class="mb-4">You are logged in.</p>
			<div class="flex justify-center gap-4">
				<a 
					href="/profile" 
					class="inline-block rounded bg-blue-500 px-4 py-2 font-semibold text-white hover:bg-blue-600"
				>
					View Profile
				</a>
				<button
					on:click={handleLogout}
					class="inline-block rounded bg-red-400 px-4 py-2 font-semibold text-white hover:bg-red-500"
				>
					Logout
				</button>
			</div>
		</div>
	{/if}

	{#if loading}
		<div class="my-4 text-center">Loading...</div>
	{:else if error}
		<div class="mb-4 rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700">
			{error}
		</div>
	{/if}
</div>
