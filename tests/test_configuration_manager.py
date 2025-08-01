#!/usr/bin/env python3
"""
Comprehensive unit tests for ConfigurationManager class.

This test suite is designed to drive the extraction of configuration management 
logic from TelegramClient into a dedicated ConfigurationManager class following
TDD principles. All tests start as skipped and are implemented in batches.

Test Coverage:
- File loading scenarios (exists, missing, invalid YAML, permissions)
- Configuration validation (structure, telegram section, actions section) 
- Public interface methods (get_telegram_config, get_actions_config, get_bot_token)
- State management (is_valid, error properties)
- Exception handling and edge cases
- Separation of concerns verification
"""

import sys
import tempfile
import pytest
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
from unittest import mock

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Mock external dependencies to avoid import issues during testing
sys.modules['rumps'] = Mock()
telegram_mock = Mock()
telegram_mock.Update = Mock()
telegram_mock.ext = Mock()
telegram_mock.ext.Application = Mock()
telegram_mock.ext.MessageHandler = Mock()
telegram_mock.ext.filters = Mock()
telegram_mock.ext.ContextTypes = Mock()
sys.modules['telegram'] = telegram_mock
sys.modules['telegram.ext'] = telegram_mock.ext


class TestConfigurationManagerInstantiation:
    """Test ConfigurationManager class instantiation and basic properties."""

    def test_should_initialize_with_config_path(self):
        """ConfigurationManager should initialize with provided config path."""
        # This will fail initially - ConfigurationManager doesn't exist yet
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        config_path = Path('/test/config.yaml')
        manager = ConfigurationManager(config_path)

        assert manager.config_path == config_path

    def test_should_initialize_with_empty_config_dict(self):
        """ConfigurationManager should initialize with empty config dictionary."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        config_path = Path('/test/config.yaml')
        manager = ConfigurationManager(config_path)

        assert manager.config == {}

    def test_should_initialize_with_is_valid_false(self):
        """ConfigurationManager should initialize with is_valid set to False."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        config_path = Path('/test/config.yaml')
        manager = ConfigurationManager(config_path)

        assert manager.is_valid == False

    def test_should_initialize_with_error_none(self):
        """ConfigurationManager should initialize with error set to None."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        config_path = Path('/test/config.yaml')
        manager = ConfigurationManager(config_path)

        assert manager.error is None

    def test_should_store_config_path_as_path_object(self):
        """ConfigurationManager should convert string paths to Path objects."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        # Test with string path
        string_path = '/test/config.yaml'
        manager = ConfigurationManager(string_path)

        assert isinstance(manager.config_path, Path)
        assert manager.config_path == Path(string_path)


