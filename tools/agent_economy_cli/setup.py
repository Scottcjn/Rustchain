from setuptools import setup, find_packages
setup(
    name="rustchain-ae",
    version="0.1.0",
    description="CLI for RustChain Agent Economy (RIP-302)",
    author="NOX Ventures",
    packages=find_packages(),
    entry_points={"console_scripts": ["rustchain-ae=rustchain_ae.cli:main"]},
    python_requires=">=3.8",
)
