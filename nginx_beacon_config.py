# SPDX-License-Identifier: MIT

import os
import sqlite3
from datetime import datetime

DB_PATH = '/root/beacon/beacon_atlas.db'

def generate_nginx_beacon_config():
    """Generate nginx configuration snippet for rustchain.org beacon routing"""

    config_template = """
# Beacon Atlas API proxy configuration for rustchain.org
# Routes /beacon/* to localhost:8071 for Atlas API

location /beacon/ {
    proxy_pass http://localhost:8071/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;

    # Timeout settings for beacon operations
    proxy_connect_timeout 10s;
    proxy_send_timeout 30s;
    proxy_read_timeout 30s;

    # Buffer settings for API responses
    proxy_buffering on;
    proxy_buffer_size 4k;
    proxy_buffers 8 4k;

    # Error handling
    proxy_intercept_errors off;
    proxy_next_upstream error timeout http_502 http_503 http_504;

    # CORS headers for beacon API
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range' always;
    add_header 'Access-Control-Expose-Headers' 'Content-Length,Content-Range' always;
}

# Handle preflight OPTIONS requests for beacon API
location /beacon {
    if ($request_method = 'OPTIONS') {
        add_header 'Access-Control-Allow-Origin' '*';
        add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS';
        add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range';
        add_header 'Access-Control-Max-Age' 1728000;
        add_header 'Content-Type' 'text/plain; charset=utf-8';
        add_header 'Content-Length' 0;
        return 204;
    }

    proxy_pass http://localhost:8071;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

# Specific route for atlas endpoint
location = /beacon/atlas {
    proxy_pass http://localhost:8071/atlas;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Cache atlas data briefly
    proxy_cache_valid 200 60s;
    proxy_cache_valid 404 10s;
}

# Specific route for join endpoint
location = /beacon/join {
    proxy_pass http://localhost:8071/api/join;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Content-Type $content_type;

    # No caching for join requests
    proxy_no_cache 1;
    proxy_cache_bypass 1;
}
"""

    return config_template.strip()

def check_beacon_service_status():
    """Check if beacon service is running on port 8071"""
    import subprocess
    try:
        result = subprocess.run(['netstat', '-tlnp'], capture_output=True, text=True)
        return ':8071' in result.stdout
    except:
        return False

def verify_atlas_db():
    """Verify beacon atlas database connectivity"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM relay_agents")
            agent_count = cursor.fetchone()[0]
            return agent_count
    except Exception as e:
        return f"DB Error: {e}"

def save_config_to_file(output_path='/tmp/nginx_beacon_config.conf'):
    """Save generated config to file"""
    config_content = generate_nginx_beacon_config()

    with open(output_path, 'w') as f:
        f.write(f"# Generated on {datetime.now().isoformat()}\n")
        f.write(f"# Beacon Atlas nginx proxy config for rustchain.org\n\n")
        f.write(config_content)

    return output_path

def print_deployment_instructions():
    """Print deployment instructions"""
    print("Nginx Beacon Configuration Generated")
    print("=" * 50)
    print()
    print("DEPLOYMENT STEPS:")
    print("1. Add the generated config to /etc/nginx/sites-available/rustchain.org")
    print("2. Test nginx config: sudo nginx -t")
    print("3. Reload nginx: sudo systemctl reload nginx")
    print("4. Verify beacon service is running on port 8071")
    print()
    print("VERIFICATION URLS:")
    print("- https://rustchain.org/beacon/atlas (should show agent list)")
    print("- POST https://rustchain.org/beacon/join (should accept registrations)")
    print()

    # Check current status
    service_status = check_beacon_service_status()
    agent_count = verify_atlas_db()

    print(f"Current Status:")
    print(f"- Beacon service (port 8071): {'Running' if service_status else 'Not detected'}")
    print(f"- Atlas DB agent count: {agent_count}")

if __name__ == '__main__':
    config_file = save_config_to_file()
    print(f"Config saved to: {config_file}")
    print()
    print(generate_nginx_beacon_config())
    print()
    print_deployment_instructions()
