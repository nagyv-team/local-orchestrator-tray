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
from .telegram_client import TelegramClient, MockTelegramClient


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
        
        # Initialize Telegram client
        self.telegram_client = TelegramClient(self.config_path)
        
        # Start Telegram client
        self.telegram_client.start_client()

        # Create menu items (will be updated with connection status)
        self._update_menu()

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

    def _update_menu(self):
        """Update menu items with current connection status."""
        status = self.telegram_client.get_connection_status()
        
        # Create dynamic menu based on connection status
        self.menu = [
            "Open configuration",
            None,  # Separator
            f"Telegram: {status}",
            None,  # Separator
            "Quit"
        ]
        
        # Schedule next update
        rumps.Timer(self._update_menu, 5).start()  # Update every 5 seconds

    @rumps.clicked("Open configuration")
    def open_configuration(self, _):
        """Open configuration file in default editor."""
        os.system(f'open "{self.config_path}"')

    def cleanup(self):
        """Clean up resources before shutdown."""
        if hasattr(self, 'telegram_client'):
            try:
                self.telegram_client.stop_client()
            except Exception as e:
                print(f"Error stopping Telegram client: {e}")
                
    @rumps.clicked("Quit")
    def quit_application(self, _):
        """Quit the application."""
        self.cleanup()
        rumps.quit_application()


def main():
    """Main entry point with crash-safe cleanup."""
    app = None
    try:
        app = LocalOrchestratorTray()
        app.run()
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        print(f"Application crashed: {e}")
    finally:
        # Ensure cleanup happens even on crash
        if app and hasattr(app, 'cleanup'):
            try:
                app.cleanup()
            except Exception as e:
                print(f"Error during cleanup: {e}")


if __name__ == "__main__":
    main()
