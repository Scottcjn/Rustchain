from setuptools import setup, find_packages

setup(
    name="rustchain-sdk",
    version="0.1.0",
    description="Python SDK for RustChain",
    author="RustChain Community",
    packages=find_packages(),
    install_requires=[
        "httpx>=0.23.0",
    ],
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
)
