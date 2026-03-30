# typed: strict
# frozen_string_literal: true

# Homebrew formula for BCOS v2 Engine — Beacon Certified Open Source verification
# Issue: https://github.com/Scottcjn/rustchain-bounties/issues/2293
class Bcos < Formula
  desc "BCOS v2 Engine — Beacon Certified Open Source verification tool"
  homepage "https://github.com/Scottcjn/Rustchain"
  url "https://github.com/Scottcjn/Rustchain/archive/refs/tags/v1.0.0-miner.tar.gz"
  version "1.0.0-miner"
  sha256 "a2e16d61e62941592f7da4a688a78a2197429e8e685e04f3748b5bc9c5a38dcf"
  license "MIT"

  depends_on "python@3.11"
  depends_on "pip-audit" => :recommended
  depends_on "semgrep" => :recommended

  def install
    # Install Python scripts to libexec
    libexec.install "tools/bcos_engine.py"
    libexec.install "tools/bcos_spdx_check.py"
    libexec.install "tools/bcos_compliance_map.json"

    # Create virtualenv with Python 3.11
    venv = virtualenv_create(libexec, "python3.11")

    # Install requirements if present
    virtualenv_install_with_resources(venv) if File.exist?("requirements.txt")

    # Install bcos command (main BCOS engine)
    (bin/"bcos").write <<~EOS
      #!/bin/bash
      exec "#{libexec}/bin/python" "#{libexec}/bcos_engine.py" "$@"
    EOS
    chmod 0755, bin/"bcos"

    # Install bcos-spdx helper command
    (bin/"bcos-spdx").write <<~EOS
      #!/bin/bash
      exec "#{libexec}/bin/python" "#{libexec}/bcos_spdx_check.py" "$@"
    EOS
    chmod 0755, bin/"bcos-spdx"
  end

  def caveats
    <<~EOS
      BCOS v2 Engine installed successfully.

      QUICK START:
        1. Navigate to a repository: cd /path/to/repo
        2. Run scan: bcos .
        3. View JSON report: bcos . --json

      TIER THRESHOLDS:
        - L0: >= 40 points (basic verification)
        - L1: >= 60 points (standard certification)
        - L2: >= 80 points + human reviewer signature (premium)

      TRUST SCORE COMPONENTS:
        - License Compliance:    20 pts (SPDX headers, OSI licenses)
        - Vulnerability Scan:    25 pts (0 critical/high CVEs)
        - Static Analysis:       20 pts (semgrep errors/warnings)
        - SBOM Completeness:     10 pts (CycloneDX generated)
        - Dependency Freshness:   5 pts (% at latest version)
        - Test Evidence:         10 pts (test suite present)
        - Review Attestation:     5 pts (L0=0, L1=5, L2=10)

      RECOMMENDED TOOLS:
        Install for full functionality:
          brew install pip-audit semgrep

      OUTPUT:
        - JSON report: bcos_report.json (in scanned directory)
        - Certificate: BCOS-<id>.json (if tier met)
        - On-chain anchor: via rustchain.org/bcos/verify/<cert-id>

      REUSABLE GITHUB ACTION:
        Any repo can use BCOS with:
          uses: Scottcjn/bcos-action@v1
          with:
            tier: L1

      SOURCE: https://github.com/Scottcjn/Rustchain
      BOUNTY: https://github.com/Scottcjn/rustchain-bounties/issues/2293
    EOS
  end

  test do
    help_output = shell_output("#{bin}/bcos --help 2>&1", 1)
    assert_match "BCOS", help_output

    spdx_output = shell_output("#{bin}/bcos-spdx --help 2>&1", 1)
    assert_match "SPDX", spdx_output

    system "#{libexec}/bin/python", "#{libexec}/bcos_engine.py", "--help"
  end
end
