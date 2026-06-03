# typed: strict
# frozen_string_literal: true

# Homebrew formula for BCOS v2 Engine — Beacon Certified Open Source verification
class Bcos < Formula
  desc "BCOS v2 Engine — Beacon Certified Open Source verification"
  homepage "https://github.com/Scottcjn/Rustchain"
  url "https://github.com/Scottcjn/Rustchain/archive/refs/tags/v2.4.0.tar.gz"
  version "2.4.0"
  # SHA256 checksum computed from the GitHub release tarball.
  # To verify or update: curl -sSL "<url>" | sha256sum
  sha256 "5123df374138327ba506b47c64fc4069c5f08014c6b21d5a86064b962ad2fd1b"
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
    venv = virtualenv_create(libexec, "python@3.11")

    # Install requirements if present
    virtualenv_install(venv, "requirements.txt") if File.exist?("requirements.txt")

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
        - Review Attestation:    10 pts (L0=0, L1=5, L2=10)

      RECOMMENDED TOOLS:
        Install for full functionality:
          brew install pip-audit semgrep

      OUTPUT:
        - JSON report: bcos_report.json (in scanned directory)
        - Certificate: BCOS-<id>.json (if tier met)
        - On-chain anchor: via rustchain.org/bcos/verify/<cert-id>

      SECURITY NOTES:
        - Engine runs locally; no data sent externally by default
        - Optional: Anchor commitment on-chain via RustChain
        - Source: https://github.com/Scottcjn/Rustchain
    EOS
  end

  test do
    # Test bcos help output
    help_output = shell_output("#{bin}/bcos --help 2>&1", 1)
    assert_match "BCOS v2", help_output
    assert_match "Beacon Certified", help_output

    # Test bcos-spdx help output
    spdx_output = shell_output("#{bin}/bcos-spdx --help 2>&1", 1)
    assert_match "SPDX", spdx_output

    # Verify Python can run the engine directly
    system "#{libexec}/bin/python", "#{libexec}/bcos_engine.py", "--help"

    # Verify dependencies installed
    system "#{libexec}/bin/pip", "show", "blake2b" if File.exist?("#{libexec}/bin/pip")
  end
end
