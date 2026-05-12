import urllib.parse
import re

def validate_cert_id(cert_id: str) -> bool:
    """Ensure cert_id only contains alphanumeric characters and hyphens."""
    return bool(re.match(r'^BCOS-[a-zA-Z0-9-]+$', cert_id))

def generate_badge_html(repo_name, tier, trust_score, cert_id):
    """
    Generates embed HTML for a BCOS badge.
    Fix: Validate and URL-encode the cert_id to prevent injection.
    """
    if not validate_cert_id(cert_id):
        raise ValueError(f"Invalid certificate ID: {cert_id}")
    
    encoded_id = urllib.parse.quote(cert_id)
    badge_url = f"https://bcos.trust/badge/{encoded_id}"
    
    return f'<a href="{badge_url}"><img src="https://img.shields.io/badge/BCOS-{tier}-{trust_score}" alt="BCOS Badge"></a>'
