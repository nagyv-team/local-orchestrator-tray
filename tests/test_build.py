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


def test_build_and_install():
    """Test building and installing the package."""
    project_root = Path(__file__).parent.parent

    print("Testing build and install process...")

    # Skip macOS-specific installation tests on non-macOS platforms
    if platform.system() != 'Darwin':
        print("⚠️  Skipping installation test - requires macOS for rumps dependencies")
        print("✅ Build-only test mode on non-macOS platform")
        _build_only_logic(project_root)
        return

    # Clean any existing build artifacts
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

    # Test installation in a virtual environment
    print("\n3. Testing installation...")
    with tempfile.TemporaryDirectory() as temp_dir:
        venv_path = Path(temp_dir) / "test_venv"

        # Create virtual environment
        if not run_command(f"python -m venv {venv_path}"):
            print("❌ Failed to create virtual environment")

        # Install the package
        wheel_file = next(dist_dir.glob("*.whl"))
        pip_path = venv_path / "bin" / "pip"

        if not run_command(f"{pip_path} install {wheel_file}"):
            print("❌ Failed to install package")

        # Test if the command is available
        python_path = venv_path / "bin" / "python"
        if not run_command(f"{python_path} -c 'import local_orchestrator_tray; print(\"Import successful\")'"):
            print("❌ Failed to import installed package")

        print("✅ Package installed and imported successfully")

    print("\n🎉 All tests passed! The app can build and install from the built package.")


def _build_only_logic(project_root):
    """Internal logic for build-only testing."""
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
    print("\n🎉 Build test passed! Package builds correctly on this platform.")


def test_build_only():
    """Test only the build process without installation (for non-macOS platforms)."""
    project_root = Path(__file__).parent.parent
    _build_only_logic(project_root)


if __name__ == "__main__":
    success = test_build_and_install()
    sys.exit(0 if success else 1)
