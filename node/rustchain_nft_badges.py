#!/usr/bin/env python3
"""
RustChain NFT Badge System
Generates and manages achievement badges for miners
"""

import json
import hashlib
import base64
from typing import Dict, List, Optional
from datetime import datetime

class NFTBadgeGenerator:
    """Generate NFT badges for RustChain achievements"""
    
    # Badge visual templates (SVG)
    BADGE_TEMPLATES = {
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
    BADGE_TYPES = {
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
        badge_info = self.BADGE_TYPES.get(badge_type, {})
        template = self.BADGE_TEMPLATES.get(badge_info.get('tier', 'common'))
        
        svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="300" height="350" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="grad1" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:{template['color']};stop-opacity:1" />
      <stop offset="100%" style="stop-color:{template['border']};stop-opacity:1" />
    </linearGradient>
    {f'''<filter id="glow">
      <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
      <feMerge>
        <feMergeNode in="coloredBlur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>''' if template['glow'] else ''}
  </defs>
  
  <!-- Badge background -->
  <rect x="10" y="10" width="280" height="330" rx="20" ry="20" 
        fill="url(#grad1)" stroke="{template['border']}" stroke-width="4"
        {f'filter="url(#glow)"' if template['glow'] else ''}/>
  
  <!-- Inner frame -->
  <rect x="20" y="20" width="260" height="310" rx="15" ry="15" 
        fill="none" stroke="#FFFFFF" stroke-width="2" opacity="0.5"/>
  
  <!-- Icon background -->
  <circle cx="150" cy="100" r="60" fill="#FFFFFF" opacity="0.2"/>
  
  <!-- Icon -->
  <text x="150" y="120" font-family="Arial" font-size="60" text-anchor="middle" fill="#FFFFFF">
    {badge_info.get('icon', '🏅')}
  </text>
  
  <!-- Badge name -->
  <text x="150" y="200" font-family="Arial Black" font-size="22" text-anchor="middle" fill="#FFFFFF">
    {badge_info.get('name', 'Badge')}
  </text>
  
  <!-- Description -->
  <foreignObject x="30" y="220" width="240" height="60">
    <div xmlns="http://www.w3.org/1999/xhtml" style="font-family: Arial; font-size: 14px; color: #FFFFFF; text-align: center;">
      {badge_info.get('description', '')}
    </div>
  </foreignObject>
  
  <!-- Stars -->
  <g transform="translate(150, 290)">
    {self._generate_stars(template['stars'])}
  </g>
  
  <!-- Date earned -->
  <text x="150" y="320" font-family="Arial" font-size="12" text-anchor="middle" fill="#FFFFFF" opacity="0.7">
    Earned: {earned_date}
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
    
    def generate_badge_metadata(self, badge_type: str, miner_info: Dict, 
                              block_height: int) -> Dict:
        """Generate complete NFT metadata for badge"""
        badge_info = self.BADGE_TYPES.get(badge_type, {})
        earned_date = datetime.now().strftime('%Y-%m-%d')
        
        # Generate unique badge ID
        badge_data = f"{badge_type}:{miner_info['wallet']}:{block_height}:{earned_date}"
        badge_hash = hashlib.sha256(badge_data.encode()).hexdigest()
        badge_id = f"RTC-{badge_type}-{badge_hash[:8]}"
        
        # Generate SVG
        svg_content = self.generate_badge_svg(badge_type, miner_info['wallet'], earned_date)
        svg_base64 = base64.b64encode(svg_content.encode()).decode()
        
        # Create metadata
        metadata = {
            'name': f"{badge_info.get('name', 'RustChain Badge')} #{badge_hash[:8]}",
            'description': badge_info.get('description', ''),
            'image': f"data:image/svg+xml;base64,{svg_base64}",
            'external_url': f"https://rustchain.org/badge/{badge_id}",
            'attributes': [
                {
                    'trait_type': 'Badge Type',
                    'value': badge_type
                },
                {
                    'trait_type': 'Tier',
                    'value': badge_info.get('tier', 'common').title()
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
                'wallet': miner_info['wallet'],
                'blockchain': 'RustChain',
                'standard': 'RTC-721'
            }
        }
        
        return metadata
    
    def check_badge_eligibility(self, miner_stats: Dict) -> List[str]:
        """Check which badges a miner is eligible for"""
        eligible = []
        
        # Check each badge type
        if miner_stats['first_seen_block'] < 100:
            eligible.append('GENESIS_MINER')
        
        if miner_stats['hardware_age'] >= 30:
            eligible.append('ANCIENT_KEEPER')
            if miner_stats['hardware_age'] >= 35:
                eligible.append('MUSEUM_PIECE')
        elif miner_stats['hardware_age'] >= 25:
            eligible.append('SACRED_GUARDIAN')
        elif miner_stats['hardware_age'] >= 20:
            eligible.append('VINTAGE_COLLECTOR')
        
        if miner_stats['blocks_mined'] >= 100:
            eligible.append('BLOCK_CENTURION')
        elif miner_stats['blocks_mined'] >= 1:
            eligible.append('FIRST_BLOCK')
        
        if miner_stats['rtc_earned'] >= 1000:
            eligible.append('RTC_MILLIONAIRE')
        
        # Check mining duration (30 days)
        if miner_stats.get('mining_days', 0) >= 30:
            eligible.append('DEDICATION_MEDAL')
        
        # Always eligible for flamekeeper if using vintage hardware
        if miner_stats['hardware_age'] >= 10:
            eligible.append('FLAMEKEEPER')
        
        # Check for unique hardware
        if miner_stats.get('unique_hardware', False):
            eligible.append('HARDWARE_DIVERSITY')
        
        # Special badges
        if '486' in miner_stats.get('hardware_model', '').lower() or \
           '386' in miner_stats.get('hardware_model', '').lower():
            eligible.append('DIAL_UP_WARRIOR')
        
        return eligible
    
    def create_badge_contract_data(self, badge_metadata: Dict) -> Dict:
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
            'timestamp': int(datetime.now().timestamp())
        }
        
        return contract_data


class BadgeDisplayGenerator:
    """Generate HTML display for badges"""
    
    @staticmethod
    def generate_badge_showcase(badges: List[Dict]) -> str:
        """Generate HTML showcase for a collection of badges"""
        html = """
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
        """
        
        for badge in badges:
            tier = badge.get('tier', 'common')
            html += f"""
            <div class="badge-card {tier}">
                <div class="badge-icon">{badge.get('icon', '🏅')}</div>
                <div class="badge-name">{badge.get('name', 'Badge')}</div>
                <div class="badge-description">{badge.get('description', '')}</div>
                <div class="badge-date">Earned: {badge.get('earned_date', 'Unknown')}</div>
            </div>
            """
        
        html += "</div>"
        return html


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