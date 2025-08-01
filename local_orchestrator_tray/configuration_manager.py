#!/usr/bin/env python3
"""
Configuration Manager for Local Orchestrator Tray.
Handles YAML configuration loading, validation, and access.
"""

import logging
import traceback
from pathlib import Path
from typing import Dict, Any, Optional, Union
import yaml

logger = logging.getLogger(__name__)


class ConfigurationManager:
    """Manages configuration loading and validation for Local Orchestrator Tray."""
    
    def __init__(self, config_path: Union[str, Path]):
        """Initialize ConfigurationManager with config path.
        
        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = Path(config_path) if isinstance(config_path, str) else config_path
        self.config = {}
        self.is_valid = False
        self.error = None
    
    def load_and_validate(self) -> bool:
        """Load configuration from file and validate it.
        
        Returns:
            bool: True if configuration is valid, False otherwise
        """
        # Reset state
        self.is_valid = False
        self.error = None
        
        # Load config
        self._load_config()
        
        # Validate config
        self._validate_config()
        
        return self.is_valid
    
    def get_telegram_config(self) -> Dict[str, Any]:
        """Get telegram configuration section.
        
        Returns:
            Dict containing telegram configuration, empty dict if missing
        """
        return self.config.get('telegram', {})
    
    def get_actions_config(self) -> Dict[str, Any]:
        """Get actions configuration section.
        
        Returns:
            Dict containing actions configuration, empty dict if missing
        """
        return self.config.get('actions', {})
    
    def get_bot_token(self) -> Optional[str]:
        """Get Telegram bot token from configuration.
        
        Returns:
            Bot token string if available, None otherwise
        """
        telegram_config = self.get_telegram_config()
        if isinstance(telegram_config, dict):
            return telegram_config.get('bot_token')
        return None
    
    def _load_config(self):
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

            # Ensure required sections exist (only if config is a dict)
            if isinstance(self.config, dict):
                if 'telegram' not in self.config:
                    self.config['telegram'] = {}
                    logger.debug("Created empty telegram section")
                if 'actions' not in self.config:
                    self.config['actions'] = {}
                    logger.debug("Created empty actions section")
            
            logger.debug(f"Final config structure: {list(self.config.keys()) if isinstance(self.config, dict) else 'non-dict'}")

        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            logger.error(f"Exception details: {traceback.format_exc()}")
            self.config = {'telegram': {}, 'actions': {}}

    def _validate_config(self):
        """Validate the configuration and set validation status."""
        logger.debug("Starting config validation")
        try:
            # Validate config structure
            if not self._validate_config_structure():
                return

            # Validate telegram section
            if not self._validate_telegram_section():
                return

            # Validate actions section
            if not self._validate_actions_section():
                return

            # If we get here, config is valid
            self.is_valid = True
            self.error = None
            logger.info("Config validation completed successfully")

        except Exception as e:
            self.error = f"Config validation error: {e}"
            logger.error(f"Config validation exception: {e}")
            logger.error(f"Exception details: {traceback.format_exc()}")

    def _validate_config_structure(self):
        """Validate that the config is a dictionary.
        
        Returns:
            bool: True if validation passes, False if it fails (with error set)
        """
        if not isinstance(self.config, dict):
            self.error = "Config file must contain a YAML dictionary"
            logger.error(f"Config validation failed: {self.error}")
            return False
        return True

    def _validate_telegram_section(self):
        """Validate the telegram section and bot token.
        
        Returns:
            bool: True if validation passes, False if it fails (with error set)
        """
        telegram_config = self.config.get('telegram', {})
        logger.debug(f"Telegram config section: {list(telegram_config.keys()) if isinstance(telegram_config, dict) else 'invalid'}")
        
        if not isinstance(telegram_config, dict):
            self.error = "Telegram section must be a dictionary"
            logger.error(f"Config validation failed: {self.error}")
            return False

        # Check if bot token exists
        bot_token = telegram_config.get('bot_token')
        if not bot_token or not isinstance(bot_token, str) or not bot_token.strip():
            self.error = "Missing or invalid Telegram bot token"
            logger.error(f"Config validation failed: {self.error}")
            return False
        
        logger.debug(f"Bot token found, length: {len(bot_token)} characters")
        return True

    def _validate_actions_section(self):
        """Validate the actions section if it exists.
        
        Returns:
            bool: True if validation passes, False if it fails (with error set)
        """
        actions_config = self.config.get('actions', {})
        logger.debug(f"Actions config: {list(actions_config.keys()) if isinstance(actions_config, dict) else 'invalid'}")
        
        if not isinstance(actions_config, dict):
            self.error = "Actions section must be a dictionary"
            logger.error(f"Config validation failed: {self.error}")
            return False

        # Validate each action
        for action_name, action_config in actions_config.items():
            if not self._validate_individual_action(action_name, action_config):
                return False
                
        return True

    def _validate_individual_action(self, action_name, action_config):
        """Validate a single action configuration.
        
        Args:
            action_name (str): The name of the action
            action_config: The action configuration
            
        Returns:
            bool: True if validation passes, False if it fails (with error set)
        """
        logger.debug(f"Validating action '{action_name}': {action_config}")
        
        # Check if action name starts with uppercase letter (reserved for built-in actions)
        if action_name and action_name[0].isupper():
            self.error = f"Action '{action_name}' starts with uppercase letter, which is reserved for built-in actions"
            logger.error(f"Config validation failed: {self.error}")
            return False
        
        if not isinstance(action_config, dict):
            self.error = f"Action '{action_name}' must be a dictionary"
            logger.error(f"Config validation failed: {self.error}")
            return False
        
        if not action_config.get('command'):
            self.error = f"Action '{action_name}' missing required 'command' field"
            logger.error(f"Config validation failed: {self.error}")
            return False
        
        logger.debug(f"Action '{action_name}' validated successfully")
        return True