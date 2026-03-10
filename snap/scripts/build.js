#!/usr/bin/env node
/**
 * RustChain Snap Build Script
 *
 * Bundles the snap source code for MetaMask Snap deployment.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const SRC_DIR = path.join(__dirname, '..', 'src');
const DIST_DIR = path.join(__dirname, '..', 'dist');
const SNAP_MANIFEST = path.join(__dirname, '..', 'snap.manifest.json');

/**
 * Simple bundler that concatenates source files
 */
function bundle() {
  console.log('Building RustChain Snap...');

  // Ensure dist directory exists
  if (!fs.existsSync(DIST_DIR)) {
    fs.mkdirSync(DIST_DIR, { recursive: true });
  }

  // Read source file
  const sourcePath = path.join(SRC_DIR, 'index.js');
  let source = fs.readFileSync(sourcePath, 'utf8');

  // Add module wrapper for snap execution
  const bundled = `
// RustChain Snap Bundle
// Generated: ${new Date().toISOString()}

${source}

// Export for snap execution
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { onRpcRequest };
}
`.trim();

  // Write bundled file
  const outputPath = path.join(DIST_DIR, 'bundle.js');
  fs.writeFileSync(outputPath, bundled);

  // Calculate SHA-256 checksum
  const shasum = crypto.createHash('sha256').update(bundled).digest('hex');
  console.log(`Bundle SHA-256: ${shasum}`);

  // Update manifest with shasum
  const manifest = JSON.parse(fs.readFileSync(SNAP_MANIFEST, 'utf8'));
  manifest.source.shasum = shasum;
  fs.writeFileSync(SNAP_MANIFEST, JSON.stringify(manifest, null, 2));

  console.log(`Bundle written to ${outputPath}`);
  console.log('Build complete!');
}

// Run build
bundle();
