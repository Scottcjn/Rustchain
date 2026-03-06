from setuptools import setup, find_packages

setup(
    name="rustchain-beacon-skill",
    version="1.0.0",
    description="Beacon integration for RustChain Agent Economy",
    author="",
    author_email="",
    url="https://github.com/sososonia-cyber/rustchain-beacon-skill",
    packages=find_packages(),
    install_requires=[
        "requests>=2.28.0",
    ],
    extras_require={
        "beacon": ["beacon-skill>=0.1.0"],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    keywords="rustchain beacon agent economy blockchain",
)
