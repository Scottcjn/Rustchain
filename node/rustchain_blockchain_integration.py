#!/usr/bin/env python3
"""
RustChain Blockchain Integration
Connects database with blockchain for verification and smart contracts
"""

import json
import hashlib
import time
import requests
from typing import Dict, List, Optional, Tuple
from db.rustchain_database_schema import RustChainDatabase
from rustchain_nft_badges import NFTBadgeGenerator

class BlockchainIntegration:
    """Integrates RustChain database with blockchain verification"""
    
    def __init__(self, node_url: str = "http://50.28.86.131:8085", 
                 db_path: str = "db/rustchain_miners.db"):
        self.node_url = node_url
        self.db = RustChainDatabase(db_path)
        self.badge_generator = NFTBadgeGenerator()
        
    def process_new_block(self, block_data: Dict) -> Dict:
        """Process a new block and update database"""
        results = {
            'new_miners': 0,
            'updated_miners': 0,
            'badges_awarded': 0,
            'errors': []
        }

        try:
            block_height = block_data['block_height']
            
            # Process each miner in the block
            for miner in block_data.get('miners', []):
                success, message = self._process_miner(miner, block_height)
                
                if success:
                    if 'registered' in message:
                        results['new_miners'] += 1
                    else:
                        results['updated_miners'] += 1
                    
                    # Check for badge eligibility
                    badges = self._check_and_award_badges(miner['wallet'], block_height)
                    results['badges_awarded'] += len(badges)
                else:
                    results['errors'].append(f"Miner {miner['wallet']}: {message}")
            
            # Create blockchain verification
            self.db.verify_blockchain_integrity(block_height)
            
        except Exception as e:
            results['errors'].append(f"Block processing error: {str(e)}")
            
        return results
    
    def _process_miner(self, miner_data: Dict, block_height: int) -> Tuple[bool, str]:
        """Process individual miner from block"""
        try:
            # Check if miner exists
            existing = self.db.get_miner_profile(miner_data['wallet'])
            
            if not existing:
                # Parse hardware info from miner data
                hardware_info = self._parse_hardware_string(miner_data['hardware'])
                
                # Register new miner
                miner_info = {
                    'wallet': miner_data['wallet'],
                    'block_height': block_height,
                    'tier': self._determine_tier(hardware_info['age_years']),
                    'multiplier': miner_data['multiplier'],
                    'hardware': hardware_info
                }
                
                return self.db.register_miner(miner_info)
            else:
                # Update existing miner stats
                self.db.update_mining_stats(
                    miner_data['wallet'],
                    block_height,
                    miner_data['reward']
                )
                return True, "Stats updated"
                
        except Exception as e:
            return False, str(e)
    
    def _parse_hardware_string(self, hardware_str: str) -> Dict:
        """Parse hardware string to extract information"""
        hardware_info = {
            'model': hardware_str,
            'generation': 'Unknown',
            'age_years': 5,
            'cpu_family': 0
        }
        
        lower = hardware_str.lower()
        
        # PowerPC parsing
        if 'powerpc g4' in lower or 'g4' in lower:
            hardware_info.update({
                'generation': 'PowerPC G4',
                'age_years': 22,
                'cpu_family': 74
            })
        elif 'powerpc g3' in lower:
            hardware_info.update({
                'generation': 'PowerPC G3',
                'age_years': 26,
                'cpu_family': 74
            })
        # Intel parsing
        elif '486' in lower:
            hardware_info.update({
                'generation': 'Intel 486',
                'age_years': 35,
                'cpu_family': 4
            })
        elif '386' in lower:
            hardware_info.update({
                'generation': 'Intel 386',
                'age_years': 38,
                'cpu_family': 3
            })
        elif 'pentium' in lower:
            if 'ii' in lower or '2' in lower:
                hardware_info.update({
                    'generation': 'Pentium II',
                    'age_years': 27,
                    'cpu_family': 6
                })
            elif 'iii' in lower or '3' in lower:
                hardware_info.update({
                    'generation': 'Pentium III',
                    'age_years': 25,
                    'cpu_family': 6
                })
        # Modern CPUs
        elif 'xeon' in lower:
            if 'scalable' in lower:
                hardware_info.update({
                    'generation': 'Xeon Scalable',
                    'age_years': 3,
                    'cpu_family': 6
                })
            else:
                hardware_info.update({
                    'generation': 'Xeon',
                    'age_years': 5,
                    'cpu_family': 6
                })
        elif 'ryzen' in lower:
            hardware_info.update({
                'generation': 'AMD Ryzen',
                'age_years': 5,
                'cpu_family': 23
            })
        
        return hardware_info
    
    def _determine_tier(self, age_years: int) -> str:
        """Determine hardware tier based on age"""
        if age_years >= 30:
            return 'ancient'
        elif age_years >= 25:
            return 'sacred'
        elif age_years >= 20:
            return 'vintage'
        elif age_years >= 15:
            return 'classic'
        elif age_years >= 10:
            return 'retro'
        else:
            return 'modern'
    
    def _check_and_award_badges(self, wallet: str, block_height: int) -> List[str]:
        """Check and award badges for a miner"""
        awarded = []
        
        try:
            # Get miner profile
            profile = self.db.get_miner_profile(wallet)
            if not profile:
                return awarded
            
            # Get miner stats for badge checking
            miner_stats = {
                'wallet': wallet,
                'hardware': profile['hardware']['model'],
                'hardware_model': profile['hardware']['model'],
                'hardware_age': profile['hardware']['age'],
                'age': profile['hardware']['age'],
                'first_seen_block': profile['stats']['first_seen'],
                'blocks_mined': profile['stats']['blocks_mined'],
                'rtc_earned': profile['stats']['rtc_earned'],
                'mining_days': (profile['stats']['last_seen'] - profile['stats']['first_seen']) / 86400
            }
            
            # Check eligibility
            eligible_badges = self.badge_generator.check_badge_eligibility(miner_stats)
            
            # Get existing badges
            existing_badges = [b['badge_type'] for b in profile['badges']]
            
            # Award new badges
            for badge_type in eligible_badges:
                if badge_type not in existing_badges:
                    badge_id = self.db.award_badge(
                        wallet,
                        badge_type,
                        self.badge_generator.BADGE_TYPES[badge_type]['tier'],
                        block_height
                    )
                    
                    if badge_id:
                        awarded.append(badge_type)
                        
                        # Generate badge metadata for future IPFS/contract upload
                        metadata = self.badge_generator.generate_badge_metadata(
                            badge_type,
                            miner_stats,
                            block_height
                        )
                        
                        # Store metadata (would be uploaded to IPFS in production)
                        self._store_badge_metadata(badge_id, metadata)
            
        except Exception as e:
            print(f"Error awarding badges: {e}")
            
        return awarded
    
    def _store_badge_metadata(self, badge_id: str, metadata: Dict):
        """Store badge metadata (placeholder for IPFS upload)"""
        # In production, this would upload to IPFS and return the hash
        # For now, we'll store it locally
        with open(f"badges/{badge_id}.json", 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def sync_with_blockchain(self) -> Dict:
        """Sync database with current blockchain state"""
        results = {
            'blocks_processed': 0,
            'new_miners': 0,
            'badges_awarded': 0,
            'errors': []
        }
        
        try:
            # Get current blockchain state
            response = requests.get(f"{self.node_url}/api/blocks")
            data = response.json()
            blocks = data.get('blocks', [])
            
            for block in blocks:
                # Skip genesis block (usually has different structure)
                if block.get('block_height', 0) == 0:
                    continue
                    
                result = self.process_new_block(block)
                results['blocks_processed'] += 1
                results['new_miners'] += result['new_miners']
                results['badges_awarded'] += result['badges_awarded']
                results['errors'].extend(result['errors'])
                
        except Exception as e:
            results['errors'].append(f"Sync error: {str(e)}")
            
        return results
    
    def generate_miner_certificate(self, wallet: str) -> Optional[Dict]:
        """Generate a verifiable certificate for a miner"""
        profile = self.db.get_miner_profile(wallet)
        
        if not profile:
            return None
        
        certificate = {
            'version': '1.0',
            'blockchain': 'RustChain',
            'timestamp': int(time.time()),
            'miner': {
                'wallet': wallet,
                'hardware': profile['hardware'],
                'registration_hash': profile['verification_hash'],
                'is_verified': profile['is_verified']
            },
            'achievements': {
                'blocks_mined': profile['stats']['blocks_mined'],
                'rtc_earned': profile['stats']['rtc_earned'],
                'mining_since': profile['stats']['first_seen'],
                'badges': len(profile['badges'])
            },
            'badges': [
                {
                    'type': badge['badge_type'],
                    'tier': badge['badge_tier'],
                    'earned': badge['earned_timestamp']
                }
                for badge in profile['badges']
            ]
        }
        
        # Generate certificate hash
        cert_string = json.dumps(certificate, sort_keys=True)
        certificate['certificate_hash'] = hashlib.sha256(cert_string.encode()).hexdigest()
        
        return certificate
    
    def get_network_statistics(self) -> Dict:
        """Get comprehensive network statistics"""
        stats = {
            'tier_distribution': self.db.get_tier_statistics(),
            'total_miners': 0,
            'total_blocks': 0,
            'total_rtc': 0,
            'total_badges': 0,
            'oldest_hardware': None,
            'most_productive': None
        }
        
        # Calculate totals
        for tier_stats in stats['tier_distribution'].values():
            stats['total_miners'] += tier_stats['miners']
            stats['total_blocks'] += tier_stats['blocks']
            stats['total_rtc'] += tier_stats['rtc']
        
        # Get additional stats from database
        conn = self.db.conn
        
        # Oldest hardware
        oldest = conn.execute("""
        SELECT wallet_address, hardware_model, estimated_age 
        FROM miners 
        ORDER BY estimated_age DESC 
        LIMIT 1
        """).fetchone()
        
        if oldest:
            stats['oldest_hardware'] = {
                'wallet': oldest['wallet_address'],
                'hardware': oldest['hardware_model'],
                'age': oldest['estimated_age']
            }
        
        # Most productive miner
        productive = conn.execute("""
        SELECT wallet_address, hardware_model, total_rtc_earned 
        FROM miners 
        ORDER BY total_rtc_earned DESC 
        LIMIT 1
        """).fetchone()
        
        if productive:
            stats['most_productive'] = {
                'wallet': productive['wallet_address'],
                'hardware': productive['hardware_model'],
                'rtc_earned': productive['total_rtc_earned']
            }
        
        # Total badges
        badge_count = conn.execute("SELECT COUNT(*) as count FROM nft_badges").fetchone()
        stats['total_badges'] = badge_count['count'] if badge_count else 0
        
        return stats


# Smart contract templates (Ergo-style pseudocode)
SMART_CONTRACT_TEMPLATES = {
    'miner_registration': """
    {
        // Miner Registration Contract
        val minerWallet = SELF.R4[Coll[Byte]].get
        val hardwareHash = SELF.R5[Coll[Byte]].get
        val verificationHash = SELF.R6[Coll[Byte]].get
        val blockHeight = CONTEXT.HEIGHT
        
        // Verify unique hardware
        val isUniqueHardware = !CONTEXT.dataInputs.exists { box =>
            box.R5[Coll[Byte]].get == hardwareHash
        }
        
        // Store registration
        sigmaProp(
            isUniqueHardware &&
            OUTPUTS(0).R4[Coll[Byte]].get == minerWallet &&
            OUTPUTS(0).R5[Coll[Byte]].get == hardwareHash &&
            OUTPUTS(0).R6[Coll[Byte]].get == verificationHash &&
            OUTPUTS(0).R7[Long].get == blockHeight
        )
    }
    """,
    
    'badge_minting': """
    {
        // NFT Badge Minting Contract
        val badgeId = SELF.R4[Coll[Byte]].get
        val minerWallet = SELF.R5[Coll[Byte]].get
        val badgeType = SELF.R6[Coll[Byte]].get
        val metadataHash = SELF.R7[Coll[Byte]].get
        
        // Verify miner owns wallet
        val isMinerOwner = INPUTS(0).propositionBytes == minerWallet
        
        // Create NFT token
        sigmaProp(
            isMinerOwner &&
            OUTPUTS(0).tokens(0)._1 == SELF.id &&
            OUTPUTS(0).tokens(0)._2 == 1L &&
            OUTPUTS(0).R4[Coll[Byte]].get == badgeId &&
            OUTPUTS(0).R5[Coll[Byte]].get == minerWallet &&
            OUTPUTS(0).R6[Coll[Byte]].get == badgeType &&
            OUTPUTS(0).R7[Coll[Byte]].get == metadataHash
        )
    }
    """
}


if __name__ == "__main__":
    # Example usage
    integration = BlockchainIntegration()
    
    # Sync with blockchain
    print("Syncing with blockchain...")
    sync_results = integration.sync_with_blockchain()
    print(f"Sync results: {sync_results}")
    
    # Get network statistics
    stats = integration.get_network_statistics()
    print(f"Network statistics: {json.dumps(stats, indent=2)}")
    
    # Generate certificate for a miner
    cert = integration.generate_miner_certificate("RTCtest123")
    if cert:
        print(f"Miner certificate: {json.dumps(cert, indent=2)}")