#!/bin/bash
cd /mnt/c/Users/TRS/desktop/Rustchain_Repo_Scaffold
mkdir -p nfts
mv nft_badge_ppc_flame_valve.json nfts/
mv nft_badge_vickimac_flamekeeper.json nfts/
mv nft_badge_museum_relic.json nfts/
mv nft_badge_runs_doom.json nfts/
mv nft_badge_dos_wifi_alchemist.json nfts/
mv nft_badge_ham_radio_validator.json nfts/
mv nft_badge_quickbasic_listener.json nfts/
mv nft_badge_gravis_reclaimer.json nfts/
mv nft_badge_pawpaw_bios_flame.json nfts/
git add "README.md"
git add "RustChain_Whitepaper_Flameholder_v0.97-1.pdf"
git add "anti_vm.py"
git add "bios_pawpaw_detector.py"
git add "ergo_wrapper.py"
git add "leaderboard.json"
git add "proof_of_antiquity.json"
git add "relic_rewards.json"
git add "validator_core.py"
git add "weighted_decryption.py"
git add "nfts/nft_badge_ppc_flame_valve.json"
git add "nfts/nft_badge_vickimac_flamekeeper.json"
git add "nfts/nft_badge_museum_relic.json"
git add "nfts/nft_badge_runs_doom.json"
git add "nfts/nft_badge_dos_wifi_alchemist.json"
git add "nfts/nft_badge_ham_radio_validator.json"
git add "nfts/nft_badge_quickbasic_listener.json"
git add "nfts/nft_badge_gravis_reclaimer.json"
git add "nfts/nft_badge_pawpaw_bios_flame.json"
git commit -m "Moved NFT metadata into /nfts folder and synced all core updates"
git push origin main