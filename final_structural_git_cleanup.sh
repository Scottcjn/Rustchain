#!/bin/bash
cd /mnt/c/Users/TRS/desktop/Rustchain_Repo_Scaffold
mkdir -p badges
mkdir -p tools
mkdir -p docs
mkdir -p scripts
mv -f badge_uber_dev_forge.json badges/ 2>/dev/null || true
git rm -f --cached badge_uber_dev_forge.json 2>/dev/null || true
git add badges/badge_uber_dev_forge.json
mv -f bios_pawpaw_detector.py tools/ 2>/dev/null || true
git rm -f --cached bios_pawpaw_detector.py 2>/dev/null || true
git add tools/bios_pawpaw_detector.py
mv -f anti_vm.py tools/ 2>/dev/null || true
git rm -f --cached anti_vm.py 2>/dev/null || true
git add tools/anti_vm.py
mv -f ergo_wrapper.py tools/ 2>/dev/null || true
git rm -f --cached ergo_wrapper.py 2>/dev/null || true
git add tools/ergo_wrapper.py
mv -f gpu_display_detector.py tools/ 2>/dev/null || true
git rm -f --cached gpu_display_detector.py 2>/dev/null || true
git add tools/gpu_display_detector.py
mv -f os_detector.py tools/ 2>/dev/null || true
git rm -f --cached os_detector.py 2>/dev/null || true
git add tools/os_detector.py
mv -f quantum_flux_validator.py tools/ 2>/dev/null || true
git rm -f --cached quantum_flux_validator.py 2>/dev/null || true
git add tools/quantum_flux_validator.py
mv -f validator_core.py tools/ 2>/dev/null || true
git rm -f --cached validator_core.py 2>/dev/null || true
git add tools/validator_core.py
mv -f validator_core_with_badge.py tools/ 2>/dev/null || true
git rm -f --cached validator_core_with_badge.py 2>/dev/null || true
git add tools/validator_core_with_badge.py
mv -f weighted_decryption.py tools/ 2>/dev/null || true
git rm -f --cached weighted_decryption.py 2>/dev/null || true
git add tools/weighted_decryption.py
mv -f chain_architecture.md docs/ 2>/dev/null || true
git rm -f --cached chain_architecture.md 2>/dev/null || true
git add docs/chain_architecture.md
mv -f tokenomics_v1.md docs/ 2>/dev/null || true
git rm -f --cached tokenomics_v1.md 2>/dev/null || true
git add docs/tokenomics_v1.md
mv -f update_git_rustchain.sh scripts/ 2>/dev/null || true
git rm -f --cached update_git_rustchain.sh 2>/dev/null || true
git add scripts/update_git_rustchain.sh
git commit -m "🧹 Final structural pass: moved leftover tools, badges, and docs into folders"
git push origin main