from setuptools import setup, find_packages

setup(
    name="rustchain-monitor",
    version="1.0.0",
    author="Thibault (RavMonSOL)",
    description="CLI tool for monitoring RustChain network health, miners, and epoch",
    py_modules=["rustchain_monitor"],
    install_requires=[
        "requests>=2.25.0",
    ],
    entry_points={
        "console_scripts": [
            "rustchain-monitor=rustchain_monitor:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)
