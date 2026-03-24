# GitHub App Setup Guide

This guide walks you through creating and configuring a GitHub App for the Comment Moderation Bot.

## Step 1: Create a New GitHub App

1. Navigate to **GitHub Settings** → **Developer settings** → **GitHub Apps**
2. Click **New GitHub App**

### Basic Information

| Field | Value |
|-------|-------|
| **Name** | `Comment Moderation Bot` (or your preferred name) |
| **Description** | `Automated moderation of spam and low-quality issue comments` |
| **Homepage URL** | `https://your-domain.com` (your service URL) |
| **Authorization callback URL** | (Leave blank - not needed for this bot) |
| **Setup URL** | (Leave blank) |
| **Request user authorization (OAuth)** | ❌ Unchecked |

## Step 2: Configure Webhook

### Webhook Settings

| Field | Value |
|-------|-------|
| **Webhook URL** | `https://your-domain.com/webhook` |
| **Webhook secret** | Generate a random secret (use `openssl rand -hex 32`) |

**Important**: Save the webhook secret! You'll need it for `GITHUB_APP_WEBHOOK_SECRET`.

### SSL Verification
- ✅ **Verify SSL** (keep enabled for production)

## Step 3: Set Permissions

Navigate to **Permissions & Webhooks** tab.

### Repository Permissions

Click **Change** next to Repository permissions:

| Permission | Access Level | Why |
|------------|--------------|-----|
| **Issues** | Read & Write | Read issue data, delete spam comments |
| **Metadata** | Read-only | Required baseline permission |

### Organization Permissions (Optional)

If moderating organization repositories:

| Permission | Access Level | Why |
|------------|--------------|-----|
| **Members** | Read-only | Check user org membership for whitelist |

### Account Permissions

| Permission | Access Level |
|------------|--------------|
| **Email addresses** | Read-only (optional) |

## Step 4: Subscribe to Events

Under **Subscribe to events**:

| Event | Subscribe |
|-------|-----------|
| **Issues** | ✅ Yes |
| **Issue comment** | ✅ Yes |

All other events can remain unchecked.

## Step 5: Generate Private Key

1. Scroll to **Private keys** section
2. Click **Generate a private key**
3. A `.pem` file will download automatically
4. **Store this file securely** - you'll need it for `GITHUB_APP_PRIVATE_KEY`

## Step 6: Install the App

1. Click **Install App** in the left sidebar
2. Choose where to install:
   - **Only on this account** - for personal repos
   - **Any account** - for broader installation
3. Select repositories:
   - **All repositories** - moderate all current and future repos
   - **Only select repositories** - choose specific repos
4. Click **Install**

### Note Your Installation ID

After installation, the URL will look like:
```
https://github.com/settings/installations/12345678
```
The number (`12345678`) is your **Installation ID**.

## Step 7: Gather Credentials

You'll need these values for your `.env` file:

| Config Variable | Where to Find |
|-----------------|---------------|
| `GITHUB_APP_APP_ID` | App settings page (top of page) |
| `GITHUB_APP_CLIENT_ID` | App settings → Client ID |
| `GITHUB_APP_CLIENT_SECRET` | App settings → Generate new secret |
| `GITHUB_APP_PRIVATE_KEY` | Downloaded .pem file |
| `GITHUB_APP_WEBHOOK_SECRET` | The secret you generated in Step 2 |

### Example .env Configuration

```ini
GITHUB_APP_APP_ID=123456
GITHUB_APP_CLIENT_ID=Iv1.abc123def456
GITHUB_APP_CLIENT_SECRET=your_client_secret_here
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
GITHUB_APP_WEBHOOK_SECRET=your_webhook_secret_here
GITHUB_APP_API_BASE_URL=https://api.github.com
```

## Step 8: Configure Webhook URL

### For Local Development

Use ngrok to expose your local server:

```bash
# Start your server
uvicorn src.webhook:app --reload --port 8000

# In another terminal
ngrok http 8000

# Copy the ngrok URL (e.g., https://abc123.ngrok.io)
```

Update your GitHub App:
1. Go to App settings
2. Edit **Webhook URL**: `https://abc123.ngrok.io/webhook`
3. Save changes

### For Production

Use your actual domain:
```
https://your-domain.com/webhook
```

## Step 9: Test the Integration

### Verify Webhook Connection

1. Go to App settings → **Advanced**
2. You should see recent ping events
3. Look for ✅ (200 OK) responses

### Test with a Comment

1. Create a test issue in an installed repository
2. Add a comment with spam-like content:
   ```
   Check out my crypto giveaway! Click here: bit.ly/spam
   @user1 @user2 @user3 @user4 @user5 @user6
   ```
3. Check your audit logs for the moderation decision

## Troubleshooting

### Webhook Not Receiving Events

1. **Check webhook URL**: Must end with `/webhook`
2. **Verify server is running**: Check `/health` endpoint
3. **Check firewall**: Port 8000 (or your port) must be accessible
4. **Review GitHub delivery logs**: App settings → Advanced → Recent deliveries

### Permission Errors

If you see 403 errors:
1. Go to App settings → Permissions
2. Ensure **Issues** is set to **Read & Write**
3. Re-install the app on repositories if permissions changed

### Signature Verification Failed

1. Verify `GITHUB_APP_WEBHOOK_SECRET` matches exactly
2. Check for extra whitespace or newlines
3. Regenerate the secret if needed

### App Not Installed on Repository

1. Go to App settings → Install App
2. Select the repository
3. Click Install

## Security Best Practices

1. **Rotate secrets regularly**: Update webhook secret and client secret periodically
2. **Secure private key**: Never commit to version control
3. **Use HTTPS**: Always use HTTPS for webhook URL
4. **Limit repository access**: Only install on necessary repositories
5. **Monitor audit logs**: Review moderation actions regularly

## Updating the App

To modify permissions or webhook settings:
1. Go to App settings
2. Make changes
3. Save changes
4. Some changes may require re-installation

## Removing the App

To uninstall:
1. Go to GitHub Settings → Applications
2. Find the app under **Installed GitHub Apps**
3. Click **Configure** → **Uninstall**
