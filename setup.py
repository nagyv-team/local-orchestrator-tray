#!/usr/bin/env python3
"""
Setup script for Local Orchestrator Tray application.
Configured for py2app standalone Mac app building.
"""

import sys
from setuptools import setup, find_packages
from pathlib import Path

# Read README file
readme_path = Path(__file__).parent / "README.md"
with open(readme_path, "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Use pyproject.toml dependencies to avoid conflicts
# Only use requirements.txt for Mac-specific dependencies that aren't in pyproject.toml
requirements = [
    "rumps>=0.4.0",
    "PyYAML>=6.0",
    "python-telegram-bot>=20.7",
    "toml>=0.10.2",
]

# py2app OPTIONS configuration
OPTIONS = {
    'argv_emulation': True,  # Handle file associations properly on Mac
    'strip': True,           # Strip debug symbols to reduce size
    'optimize': 2,           # Python optimization level
    'iconfile': 'assets/tray-icon.png',  # App icon
    'plist': {
        'CFBundleName': 'Local Orchestrator Tray',
        'CFBundleDisplayName': 'Local Orchestrator Tray',
        'CFBundleIdentifier': 'com.nagyv-team.local-orchestrator-tray',
        'CFBundleVersion': '0.1.0',
        'CFBundleShortVersionString': '0.1.0',
        'NSHighResolutionCapable': True,
        'LSUIElement': True,  # Background app (no dock icon)
        'NSPrincipalClass': 'NSApplication',
    },
    'packages': [
        'rumps', 'yaml', 'telegram', 'toml',
        'anyio', 'httpx', 'sniffio', 'idna',  # Required for telegram bot HTTP functionality
        'typing_extensions', 'certifi', 'h11', 'httpcore'  # Additional HTTP dependencies
    ],  # Ensure these packages are included
    'includes': ['local_orchestrator_tray'],
    'excludes': ['tkinter'],  # Exclude unnecessary packages
    'resources': [
        'assets/',
        'local_orchestrator_tray/assets/',
    ],
}

# Platform-specific configuration
if sys.platform == 'darwin':
    # Mac-specific setup for py2app
    extra_options = dict(
        app=['local_orchestrator_tray/main.py'],
        setup_requires=['py2app>=0.28.0'],
        options={'py2app': OPTIONS},
    )
else:
    # Non-Mac platforms
    extra_options = dict(
        entry_points={
            "console_scripts": [
                "local-orchestrator-tray=local_orchestrator_tray:main",
            ],
        },
    )

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
    # install_requires handled by pyproject.toml dependencies
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
    **extra_options  # Apply platform-specific options
)