#!/usr/bin/env python3
"""
RustChain NFT Badge System
Generates and manages achievement badges for miners
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import math
import re
from datetime import datetime, timezone
from typing import ClassVar
from urllib.parse import quote

_XML_INVALID_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _escape_xml_text(value: object) -> str:
    """Strip illegal XML 1.0 control characters and escape HTML/XML metacharacters."""
    text = "" if value is None else str(value)
    text = _XML_INVALID_RE.sub("", text)
    return html.escape(text, quote=True)


def _safe_number(value: object) -> float | None:
    """Return finite numeric value, rejecting bool, None, NaN, and infinity."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value):
        return None
    return float(value)

class NFTBadgeGenerator:
    """Generate NFT badges for RustChain achievements"""
    
    # Badge visual templates (SVG)
    BADGE_TEMPLATES: ClassVar[dict[str, dict[str, object]]] = {
        'legendary': {
            'color': '#FFD700',  # Gold
            'border': '#FFA500',
            'stars': 5,
            'glow': True
        },
        'epic': {
            'color': '#9370DB',  # Purple
            'border': '#7B68EE',
            'stars': 4,
            'glow': True
        },
        'rare': {
            'color': '#4169E1',  # Blue
            'border': '#1E90FF',
            'stars': 3,
            'glow': False
        },
        'uncommon': {
            'color': '#32CD32',  # Green
            'border': '#228B22',
            'stars': 2,
            'glow': False
        },
        'common': {
            'color': '#C0C0C0',  # Silver
            'border': '#808080',
            'stars': 1,
            'glow': False
        }
    }
    
    # Badge type definitions
    BADGE_TYPES: ClassVar[dict[str, dict[str, str]]] = {
        'GENESIS_MINER': {
            'name': 'Genesis Miner',
            'description': 'One of the first 100 miners on RustChain',
            'tier': 'legendary',
            'icon': '⛏️'
        },
        'ANCIENT_KEEPER': {
            'name': 'Ancient Silicon Keeper',
            'description': 'Mining with 30+ year old hardware',
            'tier': 'epic',
            'icon': '🏛️'
        },
        'SACRED_GUARDIAN': {
            'name': 'Sacred Silicon Guardian',
            'description': 'Mining with 25+ year old hardware',
            'tier': 'rare',
            'icon': '👑'
        },
        'VINTAGE_COLLECTOR': {
            'name': 'Vintage Collector',
            'description': 'Mining with 20+ year old hardware',
            'tier': 'rare',
            'icon': '🏆'
        },
        'BLOCK_CENTURION': {
            'name': 'Block Centurion',
            'description': 'Mined 100+ blocks',
            'tier': 'rare',
            'icon': '💯'
        },
        'RTC_MILLIONAIRE': {
            'name': 'RTC Millionaire',
            'description': 'Earned 1,000+ RTC',
            'tier': 'epic',
            'icon': '💰'
        },
        'DEDICATION_MEDAL': {
            'name': 'Dedication Medal',
            'description': 'Mining for 30+ consecutive days',
            'tier': 'rare',
            'icon': '🎖️'
        },
        'FIRST_BLOCK': {
            'name': 'First Block',
            'description': 'Mined your first block',
            'tier': 'common',
            'icon': '🎯'
        },
        'HARDWARE_DIVERSITY': {
            'name': 'Hardware Diversity',
            'description': 'Mining with unique or rare hardware',
            'tier': 'uncommon',
            'icon': '🌈'
        },
        'FLAMEKEEPER': {
            'name': 'Flamekeeper',
            'description': 'Keeping vintage hardware alive',
            'tier': 'uncommon',
            'icon': '🔥'
        },
        'MUSEUM_PIECE': {
            'name': 'Museum Piece',
            'description': 'Mining with hardware older than the internet',
            'tier': 'legendary',
            'icon': '🗿'
        },
        'DIAL_UP_WARRIOR': {
            'name': 'Dial-Up Warrior',
            'description': 'Mining like it\'s 1995',
            'tier': 'rare',
            'icon': '📞'
        }
    }
    
    def generate_badge_svg(self, badge_type: str, wallet: str, earned_date: str) -> str:
        """Generate SVG image for badge"""
        badge_info = self.BADGE_TYPES.get(badge_type)
        if not isinstance(badge_info, dict):
            badge_info = {}
        tier = badge_info.get('tier', 'common')
        template = self.BADGE_TEMPLATES.get(tier, self.BADGE_TEMPLATES['common'])

        color = _escape_xml_text(template['color'])
        border = _escape_xml_text(template['border'])
        icon = _escape_xml_text(badge_info.get('icon', '🏅'))
        name = _escape_xml_text(badge_info.get('name', 'Badge'))
        description = _escape_xml_text(badge_info.get('description', ''))
        safe_earned_date = _escape_xml_text(earned_date)

        svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="300" height="350" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="grad1" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
      <stop offset="100%" style="stop-color:{border};stop-opacity:1" />
    </linearGradient>
    {'''<filter id="glow">
      <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
      <feMerge>
        <feMergeNode in="coloredBlur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>''' if template['glow'] else ''}
  </defs>

  <!-- Badge background -->
  <rect x="10" y="10" width="280" height="330" rx="20" ry="20"
        fill="url(#grad1)" stroke="{border}" stroke-width="4"
        {'filter="url(#glow)"' if template['glow'] else ''}/>

  <!-- Inner frame -->
  <rect x="20" y="20" width="260" height="310" rx="15" ry="15"
        fill="none" stroke="#FFFFFF" stroke-width="2" opacity="0.5"/>

  <!-- Icon background -->
  <circle cx="150" cy="100" r="60" fill="#FFFFFF" opacity="0.2"/>

  <!-- Icon -->
  <text x="150" y="120" font-family="Arial" font-size="60" text-anchor="middle" fill="#FFFFFF">
    {icon}
  </text>

  <!-- Badge name -->
  <text x="150" y="200" font-family="Arial Black" font-size="22" text-anchor="middle" fill="#FFFFFF">
    {name}
  </text>

  <!-- Description -->
  <foreignObject x="30" y="220" width="240" height="60">
    <div xmlns="http://www.w3.org/1999/xhtml" style="font-family: Arial; font-size: 14px; color: #FFFFFF; text-align: center;">
      {description}
    </div>
  </foreignObject>

  <!-- Stars -->
  <g transform="translate(150, 290)">
    {self._generate_stars(template['stars'])}
  </g>

  <!-- Date earned -->
  <text x="150" y="320" font-family="Arial" font-size="12" text-anchor="middle" fill="#FFFFFF" opacity="0.7">
    Earned: {safe_earned_date}
  </text>
