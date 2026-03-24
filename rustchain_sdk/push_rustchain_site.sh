#!/bin/bash

# Ensure media folder exists
mkdir -p docs/media

# Move images into media folder
mv rustchain_hero_terminal.png docs/media/
mv blockchain_validators_vintage.png docs/media/
mv nft_badge_preview_grid.png docs/media/
mv join_the_flamekeepers.png docs/media/
mv rustchain_promo_banner.png docs/media/
mv elyan_logo.png docs/media/

# Optional: zip the landing site for distribution
cd docs
zip -r rustchain_landing_bundle.zip index.html media/
cd ..

# Git add, commit, and push
git add docs/index.html docs/media/ docs/rustchain_landing_bundle.zip
git commit -m "🌐 GitHub Pages: Added landing page with RustChain media visuals"
git push origin main