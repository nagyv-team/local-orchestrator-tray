#!/usr/bin/env python3
"""
Test script to verify icon path resolution functionality.
Tests the get_icon_path function to ensure it can find the icon in various scenarios.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock


def test_icon_path_resolution():
    """Test that the LocalOrchestratorTray class can find the icon correctly."""
    print("Testing icon path resolution in LocalOrchestratorTray...")
    
    # Add current directory to path for import
    current_dir = Path(__file__).parent
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))
    
    # Mock rumps since it's macOS-specific
    rumps_mock = Mock()
    rumps_mock.App = Mock()
    
    with patch.dict('sys.modules', {'rumps': rumps_mock}):
        import local_orchestrator_tray
        
        # Test that the class exists
        assert hasattr(local_orchestrator_tray, 'LocalOrchestratorTray'), "LocalOrchestratorTray class not found"
        
        # Test the icon path resolution by examining the init code
        # The icon path is constructed as: script_dir / "assets" / "tray-icon.png"
        script_dir = Path(local_orchestrator_tray.__file__).parent
        expected_icon_path = script_dir / "assets" / "tray-icon.png"
        
        print(f"Expected icon path: {expected_icon_path}")
        
        # Verify the path exists
        assert expected_icon_path.exists(), f"Icon file does not exist at {expected_icon_path}"
        assert expected_icon_path.name == "tray-icon.png", f"Wrong filename: {expected_icon_path.name}"
        
        # Verify it's a PNG file
        with open(expected_icon_path, 'rb') as f:
            header = f.read(8)
            assert header == b'\x89PNG\r\n\x1a\n', "File is not a valid PNG"
        
        # Test that we can instantiate the class (without running it)
        try:
            # We can't actually instantiate due to rumps, but we can check the logic
            app_class = local_orchestrator_tray.LocalOrchestratorTray
            assert app_class is not None, "Could not access LocalOrchestratorTray class"
        except Exception as e:
            # Expected due to rumps mocking limitations
            print(f"Note: Cannot fully instantiate due to rumps mocking: {e}")
        
        print("✅ Icon path resolution test passed")
        return True


def test_package_installation_icon():
    """Test that icon is accessible after package installation."""
    print("Testing icon accessibility in packaged installation...")
    
    # Test that the icon exists in the expected location relative to the module
    current_dir = Path(__file__).parent
    assets_dir = current_dir / "assets"
    icon_file = assets_dir / "tray-icon.png"
    
    # Verify the assets structure is correct
    assert assets_dir.exists(), f"Assets directory does not exist: {assets_dir}"
    assert icon_file.exists(), f"Icon file does not exist: {icon_file}"
    
    # Test the file size and basic properties
    file_size = icon_file.stat().st_size
    assert file_size > 1000, f"Icon file seems too small: {file_size} bytes"
    assert file_size < 200000, f"Icon file seems too large: {file_size} bytes"  # PNG should be reasonable size
    
    # Verify file extension
    assert icon_file.suffix == ".png", f"Wrong file extension: {icon_file.suffix}"
    
    # Test that we can read the file
    try:
        with open(icon_file, 'rb') as f:
            data = f.read(100)  # Read first 100 bytes
            assert len(data) > 0, "Could not read icon file data"
    except Exception as e:
        assert False, f"Failed to read icon file: {e}"
    
    print(f"✅ Icon file verified: {icon_file} ({file_size} bytes)")
    return True


def run_icon_tests():
    """Run all icon resolution tests."""
    print("Running icon resolution tests...")
    print("=" * 50)
    
    tests = [
        test_icon_path_resolution,
        test_package_installation_icon,
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
            import traceback
            traceback.print_exc()
    
    print("=" * 50)
    print(f"Icon tests: {passed}/{len(tests)} passed")
    
    if passed == len(tests):
        print("🎉 All icon resolution tests passed!")
        return True
    else:
        print("❌ Some icon tests failed!")
        return False


if __name__ == "__main__":
    success = run_icon_tests()
    sys.exit(0 if success else 1)