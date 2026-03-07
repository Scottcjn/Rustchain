from setuptools import setup, find_packages

setup(
    name="clawrtc",
    version="1.0.0",
    description="RustChain Miner Setup Wizard - From Zero to Mining in 60 Seconds",
    author="sososonia-cyber",
    author_email="sososonia@example.com",
    url="https://github.com/Scottcjn/Rustchain",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "requests>=2.28.0",
        "psutil>=5.9.0",
        "ecdsa>=0.18.0",
    ],
    entry_points={
        "console_scripts": [
            "clawrtc=clawrtc.__init__:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: System :: Monitoring",
    ],
    python_requires=">=3.8",
)
