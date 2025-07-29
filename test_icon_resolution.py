#!/usr/bin/env python3
"""
Test script to verify the icon path resolution fix.
This tests the _find_icon_path method without requiring rumps.
"""

import sys
from pathlib import Path


def test_find_icon_path():
    """Test the icon path resolution logic."""
    try:
        # Python 3.9+ approach using importlib.resources
        from importlib import resources
        try:
            # Try the new API first (Python 3.9+)
            ref = resources.files('local_orchestrator_tray').joinpath(
                'assets', 'tray-icon.png')
            with resources.as_file(ref) as path:
                return str(path)
        except AttributeError:
            # Fallback for older Python versions
            import local_orchestrator_tray.assets
            with resources.path(local_orchestrator_tray.assets, 'tray-icon.png') as path:
                return str(path)
    except (FileNotFoundError, ModuleNotFoundError, ImportError, TypeError) as e:
        print(f"Resource loading failed: {e}")
        # Development fallback - check multiple locations
        icon_path = Path(__file__).parent / 'assets' / 'tray-icon.png'
        if icon_path.exists():
            return str(icon_path)

        # If we can't find the icon, log and continue without it
        print(f"Warning: Could not find tray-icon.png in any expected location")
        return None


if __name__ == "__main__":
    print("Testing icon path resolution...")

    # Add current directory to Python path
    sys.path.insert(0, '.')

    icon_path = test_find_icon_path()

    if icon_path:
        print(f"SUCCESS: Icon path resolved to: {icon_path}")
        print(f"Icon file exists: {Path(icon_path).exists()}")
        if Path(icon_path).exists():
            print(f"Icon file size: {Path(icon_path).stat().st_size} bytes")
    else:
        print("FAILURE: Could not resolve icon path")

    print("\nTest completed!")
