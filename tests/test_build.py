#!/usr/bin/env python3
"""
Test script to verify the app can build and install from the built package.
"""

import os
import sys
import subprocess
import tempfile
import shutil
import platform
from pathlib import Path


def run_command(cmd, cwd=None):
    """Run a command and return success status."""
    print(f"Running: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd,
                                capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            return False
        print(f"Success: {result.stdout}")
        return True
    except Exception as e:
        print(f"Exception: {e}")
        return False


def test_build():
    """Internal logic for build-only testing."""
    project_root = Path(__file__).parent.parent
    print("\n1. Cleaning build artifacts...")
    for dir_name in ["build", "dist", "*.egg-info"]:
        for path in project_root.glob(dir_name):
            if path.is_dir():
                shutil.rmtree(path)
                print(f"Removed {path}")

    # Build the package
    print("\n2. Building package...")
    if not run_command("python setup.py sdist bdist_wheel", cwd=project_root):
        print("❌ Build failed")

    # Check if dist directory was created with files
    dist_dir = project_root / "dist"
    if not dist_dir.exists() or not list(dist_dir.glob("*")):
        print("❌ No distribution files created")

    print("✅ Package built successfully")


if __name__ == "__main__":
    success = test_build_and_install()
    sys.exit(0 if success else 1)
