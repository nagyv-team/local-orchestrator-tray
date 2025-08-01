#!/usr/bin/env python3
"""
Telegram client module for Local Orchestrator Tray.
Handles Telegram Bot API integration, TOML parsing, and action execution.
"""

import asyncio
import logging
import logging.handlers
import subprocess
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml

from local_orchestrator_tray.configuration_manager import ConfigurationManager

try:
    import tomllib
except ImportError:
    import toml as tomllib

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
try:
    import rumps
except ImportError:
    rumps = None  # rumps might not be available in all environments


# Configure logging with file handler and formatting
def setup_logging():
    """Set up comprehensive logging to file with rotation."""
    log_dir = Path.home() / ".config" / "local-orchestrator-tray"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "telegram_debug.log"
    
    # Create formatter for detailed logging
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Set up rotating file handler (10MB max, keep 5 files)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Set up console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Configure telegram library logging
    telegram_logger = logging.getLogger('telegram')
    telegram_logger.setLevel(logging.WARNING)  # Reduce telegram lib noise
    
    return log_file

# Initialize logging and get log file path
LOG_FILE_PATH = setup_logging()
logger = logging.getLogger(__name__)


class BuiltInActionRegistry:
    """Registry for built-in actions that start with uppercase letters."""

    def __init__(self):
        self.actions: Dict[str, Dict[str, Any]] = {
            'Notification': {
                'handler': self._handle_notification,
                'description': 'Show a system notification with message and optional title',
                'required_params': ['message'],
                'optional_params': ['title']
            }
        }
        logger.info(f"BuiltInActionRegistry initialized with {len(self.actions)} built-in actions")

    def get_action(self, name: str) -> Optional[Dict[str, Any]]:
        """Get built-in action configuration by name."""
        return self.actions.get(name)

    def list_actions(self) -> List[str]:
        """Get list of available built-in action names."""
        return list(self.actions.keys())

    def is_built_in_action(self, name: str) -> bool:
        """Check if name corresponds to a built-in action."""
        return name in self.actions

    async def _handle_notification(self, params: Dict[str, Any]) -> str:
        """Handle Notification built-in action."""
        message = params.get('message')
        title = params.get('title', 'Local Orchestrator')
        
        if not message:
            raise ValueError("Notification action requires 'message' parameter")
        
        logger.info(f"Showing notification: title='{title}', message='{message}'")
        
        if rumps:
            rumps.notification(
                title=title,
                subtitle="",
                message=str(message)
            )
            return f"Notification shown: {title} - {message}"
        else:
            # Fallback for environments without rumps
            logger.warning("rumps not available, notification not shown")
            return f"Notification would show: {title} - {message} (rumps not available)"

    def get_actions_description(self) -> str:
        """Get formatted description of all built-in actions."""
        if not self.actions:
            return "No built-in actions available."

        descriptions = []
        for name, config in self.actions.items():
            desc = config.get('description', 'No description')
            required = config.get('required_params', [])
            optional = config.get('optional_params', [])
            param_info = ""
            if required:
                param_info += f" (Required: {', '.join(required)})"
            if optional:
                param_info += f" (Optional: {', '.join(optional)})"
            descriptions.append(f"• **{name}**: {desc}{param_info}")

        return "Built-in actions:\n" + "\n".join(descriptions)


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
            return "No custom actions are currently configured."

        descriptions = []
        for name, config in self.actions.items():
            desc = config.get('description', 'No description')
            descriptions.append(f"• **{name}**: {desc}")

        return "Custom actions:\n" + "\n".join(descriptions)


