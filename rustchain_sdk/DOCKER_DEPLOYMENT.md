# RustChain Docker Deployment Guide

Complete Docker setup for RustChain node with nginx reverse proxy and optional SSL.

## Quick Start

### Single Command Deployment

On a fresh Ubuntu 22.04 VPS:

```bash
# Clone the repository
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# Start all services
docker-compose up -d
```

That's it! RustChain will be available at:
- **HTTP**: http://your-server-ip (via nginx)
- **Direct**: http://your-server-ip:8099 (bypass nginx)

## What Gets Deployed

### Services

1. **rustchain-node** (Python Flask application)
   - Dashboard on port 8099
   - SQLite database with persistent storage
   - Automatic health checks and restarts

2. **nginx** (Reverse proxy)
   - HTTP on port 80
   - HTTPS on port 443 (when SSL enabled)
   - Load balancing and SSL termination

### Persistent Data

All data is stored in Docker volumes:
- `rustchain-data`: SQLite database (`rustchain_v2.db`)
- `rustchain-downloads`: Downloaded files

Data persists across container restarts and updates.

## Configuration

### Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` to customize:
- Port mappings
- SSL settings
- Resource limits
- Logging levels

### Example `.env`:

```env
RUSTCHAIN_DASHBOARD_PORT=8099
NGINX_HTTP_PORT=80
NGINX_HTTPS_PORT=443
ENABLE_SSL=false
LOG_LEVEL=INFO
```

## SSL Setup (Optional)

### Using Self-Signed Certificates

Generate certificates:

```bash
mkdir -p ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/key.pem -out ssl/cert.pem \
  -subj "/CN=rustchain.local"
```

### Using Let's Encrypt

```bash
# Install certbot
sudo apt-get install certbot

# Get certificate
sudo certbot certonly --standalone -d your-domain.com

# Copy certificates
mkdir -p ssl
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ssl/key.pem
sudo chown $USER:$USER ssl/*.pem
```

Enable SSL in `docker-compose.yml`:

```yaml
services:
  nginx:
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./ssl/cert.pem:/etc/nginx/ssl/cert.pem:ro
      - ./ssl/key.pem:/etc/nginx/ssl/key.pem:ro
```

Update `.env`:

```env
ENABLE_SSL=true
```

Restart:

```bash
docker-compose restart nginx
```

## Management Commands

### Start Services

```bash
docker-compose up -d
```

### Stop Services

```bash
docker-compose down
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f rustchain-node
docker-compose logs -f nginx
```

### Restart Services

```bash
# All services
docker-compose restart

# Specific service
docker-compose restart rustchain-node
```

### Update to Latest Version

```bash
git pull origin main
docker-compose build --no-cache
docker-compose up -d
```

### Check Service Health

```bash
# Check running containers
docker-compose ps

# Check node health
curl http://localhost:8099/health

# Check via nginx
curl http://localhost/health
```

## Database Management

### Backup Database

```bash
# Create backup directory
mkdir -p backups

# Backup database
docker cp rustchain-node:/rustchain/data/rustchain_v2.db \
  backups/rustchain_v2_$(date +%Y%m%d_%H%M%S).db
```

### Restore Database

```bash
# Stop services
docker-compose down

# Restore database
docker volume create rustchain-data
docker run --rm -v rustchain-data:/data -v $(pwd)/backups:/backup \
  alpine sh -c "cp /backup/rustchain_v2_YYYYMMDD_HHMMSS.db /data/rustchain_v2.db"

# Start services
docker-compose up -d
```

### Access Database

```bash
docker exec -it rustchain-node sqlite3 /rustchain/data/rustchain_v2.db
```

## Troubleshooting

### Service Won't Start

Check logs:
```bash
docker-compose logs rustchain-node
```

Check if port is already in use:
```bash
sudo netstat -tulpn | grep :8099
sudo netstat -tulpn | grep :80
```

### Database Locked

Stop all containers and restart:
```bash
docker-compose down
docker-compose up -d
```

### Permission Issues

Fix volume permissions:
```bash
docker-compose down
docker volume rm rustchain-data rustchain-downloads
docker-compose up -d
```

### Container Keeps Restarting

Check health status:
```bash
docker inspect rustchain-node | grep -A 10 Health
```

View full logs:
```bash
docker logs rustchain-node --tail 100
```

## System Requirements

### Minimum Requirements

- **OS**: Ubuntu 22.04 LTS (or any Linux with Docker)
- **RAM**: 512 MB
- **Disk**: 2 GB free space
- **CPU**: 1 core

### Recommended Requirements

- **OS**: Ubuntu 22.04 LTS
- **RAM**: 1 GB
- **Disk**: 10 GB free space
- **CPU**: 2 cores

### Required Software

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose (if not included)
sudo apt-get install docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER
```

Log out and log back in for group changes to take effect.

## Firewall Configuration

### UFW (Ubuntu)

```bash
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 8099/tcp  # Direct dashboard access (optional)
sudo ufw enable
```

### iptables

```bash
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables-save | sudo tee /etc/iptables/rules.v4
```

## Production Deployment Checklist

- [ ] Set custom `.env` configuration
- [ ] Enable SSL with valid certificates
- [ ] Configure firewall rules
- [ ] Set up automated backups
- [ ] Configure log rotation
- [ ] Enable Docker auto-start: `sudo systemctl enable docker`
- [ ] Test health checks: `curl http://localhost/health`
- [ ] Monitor logs for errors
- [ ] Set up monitoring (optional: Prometheus, Grafana)

## Security Best Practices

1. **Always use SSL in production**
   - Use Let's Encrypt for free certificates
   - Never expose unencrypted HTTP on public internet

2. **Regular Backups**
   - Automate database backups daily
   - Store backups off-site

3. **Keep Updated**
   - Run `git pull && docker-compose build --no-cache` weekly
   - Monitor security advisories

4. **Resource Limits**
   - Set memory and CPU limits in docker-compose.yml
   - Monitor resource usage

5. **Network Security**
   - Use UFW or iptables to restrict access
   - Only expose necessary ports
   - Consider using a VPN or SSH tunnel for admin access

## Support

- **GitHub Issues**: https://github.com/Scottcjn/Rustchain/issues
- **Documentation**: https://github.com/Scottcjn/Rustchain
- **Community**: Check the main README for community links

## License

MIT License - See LICENSE file for details
