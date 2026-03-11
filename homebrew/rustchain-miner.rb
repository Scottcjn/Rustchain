# typed: strict
# frozen_string_literal: true

# Homebrew formula for RustChain Proof-of-Antiquity Miner
class RustchainMiner < Formula
  desc "RustChain Proof-of-Antiquity Miner - rewards vintage hardware"
  homepage "https://github.com/Scottcjn/Rustchain"
  url "https://github.com/Scottcjn/Rustchain/archive/refs/tags/v2.5.0.tar.gz"
  version "2.5.0"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000" # REPLACE with actual sha256
  license "MIT"

  depends_on "python@3.11"

  def install
    libexec.install "miners/macos/rustchain_mac_miner_v2.5.py" => "rustchain_miner.py"
    libexec.install "miners/macos/color_logs.py"
    libexec.install "miners/fingerprint_checks.py"

    venv = virtualenv_create(libexec, "python@3.11")
    virtualenv_install(venv, "miners/macos/requirements-miner.txt")

    (bin/"rustchain-miner").write <<~EOS
      #!/bin/bash
      exec "#{libexec}/bin/python" "#{libexec}/rustchain_miner.py" "$@"
    EOS
    chmod 0755, bin/"rustchain-miner"
  end

  def caveats
    <<~EOS
      RustChain Miner installed successfully.

      QUICK START:
        1. Get a wallet address (or use auto-generated)
        2. Run: rustchain-miner --wallet YOUR_WALLET_ID

      AUTO-START (launchd):
        The miner does NOT auto-start by default for security.
        To enable auto-start, run:
          brew services start rustchain-miner -- --wallet YOUR_WALLET_ID

        Or manually load the launchd plist:
          cp #{opt_prefix}/homebrew/opt/rustchain-miner/homebrew.mxcl.rustchain-miner.plist ~/Library/LaunchAgents/
          Edit wallet in plist, then:
          launchctl load ~/Library/LaunchAgents/homebrew.mxcl.rustchain-miner.plist

      MINING TIPS:
        - Vintage hardware (PowerPC G4/G5) earns 2.0-2.5x multiplier
        - Modern Macs (M1/M2/M3, Intel) earn 0.8x multiplier
        - Requires network connectivity to rustchain.org
        - Logs to stdout; use --headless for background operation

      SECURITY NOTES:
        - Never share your wallet ID
        - Miner runs as your user (no root required)
        - Checksums verified on download
        - Source: https://github.com/Scottcjn/Rustchain
    EOS
  end

  test do
    assert_match "RustChain", shell_output("#{libexec}/bin/python #{libexec}/rustchain_miner.py --help 2>&1", 1).strip
    system "#{libexec}/bin/pip", "show", "requests"
    assert_match "rustchain_miner", shell_output("#{bin}/rustchain-miner --help 2>&1", 1).strip
  end
end
