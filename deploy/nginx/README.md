# RustChain Nginx Configuration

Production-ready reverse proxy with SSL, rate limiting, and security headers.

## Install
```bash
sudo cp deploy/nginx/rustchain.conf /etc/nginx/sites-available/rustchain
sudo ln -s /etc/nginx/sites-available/rustchain /etc/nginx/sites-enabled/
sudo certbot --nginx -d rustchain.example.com
sudo nginx -t && sudo systemctl reload nginx
```
