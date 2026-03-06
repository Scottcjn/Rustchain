"""
RustChain SDK Setup
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="rustchain-sdk",
    version="0.1.0",
    author="sososonia-cyber",
    author_email="sososonia@example.com",
    description="Python SDK for RustChain blockchain network",
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
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: HTTP Clients",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "async": ["aiohttp>=3.8.0"],
    },
    entry_points={
        "console_scripts": [
            "rustchain-cli=rustchain_sdk.cli:main",
        ],
    },
)