class TelegramClient:
    """Telegram client for handling bot interactions."""

    def __init__(self, config_path: Path):
        self.config_manager = ConfigurationManager(config_path)
        self.built_in_action_registry = BuiltInActionRegistry()
        self.action_registry = ActionRegistry()
        self.connection_status = "disconnected"
        self.application: Optional[Application] = None
        self.running = False
        self._loop = None
        self._thread = None
        self.message_count = 0
        self.error_count = 0
        self.last_message_time = None
        
        logger.info(f"TelegramClient initializing with config: {config_path}")
        
        if self.config_manager.load_and_validate():
            self.setup_actions()
            logger.info(f"Client initialized successfully with {len(self.action_registry.actions)} actions")
        else:
            logger.error(f"Client initialization failed: {self.config_manager.error}")
    
    @property
    def config_valid(self) -> bool:
        """Backward compatibility property for config validation status."""
        return self.config_manager.is_valid
    
    @property
    def config_error(self) -> Optional[str]:
        """Backward compatibility property for config error message."""
        return self.config_manager.error
    
    @property
    def config(self) -> Dict[str, Any]:
        """Backward compatibility property for config data."""
        return self.config_manager.config





    def setup_actions(self):
        """Setup actions from configuration."""
        actions_config = self.config_manager.get_actions_config()
        logger.debug(f"Setting up {len(actions_config)} actions")
        
        for name, action_config in actions_config.items():
            if isinstance(action_config, dict):
                logger.debug(f"Registering action '{name}' with command: {action_config.get('command', 'N/A')}")
                self.action_registry.register_action(
                    name=name,
                    command=action_config.get('command', ''),
                    description=action_config.get('description', ''),
                    working_dir=action_config.get('working_dir')
                )
                logger.info(f"Action '{name}' registered successfully")
            else:
                logger.warning(f"Skipping invalid action config for '{name}': {action_config}")
        
        logger.info(f"Action setup completed. Total actions: {len(self.action_registry.actions)}")

    def get_connection_status(self) -> str:
        """Get current connection status for tray menu."""
        if not self.config_manager.is_valid:
            return f"Config Error: {self.config_manager.error}"
        return self.connection_status

    def start_client(self) -> bool:
        """Start the Telegram client in a separate thread."""
        logger.info("Starting Telegram client...")
        
        if self.running:
            logger.warning("Client already running")
            return True

        # Don't start client if config is invalid
        if not self.config_manager.is_valid:
            self.connection_status = f"Config Error: {self.config_manager.error}"
            logger.error(f"Cannot start client - invalid config: {self.config_manager.error}")
            return False

        token = self.config_manager.get_bot_token()
        if not token:
            self.connection_status = "No bot token configured"
            logger.error("No Telegram bot token configured")
            return False

        try:
            logger.debug("Creating client thread...")
            # Start client in separate thread to avoid blocking tray
            self._thread = threading.Thread(
                target=self._run_client, daemon=True)
            self._thread.start()
            logger.info("Client thread started successfully")
            return True
        except Exception as e:
            self.connection_status = f"Failed to start: {e}"
            logger.error(f"Failed to start Telegram client: {e}")
            logger.error(f"Exception details: {traceback.format_exc()}")
            return False

    def _run_client(self):
        """Run the Telegram client (async)."""
        logger.debug("Client thread started, creating event loop...")
        try:
            # Create new event loop for this thread
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            logger.debug("Event loop created and set")

            # Run the async client
            logger.debug("Starting async client...")
            self._loop.run_until_complete(self._async_run_client())
        except Exception as e:
            self.connection_status = f"Client error: {e}"
            logger.error(f"Telegram client error: {e}")
            logger.error(f"Exception details: {traceback.format_exc()}")
            self.error_count += 1
        finally:
            self.running = False
            logger.info("Client thread terminated")

    async def _async_run_client(self):
        """Async client runner."""
        token = self.config_manager.get_bot_token()
        logger.debug(f"Creating application with token (length: {len(token)})")

        # Create application (telegram library will be available)
        self.application = Application.builder().token(token).build()
        logger.debug("Application created")

        # Add message handler
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND,
                           self.handle_message)
        )
        logger.debug("Message handler added")

        # Start the client
        try:
            self.running = True
            self.connection_status = "Connecting..."
            logger.info("Initializing Telegram application...")

            await self.application.initialize()
            logger.debug("Application initialized")
            
            await self.application.start()
            logger.debug("Application started")
            
            await self.application.updater.start_polling(allowed_updates=["channel_post", "message"])
            logger.info("Telegram client connected and polling started")
            
            self.connection_status = "Connected"

            # Keep running until stopped
            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            self.connection_status = f"Connection failed: {e}"
            logger.error(f"Telegram connection failed: {e}")
            logger.error(f"Exception details: {traceback.format_exc()}")
            self.error_count += 1
        finally:
            logger.info("Shutting down Telegram client...")
            if self.application:
                try:
                    await self.application.updater.stop()
                    logger.debug("Updater stopped")
                    await self.application.stop()
                    logger.debug("Application stopped")
                    await self.application.shutdown()
                    logger.debug("Application shutdown complete")
                except Exception as e:
                    logger.error(f"Error during cleanup: {e}")
                    logger.error(f"Exception details: {traceback.format_exc()}")

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
        self.message_count += 1
        self.last_message_time = datetime.now()
        
        message = update.message or update.channel_post
        text = message.text.strip()
        user_info = f"{message.from_user.first_name} ({message.from_user.id})"
        chat_info = f"Chat: {message.chat.id} ({message.chat.type})"
        
        logger.info(f"[MSG #{self.message_count}] Received from {user_info} in {chat_info}")
        logger.info(f"[MSG #{self.message_count}] Message length: {len(text)} characters")
        logger.debug(f"[MSG #{self.message_count}] Full message: {text[:500]}{'...' if len(text) > 500 else ''}")

        try:
            # Parse TOML content
            logger.debug(f"[MSG #{self.message_count}] Attempting TOML parsing...")
            toml_data = self.parse_toml_message(text)
            if not toml_data:
                logger.debug(f"[MSG #{self.message_count}] Not a TOML message, ignoring")
                return  # Not a TOML message, ignore

            logger.info(f"[MSG #{self.message_count}] TOML parsed successfully: {list(toml_data.keys())}")
            
            # Process actions from TOML
            await self.process_toml_actions(message, toml_data)
            logger.info(f"[MSG #{self.message_count}] Message processing completed")

        except Exception as e:
            self.error_count += 1
            logger.error(f"[MSG #{self.message_count}] Message handling error: {e}")
            logger.error(f"[MSG #{self.message_count}] Exception details: {traceback.format_exc()}")
            try:
                await message.reply_text(f"Error processing message: {e}")
            except Exception as reply_error:
                logger.error(f"[MSG #{self.message_count}] Failed to send error reply: {reply_error}")

    def parse_toml_message(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse TOML content from message."""
        logger.debug(f"Parsing TOML from {len(text)} character message")
        try:
            if hasattr(tomllib, 'loads'):
                # Python 3.11+ tomllib
                logger.debug("Using Python 3.11+ tomllib")
                result = tomllib.loads(text)
            else:
                # toml library fallback
                logger.debug("Using toml library fallback")
                result = tomllib.loads(text)
            
            logger.debug(f"TOML parsing successful, found {len(result)} top-level keys: {list(result.keys())}")
            return result
        except Exception as e:
            logger.debug(f"Failed to parse as TOML: {e}")
            return None

    async def process_toml_actions(self, message, toml_data: Dict[str, Any]):
        """Process actions from parsed TOML data."""
        logger.debug(f"Processing {len(toml_data)} TOML sections: {list(toml_data.keys())}")
        
        # Find action tables (top-level sections)
        for section_name, section_data in toml_data.items():
            logger.debug(f"Processing section '{section_name}': {type(section_data)}")
            
            if not isinstance(section_data, dict):
                logger.debug(f"Skipping section '{section_name}' - not a dictionary")
                continue

            await self._route_and_execute_action(message, section_name, section_data)

    async def _route_and_execute_action(self, message, section_name: str, section_data: Dict[str, Any]):
        """Route and execute a single action based on its type."""
        # Check built-in actions first (uppercase names)
        if self.built_in_action_registry.is_built_in_action(section_name):
            await self._execute_built_in_action_with_handling(message, section_name, section_data)
            return
        
        # Check custom actions
        action_config = self.action_registry.get_action(section_name)
        if not action_config:
            await self._handle_action_not_found(message, section_name)
            return

        await self._execute_custom_action_with_handling(message, section_name, section_data, action_config)

    async def _execute_built_in_action_with_handling(self, message, section_name: str, section_data: Dict[str, Any]):
        """Execute built-in action with error handling."""
        logger.info(f"Executing built-in action '{section_name}' with parameters: {section_data}")
        try:
            result = await self.execute_built_in_action(section_name, section_data)
            logger.info(f"Built-in action '{section_name}' completed successfully, result: {result}")
            await message.reply_text(f"✅ Built-in action '{section_name}' completed: {result}")
        except Exception as e:
            logger.error(f"Built-in action '{section_name}' failed: {e}")
            logger.error(f"Built-in action failure details: {traceback.format_exc()}")
            await message.reply_text(f"❌ Built-in action '{section_name}' failed: {e}")

    async def _execute_custom_action_with_handling(self, message, section_name: str, section_data: Dict[str, Any], action_config: Dict[str, Any]):
        """Execute custom action with error handling and result formatting."""
        logger.info(f"Executing custom action '{section_name}' with parameters: {section_data}")
        
        try:
            result = await self.execute_action(action_config, section_data)
            logger.info(f"Custom action '{section_name}' completed successfully, result length: {len(result)} chars")
            await self._format_and_send_custom_result(message, section_name, result)
        except Exception as e:
            logger.error(f"Custom action '{section_name}' failed: {e}")
            logger.error(f"Custom action failure details: {traceback.format_exc()}")
            await message.reply_text(f"❌ Custom action '{section_name}' failed: {e}")

    async def _handle_action_not_found(self, message, section_name: str):
        """Handle case when action is not found in any registry."""
        logger.warning(f"Action '{section_name}' not found in any registry")
        # Get combined actions description
        built_in_desc = self.built_in_action_registry.get_actions_description()
        custom_desc = self.action_registry.get_actions_description()
        combined_desc = f"{built_in_desc}\n\n{custom_desc}"
        await message.reply_text(
            f"Action '{section_name}' not found.\n\n{combined_desc}"
        )

    async def _format_and_send_custom_result(self, message, section_name: str, result: str):
        """Format and send custom action result, handling truncation if needed."""
        if result.strip():
            # Truncate long results for Telegram
            max_length = 4000  # Telegram message limit minus formatting
            if len(result) > max_length:
                truncated_result = result[:max_length] + "\n\n[Output truncated - see logs for full result]"
                logger.debug(f"Truncated result from {len(result)} to {len(truncated_result)} characters")
                await message.reply_text(f"✅ Custom action '{section_name}' completed:\n```\n{truncated_result}\n```")
            else:
                await message.reply_text(f"✅ Custom action '{section_name}' completed:\n```\n{result}\n```")
        else:
            await message.reply_text(f"✅ Custom action '{section_name}' completed successfully")

    async def execute_action(self, action_config: Dict[str, Any], params: Dict[str, Any]) -> str:
        """Execute an action with given parameters."""
        command = action_config['command']
        working_dir = action_config.get('working_dir')
        
        logger.debug(f"Executing action - command: {command}")
        logger.debug(f"Working directory: {working_dir or 'current'}")
        logger.debug(f"Parameters: {params}")

        # Convert TOML parameters to command line arguments
        args = []
        for key, value in params.items():
            # Convert camelCase to kebab-case for CLI args
            cli_key = self._camel_to_kebab(key)
            args.extend([f'--{cli_key}', str(value)])
            logger.debug(f"Added arg: --{cli_key} {value}")

        # Build full command
        full_command = command.split() + args
        logger.info(f"Executing command: {' '.join(full_command)}")
        
        # Execute command
        start_time = datetime.now()
        try:
            result = subprocess.run(
                full_command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )
            
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Command completed in {execution_time:.2f}s with exit code {result.returncode}")
            
            output = result.stdout
            if result.stderr:
                logger.warning(f"Command had stderr output: {result.stderr[:200]}{'...' if len(result.stderr) > 200 else ''}")
                output += f"\nErrors:\n{result.stderr}"
            
            logger.debug(f"Command output length: {len(output)} characters")
            return output

        except subprocess.TimeoutExpired:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Command timed out after {execution_time:.2f}s")
            raise Exception("Command timed out after 30 seconds")
        except subprocess.CalledProcessError as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Command failed after {execution_time:.2f}s with exit code {e.returncode}")
            logger.error(f"Command stderr: {e.stderr}")
            raise Exception(
                f"Command failed with exit code {e.returncode}: {e.stderr}")
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Command execution failed after {execution_time:.2f}s: {e}")
            logger.error(f"Exception details: {traceback.format_exc()}")
            raise Exception(f"Failed to execute command: {e}")
    
    async def execute_built_in_action(self, action_name: str, params: Dict[str, Any]) -> str:
        """Execute a built-in action with given parameters."""
        action_config = self.built_in_action_registry.get_action(action_name)
        if not action_config:
            raise Exception(f"Built-in action '{action_name}' not found")
        
        handler = action_config.get('handler')
        if not handler:
            raise Exception(f"Built-in action '{action_name}' has no handler")
        
        logger.debug(f"Executing built-in action '{action_name}' with params: {params}")
        
        # Validate required parameters
        required_params = action_config.get('required_params', [])
        for param in required_params:
            if param not in params:
                raise ValueError(f"Built-in action '{action_name}' requires parameter '{param}'")
        
        # Execute the handler
        return await handler(params)
    
    def get_log_file_path(self) -> Path:
        """Get the path to the log file."""
        return LOG_FILE_PATH
    
    def _camel_to_kebab(self, name: str) -> str:
        """Convert camelCase/snake_case to kebab-case for CLI arguments.
        
        Fixes issue #8: myKey should become --my-key, not --mykey
        
        Args:
            name: Parameter name in camelCase, snake_case, or kebab-case
            
        Returns:
            Kebab-case string suitable for CLI arguments
            
        Examples:
            - myKey -> my-key
            - dayOfYear -> day-of-year
            - snake_case -> snake-case
            - already-kebab -> already-kebab
        """
        import re
        # Insert hyphens before uppercase letters (but not at the start)
        s1 = re.sub('([a-z0-9])([A-Z])', r'\1-\2', name)
        # Convert underscores to hyphens and make lowercase
        return s1.replace('_', '-').lower()

    def get_debug_stats(self) -> Dict[str, Any]:
        """Get debugging statistics."""
        return {
            'message_count': self.message_count,
            'error_count': self.error_count,
            'last_message_time': self.last_message_time.isoformat() if self.last_message_time else None,
            'connection_status': self.connection_status,
            'config_valid': self.config_manager.is_valid,
            'actions_registered': len(self.action_registry.actions),
            'running': self.running
        }
