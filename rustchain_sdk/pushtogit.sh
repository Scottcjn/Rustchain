#!/bin/bash

mkdir -p media

# Move images
mv rustchain_hero_terminal.png media/
mv blockchain_validators_vintage.png media/
mv nft_badge_preview_grid.png media/
mv join_the_flamekeepers.png media/
mv rustchain_promo_banner.png media/
mv elyan_logo.png media/

# Optional: zip repo for distribution
zip -r rustchain_web_package.zip index.html media/

# Git operations
git add index.html media/ rustchain_web_package.zip
git commit -m "Added updated HTML landing page with media assets"
git push origin main
