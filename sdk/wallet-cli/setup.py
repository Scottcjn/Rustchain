"""
RustChain Wallet CLI Setup
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="rustchain-wallet-cli",
    version="0.1.0",
    author="sososonia-cyber",
    description="Command-line wallet tool for RustChain RTC tokens",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sososonia-cyber/RustChain",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8+",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.28.0",
    ],
    entry_points={
        "console_scripts": [
            "rustchain-wallet=rustchain_wallet.cli:main",
        ],
    },
)
