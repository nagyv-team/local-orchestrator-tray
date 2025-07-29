#!/usr/bin/env python3
"""
Mac-specific build script for py2app.
This script should be run on macOS to build the standalone app.
"""

import sys
import os
from pathlib import Path

def main():
    """Main build function for Mac app."""
    if sys.platform != 'darwin':
        print("⚠️  Warning: This script should be run on macOS for optimal results.")
        print("   Building on non-Mac platforms may not work correctly.")
        response = input("   Continue anyway? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            sys.exit(1)
    
    # Ensure we're in the project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)
    
    print("🔧 Building Mac app with py2app...")
    print("📁 Project directory:", project_dir)
    
    # Check for required files
    required_files = [
        "setup.py",
        "local_orchestrator_tray/main.py",
        "assets/tray-icon.png"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print("❌ Missing required files:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        sys.exit(1)
    
    print("✅ All required files found")
    
    # Clean previous builds
    print("🧹 Cleaning previous builds...")
    import shutil
    for dir_name in ['build', 'dist']:
        if Path(dir_name).exists():
            shutil.rmtree(dir_name)
            print(f"   Removed {dir_name}/")
    
    # Run py2app build
    print("🚀 Running py2app build...")
    exit_code = os.system("python setup.py py2app")
    
    if exit_code == 0:
        print("✅ Build completed successfully!")
        print("📦 App bundle location: dist/Local Orchestrator Tray.app")
        print("\n🎯 Next steps:")
        print("   1. Test the app: open 'dist/Local Orchestrator Tray.app'")
        print("   2. Distribute: Copy the .app bundle to Applications folder")
        print("   3. Optional: Code sign for distribution")
    else:
        print("❌ Build failed with exit code:", exit_code)
        sys.exit(exit_code)

if __name__ == "__main__":
    main()