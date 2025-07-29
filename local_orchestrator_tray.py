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
        # Get the directory where this script is located
        script_dir = Path(__file__).parent
        icon_path = script_dir / "assets" / "tray-icon.png"
        
        super(LocalOrchestratorTray, self).__init__(
            "Local Orchestrator", 
            icon=str(icon_path),  # Use the tray icon from assets folder
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