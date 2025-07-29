#!/usr/bin/env python3
"""
Setup script for Local Orchestrator Tray application.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README file
readme_path = Path(__file__).parent / "README.md"
with open(readme_path, "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
with open(requirements_path, "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="local-orchestrator-tray",
    version="0.1.0",
    author="nagyv-team",
    description="A Mac system tray application that listens for events in a Telegram chat",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/nagyv-team/local-orchestrator-tray",
    packages=find_packages(),
    package_data={
        'local_orchestrator_tray': ['assets/*'],
    },
    include_package_data=True,
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "local-orchestrator-tray=local_orchestrator_tray:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: Public Domain",
        "Operating System :: MacOS",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    platforms=["MacOS"],
)