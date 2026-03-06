#!/bin/bash
cd /mnt/c/Users/TRS/desktop/Rustchain_Repo_Scaffold
mkdir -p bounties
mkdir -p schemas
mkdir -p badges
mkdir -p manifest
mv badge_5pin_din_keyboard_warrior.json badges/
git add badges/badge_5pin_din_keyboard_warrior.json
mv badge_apollo_guidance_forge.json badges/
git add badges/badge_apollo_guidance_forge.json
mv badge_directx_defiler.json badges/
git add badges/badge_directx_defiler.json
mv badge_newton_validator_node.json badges/
git add badges/badge_newton_validator_node.json
mv badge_oregon_tcp_trail_survivor.json badges/
git add badges/badge_oregon_tcp_trail_survivor.json
mv badge_win95a_wireless_whisperer.json badges/
git add badges/badge_win95a_wireless_whisperer.json
mv badge_rust_over_radio.json badges/
git add badges/badge_rust_over_radio.json
mv badge_bondi_g3_flamekeeper.json badges/
git add badges/badge_bondi_g3_flamekeeper.json
mv relic_cpu_badges.json schemas/
git add schemas/relic_cpu_badges.json
mv relic_display_badges.json schemas/
git add schemas/relic_display_badges.json
mv relic_gpu_badges.json schemas/
git add schemas/relic_gpu_badges.json
mv relic_io_badges.json schemas/
git add schemas/relic_io_badges.json
mv nft_asset_manifest.json manifest/
git add manifest/nft_asset_manifest.json
mv dev_bounties.json bounties/
git add bounties/dev_bounties.json
git commit -m "Final JSON reorg: badges, schema, manifest, bounties structured"
git push origin main