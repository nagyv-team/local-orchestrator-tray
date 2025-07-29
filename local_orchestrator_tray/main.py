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

# Fix import for py2app packaging - use absolute import
try:
    from local_orchestrator_tray.telegram_client import TelegramClient
except ImportError:
    # Fallback for relative import in development
    from .telegram_client import TelegramClient


class LocalOrchestratorTray(rumps.App):
    """Main tray application class."""

    def __init__(self):
        # Try multiple paths to find the icon
        icon_path = self._find_icon_path()

        self.config_path = Path.home() / ".config" / "local-orchestrator-tray.yaml"
        self.ensure_config_file()

        # Initialize Telegram client
        self.telegram_client = TelegramClient(self.config_path)

        # Start Telegram client (will handle config validation internally)
        self.telegram_client.start_client()

        # Create initial menu with MenuItem objects for dynamic items
        self.telegram_status_item = rumps.MenuItem("Telegram: Connecting...")

        initial_menu = [
            self.telegram_status_item,
            None,  # Separator
            "Open configuration",
            "Open log file",
            None,  # Separator
            "Quit"
        ]

        super(LocalOrchestratorTray, self).__init__(
            "Local Orchestrator",
            # Use the tray icon if found
            icon=str(icon_path) if icon_path else None,
            menu=initial_menu,
            quit_button=None  # We'll handle quit ourselves
        )

        # Start periodic menu updates
        self._start_menu_updates()

    def _find_icon_path(self):
        """Find the tray icon using proper resource management."""
        # First check if we're in a py2app bundle
        if hasattr(sys, 'frozen') and sys.frozen:
            # py2app bundles resources in Contents/Resources/
            bundle_path = Path(sys.executable).parent.parent / \
                'Resources' / 'assets' / 'tray-icon.png'
            if bundle_path.exists():
                return str(bundle_path)

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

    def _start_menu_updates(self):
        """Start periodic menu updates."""
        # Update immediately
        self._update_menu()
        # Schedule periodic updates
        rumps.Timer(self._update_menu, 5).start()  # Update every 5 seconds

    def _update_menu(self, _=None):
        """Update menu items with current connection status."""
        status = self.telegram_client.get_connection_status()

        # Update the telegram status menu item
        self.telegram_status_item.title = f"Telegram: {status}"

    @rumps.clicked("Open configuration")
    def open_configuration(self, _):
        """Open configuration file in default editor."""
        os.system(f'open "{self.config_path}"')
    
    @rumps.clicked("Open log file")
    def open_log_file(self, _):
        """Open the Telegram debug log file in default editor."""
        try:
            log_file_path = self.telegram_client.get_log_file_path()
            if log_file_path.exists():
                os.system(f'open "{log_file_path}"')
            else:
                # Show notification if log file doesn't exist yet
                rumps.notification(
                    title="Local Orchestrator",
                    subtitle="Log file not found",
                    message="No log file has been created yet. Send a message to the Telegram bot to generate logs."
                )
        except Exception as e:
            rumps.notification(
                title="Local Orchestrator",
                subtitle="Error opening log",
                message=f"Failed to open log file: {e}"
            )

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
