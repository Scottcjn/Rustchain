#!/bin/bash

cd /mnt/c/Users/TRS/desktop/Rustchain_Repo_Scaffold/docs

# Use sed to replace the footer line in index.html
sed -i 's/Maintained by the Flameholder Foundation.*/Maintained by <strong>Elyan Labs<\/strong> — Powered by old iron & retro love 🧡<\/small><\/p>/' index.html

# Go back to root to commit
cd ..

git add docs/index.html
git commit -m "🔧 Updated GitHub Pages footer to Elyan Labs"
git push origin main