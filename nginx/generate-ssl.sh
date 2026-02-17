#!/bin/bash
# SSL certificate generation script for RustChain

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSL_DIR="$SCRIPT_DIR/ssl"

mkdir -p "$SSL_DIR"

echo "=== RustChain SSL Certificate Generator ==="
echo ""

# Check if domain is provided
if [ -z "$1" ]; then
    echo "Usage: $0 [self-signed|letsencrypt] [domain]"
    echo ""
    echo "Examples:"
    echo "  $0 self-signed                          # Generate self-signed certificate for testing"
    echo "  $0 letsencrypt rustchain.example.com    # Generate Let's Encrypt certificate for production"
    exit 1
fi

MODE="$1"
DOMAIN="${2:-localhost}"

if [ "$MODE" = "self-signed" ]; then
    echo "Generating self-signed SSL certificate for $DOMAIN..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$SSL_DIR/key.pem" \
        -out "$SSL_DIR/cert.pem" \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=$DOMAIN"

    echo ""
    echo "✅ Self-signed certificate generated successfully!"
    echo "   Certificate: $SSL_DIR/cert.pem"
    echo "   Private key: $SSL_DIR/key.pem"
    echo ""
    echo "⚠️  Note: Browsers will show a security warning for self-signed certificates."
    echo "   This is normal for development/testing environments."

elif [ "$MODE" = "letsencrypt" ]; then
    echo "Generating Let's Encrypt SSL certificate for $DOMAIN..."

    # Check if certbot is installed
    if ! command -v certbot &> /dev/null; then
        echo "❌ certbot is not installed. Installing..."
        apt-get update && apt-get install -y certbot
    fi

    # Check if domain is accessible
    echo "Verifying that $DOMAIN is accessible from this server..."
    if ! curl -fsS "http://$DOMAIN" > /dev/null 2>&1; then
        echo "❌ Domain $DOMAIN is not accessible via HTTP."
        echo "   Make sure your domain is pointing to this server's IP address."
        exit 1
    fi

    # Generate certificate using certbot
    certbot certonly --standalone \
        -d "$DOMAIN" \
        --email "${LETSENCRYPT_EMAIL:-admin@example.com}" \
        --agree-tos \
        --non-interactive \
        --keep-until-expiring

    # Copy certificates to SSL directory
    cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$SSL_DIR/cert.pem"
    cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$SSL_DIR/key.pem"

    echo ""
    echo "✅ Let's Encrypt certificate generated successfully!"
    echo "   Certificate: $SSL_DIR/cert.pem"
    echo "   Private key: $SSL_DIR/key.pem"
    echo ""
    echo "ℹ️  Note: Certificates will be automatically renewed by certbot."
    echo "   Check renewal status with: certbot renew --dry-run"

else
    echo "❌ Invalid mode: $MODE"
    echo "   Valid modes: self-signed, letsencrypt"
    exit 1
fi

echo ""
echo "🎉 SSL certificate setup complete!"
echo ""
echo "Next steps:"
echo "1. Update nginx.conf if you changed the domain"
echo "2. Restart nginx: docker-compose restart nginx"
echo "3. Access your site at: https://$DOMAIN"
