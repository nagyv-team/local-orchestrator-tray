#!/usr/bin/env python3
"""
Test script to verify application startup and icon loading functionality.
Tests that the LocalOrchestratorTray application can initialize properly with the icon.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock


def test_application_initialization():
    """Test that the LocalOrchestratorTray application can initialize with proper icon."""
    print("Testing application initialization with icon...")
    
    # Add current directory to path for import
    current_dir = Path(__file__).parent
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))
    
    # Create comprehensive rumps mock
    rumps_mock = Mock()
    rumps_mock.App = MagicMock()
    
    # Mock the specific methods we expect to be called
    app_instance = MagicMock()
    rumps_mock.App.return_value = app_instance
    rumps_mock.clicked = lambda x: lambda f: f  # Mock decorator
    rumps_mock.quit_application = Mock()
    
    with patch.dict('sys.modules', {'rumps': rumps_mock}):
        import local_orchestrator_tray
        
        try:
            # Test application initialization
            app = local_orchestrator_tray.LocalOrchestratorTray()
            
            # Verify that rumps.App was called with correct parameters
            rumps_mock.App.assert_called_once()
            call_args = rumps_mock.App.call_args
            
            # Extract the arguments passed to rumps.App
            args, kwargs = call_args
            app_name = args[0] if args else kwargs.get('name', None)
            
            # Check that the app name is correct
            assert app_name == "Local Orchestrator", f"Wrong app name: {app_name}"
            
            # Check that icon parameter was passed and points to correct file
            if 'icon' in kwargs:
                icon_path = kwargs['icon']
                print(f"Icon path passed to rumps.App: {icon_path}")
                
                # Verify the icon path exists and is correct
                assert Path(icon_path).exists(), f"Icon file doesn't exist: {icon_path}"
                assert Path(icon_path).name == "tray-icon.png", f"Wrong icon filename: {Path(icon_path).name}"
            
            # Verify the app has the expected attributes
            assert hasattr(app, 'config_path'), "App should have config_path attribute"
            assert hasattr(app, 'menu'), "App should have menu attribute"
            
            # Verify config path is set correctly
            expected_config = Path.home() / ".config" / "local-orchestrator-tray.yaml"
            assert app.config_path == expected_config, f"Wrong config path: {app.config_path}"
            
            print("✅ Application initialization test passed")
            return True
            
        except Exception as e:
            print(f"❌ Application initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_configuration_file_handling():
    """Test that the application correctly handles configuration file creation."""
    print("Testing configuration file handling...")
    
    current_dir = Path(__file__).parent
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))
    
    # Create comprehensive rumps mock
    rumps_mock = Mock()
    rumps_mock.App = MagicMock()
    rumps_mock.clicked = lambda x: lambda f: f
    
    with patch.dict('sys.modules', {'rumps': rumps_mock}):
        import local_orchestrator_tray
        
        # Test configuration file creation in a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_home = Path(temp_dir)
            
            # Mock Path.home() to return our temporary directory
            with patch('pathlib.Path.home', return_value=temp_home):
                try:
                    app = local_orchestrator_tray.LocalOrchestratorTray()
                    
                    expected_config = temp_home / ".config" / "local-orchestrator-tray.yaml"
                    
                    # Verify config file was created
                    assert expected_config.exists(), f"Config file was not created: {expected_config}"
                    
                    # Verify config file is valid YAML
                    import yaml
                    with open(expected_config, 'r') as f:
                        config = yaml.safe_load(f)
                        assert isinstance(config, dict), "Config file should contain a dictionary"
                    
                    print(f"✅ Configuration file created at: {expected_config}")
                    return True
                    
                except Exception as e:
                    print(f"❌ Configuration handling failed: {e}")
                    import traceback
                    traceback.print_exc()
                    return False


def test_menu_functionality():
    """Test that the application menu is set up correctly."""
    print("Testing menu functionality...")
    
    current_dir = Path(__file__).parent
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))
    
    # Create comprehensive rumps mock
    rumps_mock = Mock()
    rumps_mock.App = MagicMock()
    rumps_mock.clicked = lambda x: lambda f: f
    
    with patch.dict('sys.modules', {'rumps': rumps_mock}):
        import local_orchestrator_tray
        
        try:
            app = local_orchestrator_tray.LocalOrchestratorTray()
            
            # Verify menu structure
            expected_menu = [
                "Open configuration",
                None,  # Separator
                "Quit"
            ]
            
            assert hasattr(app, 'menu'), "App should have menu attribute"
            assert app.menu == expected_menu, f"Menu structure incorrect: {app.menu}"
            
            # Verify menu handler methods exist
            assert hasattr(app, 'open_configuration'), "Missing open_configuration method"
            assert hasattr(app, 'quit_application'), "Missing quit_application method"
            
            print("✅ Menu functionality test passed")
            return True
            
        except Exception as e:
            print(f"❌ Menu functionality test failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def run_application_tests():
    """Run all application startup tests."""
    print("Running application startup tests...")
    print("=" * 60)
    
    tests = [
        test_application_initialization,
        test_configuration_file_handling,
        test_menu_functionality,
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
    
    print("=" * 60)
    print(f"Application tests: {passed}/{len(tests)} passed")
    
    if passed == len(tests):
        print("🎉 All application startup tests passed!")
        return True
    else:
        print("❌ Some application tests failed!")
        return False


if __name__ == "__main__":
    success = run_application_tests()
    sys.exit(0 if success else 1)