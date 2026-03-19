// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from setuptools import setup, find_packages

setup(
    name="rustchain-sdk",
    version="0.1.0",
    description="Python SDK for RustChain Agent Economy API",
    long_description="A pip-installable Python SDK for the RustChain Agent Economy with full API coverage including job posting, claiming, delivery, and reputation management.",
    long_description_content_type="text/plain",
    author="RustChain Team",
    author_email="dev@rustchain.org",
    url="https://github.com/Scottcjn/Rustchain",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Database :: Database Engines/Servers",
    ],
    python_requires=">=3.8",
    install_requires=[
        "flask>=2.0.0",
        "requests>=2.25.0",
        "cryptography>=3.4.0",
        "python-dotenv>=0.19.0",
        "jsonschema>=4.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "pytest-cov>=2.12.0",
            "black>=21.0.0",
            "flake8>=3.9.0",
            "mypy>=0.910",
        ],
        "blockchain": [
            "web3>=6.0.0",
            "solana>=0.30.0",
            "base58>=2.1.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "rustchain-node=node.rustchain_v2_integrated_v2.2.1_rip200:main",
            "rustchain-sdk=rustchain_sdk.cli:main",
        ],
    },
    package_data={
        "": ["*.sql", "*.json", "*.md"],
    },
    include_package_data=True,
    zip_safe=False,
    keywords="rustchain blockchain agent economy api sdk",
    project_urls={
        "Bug Reports": "https://github.com/Scottcjn/Rustchain/issues",
        "Source": "https://github.com/Scottcjn/Rustchain",
        "Documentation": "https://github.com/Scottcjn/Rustchain/wiki",
    },
)