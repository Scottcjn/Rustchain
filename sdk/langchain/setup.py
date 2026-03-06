from setuptools import setup, find_packages

setup(
    name="rustchain-langchain",
    version="1.0.0",
    description="LangChain tools for RustChain Agent Economy",
    author="",
    author_email="",
    url="https://github.com/sososonia-cyber/rustchain-agent-langchain",
    packages=find_packages(),
    install_requires=[
        "langchain>=0.1.0",
        "langchain-core>=0.1.0",
        "requests>=2.28.0",
        "pydantic>=2.0.0",
    ],
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
    keywords="langchain rustchain blockchain agent economy",
)
