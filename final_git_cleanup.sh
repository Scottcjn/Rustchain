#!/bin/bash
cd /mnt/c/Users/TRS/desktop/Rustchain_Repo_Scaffold
mkdir -p badges
mkdir -p schemas
mkdir -p manifest
mkdir -p bounties
mkdir -p nfts
mv -f badge_5pin_din_keyboard_warrior.json badges/ 2>/dev/null || true
git rm -f --cached badge_5pin_din_keyboard_warrior.json 2>/dev/null || true
git add badges/badge_5pin_din_keyboard_warrior.json
mv -f badge_apollo_guidance_forge.json badges/ 2>/dev/null || true
git rm -f --cached badge_apollo_guidance_forge.json 2>/dev/null || true
git add badges/badge_apollo_guidance_forge.json
mv -f badge_directx_defiler.json badges/ 2>/dev/null || true
git rm -f --cached badge_directx_defiler.json 2>/dev/null || true
git add badges/badge_directx_defiler.json
mv -f badge_newton_validator_node.json badges/ 2>/dev/null || true
git rm -f --cached badge_newton_validator_node.json 2>/dev/null || true
git add badges/badge_newton_validator_node.json
mv -f badge_oregon_tcp_trail_survivor.json badges/ 2>/dev/null || true
git rm -f --cached badge_oregon_tcp_trail_survivor.json 2>/dev/null || true
git add badges/badge_oregon_tcp_trail_survivor.json
mv -f badge_win95a_wireless_whisperer.json badges/ 2>/dev/null || true
git rm -f --cached badge_win95a_wireless_whisperer.json 2>/dev/null || true
git add badges/badge_win95a_wireless_whisperer.json
mv -f badge_rust_over_radio.json badges/ 2>/dev/null || true
git rm -f --cached badge_rust_over_radio.json 2>/dev/null || true
git add badges/badge_rust_over_radio.json
mv -f badge_bondi_g3_flamekeeper.json badges/ 2>/dev/null || true
git rm -f --cached badge_bondi_g3_flamekeeper.json 2>/dev/null || true
git add badges/badge_bondi_g3_flamekeeper.json
mv -f badge_if_it_runs_doom_it_mines_rust.json badges/ 2>/dev/null || true
git rm -f --cached badge_if_it_runs_doom_it_mines_rust.json 2>/dev/null || true
git add badges/badge_if_it_runs_doom_it_mines_rust.json
mv -f badge_it_belongs_in_a_museum.json badges/ 2>/dev/null || true
git rm -f --cached badge_it_belongs_in_a_museum.json 2>/dev/null || true
git add badges/badge_it_belongs_in_a_museum.json
mv -f badge_dos_wifi_alchemist.json badges/ 2>/dev/null || true
git rm -f --cached badge_dos_wifi_alchemist.json 2>/dev/null || true
git add badges/badge_dos_wifi_alchemist.json
mv -f badge_pawpaw_legacy_miner.json badges/ 2>/dev/null || true
git rm -f --cached badge_pawpaw_legacy_miner.json 2>/dev/null || true
git add badges/badge_pawpaw_legacy_miner.json
mv -f relic_cpu_badges.json schemas/ 2>/dev/null || true
git rm -f --cached relic_cpu_badges.json 2>/dev/null || true
git add schemas/relic_cpu_badges.json
mv -f relic_display_badges.json schemas/ 2>/dev/null || true
git rm -f --cached relic_display_badges.json 2>/dev/null || true
git add schemas/relic_display_badges.json
mv -f relic_gpu_badges.json schemas/ 2>/dev/null || true
git rm -f --cached relic_gpu_badges.json 2>/dev/null || true
git add schemas/relic_gpu_badges.json
mv -f relic_io_badges.json schemas/ 2>/dev/null || true
git rm -f --cached relic_io_badges.json 2>/dev/null || true
git add schemas/relic_io_badges.json
mv -f nft_asset_manifest.json manifest/ 2>/dev/null || true
git rm -f --cached nft_asset_manifest.json 2>/dev/null || true
git add manifest/nft_asset_manifest.json
mv -f dev_bounties.json bounties/ 2>/dev/null || true
git rm -f --cached dev_bounties.json 2>/dev/null || true
git add bounties/dev_bounties.json
mv -f nft_badge_ppc_flame_valve.json nfts/ 2>/dev/null || true
git rm -f --cached nft_badge_ppc_flame_valve.json 2>/dev/null || true
git add nfts/nft_badge_ppc_flame_valve.json
mv -f nft_badge_vickimac_flamekeeper.json nfts/ 2>/dev/null || true
git rm -f --cached nft_badge_vickimac_flamekeeper.json 2>/dev/null || true
git add nfts/nft_badge_vickimac_flamekeeper.json
mv -f nft_badge_museum_relic.json nfts/ 2>/dev/null || true
git rm -f --cached nft_badge_museum_relic.json 2>/dev/null || true
git add nfts/nft_badge_museum_relic.json
mv -f nft_badge_runs_doom.json nfts/ 2>/dev/null || true
git rm -f --cached nft_badge_runs_doom.json 2>/dev/null || true
git add nfts/nft_badge_runs_doom.json
mv -f nft_badge_dos_wifi_alchemist.json nfts/ 2>/dev/null || true
git rm -f --cached nft_badge_dos_wifi_alchemist.json 2>/dev/null || true
git add nfts/nft_badge_dos_wifi_alchemist.json
mv -f nft_badge_ham_radio_validator.json nfts/ 2>/dev/null || true
git rm -f --cached nft_badge_ham_radio_validator.json 2>/dev/null || true
git add nfts/nft_badge_ham_radio_validator.json
mv -f nft_badge_quickbasic_listener.json nfts/ 2>/dev/null || true
git rm -f --cached nft_badge_quickbasic_listener.json 2>/dev/null || true
git add nfts/nft_badge_quickbasic_listener.json
mv -f nft_badge_gravis_reclaimer.json nfts/ 2>/dev/null || true
git rm -f --cached nft_badge_gravis_reclaimer.json 2>/dev/null || true
git add nfts/nft_badge_gravis_reclaimer.json
mv -f nft_badge_pawpaw_bios_flame.json nfts/ 2>/dev/null || true
git rm -f --cached nft_badge_pawpaw_bios_flame.json 2>/dev/null || true
git add nfts/nft_badge_pawpaw_bios_flame.json
git commit -m "🔥 Final cleanup: removed stale root-level JSONs and synced structured folders"
git push origin main