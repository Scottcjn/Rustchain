# typed: strict
# frozen_string_literal: true

class Clawrtc < Formula
  include Language::Python::Virtualenv

  desc "RustChain miner - mine RTC tokens on any modern hardware"
  homepage "https://rustchain.org"
  url "https://files.pythonhosted.org/packages/da/23/44c4e03bfb3d03635594fe18afda4a7f157464641e7b035e9ddd91f8c48f/clawrtc-1.7.1.tar.gz"
  sha256 "d609eb74f9d833092595295893d5c616bfed2d6685ea21eeeca9dfcdddd30484"
  license "MIT"

  depends_on "python@3.12"

  resource "requests" do
    url "https://files.pythonhosted.org/packages/63/70/2bf7780ad2d390a8d301ad0b550f1581eadbd9a20f896afe06353c2a2913/requests-2.32.3.tar.gz"
    sha256 "55365417734eb18255590a9ff9eb97e9e1da868d4ccd6402399eaf68af20a760"
  end

  resource "urllib3" do
    url "https://files.pythonhosted.org/packages/aa/63/e53da845320b757bf29ef6a9062f5c669fe997973f966045cb019c3f4b66/urllib3-2.3.0.tar.gz"
    sha256 "aa63e53da845320b757bf29ef6a9062f5c669fe997973f966045cb019c3f4b66"
  end

  resource "charset-normalizer" do
    url "https://files.pythonhosted.org/packages/0d/58/5580c1716040bc89206c77d8f74418caf82ce519aae06450393ca73475d1/charset_normalizer-3.4.1.tar.gz"
    sha256 "91b36a978b5ae0ee86c394f5a54d6ef44db1de0815eb43de826d41d21e4af3de"
  end

  resource "idna" do
    url "https://files.pythonhosted.org/packages/f1/70/7703c29685631f5a7590aa73f1f1d3fa9a380e654b86af429e0934a32f7d/idna-3.10.tar.gz"
    sha256 "12f65c9b470abda6dc35cf8e63cc574b1c52b11df2c86030af0ac09b01b13ea9"
  end

  resource "certifi" do
    url "https://files.pythonhosted.org/packages/1c/ab/c9f1e32b7b1bf505bf26f0ef697775960db7932abeb7b516de930ba2705f/certifi-2025.1.31.tar.gz"
    sha256 "3d5da6925056f6f18f119200434a4780a94263f10d1c21d032a6f6b2baa20651"
  end

  resource "cryptography" do
    url "https://files.pythonhosted.org/packages/c7/67/545c79fe50f7af51dbad56d16b23fe33f63ee6a5d956b3cb68ea110cbe64/cryptography-44.0.1.tar.gz"
    sha256 "f51f5705ab27898afda1aaa430f34ad90dc117421057782022edf0600bec5f14"
  end

  resource "cffi" do
    url "https://files.pythonhosted.org/packages/fc/97/c783634659c2920c3fc70419e3af40972dbaf758daa229a7d6ea6135c90d/cffi-1.17.1.tar.gz"
    sha256 "1c39c6016c32bc48dd54561950ebd6836e1670f2ae46128f67cf49e789c52824"
  end

  resource "pycparser" do
    url "https://files.pythonhosted.org/packages/1d/b2/31537cf4b1ca988837256c910a668b553fceb8f069bedc4b1c826024b52c/pycparser-2.22.tar.gz"
    sha256 "491c8be9c040f5390f5bf44a5b07752bd07f56edf992381b05c701439eec10f6"
  end

  def install
    virtualenv_install_with_resources
  end

  def caveats
    <<~EOS
      RustChain Miner (clawrtc) installed successfully.

      Quick start:
        clawrtc mine --wallet YOUR_WALLET_ADDRESS

      For help:
        clawrtc --help

      More info: https://rustchain.org
    EOS
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/clawrtc --version 2>&1", 0).strip
  end
end
