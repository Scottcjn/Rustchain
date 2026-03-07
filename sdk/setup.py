"""
Setup configuration for RustChain SDK

Includes core blockchain client and RIP-302 Agent Economy SDK.
"""

from setuptools import setup, find_packages

# Read README for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="rustchain-sdk",
    version="1.0.0",
    author="RustChain Community",
    author_email="dev@rustchain.org",
    description="Python SDK for RustChain blockchain and Agent Economy (RIP-302)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Scottcjn/Rustchain",
    project_urls={
        "Bug Tracker": "https://github.com/Scottcjn/Rustchain/issues",
        "Documentation": "https://github.com/Scottcjn/Rustchain/tree/main/sdk",
        "Source Code": "https://github.com/Scottcjn/Rustchain",
        "Agent Economy": "https://github.com/Scottcjn/Rustchain/tree/main/sdk/docs/AGENT_ECONOMY_SDK.md",
    },
    packages=find_packages(exclude=["tests", "examples"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Blockchain",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Environment :: Console",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.28.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-mock>=3.10",
            "pytest-cov>=4.0",
            "black>=23.0",
            "mypy>=1.0",
            "ruff>=0.1.0",
        ],
        "examples": [
            "asyncio",
        ],
    },
    keywords="rustchain blockchain crypto proof-of-antiquity agent-economy x402 payments reputation bounties",
    license="MIT",
    include_package_data=True,
    package_data={
        "rustchain": ["py.typed"],
    },
)
