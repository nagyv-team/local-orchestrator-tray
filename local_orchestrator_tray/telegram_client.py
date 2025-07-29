#!/usr/bin/env python3
"""
Telegram client module for Local Orchestrator Tray.
Handles Telegram Bot API integration, TOML parsing, and action execution.
"""

import asyncio
import logging
import subprocess
import sys
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml

try:
    import tomllib
except ImportError:
    import toml as tomllib

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes


logger = logging.getLogger(__name__)


class ActionRegistry:
    """Registry for managing available actions."""

    def __init__(self):
        self.actions: Dict[str, Dict[str, Any]] = {}

    def register_action(self, name: str, command: str, description: str = "",
                        working_dir: Optional[str] = None):
        """Register a new action."""
        self.actions[name] = {
            'command': command,
            'description': description,
            'working_dir': working_dir
        }

    def get_action(self, name: str) -> Optional[Dict[str, Any]]:
        """Get action configuration by name."""
        return self.actions.get(name)

    def list_actions(self) -> List[str]:
        """Get list of available action names."""
        return list(self.actions.keys())

    def get_actions_description(self) -> str:
        """Get formatted description of all available actions."""
        if not self.actions:
            return "No actions are currently configured."

        descriptions = []
        for name, config in self.actions.items():
            desc = config.get('description', 'No description')
            descriptions.append(f"• **{name}**: {desc}")

        return "Available actions:\n" + "\n".join(descriptions)


class TelegramClient:
    """Telegram client for handling bot interactions."""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = {}
        self.action_registry = ActionRegistry()
        self.connection_status = "disconnected"
        self.application: Optional[Application] = None
        self.running = False
        self._loop = None
        self._thread = None

        self.load_config()
        self.setup_actions()

    def load_config(self):
        """Load configuration from YAML file."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    self.config = yaml.safe_load(f) or {}
            else:
                self.config = {}

            # Ensure required sections exist
            if 'telegram' not in self.config:
                self.config['telegram'] = {}
            if 'actions' not in self.config:
                self.config['actions'] = {}

        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self.config = {'telegram': {}, 'actions': {}}

    def setup_actions(self):
        """Setup actions from configuration."""
        actions_config = self.config.get('actions', {})
        for name, action_config in actions_config.items():
            if isinstance(action_config, dict):
                self.action_registry.register_action(
                    name=name,
                    command=action_config.get('command', ''),
                    description=action_config.get('description', ''),
                    working_dir=action_config.get('working_dir')
                )

    def get_connection_status(self) -> str:
        """Get current connection status for tray menu."""
        return self.connection_status

    def start_client(self) -> bool:
        """Start the Telegram client in a separate thread."""
        if self.running:
            return True

        token = self.config.get('telegram', {}).get('bot_token')
        if not token:
            self.connection_status = "No bot token configured"
            logger.error("No Telegram bot token configured")
            return False

        try:
            # Start client in separate thread to avoid blocking tray
            self._thread = threading.Thread(
                target=self._run_client, daemon=True)
            self._thread.start()
            return True
        except Exception as e:
            self.connection_status = f"Failed to start: {e}"
            logger.error(f"Failed to start Telegram client: {e}")
            return False

    def _run_client(self):
        """Run the Telegram client (async)."""
        try:
            # Create new event loop for this thread
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            # Run the async client
            self._loop.run_until_complete(self._async_run_client())
        except Exception as e:
            self.connection_status = f"Client error: {e}"
            logger.error(f"Telegram client error: {e}")
        finally:
            self.running = False

    async def _async_run_client(self):
        """Async client runner."""
        token = self.config.get('telegram', {}).get('bot_token')

        # Create application (telegram library will be available)

        self.application = Application.builder().token(token).build()

        # Add message handler
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND,
                           self.handle_message)
        )

        # Start the client
        try:
            self.running = True
            self.connection_status = "Connected"
            logger.info("Telegram client connected")

            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()

            # Keep running until stopped
            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            self.connection_status = f"Connection failed: {e}"
            logger.error(f"Telegram connection failed: {e}")
        finally:
            if self.application:
                try:
                    await self.application.updater.stop()
                    await self.application.stop()
                    await self.application.shutdown()
                except Exception as e:
                    logger.error(f"Error during cleanup: {e}")

    def stop_client(self):
        """Stop the Telegram client gracefully."""
        logger.info("Stopping Telegram client...")
        self.running = False
        self.connection_status = "Disconnected"

        # Cancel the event loop if running
        if self._loop and self._loop.is_running():
            try:
                # Schedule shutdown in the loop's thread
                asyncio.run_coroutine_threadsafe(
                    self._async_shutdown(), self._loop)
            except Exception as e:
                logger.error(f"Error during async shutdown: {e}")

        # Wait for thread to finish (with timeout)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logger.warning(
                    "Telegram client thread did not stop gracefully")

    async def _async_shutdown(self):
        """Async shutdown helper."""
        if self.application:
            try:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            except Exception as e:
                logger.error(f"Error during application shutdown: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming Telegram messages."""
        message = update.message
        text = message.text.strip()

        logger.info(f"Received message: {text[:100]}...")

        try:
            # Parse TOML content
            toml_data = self.parse_toml_message(text)
            if not toml_data:
                return  # Not a TOML message, ignore

            # Process actions from TOML
            await self.process_toml_actions(message, toml_data)

        except Exception as e:
            logger.error(f"Message handling error: {e}")
            await message.reply_text(f"Error processing message: {e}")

    def parse_toml_message(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse TOML content from message."""
        try:
            if hasattr(tomllib, 'loads'):
                # Python 3.11+ tomllib
                return tomllib.loads(text)
            else:
                # toml library fallback
                return tomllib.loads(text)
        except Exception as e:
            logger.debug(f"Failed to parse as TOML: {e}")
            return None

    async def process_toml_actions(self, message, toml_data: Dict[str, Any]):
        """Process actions from parsed TOML data."""
        # Find action tables (top-level sections)
        for section_name, section_data in toml_data.items():
            if not isinstance(section_data, dict):
                continue

            # Check if action exists
            action_config = self.action_registry.get_action(section_name)
            if not action_config:
                await message.reply_text(
                    f"Action '{section_name}' not found.\n\n" +
                    self.action_registry.get_actions_description()
                )
                continue

            # Execute the action
            try:
                result = await self.execute_action(action_config, section_data)
                if result.strip():
                    await message.reply_text(f"✅ Action '{section_name}' completed:\n```\n{result}\n```")
                else:
                    await message.reply_text(f"✅ Action '{section_name}' completed successfully")
            except Exception as e:
                await message.reply_text(f"❌ Action '{section_name}' failed: {e}")

    async def execute_action(self, action_config: Dict[str, Any], params: Dict[str, Any]) -> str:
        """Execute an action with given parameters."""
        command = action_config['command']
        working_dir = action_config.get('working_dir')

        # Convert TOML parameters to command line arguments
        args = []
        for key, value in params.items():
            # Convert camelCase to kebab-case for CLI args
            cli_key = key.replace('_', '-').lower()
            args.extend([f'--{cli_key}', str(value)])

        # Build full command
        full_command = command.split() + args

        # Execute command
        try:
            result = subprocess.run(
                full_command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )

            output = result.stdout
            if result.stderr:
                output += f"\nErrors:\n{result.stderr}"

            return output

        except subprocess.TimeoutExpired:
            raise Exception("Command timed out after 30 seconds")
        except subprocess.CalledProcessError as e:
            raise Exception(
                f"Command failed with exit code {e.returncode}: {e.stderr}")
        except Exception as e:
            raise Exception(f"Failed to execute command: {e}")
