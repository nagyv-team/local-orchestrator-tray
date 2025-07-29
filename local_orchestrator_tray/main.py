#!/usr/bin/env python3
"""
Local Orchestrator Tray Application
A Mac system tray application with configuration management.
"""

import os
import sys
import yaml
from pathlib import Path
import rumps


class LocalOrchestratorTray(rumps.App):
    """Main tray application class."""

    def __init__(self):
        # Try multiple paths to find the icon
        icon_path = self._find_icon_path()

        super(LocalOrchestratorTray, self).__init__(
            "Local Orchestrator",
            # Use the tray icon if found
            icon=str(icon_path) if icon_path else None,
            quit_button=None  # We'll handle quit ourselves
        )

        self.config_path = Path.home() / ".config" / "local-orchestrator-tray.yaml"
        self.ensure_config_file()

        # Create menu items
        self.menu = [
            "Open configuration",
            None,  # Separator
            "Quit"
        ]

    def _find_icon_path(self):
        """Find the tray icon using proper resource management."""
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
        except (FileNotFoundError, ModuleNotFoundError, ImportError, TypeError):
            # Development fallback - check multiple locations
            icon_path = Path(__file__).parent / 'assets' / 'tray-icon.png'
            if icon_path.exists():
                return str(icon_path)

            # If we can't find the icon, log and continue without it
            print(f"Warning: Could not find tray-icon.png in any expected location")
            return None

    def ensure_config_file(self):
        """Create empty configuration file if it doesn't exist."""
        # Ensure .config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Create empty config file if it doesn't exist
        if not self.config_path.exists():
            with open(self.config_path, 'w') as f:
                yaml.dump({}, f, default_flow_style=False)

    @rumps.clicked("Open configuration")
    def open_configuration(self, _):
        """Open configuration file in default editor."""
        os.system(f'open "{self.config_path}"')

    @rumps.clicked("Quit")
    def quit_application(self, _):
        """Quit the application."""
        rumps.quit_application()


def main():
    """Main entry point."""
    app = LocalOrchestratorTray()
    app.run()


if __name__ == "__main__":
    main()
