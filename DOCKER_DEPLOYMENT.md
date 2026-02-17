# Docker Deployment for RustChain

This directory contains Docker configuration files for easy deployment of RustChain node with nginx proxy and SSL support.

## Quick Start

### 1. Clone and Configure

```bash
# Clone the repository
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# Copy environment file
cp .env.example .env

# Edit .env with your configuration
nano .env
```

### 2. Generate SSL Certificates

**For development/testing (self-signed):**
```bash
cd nginx
./generate-ssl.sh self-signed
```

**For production (Let's Encrypt):**
```bash
cd nginx
./generate-ssl.sh letsencrypt yourdomain.com
```

Make sure your domain is pointing to the server's IP address before running the Let's Encrypt command.

### 3. Start the Stack

```bash
# Build and start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f rustchain-node
docker-compose logs -f nginx
```

### 4. Access the Services

- **RustChain API**: https://your-domain.com/api/stats
- **Light Client**: https://your-domain.com/light
- **Museum**: https://your-domain.com/museum
- **Health Check**: https://your-domain.com/health

## Architecture

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Nginx     │ (SSL, Proxy, Load Balancing)
│  :443:80   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ RustChain   │ (Flask App)
│   Node      │ :8099
└─────────────┘
       │
       ▼
┌─────────────┐
│  SQLite     │ (Persistent Volume)
│  Database   │
└─────────────┘
```

## Configuration

### Environment Variables (.env)

Key configuration options:

```bash
# Database
RUSTCHAIN_DB_PATH=/app/data/rustchain_v2.db

# Server
PORT=8099
HOST=0.0.0.0

# SSL
DOMAIN=yourdomain.com
LETSENCRYPT_EMAIL=admin@yourdomain.com

# Gunicorn
GUNICORN_WORKERS=2
GUNICORN_TIMEOUT=120
```

### Nginx Configuration

The nginx configuration in `nginx/nginx.conf` includes:

- SSL/TLS termination
- HTTP to HTTPS redirect
- Reverse proxy to RustChain node
- Gzip compression
- Security headers
- Health checks
- Caching for static assets

## Data Persistence

All data is persisted in Docker volumes:

- `./data` - SQLite database
- `./nginx/ssl` - SSL certificates
- `./nginx/logs` - Nginx logs

## Health Checks

Both services include health checks:

```bash
# Check RustChain node health
curl http://localhost:8099/api/stats

# Check nginx health
curl https://localhost/health
```

## Logs

View logs for each service:

```bash
# RustChain node logs
docker-compose logs -f rustchain-node

# Nginx logs
docker-compose logs -f nginx
docker-compose logs -f nginx | grep error

# Access logs
tail -f nginx/logs/access.log

# Error logs
tail -f nginx/logs/error.log
```

## Management Commands

### Start, Stop, Restart

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Restart specific service
docker-compose restart rustchain-node

# Rebuild and restart
docker-compose up -d --build
```

### Update Code

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose up -d --build
```

### Database Backup

```bash
# Backup database
docker exec rustchain-node cp /app/data/rustchain_v2.db /tmp/backup_$(date +%Y%m%d).db
docker cp rustchain-node:/tmp/backup_$(date +%Y%m%d).db ./backups/

# Restore database
docker cp ./backups/backup_20240217.db rustchain-node:/app/data/rustchain_v2.db
docker-compose restart rustchain-node
```

## Troubleshooting

### Port Already in Use

If port 8099 or 80/443 is already in use:

```bash
# Find what's using the port
sudo lsof -i :8099
sudo lsof -i :80
sudo lsof -i :443

# Change ports in .env or docker-compose.yml
```

### SSL Certificate Issues

```bash
# Regenerate self-signed certificate
cd nginx
./generate-ssl.sh self-signed

# Renew Let's Encrypt certificate
sudo certbot renew

# Check certificate expiry
openssl x509 -in nginx/ssl/cert.pem -noout -dates
```

### Database Locked

```bash
# Stop the service
docker-compose stop rustchain-node

# Check for lock files
ls -la data/*.db-*

# Remove lock files (be careful!)
rm data/*.db-*

# Restart the service
docker-compose start rustchain-node
```

### Service Not Starting

```bash
# Check logs
docker-compose logs rustchain-node

# Inspect the container
docker-compose ps
docker inspect rustchain-node

# Enter container for debugging
docker-compose exec rustchain-node bash
```

## Production Checklist

Before deploying to production:

- [ ] Use Let's Encrypt SSL certificates
- [ ] Set strong `PRIVACY_PEPPER` in .env
- [ ] Configure `ADMIN_KEY` if needed
- [ ] Enable nginx authentication for `/metrics` endpoint
- [ ] Set up firewall rules (allow only 80, 443, SSH)
- [ ] Configure automatic backups
- [ ] Set up monitoring and alerting
- [ ] Review and adjust resource limits in docker-compose.yml
- [ ] Test the full deployment on a staging server first

## Security Considerations

1. **SSL/TLS**: Always use HTTPS in production
2. **Environment Variables**: Never commit .env files
3. **Database Backups**: Regular automated backups
4. **Firewall**: Restrict access to necessary ports only
5. **Updates**: Keep Docker images and dependencies updated
6. **Monitoring**: Set up alerts for service failures

## Performance Tuning

### Gunicorn Workers

Adjust worker count based on CPU cores:

```bash
# In .env or docker-compose.yml
GUNICORN_WORKERS=$(nproc)
```

### Nginx Caching

Adjust cache times in `nginx/nginx.conf`:

```nginx
proxy_cache_valid 200 60s;  # Cache for 60 seconds
```

### Database Optimization

For high-traffic deployments, consider migrating to PostgreSQL or MySQL.

## Support

For issues and questions:
- GitHub: https://github.com/Scottcjn/Rustchain/issues
- Documentation: https://docs.rustchain.org
- Community: [Discord/Telegram links]

## License

Same as RustChain project.
