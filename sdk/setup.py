"""
Setup configuration for RustChain SDK
"""

from setuptools import setup

# Read README for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="rustchain-sdk",
    version="0.1.0",
    author="RustChain Community",
    author_email="dev@rustchain.org",
    description="Python SDK for RustChain blockchain",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Scottcjn/Rustchain",
    project_urls={
        "Bug Tracker": "https://github.com/Scottcjn/Rustchain/issues",
        "Documentation": "https://github.com/Scottcjn/Rustchain#readme",
        "Source Code": "https://github.com/Scottcjn/Rustchain",
    },
    packages=["rustchain"],
    classifiers=[
        "Development Status :: 3 - Alpha",
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
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.28.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-mock>=3.10",
            "black>=23.0",
            "mypy>=1.0",
        ],
    },
    keywords="rustchain blockchain crypto proof-of-antiquity",
    license="MIT",
)
