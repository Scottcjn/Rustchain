// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="rustchain-sdk",
    version="1.0.0",
    author="RustChain Team",
    author_email="dev@rustchain.org",
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
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Office/Business :: Financial",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.28.0",
        "pydantic>=1.10.0",
        "typing-extensions>=4.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=1.0.0",
        ],
        "async": [
            "aiohttp>=3.8.0",
            "asyncio",
        ],
    },
    entry_points={
        "console_scripts": [
            "rustchain-cli=rustchain.cli:main",
        ],
    },
    keywords="rustchain blockchain agent economy api sdk cryptocurrency",
    project_urls={
        "Bug Reports": "https://github.com/Scottcjn/Rustchain/issues",
        "Source": "https://github.com/Scottcjn/Rustchain",
        "Documentation": "https://docs.rustchain.org",
    },
    include_package_data=True,
    zip_safe=False,
)