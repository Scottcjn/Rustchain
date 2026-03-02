#!/usr/bin/env python3
"""
Hall of Fame Machine Detail API Endpoint
Bounty #505 - 50 RTC

GET /api/hall_of_fame/machine?id=<fingerprint_hash>
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List


def get_machine_details(fingerprint_hash: str, db_connection) -> Optional[Dict]:
    """
    Retrieve full machine details from hall_of_rust table.
    
    Args:
        fingerprint_hash: Machine fingerprint hash
        db_connection: Database connection
        
    Returns:
        Machine details dict or None if not found
    """
    query = """
        SELECT 
            fingerprint_hash,
            miner_id,
            device_family,
            device_arch,
            device_model,
            manufacture_year,
            rust_score,
            total_attestations,
            nickname,
            is_deceased,
            capacitor_plague,
            thermal_events,
            first_attestation,
            last_attestation
        FROM hall_of_rust
        WHERE fingerprint_hash = %s
    """
    
    try:
        cursor = db_connection.cursor()
        cursor.execute(query, (fingerprint_hash,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        # Calculate age
        manufacture_year = row[5]
        age_years = datetime.now().year - manufacture_year if manufacture_year else None
        
        # Get attestation timeline (last 30 days)
        timeline = get_attestation_timeline(fingerprint_hash, db_connection)
        
        return {
            "fingerprint_hash": row[0],
            "miner_id": row[1],
            "device_family": row[2],
            "device_arch": row[3],
            "device_model": row[4],
            "manufacture_year": manufacture_year,
            "age_years": age_years,
            "rust_score": float(row[6]) if row[6] else 0.0,
            "total_attestations": row[7],
            "nickname": row[8],
            "is_deceased": row[9],
            "capacitor_plague": row[10],
            "thermal_events": row[11],
            "first_attestation": row[12].isoformat() if row[12] else None,
            "last_attestation": row[13].isoformat() if row[13] else None,
            "attestation_timeline": timeline,
            "badge": get_rust_badge(row[6]),
            "ascii_silhouette": get_ascii_silhouette(row[2], row[3])
        }
    except Exception as e:
        print(f"Error fetching machine details: {e}")
        return None


def get_attestation_timeline(fingerprint_hash: str, db_connection, days: int = 30) -> List[Dict]:
    """Get attestation timeline for last N days."""
    query = """
        SELECT 
            DATE(attestation_time) as date,
            COUNT(*) as count
        FROM attestations
        WHERE fingerprint_hash = %s
          AND attestation_time >= NOW() - INTERVAL '%s days'
        GROUP BY DATE(attestation_time)
        ORDER BY date DESC
    """
    
    try:
        cursor = db_connection.cursor()
        cursor.execute(query, (fingerprint_hash, days))
        
        timeline = []
        for row in cursor.fetchall():
            timeline.append({
                "date": row[0].isoformat(),
                "attestations": row[1]
            })
        return timeline
    except Exception as e:
        print(f"Error fetching timeline: {e}")
        return []


def get_rust_badge(rust_score: float) -> Dict:
    """Get rust badge details based on score."""
    if rust_score >= 500:
        return {"tier": "Legendary", "color": "#FFD700", "icon": "👑"}
    elif rust_score >= 400:
        return {"tier": "Epic", "color": "#9370DB", "icon": "💎"}
    elif rust_score >= 300:
        return {"tier": "Rare", "color": "#4169E1", "icon": "🔷"}
    elif rust_score >= 200:
        return {"tier": "Uncommon", "color": "#32CD32", "icon": "🔹"}
    else:
        return {"tier": "Common", "color": "#C0C0C0", "icon": "⚙️"}


def get_ascii_silhouette(device_family: str, device_arch: str) -> str:
    """Get ASCII art silhouette based on device type."""
    silhouettes = {
        "vintage_powerpc": """
    _____
   /     \\
  |  o o  |
  |   <   |
  |  \_/  |
   \\_____/
   |_____|
        """,
        "vintage_x86": """
   +-------+
   |       |
   | [===] |
   |       |
   +-------+
   |_______|
        """,
        "apple_silicon": """
     __
   /    \\
  |  🍎  |
   \\    /
    |  |
    |__|
        """,
        "modern": """
   .-------.
   |=======|
   |       |
   | [CPU] |
   |       |
   '-------'
        """,
        "default": """
    ____
   |    |
   |    |
   |____|
   |____|
        """
    }
    
    key = f"{device_family}_{device_arch}" if device_family else "default"
    return silhouettes.get(key, silhouettes["default"])


# Flask/FastAPI endpoint handler
def handle_machine_detail_request(fingerprint_hash: str, db_connection):
    """Handle GET /api/hall_of_fame/machine request."""
    machine = get_machine_details(fingerprint_hash, db_connection)
    
    if not machine:
        return {
            "success": False,
            "error": "Machine not found",
            "code": 404
        }, 404
    
    return {
        "success": True,
        "data": machine
    }, 200


if __name__ == '__main__':
    # Test the functions
    print("Hall of Fame Machine Detail API")
    print("=" * 40)
    
    # Test badge generation
    for score in [100, 250, 350, 450, 550]:
        badge = get_rust_badge(score)
        print(f"Score {score}: {badge['tier']} {badge['icon']}")
    
    # Test ASCII silhouettes
    print("\nASCII Silhouettes:")
    for family in ["vintage_powerpc", "vintage_x86", "apple_silicon", "modern"]:
        print(f"\n{family}:")
        print(get_ascii_silhouette(family, ""))
