"""
RustChain SDK Setup
pip install rustchain — Python SDK for RustChain blockchain
Bounty Wallet (RTC): eB51DWp1uECrLZRLsE2cnyZUzfRWvzUzaJzkatTpQV9
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="rustchain",
    version="0.2.0",
    author="sungdark",
    author_email="sungdark@proton.me",
    description="Python SDK for RustChain blockchain network — pip install rustchain",
    package_name="rustchain",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Scottcjn/Rustchain",
    project_urls={
        "Bounty": "https://github.com/Scottcjn/rustchain-bounties/issues/2297",
        "Explorer": "https://rustchain.org",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: HTTP Clients",
        "Topic :: Office/Business :: Financial",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "async": ["aiohttp>=3.8.0"],
    },
    entry_points={
        "console_scripts": [
            "rustchain=rustchain.cli:main",
        ],
    },
)
