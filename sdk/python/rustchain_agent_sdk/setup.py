"""
Setup script for rustchain-agent-sdk
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read long description from README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="rustchain-agent-sdk",
    version="1.0.0",
    author="sososonia-cyber",
    author_email="sososonia@example.com",
    description="Python SDK for RustChain RIP-302 Agent Economy",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sososonia-cyber/Rustchain",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        # No external dependencies - uses only stdlib
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "rustchain-agent=rustchain_agent_sdk.cli:main",
        ],
    },
    keywords="rustchain blockchain agent economy sdk",
    project_urls={
        "Bug Reports": "https://github.com/sososonia-cyber/Rustchain/issues",
        "Source": "https://github.com/sososonia-cyber/Rustchain",
    },
)
