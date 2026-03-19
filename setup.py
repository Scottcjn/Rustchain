// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="rustchain-agent-economy",
    version="1.0.0",
    author="Scott Johnson",
    author_email="scott@rustchain.io",
    description="Python SDK for RustChain Agent Economy API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Scottcjn/Rustchain",
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
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: System :: Distributed Computing",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.25.0",
        "typing_extensions>=4.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "flake8>=3.8",
        ],
    },
    entry_points={
        "console_scripts": [
            "rustchain-cli=rustchain_sdk.cli:main",
        ],
    },
    keywords="rustchain blockchain agent economy api sdk rip-302",
    project_urls={
        "Bug Reports": "https://github.com/Scottcjn/Rustchain/issues",
        "Source": "https://github.com/Scottcjn/Rustchain",
        "Documentation": "https://rustchain.io/docs",
    },
)