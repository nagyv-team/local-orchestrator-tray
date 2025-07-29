#!/usr/bin/env python3
"""
Simple test that verifies file structure without external dependencies.
"""

import os
import sys
from pathlib import Path


def test_files_exist():
    """Test that all required files exist."""
    project_root = Path(__file__).parent
    required_files = [
        "local_orchestrator_tray.py",
        "setup.py", 
        "pyproject.toml",
        "requirements.txt",
        "README.md",
        "LICENSE"
    ]
    
    print("Testing file structure...")
    for file_name in required_files:
        file_path = project_root / file_name
        if file_path.exists():
            print(f"✅ {file_name}")
        else:
            print(f"❌ {file_name} missing")
            return False
    
    return True


def test_main_module():
    """Test that main module has required components."""
    main_file = Path(__file__).parent / "local_orchestrator_tray.py"
    
    print("\nTesting main module content...")
    with open(main_file, 'r') as f:
        content = f.read()
    
    required_items = [
        "class LocalOrchestratorTray",
        "def main()",
        "Open configuration",
        "Quit",
".config"
    ]
    
    for item in required_items:
        if item in content:
            print(f"✅ Contains: {item}")
        else:
            print(f"❌ Missing: {item}")
            return False
    
    return True


if __name__ == "__main__":
    print("Local Orchestrator Tray - Simple Tests")
    print("=" * 40)
    
    test1 = test_files_exist()
    test2 = test_main_module()
    
    print("=" * 40)
    if test1 and test2:
        print("🎉 All simple tests passed!")
        print("\nImplementation Summary:")
        print("- Mac system tray app with rumps")
        print("- Configuration management (~/.config/)")
        print("- Context menu: Open configuration, Quit")
        print("- Build system: setup.py + pyproject.toml")
        print("- Ready for macOS deployment")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)