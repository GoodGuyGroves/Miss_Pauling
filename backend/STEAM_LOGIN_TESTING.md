# Testing Steam Login with ngrok

This guide explains how to test the "login with Steam" functionality in your local development environment using ngrok.

## Prerequisites

- ngrok installed (`brew install ngrok` or download from [ngrok.com](https://ngrok.com/download))
- claim a static domain from ngrok
- Steam API key (optional, but recommended for full user profile data)

## Setup Steps

### 1. Start the Backend Server

```bash
cd /Users/russellgroves/Documents/code/copilot-agent-test
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2. Start ngrok

Open a new terminal and run:

```bash
ngrok http --url=distinct-climbing-shrimp.ngrok-free.app 8000
```

This will display a URL that looks like: `https://distinct-climbing-shrimp.ngrok-free.app`

### 3. Update Configuration Files

#### Backend Configuration (app/config.json)

Replace `your-ngrok-url.ngrok-free.app` with your actual ngrok URL (without https://):

```json
{
    "realm": "https://your-actual-ngrok-url.ngrok-free.app",
    "return_to": "https://your-actual-ngrok-url.ngrok-free.app/auth/steam/callback",
    "is_using_ngrok": true
}
```

#### Frontend Configuration (frontend/.env)

```
VITE_API_URL=https://your-actual-ngrok-url.ngrok-free.app
VITE_USING_NGROK=true
```

### 4. Start the Frontend

```bash
cd frontend
npm run dev
```

### 5. Test the Login Flow

1. Open your frontend application (usually at http://localhost:5173)
2. Click the "Login with Steam" button
3. You should be redirected to Steam's login page
4. After logging in with Steam, you'll be redirected back through the ngrok URL to your frontend
5. The login should complete successfully, showing your Steam profile information

## Troubleshooting

- **Browser Warning**: The code has been updated to include the `ngrok-skip-browser-warning` header which bypasses the ngrok warning page.
- **CORS Issues**: The backend has CORS configured to allow requests from the frontend. If you encounter CORS errors, make sure the frontend's origin is included in the `allowed_origins` list in the backend config.
- **Steam API Key**: For full profile data (name, avatar), you'll need to set a valid Steam API key in the config.
- **Redirect URL Mismatch**: Double-check that all URLs in the config files match exactly what ngrok provides.

## Important Notes

- This setup is for development purposes only
- For production, you should use a proper domain name
- Never commit sensitive information like API keys to version control