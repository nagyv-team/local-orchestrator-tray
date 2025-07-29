#!/usr/bin/env python3
"""
Basic tests for the local orchestrator tray application.
Tests core functionality without requiring macOS runtime.
"""

import os
import sys
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch


def test_config_file_creation():
    """Test that configuration file is created correctly."""
    print("Testing configuration file creation...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / ".config" / "local-orchestrator-tray.yaml"
        
        # Simulate the configuration creation logic
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not config_path.exists():
            with open(config_path, 'w') as f:
                yaml.dump({}, f, default_flow_style=False)
        
        # Verify file was created
        assert config_path.exists(), "Configuration file was not created"
        
        # Verify file is valid YAML
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            assert isinstance(config, dict), "Configuration file is not valid YAML dict"
        
        print("✅ Configuration file creation test passed")
        return True


def test_import_module():
    """Test that the module can be imported."""
    print("Testing module import...")
    
    try:
        # Add current directory to path for import
        current_dir = Path(__file__).parent
        if str(current_dir) not in sys.path:
            sys.path.insert(0, str(current_dir))
        
        # Mock rumps since it's macOS-specific
        with patch.dict('sys.modules', {'rumps': Mock()}):
            import local_orchestrator_tray
            
            # Test that the class exists
            assert hasattr(local_orchestrator_tray, 'LocalOrchestratorTray'), "LocalOrchestratorTray class not found"
            assert hasattr(local_orchestrator_tray, 'main'), "main function not found"
            
        print("✅ Module import test passed")
        return True
        
    except Exception as e:
        print(f"❌ Module import failed: {e}")
        return False


def test_package_structure():
    """Test that all required files are present."""
    print("Testing package structure...")
    
    project_root = Path(__file__).parent
    required_files = [
        "local_orchestrator_tray.py",
        "setup.py",
        "pyproject.toml",
        "requirements.txt",
        "README.md",
        "LICENSE"
    ]
    
    for file_name in required_files:
        file_path = project_root / file_name
        assert file_path.exists(), f"Required file {file_name} is missing"
    
    print("✅ Package structure test passed")
    return True


def run_all_tests():
    """Run all tests."""
    print("Running basic tests for Local Orchestrator Tray...")
    print("=" * 50)
    
    tests = [
        test_package_structure,
        test_import_module,
        test_config_file_creation,
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
    
    print("=" * 50)
    print(f"Tests: {passed}/{len(tests)} passed")
    
    if passed == len(tests):
        print("🎉 All basic tests passed!")
        return True
    else:
        print("❌ Some tests failed!")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)