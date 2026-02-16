# Docker Deployment (RustChain Node + Nginx TLS)

This setup provides:
- RustChain node container
- Nginx reverse proxy with HTTPS
- Persistent SQLite volume
- Health checks + auto-restart

## 1) Prepare environment

```bash
cp .env.example .env
# set RC_ADMIN_KEY to a random 64-hex key
openssl rand -hex 32
```

Edit `.env` and paste the generated key:

```env
RC_ADMIN_KEY=<your-64-hex>
RUSTCHAIN_DOMAIN=localhost
RUSTCHAIN_DB_PATH=/data/rustchain_v2.db
```

## 2) Start (single command)

```bash
docker compose up -d
```

## 3) Verify services

```bash
docker compose ps
curl -s http://localhost/health
curl -sk https://localhost/health
curl -sk https://localhost/epoch
```

## 4) Data persistence

SQLite DB persists in Docker volume `rustchain_data` at:
- container path: `/data/rustchain_v2.db`

TLS cert persists in volume `rustchain_tls`.

## 5) Restart / logs

```bash
docker compose restart
docker compose logs -f rustchain
docker compose logs -f nginx
```

## 6) Stop

```bash
docker compose down
```

## Notes

- If no cert exists, Nginx auto-generates a self-signed TLS certificate.
- For production, replace certs in `rustchain_tls` with real certificates.
