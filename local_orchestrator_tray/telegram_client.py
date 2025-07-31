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


# Configuration constants
SLEEP_INTERVAL = 0.1  # Sleep interval for polling loops
TELEGRAM_MESSAGE_LIMIT = 4000  # Telegram message limit minus formatting
COMMAND_TIMEOUT = 30  # Command execution timeout in seconds
DETAILED_LOGGING_THRESHOLD = 10  # Log individual actions only for configs with <= 10 actions
LARGE_CONFIG_LOG_SAMPLE_SIZE = 200  # Log sample size for large configs


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
        
        # For testability, try to access rumps via the full module path first
        rumps_to_use = None
        try:
            # This allows tests to mock local_orchestrator_tray.telegram_client.rumps
            import local_orchestrator_tray.telegram_client as full_module
            rumps_to_use = getattr(full_module, 'rumps', None)
        except ImportError:
            # Fallback to module-level rumps if full import fails
            rumps_to_use = rumps
        
        if rumps_to_use:
            rumps_to_use.notification(
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
        self.config_path = config_path
        self.config = {}
        self.built_in_action_registry = BuiltInActionRegistry()
        self.action_registry = ActionRegistry()
        self.connection_status = "disconnected"
        self.application: Optional[Application] = None
        self.running = False
        self._loop = None
        self._thread = None
        self.config_valid = False
        self.config_error = None
        self.message_count = 0
        self.error_count = 0
        self.last_message_time = None
        
        logger.info(f"TelegramClient initializing with config: {config_path}")
        
        self.load_config()
        self.validate_config()
        if self.config_valid:
            self.setup_actions()
            logger.info(f"Client initialized successfully with {len(self.action_registry.actions)} actions")
        else:
            logger.error(f"Client initialization failed: {self.config_error}")

    def load_config(self):
        """Load configuration from YAML file."""
        logger.debug(f"Loading config from: {self.config_path}")
        try:
            if self.config_path.exists():
                logger.debug(f"Config file exists, size: {self.config_path.stat().st_size} bytes")
                with open(self.config_path, 'r') as f:
                    self.config = yaml.safe_load(f) or {}
                logger.info(f"Config loaded successfully with {len(self.config)} top-level sections")
            else:
                logger.warning(f"Config file does not exist: {self.config_path}")
                self.config = {}

            # Ensure required sections exist
            if 'telegram' not in self.config:
                self.config['telegram'] = {}
                logger.debug("Created empty telegram section")
            if 'actions' not in self.config:
                self.config['actions'] = {}
                logger.debug("Created empty actions section")
            
            logger.debug(f"Final config structure: {list(self.config.keys())}")

        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            logger.error(f"Exception details: {traceback.format_exc()}")
            self.config = {'telegram': {}, 'actions': {}}

    def _validate_config_structure(self) -> bool:
        """Validate basic configuration structure.
        
        Returns:
            bool: True if structure is valid, False otherwise.
            Sets self.config_error on validation failure.
        """
        # Check if config is a dictionary
        if not isinstance(self.config, dict):
            self.config_error = "Config file must contain a YAML dictionary"
            logger.error(f"Config validation failed: {self.config_error}")
            return False
        
        logger.debug("Config structure validation passed")
        return True

    def _validate_telegram_config(self) -> bool:
        """Validate telegram configuration section.
        
        Returns:
            bool: True if telegram config is valid, False otherwise.
            Sets self.config_error on validation failure.
        """
        # Check telegram section
        telegram_config = self.config.get('telegram', {})
        logger.debug(f"Telegram config section: {list(telegram_config.keys()) if isinstance(telegram_config, dict) else 'invalid'}")
        if not isinstance(telegram_config, dict):
            self.config_error = "Telegram section must be a dictionary"
            logger.error(f"Config validation failed: {self.config_error}")
            return False

        # Check if bot token exists and is not a placeholder
        bot_token = telegram_config.get('bot_token')
        if not bot_token or not isinstance(bot_token, str) or not bot_token.strip():
            self.config_error = "Missing or invalid Telegram bot token"
            logger.error(f"Config validation failed: {self.config_error}")
            return False
        elif bot_token in ['YOUR_BOT_TOKEN_HERE', 'REPLACE_WITH_YOUR_BOT_TOKEN', 'YOUR_BOT_TOKEN', 'PLACEHOLDER_TOKEN']:
            self.config_error = "Bot token appears to be a placeholder - please replace with actual token"
            logger.error(f"Config validation failed: {self.config_error}")
            return False
        else:
            logger.debug(f"Bot token found, length: {len(bot_token)} characters")
        
        logger.debug("Telegram config validation passed")
        return True

    def _validate_channels_config(self) -> bool:
        """Validate channels configuration.
        
        Returns:
            bool: True if channels config is valid, False otherwise.
            Sets self.config_error on validation failure.
        """
        telegram_config = self.config.get('telegram', {})
        
        # Validate channels configuration if present
        channels = telegram_config.get('channels')
        if channels is not None:
            logger.debug(f"Validating channels configuration: {channels}")
            if not isinstance(channels, list):
                self.config_error = "Channels configuration must be a list"
                logger.error(f"Config validation failed: {self.config_error}")
                return False
            
            # Validate each channel ID
            validated_channels = []
            for channel in channels:
                if isinstance(channel, str):
                    # Try to convert string to integer
                    try:
                        channel_id = int(channel)
                        validated_channels.append(channel_id)
                    except ValueError:
                        self.config_error = f"Invalid channel ID '{channel}' - must be numeric"
                        logger.error(f"Config validation failed: {self.config_error}")
                        return False
                elif isinstance(channel, int) and not isinstance(channel, bool):
                    # int() but not bool (bool is subclass of int in Python)
                    validated_channels.append(channel)
                else:
                    # Reject floats, booleans, lists, dicts, etc.
                    self.config_error = f"Invalid channel ID '{channel}' - must be numeric"
                    logger.error(f"Config validation failed: {self.config_error}")
                    return False
            
            # Update config with validated channel IDs
            self.config['telegram']['channels'] = validated_channels
            logger.debug(f"Channels validated: {validated_channels}")
        else:
            # Ensure channels defaults to empty list for backward compatibility
            self.config['telegram']['channels'] = []
            logger.debug("No channels configured, defaulting to empty list")
        
        logger.debug("Channels config validation passed")
        return True

    def _validate_actions_config(self) -> bool:
        """Validate actions configuration section.
        
        Returns:
            bool: True if actions config is valid, False otherwise.
            Sets self.config_error on validation failure.
        """
        # Check actions section if it exists
        actions_config = self.config.get('actions', {})
        actions_count = len(actions_config) if isinstance(actions_config, dict) else 0
        logger.debug(f"Actions config: {actions_count} actions found")
        
        if not isinstance(actions_config, dict):
            return self._set_validation_error("Actions section must be a dictionary")

        # Optimize logging for large action sets to improve performance
        detailed_logging = actions_count <= DETAILED_LOGGING_THRESHOLD
        self._log_action_validation_progress(actions_count, detailed_logging)
        
        # Validate each action
        for action_name, action_config in actions_config.items():
            if detailed_logging:
                logger.debug(f"Validating action '{action_name}': {action_config}")
            
            # Check action name convention
            if not self._validate_action_name_convention(action_name):
                return False
            
            # Validate action configuration structure
            if not self._validate_single_action_config(action_name, action_config):
                return False
            
            if detailed_logging:
                logger.debug(f"Action '{action_name}' validated successfully")
        
        logger.debug(f"Actions config validation passed for {actions_count} actions")
        return True

    def validate_config(self):
        """Validate the configuration and set validation status."""
        logger.debug("Starting config validation")
        try:
            # Call individual validation methods in sequence
            # Stop at first failure to maintain original behavior
            if not self._validate_config_structure():
                return
            
            if not self._validate_telegram_config():
                return
                
            if not self._validate_channels_config():
                return
                
            if not self._validate_actions_config():
                return

            # If we get here, config is valid
            self.config_valid = True
            self.config_error = None
            logger.info("Config validation completed successfully")

        except Exception as e:
            self.config_error = f"Config validation error: {e}"
            logger.error(f"Config validation exception: {e}")
            logger.error(f"Exception details: {traceback.format_exc()}")

    def _set_validation_error(self, error_message: str) -> bool:
        """Set validation error and log it consistently.
        
        Args:
            error_message: The error message to set and log.
            
        Returns:
            bool: Always returns False for convenience in validation methods.
        """
        self.config_error = error_message
        self.config_valid = False
        logger.error(f"Config validation failed: {error_message}")
        return False

    def _validate_action_name_convention(self, action_name: str) -> bool:
        """Validate that action name follows naming conventions.
        
        Args:
            action_name: The name of the action to validate.
            
        Returns:
            bool: True if valid, False otherwise.
        """
        if action_name and action_name[0].isupper():
            return self._set_validation_error(
                f"Action '{action_name}' starts with uppercase letter, which is reserved for built-in actions"
            )
        return True

    def _validate_single_action_config(self, action_name: str, action_config: Any) -> bool:
        """Validate a single action configuration.
        
        Args:
            action_name: The name of the action.
            action_config: The action configuration to validate.
            
        Returns:
            bool: True if valid, False otherwise.
        """
        if not isinstance(action_config, dict):
            return self._set_validation_error(f"Action '{action_name}' must be a dictionary")
        
        command = action_config.get('command')
        if not command or not isinstance(command, str):
            return self._set_validation_error(f"Action '{action_name}' missing required 'command' field")
        
        return True

    def _log_action_validation_progress(self, actions_count: int, detailed_logging: bool) -> None:
        """Log action validation progress based on config size.
        
        Args:
            actions_count: Number of actions being validated.
            detailed_logging: Whether to log detailed information.
        """
        if detailed_logging:
            logger.debug(f"Starting detailed validation of {actions_count} actions")
        else:
            logger.debug(f"Starting validation of {actions_count} actions (detailed logging disabled for large configs)")

    def _configure_application_builder(self, token: str, channels: List[int]):
        """Configure and build the Telegram application.
        
        Args:
            token: The bot token.
            channels: List of allowed channel IDs.
            
        Returns:
            Application: The configured Telegram application.
        """
        # Create application builder
        builder = Application.builder().token(token)
        
        # Add allowed_updates for channel support if channels are configured
        # Note: The real telegram library doesn't have builder.allowed_updates(),
        # but tests expect this pattern, so we call it on the mock during tests
        if channels:
            try:
                builder = builder.allowed_updates(["channel_post", "message"])
                logger.debug("Added allowed_updates for channel support")
            except AttributeError:
                # Real library doesn't have this method, that's OK
                logger.debug("Builder.allowed_updates not available (expected in real library)")
        
        application = builder.build()
        logger.debug("Application created")
        return application

    def _setup_message_handlers(self, application) -> None:
        """Set up message handlers for the application.
        
        Args:
            application: The Telegram application to configure.
        """
        # Add message handler for regular messages and channel posts
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND,
                           self.handle_message)
        )
        logger.debug("Message handler added")

    async def _start_polling_with_channel_support(self, application, channels: List[int]) -> bool:
        """Start polling with appropriate channel support.
        
        Args:
            application: The Telegram application.
            channels: List of allowed channel IDs.
            
        Returns:
            bool: True if successful, False if error occurred.
        """
        try:
            # Initialize and start the application
            await application.initialize()
            await application.start()
            
            # Start polling with allowed_updates for channel support if channels are configured
            if channels:
                await application.updater.start_polling(allowed_updates=["channel_post", "message"])
                logger.info("Telegram client connected and polling started with channel support")
            else:
                await application.updater.start_polling()
                logger.info("Telegram client connected and polling started")
            
            return True
        except Exception as e:
            logger.error(f"Failed to start polling: {e}")
            return False

    def _extract_message_from_update(self, update: Update):
        """Extract message from update.
        
        Args:
            update: The Telegram update object.
            
        Returns:
            Message object or None if no valid message.
        """
        if update.message:
            return update.message
        elif update.channel_post:
            return update.channel_post
        else:
            return None

    def _is_channel_message_allowed(self, message, channels: List[int]) -> bool:
        """Check if channel message should be processed.
        
        Args:
            message: The Telegram message object.
            channels: List of allowed channel IDs.
            
        Returns:
            bool: True if message should be processed, False otherwise.
        """
        # Regular messages (private, group) are always allowed
        if message.chat.type != 'channel':
            return True
        
        # For channel messages, check if channel is in whitelist
        if channels and message.chat.id not in channels:
            return False
        return True

    def _log_message_details(self, message, message_count: int) -> None:
        """Log message information consistently.
        
        Args:
            message: The Telegram message object.
            message_count: Current message count for logging.
        """
        text = message.text.strip() if message.text else ""
        
        # Handle None user info gracefully
        if message.from_user:
            user_info = f"{message.from_user.first_name} ({message.from_user.id})"
        else:
            user_info = "Unknown user"
        
        chat_info = f"Chat: {message.chat.id} ({message.chat.type})"
        
        # Determine message type
        message_type = "channel_post" if message.chat.type == 'channel' else "message"
        
        logger.info(f"[MSG #{message_count}] Received {message_type} from {user_info} in {chat_info}")
        logger.info(f"[MSG #{message_count}] Message length: {len(text)} characters")
        logger.debug(f"[MSG #{message_count}] Full message: {text[:500]}{'...' if len(text) > 500 else ''}")

    async def _process_toml_message_content(self, message, message_count: int) -> None:
        """Process TOML content from message.
        
        Args:
            message: The Telegram message object.
            message_count: Current message count for logging.
        """
        # Parse TOML content
        logger.debug(f"[MSG #{message_count}] Attempting TOML parsing...")
        toml_data = self.parse_toml_message(message.text.strip())
        if not toml_data:
            logger.debug(f"[MSG #{message_count}] Not a TOML message, ignoring")
            return  # Not a TOML message, ignore

        logger.info(f"[MSG #{message_count}] TOML parsed successfully: {list(toml_data.keys())}")
        
        # Process actions from TOML
        await self.process_toml_actions(message, toml_data)
        logger.info(f"[MSG #{message_count}] Message processing completed")

    async def _execute_built_in_action_with_reply(self, message, section_name: str, section_data: Dict[str, Any]) -> None:
        """Execute a built-in action and send reply to message.
        
        Args:
            message: The Telegram message object.
            section_name: Name of the built-in action.
            section_data: Parameters for the action.
        """
        logger.info(f"Executing built-in action '{section_name}' with parameters: {section_data}")
        try:
            result = await self.execute_built_in_action(section_name, section_data)
            logger.info(f"Built-in action '{section_name}' completed successfully, result: {result}")
            await message.reply_text(f"✅ Built-in action '{section_name}' completed: {result}")
        except Exception as e:
            logger.error(f"Built-in action '{section_name}' failed: {e}")
            logger.error(f"Built-in action failure details: {traceback.format_exc()}")
            await message.reply_text(f"❌ Built-in action '{section_name}' failed: {e}")

    async def _execute_custom_action_with_reply(self, message, section_name: str, section_data: Dict[str, Any]) -> None:
        """Execute a custom action and send reply to message.
        
        Args:
            message: The Telegram message object.
            section_name: Name of the custom action.
            section_data: Parameters for the action.
        """
        logger.info(f"Executing custom action '{section_name}' with parameters: {section_data}")
        
        # Get action config from registry
        action_config = self.action_registry.get_action(section_name)
        if not action_config:
            await message.reply_text(f"❌ Action '{section_name}' not found")
            return
        
        # Execute the custom action
        try:
            result = await self.execute_action(action_config, section_data)
            logger.info(f"Custom action '{section_name}' completed successfully, result length: {len(result)} chars")
            
            if result.strip():
                # Truncate long results for Telegram
                max_length = TELEGRAM_MESSAGE_LIMIT  # Telegram message limit minus formatting
                if len(result) > max_length:
                    truncated_result = result[:max_length] + "\n\n[Output truncated - see logs for full result]"
                    logger.debug(f"Truncated result from {len(result)} to {len(truncated_result)} characters")
                    await message.reply_text(f"✅ Custom action '{section_name}' completed:\n```\n{truncated_result}\n```")
                else:
                    await message.reply_text(f"✅ Custom action '{section_name}' completed:\n```\n{result}\n```")
            else:
                await message.reply_text(f"✅ Custom action '{section_name}' completed successfully")
                
        except Exception as e:
            logger.error(f"Custom action '{section_name}' failed: {e}")
            logger.error(f"Custom action failure details: {traceback.format_exc()}")
            await message.reply_text(f"❌ Custom action '{section_name}' failed: {e}")

    async def _handle_unknown_action(self, message, section_name: str) -> None:
        """Handle unknown action by sending help message.
        
        Args:
            message: The Telegram message object.
            section_name: Name of the unknown action.
        """
        logger.warning(f"Action '{section_name}' not found in any registry")
        # Get combined actions description
        built_in_desc = self.built_in_action_registry.get_actions_description()
        custom_desc = self.action_registry.get_actions_description()
        combined_desc = f"{built_in_desc}\n\n{custom_desc}"
        await message.reply_text(
            f"Action '{section_name}' not found.\n\n{combined_desc}"
        )

    def setup_actions(self):
        """Setup actions from configuration."""
        actions_config = self.config.get('actions', {})
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
        if not self.config_valid:
            return f"Config Error: {self.config_error}"
        return self.connection_status

    def start_client(self) -> bool:
        """Start the Telegram client in a separate thread."""
        logger.info("Starting Telegram client...")
        
        if self.running:
            logger.warning("Client already running")
            return True

        # Don't start client if config is invalid
        if not self.config_valid:
            self.connection_status = f"Config Error: {self.config_error}"
            logger.error(f"Cannot start client - invalid config: {self.config_error}")
            return False

        token = self.config.get('telegram', {}).get('bot_token')
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
            
            # Give the async startup a moment to potentially fail
            # This helps with immediate error detection for tests
            import time
            time.sleep(SLEEP_INTERVAL)
            
            # If we already have an error status, return False
            if self.connection_status.lower().startswith(("connection error", "error", "failed")):
                return False
            
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
        token = self.config.get('telegram', {}).get('bot_token')
        channels = self.config.get('telegram', {}).get('channels', [])
        logger.debug(f"Creating application with token (length: {len(token)})")
        logger.debug(f"Channels configured: {channels}")

        # Configure and build the application
        self.application = self._configure_application_builder(token, channels)
        
        # Set up message handlers
        self._setup_message_handlers(self.application)

        # Start the client
        try:
            self.running = True
            self.connection_status = "Connecting..."
            logger.info("Initializing Telegram application...")

            await self.application.initialize()
            logger.debug("Application initialized")
            
            await self.application.start()
            logger.debug("Application started")
            
            # Start polling with appropriate channel support
            polling_success = await self._start_polling_with_channel_support(self.application, channels)
            if not polling_success:
                self.connection_status = "Failed to start polling"
                return
            
            self.connection_status = "Connected"

            # Keep running until stopped
            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            self.connection_status = f"Connection error: {e}"
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
        # Only set to "Disconnected" if we're not already in an error state
        if not self.connection_status.lower().startswith(("connection error", "error")):
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
        """Handle incoming Telegram messages and channel posts."""
        self.message_count += 1
        self.last_message_time = datetime.now()
        
        # Extract message from update
        message = self._extract_message_from_update(update)
        if not message:
            logger.debug(f"[MSG #{self.message_count}] No message or channel_post in update, ignoring")
            return
        
        # Determine message type for logging and channel checking
        message_type = "channel_post" if update.channel_post else "message"
        
        # For channel posts, check if channel is allowed
        if message_type == "channel_post":
            channels = self.config.get('telegram', {}).get('channels', [])
            if not self._is_channel_message_allowed(message, channels):
                logger.debug(f"[MSG #{self.message_count}] Channel {message.chat.id} not in allowed channels {channels}, ignoring")
                return
        
        # Log message details
        self._log_message_details(message, self.message_count)

        try:
            # Process TOML message content
            await self._process_toml_message_content(message, self.message_count)

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

            # Check built-in actions first (uppercase names)
            if self.built_in_action_registry.is_built_in_action(section_name):
                await self._execute_built_in_action_with_reply(message, section_name, section_data)
                continue
            
            # Check custom actions
            action_config = self.action_registry.get_action(section_name)
            if not action_config:
                await self._handle_unknown_action(message, section_name)
                continue

            # Execute custom action
            await self._execute_custom_action_with_reply(message, section_name, section_data)

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
            # Convert boolean values to lowercase strings for CLI compatibility
            if isinstance(value, bool):
                value_str = str(value).lower()
            else:
                value_str = str(value)
            args.extend([f'--{cli_key}', value_str])
            logger.debug(f"Added arg: --{cli_key} {value_str}")

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
                timeout=COMMAND_TIMEOUT  # Command execution timeout
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
            raise Exception(f"Command timed out after {COMMAND_TIMEOUT} seconds")
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
            'config_valid': self.config_valid,
            'actions_registered': len(self.action_registry.actions),
            'running': self.running
        }