</svg>"""

        return svg
    
    def _generate_stars(self, count: int) -> str:
        """Generate star rating SVG"""
        stars = []
        start_x = -(count * 15)
        
        for i in range(count):
            x = start_x + (i * 30)
            stars.append(f'''
            <polygon points="{x},0 {x+6},-8 {x+12},0 {x+8},-6 {x+14},-12 {x+6},-10 {x},-12 {x+4},-6" 
                     fill="#FFD700" stroke="#FFA500" stroke-width="1"/>
            ''')
        
        return ''.join(stars)
    
    def generate_badge_metadata(self, badge_type: str, miner_info: dict,
                              block_height: int) -> dict:
        """Generate complete NFT metadata for badge"""
        if not isinstance(badge_type, str) or not badge_type.strip():
            raise ValueError("badge_type must be a non-empty string")
        if not isinstance(miner_info, dict):
            raise TypeError("miner_info must be a dict")
        wallet = miner_info.get('wallet')
        if not isinstance(wallet, str) or not wallet.strip():
            raise ValueError("miner_info['wallet'] must be a non-empty string")
        if isinstance(block_height, bool) or not isinstance(block_height, int) or block_height < 0:
            raise ValueError("block_height must be a non-negative integer")

        badge_info = self.BADGE_TYPES.get(badge_type)
        if not isinstance(badge_info, dict):
            badge_info = {}
        raw_tier = badge_info.get('tier', 'common')
        tier = raw_tier if isinstance(raw_tier, str) and raw_tier.strip() else 'common'
        earned_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

        # Generate unique badge ID
        badge_data = f"{badge_type}:{wallet}:{block_height}:{earned_date}"
        badge_hash = hashlib.sha256(badge_data.encode()).hexdigest()
        badge_id = f"RTC-{badge_type}-{badge_hash[:8]}"

        # Generate SVG
        svg_content = self.generate_badge_svg(badge_type, wallet, earned_date)
        svg_base64 = base64.b64encode(svg_content.encode()).decode()

        # Create metadata
        metadata = {
            'name': f"{badge_info.get('name', 'RustChain Badge')} #{badge_hash[:8]}",
            'description': badge_info.get('description', ''),
            'image': f"data:image/svg+xml;base64,{svg_base64}",
            'external_url': f"https://rustchain.org/badge/{quote(badge_id, safe='')}",
            'attributes': [
                {
                    'trait_type': 'Badge Type',
                    'value': badge_type
                },
                {
                    'trait_type': 'Tier',
                    'value': tier.title()
                },
                {
                    'trait_type': 'Earned Block',
                    'value': block_height
                },
                {
                    'trait_type': 'Earned Date',
                    'value': earned_date
                },
                {
                    'trait_type': 'Hardware',
                    'value': miner_info.get('hardware', 'Unknown')
                },
                {
                    'trait_type': 'Hardware Age',
                    'value': f"{miner_info.get('age', 0)} years"
                }
            ],
            'properties': {
                'badge_id': badge_id,
                'badge_hash': badge_hash,
                'wallet': wallet,
                'blockchain': 'RustChain',
                'standard': 'RTC-721'
            }
        }

        return metadata

    def check_badge_eligibility(self, miner_stats: dict) -> list[str]:
        """Check which badges a miner is eligible for"""
        if not isinstance(miner_stats, dict):
            return []

        eligible = []

        first_seen_block = _safe_number(miner_stats.get('first_seen_block'))
        hardware_age = _safe_number(miner_stats.get('hardware_age'))
        blocks_mined = _safe_number(miner_stats.get('blocks_mined'))
        rtc_earned = _safe_number(miner_stats.get('rtc_earned'))
        mining_days = _safe_number(miner_stats.get('mining_days'))

        # Check each badge type
        if first_seen_block is not None and 0 <= first_seen_block < 100:
            eligible.append('GENESIS_MINER')

        if hardware_age is not None:
            if hardware_age >= 30:
                eligible.append('ANCIENT_KEEPER')
                if hardware_age >= 35:
                    eligible.append('MUSEUM_PIECE')
            elif hardware_age >= 25:
                eligible.append('SACRED_GUARDIAN')
            elif hardware_age >= 20:
                eligible.append('VINTAGE_COLLECTOR')

        if blocks_mined is not None:
            if blocks_mined >= 100:
                eligible.append('BLOCK_CENTURION')
            elif blocks_mined >= 1:
                eligible.append('FIRST_BLOCK')

        if rtc_earned is not None and rtc_earned >= 1000:
            eligible.append('RTC_MILLIONAIRE')

        # Check mining duration (30 days)
        if mining_days is not None and mining_days >= 30:
            eligible.append('DEDICATION_MEDAL')

        # Always eligible for flamekeeper if using vintage hardware
        if hardware_age is not None and hardware_age >= 10:
            eligible.append('FLAMEKEEPER')

        # Check for unique hardware
        if miner_stats.get('unique_hardware', False):
            eligible.append('HARDWARE_DIVERSITY')

        # Special badges
        hardware_model = miner_stats.get('hardware_model')
        model_lower = hardware_model.lower() if isinstance(hardware_model, str) else ''
        if '486' in model_lower or '386' in model_lower:
            eligible.append('DIAL_UP_WARRIOR')

        return eligible

    def create_badge_contract_data(self, badge_metadata: dict) -> dict:
        """Create data for smart contract integration"""
        # This would integrate with Ergo smart contracts
        contract_data = {
            'badge_id': badge_metadata['properties']['badge_id'],
            'badge_hash': badge_metadata['properties']['badge_hash'],
            'owner': badge_metadata['properties']['wallet'],
            'metadata_hash': hashlib.sha256(
                json.dumps(badge_metadata, sort_keys=True).encode()
            ).hexdigest(),
            'ipfs_hash': None,  # Would be set after IPFS upload
            'contract_address': None,  # Would be set after deployment
            'minting_tx': None,  # Would be set after minting
            'timestamp': int(datetime.now(timezone.utc).timestamp())
        }

        return contract_data


class BadgeDisplayGenerator:
    """Generate HTML display for badges"""

    ALLOWED_TIERS = frozenset(NFTBadgeGenerator.BADGE_TEMPLATES)

    @staticmethod
    def generate_badge_showcase(badges: list[dict]) -> str:
        """Generate HTML showcase for a collection of badges"""
        parts = ["""
        <style>
        .badge-showcase {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 20px;
            padding: 20px;
        }
        .badge-card {
            background: linear-gradient(135deg, #1a1a1a, #2a2a2a);
            border-radius: 15px;
            padding: 15px;
            text-align: center;
            transition: transform 0.3s ease;
            border: 2px solid #444;
        }
        .badge-card:hover {
            transform: translateY(-5px);
            border-color: #FFD700;
        }
        .badge-card.legendary { border-color: #FFD700; box-shadow: 0 0 20px rgba(255, 215, 0, 0.5); }
        .badge-card.epic { border-color: #9370DB; box-shadow: 0 0 15px rgba(147, 112, 219, 0.5); }
        .badge-card.rare { border-color: #4169E1; }
        .badge-card.uncommon { border-color: #32CD32; }
        .badge-card.common { border-color: #C0C0C0; }
        .badge-icon { font-size: 48px; margin: 10px 0; }
        .badge-name { font-weight: bold; color: #FFD700; margin: 10px 0; }
        .badge-description { font-size: 14px; color: #CCC; }
        .badge-date { font-size: 12px; color: #888; margin-top: 10px; }
        </style>

        <div class="badge-showcase">
        """]

        if isinstance(badges, (list, tuple)):
            for badge in badges:
                if not isinstance(badge, dict):
                    continue
                raw_tier = badge.get('tier')
                tier = (
                    raw_tier
                    if isinstance(raw_tier, str) and raw_tier in BadgeDisplayGenerator.ALLOWED_TIERS
                    else 'common'
                )
                raw_icon = badge.get('icon')
                raw_name = badge.get('name')
                raw_desc = badge.get('description')
                raw_date = badge.get('earned_date')
                icon = _escape_xml_text('🏅' if raw_icon is None else raw_icon)
                name = _escape_xml_text('Badge' if raw_name is None else raw_name)
                description = _escape_xml_text('' if raw_desc is None else raw_desc)
                earned_date = _escape_xml_text('Unknown' if raw_date is None else raw_date)
                parts.append(f"""
            <div class="badge-card {tier}">
                <div class="badge-icon">{icon}</div>
                <div class="badge-name">{name}</div>
                <div class="badge-description">{description}</div>
                <div class="badge-date">Earned: {earned_date}</div>
            </div>
            """)

        parts.append("</div>")
        return "".join(parts)


if __name__ == "__main__":
    # Example usage
    generator = NFTBadgeGenerator()
    
    # Example miner stats
    miner_stats = {
        'wallet': 'RTCtest123',
        'hardware': 'PowerPC G4',
        'hardware_model': 'PowerBook G4',
        'age': 22,
        'first_seen_block': 50,
        'blocks_mined': 150,
        'rtc_earned': 1500,
        'hardware_age': 22,
        'mining_days': 45
    }
    
    # Check eligibility
    eligible_badges = generator.check_badge_eligibility(miner_stats)
    print(f"Eligible for badges: {eligible_badges}")
    
    # Generate badge metadata
    if eligible_badges:
        metadata = generator.generate_badge_metadata(
            eligible_badges[0], 
            miner_stats, 
            1000
        )
        print(f"Badge metadata: {json.dumps(metadata, indent=2)}")