from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="rustchain-sdk",
    version="0.1.0",
    author="AI Bounty Hunter",
    author_email="dunyuzoush@github.com",
    description="Zero-dependency Python SDK for RustChain blockchain",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dunyuzoush-ch/rustchain-sdk",
    packages=find_packages(exclude=["tests*"]),
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.28.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
        ]
    },
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
    ],
    keywords="rustchain, blockchain, sdk, cryptocurrency",
    project_urls={
        "Bug Reports": "https://github.com/dunyuzoush-ch/rustchain-sdk/issues",
        "Source": "https://github.com/dunyuzoush-ch/rustchain-sdk",
    },
)
