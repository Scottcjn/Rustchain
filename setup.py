from setuptools import setup, find_packages

setup(
    name='clawrtc',
    version='1.5.0',
    description='RustChain CLI Tool',
    author='RustChain Team',
    py_modules=['clawrtc'],
    entry_points={
        'console_scripts': [
            'clawrtc=clawrtc:main',
        ],
    },
    python_requires='>=3.8',
)
