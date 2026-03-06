#!/usr/bin/env python3
"""
Setup RustChain Database and Integration
"""

import os
import sys
import json
import sqlite3

def setup_database():
    """Initialize RustChain database"""
    print("🔧 Setting up RustChain database...")
    
    # Create necessary directories
    os.makedirs('badges', exist_ok=True)
    os.makedirs('certificates', exist_ok=True)
    os.makedirs('contracts', exist_ok=True)
    
    # Import modules
    from db.rustchain_database_schema import RustChainDatabase
    from rustchain_blockchain_integration import BlockchainIntegration
    
    # Initialize database
    db = RustChainDatabase()
    print("✅ Database schema created")
    
    # Initialize blockchain integration
    integration = BlockchainIntegration()
    print("✅ Blockchain integration initialized")
    
    # Sync with current blockchain
    print("🔄 Syncing with blockchain...")
    results = integration.sync_with_blockchain()
    
    print(f"✅ Sync complete:")
    print(f"   - Blocks processed: {results['blocks_processed']}")
    print(f"   - New miners: {results['new_miners']}")
    print(f"   - Badges awarded: {results['badges_awarded']}")
    
    if results['errors']:
        print(f"⚠️  Errors encountered:")
        for error in results['errors']:
            print(f"   - {error}")
    
    # Get network stats
    stats = integration.get_network_statistics()
    print(f"\n📊 Network Statistics:")
    print(f"   - Total miners: {stats['total_miners']}")
    print(f"   - Total blocks: {stats['total_blocks']}")
    print(f"   - Total RTC: {stats['total_rtc']:.2f}")
    print(f"   - Total badges: {stats['total_badges']}")
    
    if stats['oldest_hardware']:
        print(f"   - Oldest hardware: {stats['oldest_hardware']['hardware']} ({stats['oldest_hardware']['age']} years)")
    
    # Create API endpoint file
    create_api_endpoint()
    
    print("\n✅ Setup complete!")
    
def create_api_endpoint():
    """Create PHP API endpoint for database queries"""
    api_code = '''<?php
// RustChain Database API
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

$db_path = '/root/rustchain/db/rustchain_miners.db';

try {
    $db = new SQLite3($db_path);
    
    $action = $_GET['action'] ?? 'stats';
    
    switch($action) {
        case 'miners':
            $result = $db->query('
                SELECT wallet_address, hardware_model, estimated_age, tier, 
                       total_blocks_mined, total_rtc_earned, last_seen_timestamp
                FROM miners 
                ORDER BY estimated_age DESC
            ');
            
            $miners = [];
            while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
                $miners[] = $row;
            }
            echo json_encode(['miners' => $miners]);
            break;
            
        case 'badges':
            $wallet = $_GET['wallet'] ?? '';
            if ($wallet) {
                $stmt = $db->prepare('
                    SELECT badge_type, badge_tier, earned_timestamp
                    FROM nft_badges 
                    WHERE wallet_address = :wallet
                    ORDER BY earned_timestamp DESC
                ');
                $stmt->bindValue(':wallet', $wallet, SQLITE3_TEXT);
                $result = $stmt->execute();
            } else {
                $result = $db->query('
                    SELECT * FROM nft_badges 
                    ORDER BY earned_timestamp DESC 
                    LIMIT 50
                ');
            }
            
            $badges = [];
            while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
                $badges[] = $row;
            }
            echo json_encode(['badges' => $badges]);
            break;
            
        case 'stats':
        default:
            // Get tier statistics
            $tiers = ['ancient', 'sacred', 'vintage', 'classic', 'retro', 'modern'];
            $tier_stats = [];
            
            foreach ($tiers as $tier) {
                $stmt = $db->prepare('
                    SELECT COUNT(*) as count, 
                           SUM(total_blocks_mined) as blocks,
                           SUM(total_rtc_earned) as rtc
                    FROM miners WHERE tier = :tier
                ');
                $stmt->bindValue(':tier', $tier, SQLITE3_TEXT);
                $result = $stmt->execute();
                $row = $result->fetchArray(SQLITE3_ASSOC);
                
                $tier_stats[$tier] = [
                    'miners' => $row['count'] ?? 0,
                    'blocks' => $row['blocks'] ?? 0,
                    'rtc' => $row['rtc'] ?? 0
                ];
            }
            
            // Get totals
            $totals = $db->querySingle('
                SELECT COUNT(*) as miners,
                       SUM(total_blocks_mined) as blocks,
                       SUM(total_rtc_earned) as rtc
                FROM miners
            ', true);
            
            $badge_count = $db->querySingle('SELECT COUNT(*) FROM nft_badges');
            
            echo json_encode([
                'tier_stats' => $tier_stats,
                'totals' => [
                    'miners' => $totals['miners'] ?? 0,
                    'blocks' => $totals['blocks'] ?? 0,
                    'rtc' => $totals['rtc'] ?? 0,
                    'badges' => $badge_count ?? 0
                ]
            ]);
            break;
    }
    
    $db->close();
    
} catch (Exception $e) {
    echo json_encode(['error' => $e->getMessage()]);
}
?>'''
    
    with open('rustchain_db_api.php', 'w') as f:
        f.write(api_code)
    
    print("✅ API endpoint created: rustchain_db_api.php")

if __name__ == "__main__":
    setup_database()