class TestConfigurationManagerFileLoading:
    """Test ConfigurationManager file loading scenarios."""

    def test_should_load_valid_yaml_file_when_exists(self, temp_config_file, valid_config):
        """Should successfully load configuration from valid YAML file."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        # Write valid config to temp file
        with open(temp_config_file, 'w') as f:
            yaml.dump(valid_config, f)

        manager = ConfigurationManager(temp_config_file)
        success = manager.load_and_validate()

        assert success == True
        assert manager.config == valid_config
        assert manager.is_valid == True
        assert manager.error is None

    def test_should_handle_missing_config_file(self):
        """Should handle missing config file by creating empty config."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        non_existent_path = Path('/non/existent/config.yaml')
        manager = ConfigurationManager(non_existent_path)
        result = manager.load_and_validate()

        # Should create empty config with default sections
        assert 'telegram' in manager.config
        assert 'actions' in manager.config
        assert isinstance(manager.config['telegram'], dict)
        assert isinstance(manager.config['actions'], dict)

    def test_should_handle_invalid_yaml_syntax(self, temp_config_file):
        """Should handle YAML files with invalid syntax gracefully."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        # Write invalid YAML to temp file
        with open(temp_config_file, 'w') as f:
            f.write('invalid: yaml: syntax: [unclosed bracket')

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        # Should handle gracefully and create default sections
        assert 'telegram' in manager.config
        assert 'actions' in manager.config
        assert manager.is_valid == False  # Invalid due to missing bot token
        assert manager.error is not None

    def test_should_handle_empty_yaml_file(self, temp_config_file):
        """Should handle empty YAML files by creating empty config."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        # Create empty file
        temp_config_file.write_text('')

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        # Should create default sections
        assert 'telegram' in manager.config
        assert 'actions' in manager.config
        assert isinstance(manager.config['telegram'], dict)
        assert isinstance(manager.config['actions'], dict)

    def test_should_handle_file_permission_errors(self):
        """Should handle file permission errors during loading."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        # Mock file permission error
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            manager = ConfigurationManager(Path('/test/config.yaml'))
            result = manager.load_and_validate()

            # Should create default config when file can't be read
            assert 'telegram' in manager.config
            assert 'actions' in manager.config

    def test_should_create_default_sections_when_missing(self, temp_config_file):
        """Should create telegram and actions sections if missing from loaded config."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        # Write config missing sections
        incomplete_config = {'some_other_section': 'value'}
        with open(temp_config_file, 'w') as f:
            yaml.dump(incomplete_config, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        # Should add missing sections
        assert 'telegram' in manager.config
        assert 'actions' in manager.config
        assert 'some_other_section' in manager.config  # Original data preserved
        assert isinstance(manager.config['telegram'], dict)
        assert isinstance(manager.config['actions'], dict)

    def test_should_handle_file_io_exceptions(self):
        """Should handle various file I/O exceptions during loading."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        # Test various I/O exceptions
        exceptions_to_test = [OSError("OS Error"), IOError(
            "IO Error"), UnicodeDecodeError('utf-8', b'', 0, 1, 'invalid')]

        for exception in exceptions_to_test:
            with patch('builtins.open', side_effect=exception):
                manager = ConfigurationManager(Path('/test/config.yaml'))
                result = manager.load_and_validate()

                # Should handle gracefully and create default config
                assert 'telegram' in manager.config
                assert 'actions' in manager.config


class TestConfigurationManagerValidation:
    """Test ConfigurationManager validation logic."""

    def test_should_validate_config_structure_is_dict(self, valid_config, temp_config_file):
        """Should validate that config is a dictionary."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        # Write valid config
        with open(temp_config_file, 'w') as f:
            yaml.dump(valid_config, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == True
        assert manager.is_valid == True
        assert manager.error is None

    def test_should_reject_non_dict_config_structure(self, temp_config_file):
        """Should reject configuration that is not a dictionary."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        # Write non-dict config
        with open(temp_config_file, 'w') as f:
            f.write('"not a dictionary"')

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == False
        assert manager.is_valid == False
        assert manager.error == "Config file must contain a YAML dictionary"

    def test_should_validate_telegram_section_is_dict(self, temp_config_file):
        """Should validate that telegram section is a dictionary."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        valid_config = {
            'telegram': {
                'bot_token': '123456789:ABCDEFghijklmnopqrstuvwxyz_test_token'
            },
            'actions': {}
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(valid_config, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == True
        assert manager.is_valid == True

    def test_should_reject_non_dict_telegram_section(self, temp_config_file):
        """Should reject telegram section that is not a dictionary."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        invalid_config = {
            'telegram': "not a dictionary",
            'actions': {}
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(invalid_config, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == False
        assert manager.is_valid == False
        assert manager.error == "Telegram section must be a dictionary"

    def test_should_validate_bot_token_exists(self, temp_config_file):
        """Should validate that bot_token exists in telegram section."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        valid_config = {
            'telegram': {
                'bot_token': '123456789:ABCDEFghijklmnopqrstuvwxyz_test_token'
            },
            'actions': {}
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(valid_config, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == True
        assert manager.is_valid == True
        assert manager.error is None

    def test_should_reject_missing_bot_token(self, temp_config_file):
        """Should reject configuration with missing bot_token."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        invalid_config = {
            'telegram': {},  # Missing bot_token
            'actions': {}
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(invalid_config, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == False
        assert manager.is_valid == False
        assert manager.error == "Missing or invalid Telegram bot token"

    def test_should_reject_non_string_bot_token(self, temp_config_file):
        """Should reject bot_token that is not a string."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        invalid_config = {
            'telegram': {
                'bot_token': 12345  # Not a string
            },
            'actions': {}
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(invalid_config, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == False
        assert manager.is_valid == False
        assert manager.error == "Missing or invalid Telegram bot token"

    def test_should_reject_empty_bot_token(self, temp_config_file):
        """Should reject empty string bot_token."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        invalid_config = {
            'telegram': {
                'bot_token': ''  # Empty string
            },
            'actions': {}
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(invalid_config, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == False
        assert manager.is_valid == False
        assert manager.error == "Missing or invalid Telegram bot token"

    def test_should_reject_whitespace_only_bot_token(self, temp_config_file):
        """Should reject bot_token that contains only whitespace."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        invalid_config = {
            'telegram': {
                'bot_token': '   \t\n  '  # Only whitespace
            },
            'actions': {}
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(invalid_config, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == False
        assert manager.is_valid == False
        assert manager.error == "Missing or invalid Telegram bot token"

    def test_should_validate_actions_section_is_dict(self, temp_config_file):
        """Should validate that actions section is a dictionary."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        valid_config = {
            'telegram': {
                'bot_token': '123456789:ABCDEFghijklmnopqrstuvwxyz_test_token'
            },
            'actions': {
                'test_action': {
                    'command': 'echo test'
                }
            }
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(valid_config, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == True
        assert manager.is_valid == True

    def test_should_reject_non_dict_actions_section(self, temp_config_file):
        """Should reject actions section that is not a dictionary."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        invalid_config = {
            'telegram': {
                'bot_token': '123456789:ABCDEFghijklmnopqrstuvwxyz_test_token'
            },
            'actions': "not a dictionary"
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(invalid_config, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == False
        assert manager.is_valid == False
        assert manager.error == "Actions section must be a dictionary"

    def test_should_validate_individual_action_is_dict(self, temp_config_file):
        """Should validate that each action configuration is a dictionary."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        valid_config = {
            'telegram': {
                'bot_token': '123456789:ABCDEFghijklmnopqrstuvwxyz_test_token'
            },
            'actions': {
                'test_action': {
                    'command': 'echo test',
                    'description': 'Test action'
                }
            }
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(valid_config, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == True
        assert manager.is_valid == True

    def test_should_reject_non_dict_individual_action(self, temp_config_file):
        """Should reject individual actions that are not dictionaries."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        invalid_config = {
            'telegram': {
                'bot_token': '123456789:ABCDEFghijklmnopqrstuvwxyz_test_token'
            },
            'actions': {
                'test_action': "not a dictionary"
            }
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(invalid_config, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == False
        assert manager.is_valid == False
        assert manager.error == "Action 'test_action' must be a dictionary"

    def test_should_reject_uppercase_action_names(self, temp_config_file):
        """Should reject action names starting with uppercase letters."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        invalid_config = {
            'telegram': {
                'bot_token': '123456789:ABCDEFghijklmnopqrstuvwxyz_test_token'
            },
            'actions': {
                'TestAction': {  # Uppercase action name (reserved for built-in)
                    'command': 'echo test'
                }
            }
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(invalid_config, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == False
        assert manager.is_valid == False
        assert manager.error == "Action 'TestAction' starts with uppercase letter, which is reserved for built-in actions"

    def test_should_validate_action_has_command_field(self, temp_config_file):
        """Should validate that actions have required command field."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        valid_config = {
            'telegram': {
                'bot_token': '123456789:ABCDEFghijklmnopqrstuvwxyz_test_token'
            },
            'actions': {
                'test_action': {
                    'command': 'echo test',
                    'description': 'Test action'
                }
            }
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(valid_config, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == True
        assert manager.is_valid == True

    def test_should_reject_action_missing_command(self, temp_config_file):
        """Should reject actions missing the command field."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        invalid_config = {
            'telegram': {
                'bot_token': '123456789:ABCDEFghijklmnopqrstuvwxyz_test_token'
            },
            'actions': {
                'test_action': {
                    'description': 'Test action'  # Missing command field
                }
            }
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(invalid_config, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == False
        assert manager.is_valid == False
        assert manager.error == "Action 'test_action' missing required 'command' field"

    def test_should_reject_action_with_empty_command(self, temp_config_file):
        """Should reject actions with empty command field."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        invalid_config = {
            'telegram': {
                'bot_token': '123456789:ABCDEFghijklmnopqrstuvwxyz_test_token'
            },
            'actions': {
                'test_action': {
                    'command': '',  # Empty command
                    'description': 'Test action'
                }
            }
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(invalid_config, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == False
        assert manager.is_valid == False
        assert manager.error == "Action 'test_action' missing required 'command' field"

    def test_should_accept_valid_complete_configuration(self, temp_config_file):
        """Should accept a valid complete configuration."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        valid_config = {
            'telegram': {
                'bot_token': '123456789:ABCDEFghijklmnopqrstuvwxyz_test_token'
            },
            'actions': {
                'deploy': {
                    'command': 'docker-compose up -d',
                    'description': 'Deploy application',
                    'working_dir': '/app'
                },
                'test': {
                    'command': 'npm test',
                    'description': 'Run tests'
                }
            }
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(valid_config, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == True
        assert manager.is_valid == True
        assert manager.error is None
        assert manager.config == valid_config


class TestConfigurationManagerPublicInterface:
    """Test ConfigurationManager public interface methods."""

    def test_load_and_validate_should_return_true_for_valid_config(self, temp_config_file, valid_config):
        """load_and_validate() should return True for valid configuration."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        with open(temp_config_file, 'w') as f:
            yaml.dump(valid_config, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == True

    def test_load_and_validate_should_return_false_for_invalid_config(self, temp_config_file, invalid_config_missing_bot_token):
        """load_and_validate() should return False for invalid configuration."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        with open(temp_config_file, 'w') as f:
            yaml.dump(invalid_config_missing_bot_token, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == False

    def test_load_and_validate_should_set_is_valid_property(self, temp_config_file, valid_config):
        """load_and_validate() should set is_valid property correctly."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        with open(temp_config_file, 'w') as f:
            yaml.dump(valid_config, f)

        manager = ConfigurationManager(temp_config_file)

        # Before validation
        assert manager.is_valid == False

        result = manager.load_and_validate()

        # After successful validation
        assert manager.is_valid == True

    def test_load_and_validate_should_set_error_property(self, temp_config_file, invalid_config_missing_bot_token):
        """load_and_validate() should set error property for invalid config."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        with open(temp_config_file, 'w') as f:
            yaml.dump(invalid_config_missing_bot_token, f)

        manager = ConfigurationManager(temp_config_file)

        # Before validation
        assert manager.error is None

        result = manager.load_and_validate()

        # After failed validation
        assert manager.error is not None
        assert "bot token" in manager.error.lower()

    def test_get_telegram_config_should_return_telegram_section(self, temp_config_file, valid_config):
        """get_telegram_config() should return telegram configuration section."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        with open(temp_config_file, 'w') as f:
            yaml.dump(valid_config, f)

        manager = ConfigurationManager(temp_config_file)
        manager.load_and_validate()

        telegram_config = manager.get_telegram_config()

        assert telegram_config == valid_config['telegram']
        assert 'bot_token' in telegram_config

    def test_get_telegram_config_should_return_empty_dict_when_missing(self, temp_config_file):
        """get_telegram_config() should return empty dict when telegram section missing."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        config_without_telegram = {'actions': {}}
        with open(temp_config_file, 'w') as f:
            yaml.dump(config_without_telegram, f)

        manager = ConfigurationManager(temp_config_file)
        manager.load_and_validate()  # This will add default telegram section

        telegram_config = manager.get_telegram_config()

        assert isinstance(telegram_config, dict)
        assert telegram_config == {}

    def test_get_actions_config_should_return_actions_section(self, temp_config_file, valid_config):
        """get_actions_config() should return actions configuration section."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        with open(temp_config_file, 'w') as f:
            yaml.dump(valid_config, f)

        manager = ConfigurationManager(temp_config_file)
        manager.load_and_validate()

        actions_config = manager.get_actions_config()

        assert actions_config == valid_config['actions']
        assert 'test_action' in actions_config

    def test_get_actions_config_should_return_empty_dict_when_missing(self, temp_config_file):
        """get_actions_config() should return empty dict when actions section missing."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        config_without_actions = {
            'telegram': {'bot_token': '123456789:ABCDEFghijklmnopqrstuvwxyz_test_token'}
        }
        with open(temp_config_file, 'w') as f:
            yaml.dump(config_without_actions, f)

        manager = ConfigurationManager(temp_config_file)
        manager.load_and_validate()  # This will add default actions section

        actions_config = manager.get_actions_config()

        assert isinstance(actions_config, dict)
        assert actions_config == {}

    def test_get_bot_token_should_return_token_string(self, temp_config_file, valid_config):
        """get_bot_token() should return bot token string from telegram config."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        with open(temp_config_file, 'w') as f:
            yaml.dump(valid_config, f)

        manager = ConfigurationManager(temp_config_file)
        manager.load_and_validate()

        bot_token = manager.get_bot_token()

        assert bot_token == valid_config['telegram']['bot_token']
        assert isinstance(bot_token, str)
        assert len(bot_token) > 0

    def test_get_bot_token_should_return_none_when_missing(self, temp_config_file):
        """get_bot_token() should return None when bot token is missing."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        config_without_token = {
            'telegram': {},  # No bot_token
            'actions': {}
        }
        with open(temp_config_file, 'w') as f:
            yaml.dump(config_without_token, f)

        manager = ConfigurationManager(temp_config_file)
        manager.load_and_validate()  # Will fail validation

        bot_token = manager.get_bot_token()

        assert bot_token is None

    def test_get_bot_token_should_return_none_when_telegram_section_missing(self, temp_config_file):
        """get_bot_token() should return None when entire telegram section is missing."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        config_without_telegram = {'actions': {}}
        with open(temp_config_file, 'w') as f:
            yaml.dump(config_without_telegram, f)

        manager = ConfigurationManager(temp_config_file)
        manager.load_and_validate()  # Will add empty telegram section

        bot_token = manager.get_bot_token()

        assert bot_token is None


class TestConfigurationManagerStateManagement:
    """Test ConfigurationManager state management and properties."""

    def test_is_valid_should_be_false_initially(self):
        """is_valid property should be False before validation."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        manager = ConfigurationManager(Path('/test/config.yaml'))

        assert manager.is_valid == False

    def test_is_valid_should_be_true_after_successful_validation(self, temp_config_file, valid_config):
        """is_valid property should be True after successful validation."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        with open(temp_config_file, 'w') as f:
            yaml.dump(valid_config, f)

        manager = ConfigurationManager(temp_config_file)
        manager.load_and_validate()

        assert manager.is_valid == True

    def test_is_valid_should_be_false_after_failed_validation(self, temp_config_file, invalid_config_missing_bot_token):
        """is_valid property should be False after failed validation."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        with open(temp_config_file, 'w') as f:
            yaml.dump(invalid_config_missing_bot_token, f)

        manager = ConfigurationManager(temp_config_file)
        manager.load_and_validate()

        assert manager.is_valid == False

    def test_error_should_be_none_initially(self):
        """error property should be None before validation."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        manager = ConfigurationManager(Path('/test/config.yaml'))

        assert manager.error is None

    def test_error_should_be_none_after_successful_validation(self, temp_config_file, valid_config):
        """error property should be None after successful validation."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        with open(temp_config_file, 'w') as f:
            yaml.dump(valid_config, f)

        manager = ConfigurationManager(temp_config_file)
        manager.load_and_validate()

        assert manager.error is None

    def test_error_should_contain_message_after_failed_validation(self, temp_config_file, invalid_config_missing_bot_token):
        """error property should contain error message after failed validation."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        with open(temp_config_file, 'w') as f:
            yaml.dump(invalid_config_missing_bot_token, f)

        manager = ConfigurationManager(temp_config_file)
        manager.load_and_validate()

        assert manager.error is not None
        assert isinstance(manager.error, str)
        assert len(manager.error) > 0

    def test_should_reset_state_on_subsequent_validation_attempts(self, temp_config_file, valid_config, invalid_config_missing_bot_token):
        """Should reset validation state on subsequent validation attempts."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        manager = ConfigurationManager(temp_config_file)

        # First validation with invalid config
        with open(temp_config_file, 'w') as f:
            yaml.dump(invalid_config_missing_bot_token, f)

        manager.load_and_validate()
        assert manager.is_valid == False
        assert manager.error is not None

        # Second validation with valid config should reset state
        with open(temp_config_file, 'w') as f:
            yaml.dump(valid_config, f)

        manager.load_and_validate()
        assert manager.is_valid == True
        assert manager.error is None


class TestConfigurationManagerExceptionHandling:
    """Test ConfigurationManager exception handling scenarios."""

    def test_should_handle_yaml_parser_exceptions(self, temp_config_file):
        """Should handle YAML parser exceptions gracefully."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        # Create invalid YAML that will cause parser exception
        with open(temp_config_file, 'w') as f:
            f.write('invalid: yaml: [unclosed bracket')

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        # Should handle gracefully and create default config
        assert 'telegram' in manager.config
        assert 'actions' in manager.config
        assert manager.is_valid == False  # Missing bot token

    def test_should_handle_file_not_found_exceptions(self):
        """Should handle FileNotFoundError exceptions gracefully."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        non_existent_file = Path('/totally/non/existent/file.yaml')
        manager = ConfigurationManager(non_existent_file)
        result = manager.load_and_validate()

        # Should create default config when file doesn't exist
        assert 'telegram' in manager.config
        assert 'actions' in manager.config
        assert manager.is_valid == False  # Missing bot token

    def test_should_handle_permission_denied_exceptions(self):
        """Should handle PermissionError exceptions gracefully."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            manager = ConfigurationManager(Path('/test/config.yaml'))
            result = manager.load_and_validate()

            # Should create default config when permission denied
            assert 'telegram' in manager.config
            assert 'actions' in manager.config

    def test_should_handle_generic_exceptions_during_validation(self, temp_config_file, valid_config):
        """Should handle generic exceptions during validation process."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        with open(temp_config_file, 'w') as f:
            yaml.dump(valid_config, f)

        manager = ConfigurationManager(temp_config_file)

        # Mock a validation method to raise an exception
        with patch.object(manager, '_validate_config_structure', side_effect=Exception("Validation error")):
            result = manager.load_and_validate()

            assert result == False
            assert manager.is_valid == False
            assert "validation error" in manager.error.lower()

    def test_should_handle_unicode_decode_errors(self):
        """Should handle UnicodeDecodeError when reading config files."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        with patch('builtins.open', side_effect=UnicodeDecodeError('utf-8', b'\xff\xfe', 0, 1, 'invalid start byte')):
            manager = ConfigurationManager(Path('/test/config.yaml'))
            result = manager.load_and_validate()

            # Should create default config when unicode decode fails
            assert 'telegram' in manager.config
            assert 'actions' in manager.config

    def test_should_handle_os_errors_during_file_operations(self):
        """Should handle OSError exceptions during file operations."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        with patch('builtins.open', side_effect=OSError("OS operation failed")):
            manager = ConfigurationManager(Path('/test/config.yaml'))
            result = manager.load_and_validate()

            # Should create default config when OS error occurs
            assert 'telegram' in manager.config
            assert 'actions' in manager.config


class TestConfigurationManagerEdgeCases:
    """Test ConfigurationManager edge cases and boundary conditions."""

    def test_should_handle_empty_action_names(self, temp_config_file):
        """Should handle empty action names in configuration."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        config_with_empty_action = {
            'telegram': {
                'bot_token': '123456789:ABCDEFghijklmnopqrstuvwxyz_test_token'
            },
            'actions': {
                '': {  # Empty action name
                    'command': 'echo test'
                }
            }
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(config_with_empty_action, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        # Should still validate successfully (empty name doesn't start with uppercase)
        assert result == True
        assert manager.is_valid == True

    def test_should_handle_null_values_in_config(self, temp_config_file):
        """Should handle null/None values in configuration."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        config_with_nulls = {
            'telegram': {
                'bot_token': None  # Null bot token
            },
            'actions': None  # Null actions section
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(config_with_nulls, f)

        manager = ConfigurationManager(temp_config_file)
        result = manager.load_and_validate()

        assert result == False
        assert manager.is_valid == False
        # Should handle null values gracefully with appropriate error messages
        assert manager.error is not None


class TestConfigurationManagerSeparationOfConcerns:
    """Test that ConfigurationManager properly separates configuration concerns."""

    def test_should_not_contain_telegram_client_logic(self):
        """ConfigurationManager should not contain Telegram client logic."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager
        import inspect

        # Get all methods and attributes of ConfigurationManager
        members = inspect.getmembers(ConfigurationManager)

        # Should not have any telegram client related methods
        forbidden_names = ['start_client', 'stop_client',
                           'handle_message', 'process_toml']
        class_methods = [name for name, _ in members if inspect.ismethod(
            _) or inspect.isfunction(_)]

        for forbidden in forbidden_names:
            assert forbidden not in class_methods, f"ConfigurationManager should not have {forbidden} method"

    def test_should_not_contain_action_registry_logic(self):
        """ConfigurationManager should not contain action registry logic."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager
        import inspect

        # Get all methods and attributes of ConfigurationManager
        members = inspect.getmembers(ConfigurationManager)

        # Should not have any action registry related methods
        forbidden_names = ['register_action',
                           'setup_actions', 'action_registry']
        class_methods = [name for name, _ in members]

        for forbidden in forbidden_names:
            assert forbidden not in class_methods, f"ConfigurationManager should not have {forbidden}"

    def test_should_only_handle_configuration_concerns(self):
        """ConfigurationManager should only handle configuration-related concerns."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager
        import inspect

        # Get all public methods of ConfigurationManager
        public_methods = [name for name, _ in inspect.getmembers(ConfigurationManager, inspect.isfunction)
                          if not name.startswith('_')]

        # All public methods should be configuration-related
        allowed_methods = {
            'load_and_validate', 'get_telegram_config', 'get_actions_config', 'get_bot_token'
        }

        for method in public_methods:
            assert method in allowed_methods, f"Unexpected public method: {method}"

    def test_should_not_import_telegram_modules(self):
        """ConfigurationManager should not import telegram modules."""
        # Read the source file to verify no telegram imports
        config_manager_file = Path(
            project_root) / 'local_orchestrator_tray' / 'configuration_manager.py'

        if config_manager_file.exists():
            source_code = config_manager_file.read_text()

            # Should not import telegram modules
            forbidden_imports = ['from telegram', 'import telegram']

            for forbidden in forbidden_imports:
                assert forbidden not in source_code, f"ConfigurationManager should not contain: {forbidden}"

    def test_should_not_import_rumps_modules(self):
        """ConfigurationManager should not import rumps modules."""
        # Read the source file to verify no rumps imports
        config_manager_file = Path(
            project_root) / 'local_orchestrator_tray' / 'configuration_manager.py'

        if config_manager_file.exists():
            source_code = config_manager_file.read_text()

            # Should not import rumps modules
            forbidden_imports = ['from rumps', 'import rumps']

            for forbidden in forbidden_imports:
                assert forbidden not in source_code, f"ConfigurationManager should not contain: {forbidden}"

    def test_should_have_minimal_dependencies(self):
        """ConfigurationManager should have minimal external dependencies."""
        # Read the source file to verify minimal dependencies
        config_manager_file = Path(
            project_root) / 'local_orchestrator_tray' / 'configuration_manager.py'

        if config_manager_file.exists():
            source_code = config_manager_file.read_text()

            # Should only import standard library and yaml
            allowed_imports = ['yaml', 'pathlib',
                               'Path', 'logging', 'traceback', 'typing']
            import_lines = [line.strip() for line in source_code.split('\n')
                            if line.strip().startswith(('import ', 'from '))]

            for line in import_lines:
                # Extract the module name from import statements
                if line.startswith('from '):
                    module = line.split()[1].split('.')[0]
                elif line.startswith('import '):
                    module = line.split()[1].split('.')[0]
                else:
                    continue

                # Allow standard library modules and yaml
                assert (module in allowed_imports or
                        module in ['sys', 'os', 'json', 're']), f"Unexpected import: {line}"


class TestConfigurationManagerErrorMessages:
    """Test ConfigurationManager error message consistency with TelegramClient."""

    def test_should_use_same_error_message_for_non_dict_config(self, temp_config_file):
        """Should use same error message as TelegramClient for non-dict config."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        # Write non-dict config
        with open(temp_config_file, 'w') as f:
            f.write('"not a dictionary"')

        manager = ConfigurationManager(temp_config_file)
        manager.load_and_validate()

        # Must match exact error message from TelegramClient
        assert manager.error == "Config file must contain a YAML dictionary"

    def test_should_use_same_error_message_for_invalid_telegram_section(self, temp_config_file):
        """Should use same error message as TelegramClient for invalid telegram section."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        invalid_config = {
            'telegram': "not a dictionary",
            'actions': {}
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(invalid_config, f)

        manager = ConfigurationManager(temp_config_file)
        manager.load_and_validate()

        # Must match exact error message from TelegramClient
        assert manager.error == "Telegram section must be a dictionary"

    def test_should_use_same_error_message_for_missing_bot_token(self, temp_config_file):
        """Should use same error message as TelegramClient for missing bot token."""
        from local_orchestrator_tray.configuration_manager import ConfigurationManager

        invalid_config = {
            'telegram': {},  # Missing bot_token
            'actions': {}
        }

        with open(temp_config_file, 'w') as f:
            yaml.dump(invalid_config, f)

        manager = ConfigurationManager(temp_config_file)
        manager.load_and_validate()

        # Must match exact error message from TelegramClient
        assert manager.error == "Missing or invalid Telegram bot token"


# Test fixtures for common test data
@pytest.fixture
def valid_config():
    """Fixture providing a valid configuration dictionary."""
    return {
        'telegram': {
            'bot_token': '123456789:ABCDEFghijklmnopqrstuvwxyz_test_token'
        },
        'actions': {
            'test_action': {
                'command': 'echo test',
                'description': 'Test action'
            }
        }
    }


@pytest.fixture
def invalid_config_non_dict():
    """Fixture providing an invalid configuration that is not a dictionary."""
    return "not a dictionary"


@pytest.fixture
def invalid_config_missing_bot_token():
    """Fixture providing a configuration missing bot token."""
    return {
        'telegram': {},
        'actions': {}
    }


@pytest.fixture
def invalid_config_uppercase_action():
    """Fixture providing a configuration with uppercase action name."""
    return {
        'telegram': {
            'bot_token': '123456789:ABCDEFghijklmnopqrstuvwxyz_test_token'
        },
        'actions': {
            'TestAction': {
                'command': 'echo test'
            }
        }
    }


@pytest.fixture
def temp_config_file():
    """Fixture providing a temporary config file path."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yield Path(f.name)
    # Cleanup after test
    Path(f.name).unlink(missing_ok=True)


if __name__ == '__main__':
    # Run the tests
    pytest.main([__file__, '-v'])
