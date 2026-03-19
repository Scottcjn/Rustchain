// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import os

def generate_beacon_nginx_config():
    """Generate nginx configuration snippet for rustchain.org beacon routes"""
    
    nginx_config = """
# Beacon Atlas API proxy configuration for rustchain.org
# Routes /beacon/* to local port 8071 (beacon_chat.py server)

location /beacon/ {
    proxy_pass http://127.0.0.1:8071/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $server_name;
    
    # Handle CORS for beacon API
    proxy_set_header Access-Control-Allow-Origin *;
    proxy_set_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
    proxy_set_header Access-Control-Allow-Headers "Content-Type, Authorization";
    
    # Connection settings for beacon service
    proxy_connect_timeout 10s;
    proxy_send_timeout 30s;
    proxy_read_timeout 30s;
    
    # Buffer settings
    proxy_buffering on;
    proxy_buffer_size 4k;
    proxy_buffers 8 4k;
    
    # Error handling
    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;
    proxy_intercept_errors on;
}

# Specific route for beacon atlas endpoint
location /beacon/atlas {
    proxy_pass http://127.0.0.1:8071/atlas;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # Cache atlas data briefly
    proxy_cache_valid 200 30s;
    proxy_cache_bypass $http_pragma $http_authorization;
}

# Beacon join endpoint for agent registration
location /beacon/join {
    proxy_pass http://127.0.0.1:8071/api/join;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Content-Type application/json;
    
    # Allow POST requests
    if ($request_method = 'OPTIONS') {
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
        add_header Access-Control-Allow-Headers "Content-Type, Authorization";
        add_header Content-Length 0;
        add_header Content-Type text/plain;
        return 200;
    }
    
    # No caching for registration endpoint
    proxy_cache off;
}

# Error pages for beacon service
error_page 502 503 504 /beacon_error.html;
location = /beacon_error.html {
    internal;
    return 503 '{"error": "Beacon Atlas service temporarily unavailable", "status": 503}';
    add_header Content-Type application/json;
}
"""
    return nginx_config

def save_nginx_config(output_path="/tmp/beacon_nginx.conf"):
    """Save the nginx config to a file"""
    config_content = generate_beacon_nginx_config()
    
    try:
        with open(output_path, 'w') as f:
            f.write(config_content)
        print(f"Nginx config saved to: {output_path}")
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def print_config():
    """Print the nginx configuration to stdout"""
    config = generate_beacon_nginx_config()
    print("=== BEACON NGINX CONFIGURATION ===")
    print(config)
    print("\n=== INSTALLATION INSTRUCTIONS ===")
    print("1. Copy the above config to your nginx server block")
    print("2. Add it inside the 'server' block for rustchain.org")
    print("3. Reload nginx: sudo nginx -s reload")
    print("4. Test: curl https://rustchain.org/beacon/atlas")

if __name__ == "__main__":
    print_config()
    save_nginx_config()