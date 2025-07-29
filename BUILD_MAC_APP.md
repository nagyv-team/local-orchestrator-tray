# Building Mac App with py2app

This document describes how to build the Local Orchestrator Tray as a standalone Mac application using py2app.

## Prerequisites

- macOS (recommended for building)
- Python 3.8 or higher
- py2app installed (`pip install py2app>=0.28.0`)

## Quick Build

Use the provided build script for an automated build process:

```bash
python build_mac_app.py
```

This script will:
1. Validate the environment and required files
2. Clean previous builds
3. Run the py2app build process
4. Provide next steps for testing and distribution

## Manual Build Process

If you prefer to build manually:

1. **Install py2app** (if not already installed):
   ```bash
   pip install py2app>=0.28.0
   ```

2. **Clean previous builds**:
   ```bash
   rm -rf build/ dist/
   ```

3. **Build the app**:
   ```bash
   python setup.py py2app
   ```

4. **Test the app**:
   ```bash
   open "dist/Local Orchestrator Tray.app"
   ```

## Setup.py Configuration

The `setup.py` has been optimized for py2app with the following key features:

### py2app OPTIONS
- **argv_emulation**: Enables proper file association handling
- **strip**: Removes debug symbols to reduce app size
- **optimize**: Python optimization level 2
- **iconfile**: Uses `assets/tray-icon.png` as the app icon
- **LSUIElement**: Configures as background app (no dock icon)

### App Bundle Configuration
- **CFBundleName**: Local Orchestrator Tray
- **CFBundleIdentifier**: com.nagyv-team.local-orchestrator-tray
- **NSHighResolutionCapable**: Supports high-DPI displays

### Dependencies
- **Included packages**: rumps, yaml, local_orchestrator_tray
- **Excluded packages**: tkinter (not needed)
- **Resources**: assets/ and local_orchestrator_tray/assets/

## Cross-Platform Compatibility

The setup.py includes platform detection:
- **macOS (darwin)**: Uses py2app configuration
- **Other platforms**: Falls back to console scripts

## File Structure

```
local-orchestrator-tray/
├── setup.py                    # Main setup script with py2app config
├── build_mac_app.py            # Automated build script
├── pyproject.toml              # Modern Python project config
├── assets/
│   └── tray-icon.png          # App icon
├── local_orchestrator_tray/
│   ├── __init__.py
│   ├── main.py                # Main application entry point
│   └── assets/
│       └── tray-icon.png      # Packaged app icon
└── dist/                      # Built app location (after build)
    └── Local Orchestrator Tray.app
```

## Build Output

After successful build, you'll find:

- **dist/Local Orchestrator Tray.app**: The standalone Mac application
- **build/**: Temporary build files (can be deleted)

## Troubleshooting

### Common Issues

1. **Missing py2app**: Install with `pip install py2app>=0.28.0`
2. **Icon not found**: Ensure `assets/tray-icon.png` exists
3. **Module import errors**: Check that all dependencies are installed
4. **Permission errors**: Run with appropriate permissions

### Build on Non-Mac Platforms

While the build script includes warnings for non-Mac platforms, you can still run the build process on Linux/Windows. However, the resulting app bundle may not work correctly without macOS-specific libraries.

## Distribution

To distribute the app:

1. **Test locally**: Run the app from `dist/` to ensure it works
2. **Copy to Applications**: Move the .app bundle to `/Applications/`
3. **Code signing** (optional): For distribution outside the App Store
4. **Notarization** (optional): For Gatekeeper approval

## Development vs. Production

- **Development**: Use `python -m local_orchestrator_tray` for quick testing
- **Production**: Use the built .app bundle for end users

The setup.py automatically detects the platform and configures appropriately for both development and production use cases.