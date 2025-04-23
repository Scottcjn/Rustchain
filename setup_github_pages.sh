#!/bin/bash
cd /mnt/c/Users/TRS/desktop/Rustchain_Repo_Scaffold
mkdir -p docs
mv index.html docs/index.html
git add docs/index.html
git commit -m '🌐 Added GitHub Pages site at /docs/index.html'
git push origin main