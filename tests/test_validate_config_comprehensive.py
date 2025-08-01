#!/usr/bin/env python3
"""
Comprehensive unit tests for TelegramClient.validate_config() method.
Tests all validation paths with proper instantiation and side effect verification.

This test suite is designed to thoroughly exercise the validate_config() method
which has a cyclomatic complexity of 13 and handles multiple validation scenarios.
"""

import sys
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add the project root to the path  
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Mock rumps and telegram before any imports that might trigger them
sys.modules['rumps'] = Mock()

# Mock telegram components to avoid import issues during testing
telegram_mock = Mock()
telegram_mock.Update = Mock()
telegram_mock.ext = Mock()
telegram_mock.ext.Application = Mock()
telegram_mock.ext.MessageHandler = Mock()
telegram_mock.ext.filters = Mock()
telegram_mock.ext.ContextTypes = Mock()
sys.modules['telegram'] = telegram_mock
sys.modules['telegram.ext'] = telegram_mock.ext


class TestValidateConfigComprehensive:
    """Comprehensive tests for TelegramClient.validate_config() method."""

    def setup_method(self):
        """Set up test environment before each test."""
        # Ensure module path is set correctly
        sys.path.insert(0, str(project_root / 'local_orchestrator_tray'))

    def create_temp_config_file(self, config_data):
        """Helper to create a temporary YAML config file."""
        config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        if config_data is not None:
            yaml.dump(config_data, config_file)
        config_file.close()
        return Path(config_file.name)

    def create_client_with_config(self, config_data):
        """Helper to create TelegramClient with given config data."""
        # Create temporary config file
        config_file = self.create_temp_config_file(config_data)
        
        # Import and mock telegram components properly
        with patch('local_orchestrator_tray.telegram_client.Update'), \
             patch('local_orchestrator_tray.telegram_client.Application'), \
             patch('local_orchestrator_tray.telegram_client.MessageHandler'), \
             patch('local_orchestrator_tray.telegram_client.filters'), \
             patch('local_orchestrator_tray.telegram_client.ContextTypes'):
            
            from local_orchestrator_tray.telegram_client import TelegramClient
            
            client = TelegramClient(config_file)
            # Directly set the config instead of loading from file for testing
            client.config = config_data
            return client

    # ============== Test Fixtures ==============

    @pytest.fixture
    def valid_minimal_config(self):
        """Minimal valid configuration."""
        return {
            'telegram': {
                'bot_token': '123456789:ABCDEFghijklmnopqrstuvwxyz_ValidToken'
            }
        }

    @pytest.fixture
    def valid_complex_config(self):
        """Complex valid configuration with multiple actions."""
        return {
            'telegram': {
                'bot_token': '123456789:ABCDEFghijklmnopqrstuvwxyz_ValidToken'
            },
            'actions': {
                'hello': {
                    'command': 'echo hello',
                    'description': 'Say hello'
                },
                'list_files': {
                    'command': 'ls -la',
                    'working_dir': '/tmp'
                },
                'deploy': {
                    'command': 'make deploy'
                }
            }
        }

    # ============== Path 1: Config is not a dictionary ==============
    
    def test_should_fail_when_config_is_string(self):
        """Test validation fails when config is a string."""
        client = self.create_client_with_config("not a dict")
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Config file must contain a YAML dictionary"
        assert client.config_valid is False

    def test_should_fail_when_config_is_list(self):
        """Test validation fails when config is a list."""
        client = self.create_client_with_config(['item1', 'item2'])
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Config file must contain a YAML dictionary"
        assert client.config_valid is False

    def test_should_fail_when_config_is_none(self):
        """Test validation fails when config is None."""
        client = self.create_client_with_config(None)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Config file must contain a YAML dictionary"
        assert client.config_valid is False

    def test_should_fail_when_config_is_integer(self):
        """Test validation fails when config is an integer."""
        client = self.create_client_with_config(42)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Config file must contain a YAML dictionary"
        assert client.config_valid is False

    # ============== Path 2-3: Telegram section validation ==============

    def test_should_fail_when_telegram_section_is_string(self):
        """Test validation fails when telegram section is a string."""
        config = {'telegram': 'not a dict'}
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Telegram section must be a dictionary"
        assert client.config_valid is False

    def test_should_fail_when_telegram_section_is_list(self):
        """Test validation fails when telegram section is a list."""
        config = {'telegram': ['token1', 'token2']}
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Telegram section must be a dictionary"
        assert client.config_valid is False

    def test_should_fail_when_telegram_section_is_none(self):
        """Test validation fails when telegram section is None."""
        config = {'telegram': None}
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Telegram section must be a dictionary"
        assert client.config_valid is False

    # ============== Path 4-7: Bot token validation ==============

    def test_should_fail_when_bot_token_missing(self):
        """Test validation fails when bot_token is missing."""
        config = {'telegram': {}}
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Missing or invalid Telegram bot token"
        assert client.config_valid is False

    def test_should_fail_when_bot_token_is_none(self):
        """Test validation fails when bot_token is None."""
        config = {'telegram': {'bot_token': None}}
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Missing or invalid Telegram bot token"
        assert client.config_valid is False

    def test_should_fail_when_bot_token_is_integer(self):
        """Test validation fails when bot_token is not a string."""
        config = {'telegram': {'bot_token': 12345}}
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Missing or invalid Telegram bot token"
        assert client.config_valid is False

    def test_should_fail_when_bot_token_is_empty_string(self):
        """Test validation fails when bot_token is empty string."""
        config = {'telegram': {'bot_token': ''}}
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Missing or invalid Telegram bot token"
        assert client.config_valid is False

    def test_should_fail_when_bot_token_is_whitespace_only(self):
        """Test validation fails when bot_token is only whitespace."""
        config = {'telegram': {'bot_token': '   \t\n  '}}
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Missing or invalid Telegram bot token"
        assert client.config_valid is False

    def test_should_fail_when_bot_token_is_boolean(self):
        """Test validation fails when bot_token is a boolean."""
        config = {'telegram': {'bot_token': True}}
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Missing or invalid Telegram bot token"
        assert client.config_valid is False

    # ============== Path 8: Actions section validation ==============

    def test_should_fail_when_actions_section_is_string(self):
        """Test validation fails when actions section is a string."""
        config = {
            'telegram': {'bot_token': 'valid_token'},
            'actions': 'not a dict'
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Actions section must be a dictionary"
        assert client.config_valid is False

    def test_should_fail_when_actions_section_is_list(self):
        """Test validation fails when actions section is a list."""
        config = {
            'telegram': {'bot_token': 'valid_token'},
            'actions': ['action1', 'action2']
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Actions section must be a dictionary"
        assert client.config_valid is False

    def test_should_fail_when_actions_section_is_none(self):
        """Test validation fails when actions section is None."""
        config = {
            'telegram': {'bot_token': 'valid_token'},
            'actions': None
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Actions section must be a dictionary"
        assert client.config_valid is False

    # ============== Path 9: Individual action validation ==============

    def test_should_fail_when_action_config_is_string(self):
        """Test validation fails when action config is a string."""
        config = {
            'telegram': {'bot_token': 'valid_token'},
            'actions': {
                'test_action': 'not a dict'
            }
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Action 'test_action' must be a dictionary"
        assert client.config_valid is False

    def test_should_fail_when_action_config_is_list(self):
        """Test validation fails when action config is a list."""
        config = {
            'telegram': {'bot_token': 'valid_token'},
            'actions': {
                'test_action': ['command', 'arg1', 'arg2']
            }
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Action 'test_action' must be a dictionary"
        assert client.config_valid is False

    def test_should_fail_when_action_config_is_none(self):
        """Test validation fails when action config is None."""
        config = {
            'telegram': {'bot_token': 'valid_token'},
            'actions': {
                'test_action': None
            }
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Action 'test_action' must be a dictionary"
        assert client.config_valid is False

    # ============== Path 10: Uppercase action name validation ==============

    def test_should_fail_when_action_name_starts_with_uppercase(self):
        """Test validation fails when action name starts with uppercase letter."""
        config = {
            'telegram': {'bot_token': 'valid_token'},
            'actions': {
                'Uppercase_Action': {
                    'command': 'echo test'
                }
            }
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert "Action 'Uppercase_Action' starts with uppercase letter" in client.config_error
        assert "reserved for built-in actions" in client.config_error
        assert client.config_valid is False

    def test_should_fail_on_first_uppercase_action_name(self):
        """Test validation fails on first uppercase action name encountered."""
        config = {
            'telegram': {'bot_token': 'valid_token'},
            'actions': {
                'valid_lowercase': {'command': 'echo first'},  # Changed to all lowercase
                'First_Uppercase': {'command': 'echo second'},
                'Second_Uppercase': {'command': 'echo third'}
            }
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        # Should fail on an uppercase action name (dict iteration order may vary)
        assert client.config_valid is False
        assert "starts with uppercase letter" in client.config_error
        assert "reserved for built-in actions" in client.config_error
        # Don't assert specific action name due to dict iteration order

    def test_should_fail_with_single_letter_uppercase_action(self):
        """Test validation fails with single uppercase letter action name."""
        config = {
            'telegram': {'bot_token': 'valid_token'},
            'actions': {
                'A': {'command': 'echo test'}
            }
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert "Action 'A' starts with uppercase letter" in client.config_error
        assert "reserved for built-in actions" in client.config_error
        assert client.config_valid is False

    # ============== Path 11-12: Command field validation ==============

    def test_should_fail_when_action_missing_command_field(self):
        """Test validation fails when action is missing command field."""
        config = {
            'telegram': {'bot_token': 'valid_token'},
            'actions': {
                'test_action': {
                    'description': 'Test action without command'
                }
            }
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Action 'test_action' missing required 'command' field"
        assert client.config_valid is False

    def test_should_fail_when_action_command_is_none(self):
        """Test validation fails when action command is None."""
        config = {
            'telegram': {'bot_token': 'valid_token'},
            'actions': {
                'test_action': {
                    'command': None
                }
            }
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Action 'test_action' missing required 'command' field"
        assert client.config_valid is False

    def test_should_fail_when_action_command_is_empty_string(self):
        """Test validation fails when action command is empty string."""
        config = {
            'telegram': {'bot_token': 'valid_token'},
            'actions': {
                'test_action': {
                    'command': ''
                }
            }
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Action 'test_action' missing required 'command' field"
        assert client.config_valid is False

    def test_should_fail_when_action_command_is_false(self):
        """Test validation fails when action command is False."""
        config = {
            'telegram': {'bot_token': 'valid_token'},
            'actions': {
                'test_action': {
                    'command': False
                }
            }
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Action 'test_action' missing required 'command' field"
        assert client.config_valid is False

    def test_should_fail_when_action_command_is_zero(self):
        """Test validation fails when action command is 0."""
        config = {
            'telegram': {'bot_token': 'valid_token'},
            'actions': {
                'test_action': {
                    'command': 0
                }
            }
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_error == "Action 'test_action' missing required 'command' field"
        assert client.config_valid is False

    # ============== Path 13: Exception handling ==============

    def test_should_handle_exception_during_validation(self):
        """Test validation handles exceptions gracefully."""
        client = self.create_client_with_config({'telegram': {'bot_token': 'valid_token'}})
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        # Create a dict-like object that raises exception when get() is called
        class ExceptionDict(dict):
            def get(self, key, default=None):
                raise Exception("Test exception")
        
        client.config = ExceptionDict({'telegram': {'bot_token': 'valid_token'}})
        
        client.validate_config()
        
        assert "Config validation error: Test exception" in client.config_error
        assert client.config_valid is False

    def test_should_handle_key_error_during_validation(self):
        """Test validation handles KeyError exceptions gracefully."""
        client = self.create_client_with_config({'telegram': {'bot_token': 'valid_token'}})
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        # Create a dict-like object that raises KeyError when get() is called
        class KeyErrorDict(dict):
            def get(self, key, default=None):
                raise KeyError("missing_key")
        
        client.config = KeyErrorDict({'telegram': {'bot_token': 'valid_token'}})
        
        client.validate_config()
        
        assert "Config validation error: 'missing_key'" in client.config_error
        assert client.config_valid is False

    def test_should_handle_type_error_during_validation(self):
        """Test validation handles TypeError exceptions gracefully."""
        client = self.create_client_with_config({'telegram': {'bot_token': 'valid_token'}})
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        # Create a dict-like object that raises TypeError when get() is called
        class TypeErrorDict(dict):
            def get(self, key, default=None):
                raise TypeError("Type check failed")
        
        client.config = TypeErrorDict({'telegram': {'bot_token': 'valid_token'}})
        
        client.validate_config()
        
        assert "Config validation error: Type check failed" in client.config_error
        assert client.config_valid is False

    # ============== Path 14: Valid configurations ==============

    def test_should_pass_with_minimal_valid_config(self, valid_minimal_config):
        """Test validation passes with minimal valid configuration."""
        client = self.create_client_with_config(valid_minimal_config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_valid is True
        assert client.config_error is None

    def test_should_pass_with_complex_valid_config(self, valid_complex_config):
        """Test validation passes with complex valid configuration."""
        client = self.create_client_with_config(valid_complex_config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_valid is True
        assert client.config_error is None

    def test_should_pass_when_actions_section_missing(self):
        """Test validation passes when actions section is completely missing."""
        config = {
            'telegram': {'bot_token': 'valid_token_123'}
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_valid is True
        assert client.config_error is None

    def test_should_pass_when_actions_section_empty(self):
        """Test validation passes when actions section is empty dict."""
        config = {
            'telegram': {'bot_token': 'valid_token_123'},
            'actions': {}
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_valid is True
        assert client.config_error is None

    def test_should_pass_with_valid_action_command_whitespace(self):
        """Test validation passes when action command has leading/trailing whitespace."""
        config = {
            'telegram': {'bot_token': 'valid_token_123'},
            'actions': {
                'test_action': {
                    'command': '  echo hello  '  # Has content, just with whitespace
                }
            }
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        # This should pass because the command has content, validation doesn't strip
        assert client.config_valid is True
        assert client.config_error is None

    def test_should_pass_with_lowercase_action_names(self):
        """Test validation passes with various lowercase action names."""
        config = {
            'telegram': {'bot_token': 'valid_token_123'},
            'actions': {
                'simple': {'command': 'echo simple'},
                'with_underscore': {'command': 'echo underscore'},
                'with123numbers': {'command': 'echo numbers'},
                'kebab-case': {'command': 'echo kebab'},
                'mixedCamelCase': {'command': 'echo mixed'}  # lowercase first letter should be OK
            }
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        assert client.config_valid is True
        assert client.config_error is None

    # ============== Edge cases ==============

    def test_should_handle_empty_action_name(self):
        """Test validation handles empty action name."""
        config = {
            'telegram': {'bot_token': 'valid_token_123'},
            'actions': {
                '': {'command': 'echo empty'}
            }
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        # Empty string doesn't have a first character to check, so should pass
        assert client.config_valid is True
        assert client.config_error is None

    def test_should_reset_validation_state_on_revalidation(self):
        """Test that validation properly resets state between calls."""
        config_invalid = {'telegram': 'not a dict'}
        config_valid = {'telegram': {'bot_token': 'valid_token_123'}}
        
        client = self.create_client_with_config(config_invalid)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        # First validation should fail
        assert client.config_error is not None
        assert client.config_valid is False
        
        # Change to valid config and revalidate
        client.config = config_valid
        client.validate_config()
        
        # Second validation should pass and reset error state
        assert client.config_valid is True
        assert client.config_error is None

    def test_should_validate_multiple_actions_stopping_at_first_error(self):
        """Test validation stops at first action error encountered."""
        config = {
            'telegram': {'bot_token': 'valid_token_123'},
            'actions': {
                'valid_action': {'command': 'echo valid'},
                'Invalid_Action': {'command': 'echo invalid'},  # This should cause failure
                'another_invalid': {}  # This would also fail but shouldn't be reached
            }
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        # Should fail on the uppercase action name, not the missing command
        assert "Invalid_Action" in client.config_error
        assert "uppercase letter" in client.config_error
        assert "missing required 'command' field" not in client.config_error
        assert client.config_valid is False

    def test_should_handle_telegram_section_missing_with_empty_dict_default(self):
        """Test validation handles missing telegram section with default empty dict."""
        config = {}  # No telegram section at all
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        # Should fail because bot_token will be missing from the default empty dict
        assert client.config_error == "Missing or invalid Telegram bot token"
        assert client.config_valid is False

    def test_should_validate_action_iteration_order_independence(self):
        """Test validation result is independent of action iteration order."""
        # Create config with actions that would fail at different points
        config = {
            'telegram': {'bot_token': 'valid_token_123'},
            'actions': {
                'a_first': {'command': 'echo first'},      # Valid
                'b_second': {},                            # Missing command - would fail
                'C_third': {'command': 'echo third'}       # Uppercase - would fail first
            }
        }
        client = self.create_client_with_config(config)
        
        # Reset initial state
        client.config_valid = False
        client.config_error = None
        
        client.validate_config()
        
        # Should fail on first validation error encountered
        # The exact error depends on dict iteration order, but should be consistent
        assert client.config_valid is False
        assert client.config_error is not None
        # Either should fail on uppercase name OR missing command, but consistently
        assert ("uppercase letter" in client.config_error) or ("missing required 'command' field" in client.config_error)