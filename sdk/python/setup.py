from setuptools import setup, find_packages

setup(
    name="rustchain-agent-economy",
    version="0.1.0",
    description="Python async SDK for RustChain Agent Economy (RIP-302)",
    packages=find_packages(),
    install_requires=["httpx>=0.24.0"],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
