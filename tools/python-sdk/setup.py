from setuptools import setup, find_packages

setup(
    name="rustchain",
    version="0.2.0",
    packages=find_packages(),
    install_requires=["requests>=2.25.0"],
    python_requires=">=3.8",
    description="Python SDK for the RustChain blockchain API",
)
