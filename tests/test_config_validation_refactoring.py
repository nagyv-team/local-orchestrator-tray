#!/usr/bin/env python3
"""
Comprehensive TDD test suite for validate_config method refactoring.

This test suite drives the decomposition of the monolithic validate_config method
(cyclomatic complexity 21) into focused, testable validation methods:

1. _validate_config_structure() - validates basic config structure
2. _validate_telegram_config() - validates telegram section including bot token  
3. _validate_channels_config() - validates channels configuration
4. _validate_actions_config() - validates actions section

The tests are written TDD-style to fail initially since the refactored methods
don't exist yet, but should pass once the implementation is complete.

This file is part of a comprehensive test suite that includes:
- Integration tests (test_integration_message_pipeline.py)
- Property-based tests (test_property_based_config_validation.py)
- Helper method tests (test_helper_method_extraction.py)
- Concurrent processing tests (test_concurrent_message_processing.py)
- Security tests (test_security_token_validation.py)
- Error recovery tests (test_error_recovery_scenarios.py)
- Performance tests (test_performance_and_load.py)
"""

import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
import sys

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Mock rumps before any imports that might trigger it
sys.modules['rumps'] = Mock()

# Test configuration constants
TEST_TIMEOUT = 30  # seconds
MAX_TEST_EXECUTION_TIME = 5.0  # seconds per test
MEMORY_LIMIT_MB = 100  # MB increase during test execution


@pytest.fixture
def create_temp_config():
    """Helper fixture to create temporary config files."""
    created_files = []
    
    def _create_config(config_data):
        temp_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False)
        yaml.dump(config_data, temp_file, default_flow_style=False)
        temp_file.close()
        created_files.append(Path(temp_file.name))
        return Path(temp_file.name)
    
    yield _create_config
    
    # Cleanup all created files
    for file_path in created_files:
        try:
            file_path.unlink()
        except FileNotFoundError:
            pass


@pytest.fixture
def mock_telegram_imports():
    """Mock telegram-related imports to avoid dependencies during testing."""
    with patch('telegram_client.Update'), \
         patch('telegram_client.Application'), \
         patch('telegram_client.MessageHandler'), \
         patch('telegram_client.filters'), \
         patch('telegram_client.ContextTypes'):
        yield


@pytest.fixture
def performance_monitor():
    """Monitor test performance and resource usage."""
    import time
    import psutil
    import os
    
    start_time = time.time()
    try:
        process = psutil.Process(os.getpid())
        start_memory = process.memory_info().rss / 1024 / 1024  # MB
    except:
        start_memory = 0
    
    yield
    
    # Check performance after test
    execution_time = time.time() - start_time
    try:
        process = psutil.Process(os.getpid())
        end_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = end_memory - start_memory
    except:
        memory_increase = 0
    
    # Assert performance constraints
    assert execution_time < MAX_TEST_EXECUTION_TIME, f"Test took too long: {execution_time:.2f}s"
    if memory_increase > MEMORY_LIMIT_MB:
        pytest.fail(f"Memory increase too high: {memory_increase:.2f}MB")


class TestConfigStructureValidation:
    """Test suite for _validate_config_structure() method."""
    
    def test_validate_config_structure_valid_dict(self, create_temp_config):
        """Test that _validate_config_structure accepts valid dictionary configs."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        valid_config = {
            'telegram': {'bot_token': 'test_token'},
            'actions': {}
        }
        
        config_path = create_temp_config(valid_config)
        
        try:
            client = TelegramClient(config_path)
            
            # Should pass basic structure validation
            result = client._validate_config_structure()
            assert result is True, "Valid dictionary config should pass structure validation"
            assert client.config_error is None, "No error should be set for valid structure"
        finally:
            config_path.unlink()
    
    def test_validate_config_structure_rejects_non_dict(self, create_temp_config):
        """Test that _validate_config_structure rejects non-dictionary configs."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        # Test various non-dict config types
        invalid_configs = [
            "string_config",
            ["list", "config"],
            123,
            None,
            True
        ]
        
        for invalid_config in invalid_configs:
            # Manually set config to test structure validation
            config_path = create_temp_config({})
            
            try:
                client = TelegramClient(config_path)
                client.config = invalid_config  # Force invalid config for testing
                
                result = client._validate_config_structure()
                assert result is False, f"Non-dict config {type(invalid_config)} should fail structure validation"
                assert client.config_error is not None, "Error should be set for invalid structure"
                assert "dictionary" in client.config_error.lower(), "Error should mention dictionary requirement"
            finally:
                config_path.unlink()
    
    def test_validate_config_structure_empty_dict_valid(self, create_temp_config):
        """Test that _validate_config_structure accepts empty dictionary."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        empty_config = {}
        config_path = create_temp_config(empty_config)
        
        try:
            client = TelegramClient(config_path)
            
            # Clear any error from full validation to test structure method in isolation
            client.config_error = None
            
            result = client._validate_config_structure()
            assert result is True, "Empty dictionary should pass structure validation"
            assert client.config_error is None, "No error should be set for empty dict"
        finally:
            config_path.unlink()
    
    def test_validate_config_structure_error_message_clarity(self, create_temp_config):
        """Test that _validate_config_structure provides clear error messages."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config({})
        
        try:
            client = TelegramClient(config_path)
            client.config = "invalid_string_config"
            
            result = client._validate_config_structure()
            assert result is False
            assert client.config_error is not None
            
            # Error message should be clear and helpful
            error_msg = client.config_error.lower()
            assert "config" in error_msg
            assert "dictionary" in error_msg or "dict" in error_msg
            assert "yaml" in error_msg or "must" in error_msg
        finally:
            config_path.unlink()


class TestTelegramConfigValidation:
    """Test suite for _validate_telegram_config() method."""
    
    def test_validate_telegram_config_valid_token(self, create_temp_config):
        """Test that _validate_telegram_config accepts valid bot tokens."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        valid_config = {
            'telegram': {
                'bot_token': '1234567890:ABCdefGHijklmnopQRSTuvwxyz'
            }
        }
        
        config_path = create_temp_config(valid_config)
        
        try:
            client = TelegramClient(config_path)
            
            result = client._validate_telegram_config()
            assert result is True, "Valid bot token should pass telegram config validation"
            assert client.config_error is None, "No error should be set for valid telegram config"
        finally:
            config_path.unlink()
    
    def test_validate_telegram_config_missing_telegram_section(self, create_temp_config):
        """Test that _validate_telegram_config handles missing telegram section."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_without_telegram = {
            'actions': {}
        }
        
        config_path = create_temp_config(config_without_telegram)
        
        try:
            client = TelegramClient(config_path)
            
            result = client._validate_telegram_config()
            assert result is False, "Missing telegram section should fail validation"
            assert client.config_error is not None
            assert "telegram" in client.config_error.lower()
        finally:
            config_path.unlink()
    
    def test_validate_telegram_config_invalid_telegram_section_type(self, create_temp_config):
        """Test that _validate_telegram_config rejects non-dict telegram sections."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        invalid_telegram_configs = [
            {'telegram': 'string_instead_of_dict'},
            {'telegram': ['list', 'instead', 'of', 'dict']},
            {'telegram': 123},
            {'telegram': None}
        ]
        
        for invalid_config in invalid_telegram_configs:
            config_path = create_temp_config(invalid_config)
            
            try:
                client = TelegramClient(config_path)
                
                result = client._validate_telegram_config()
                assert result is False, f"Invalid telegram section type should fail: {type(invalid_config['telegram'])}"
                assert client.config_error is not None
                assert "telegram" in client.config_error.lower()
                assert "dictionary" in client.config_error.lower()
            finally:
                config_path.unlink()
    
    def test_validate_telegram_config_missing_bot_token(self, create_temp_config):
        """Test that _validate_telegram_config requires bot_token."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        configs_without_token = [
            {'telegram': {}},
            {'telegram': {'other_field': 'value'}},
            {'telegram': {'bot_token': None}},
            {'telegram': {'bot_token': ''}},
            {'telegram': {'bot_token': '   '}}  # Whitespace only
        ]
        
        for config in configs_without_token:
            config_path = create_temp_config(config)
            
            try:
                client = TelegramClient(config_path)
                
                result = client._validate_telegram_config()
                assert result is False, f"Missing/invalid bot token should fail: {config['telegram'].get('bot_token')}"
                assert client.config_error is not None
                assert "token" in client.config_error.lower()
            finally:
                config_path.unlink()
    
    def test_validate_telegram_config_rejects_placeholder_tokens(self, create_temp_config):
        """Test that _validate_telegram_config rejects placeholder bot tokens."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        placeholder_tokens = [
            'YOUR_BOT_TOKEN_HERE',
            'REPLACE_WITH_YOUR_BOT_TOKEN',
            'YOUR_BOT_TOKEN',
            'PLACEHOLDER_TOKEN'
        ]
        
        for placeholder in placeholder_tokens:
            config_with_placeholder = {
                'telegram': {'bot_token': placeholder}
            }
            config_path = create_temp_config(config_with_placeholder)
            
            try:
                client = TelegramClient(config_path)
                
                result = client._validate_telegram_config()
                assert result is False, f"Placeholder token should be rejected: {placeholder}"
                assert client.config_error is not None
                assert "placeholder" in client.config_error.lower()
            finally:
                config_path.unlink()
    
    def test_validate_telegram_config_invalid_token_types(self, create_temp_config):
        """Test that _validate_telegram_config rejects non-string bot tokens."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        invalid_token_types = [
            123456789,
            ['token', 'as', 'list'],
            {'token': 'as_dict'},
            True,
            False
        ]
        
        for invalid_token in invalid_token_types:
            config_with_invalid_token = {
                'telegram': {'bot_token': invalid_token}
            }
            config_path = create_temp_config(config_with_invalid_token)
            
            try:
                client = TelegramClient(config_path)
                
                result = client._validate_telegram_config()
                assert result is False, f"Non-string token should be rejected: {type(invalid_token)}"
                assert client.config_error is not None
                assert "token" in client.config_error.lower()
            finally:
                config_path.unlink()


class TestChannelsConfigValidation:
    """Test suite for _validate_channels_config() method."""
    
    def test_validate_channels_config_valid_integer_channels(self, create_temp_config):
        """Test that _validate_channels_config accepts valid integer channel IDs."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        valid_configs = [
            {'telegram': {'bot_token': 'test_token', 'channels': [-1002345, -1002346]}},
            {'telegram': {'bot_token': 'test_token', 'channels': [1002345, 1002346]}},
            {'telegram': {'bot_token': 'test_token', 'channels': [-1002345, 1002346]}},  # Mixed positive/negative
            {'telegram': {'bot_token': 'test_token', 'channels': [0, -1, 1]}},  # Edge values
            {'telegram': {'bot_token': 'test_token', 'channels': []}}  # Empty list
        ]
        
        for config in valid_configs:
            config_path = create_temp_config(config)
            
            try:
                client = TelegramClient(config_path)
                
                result = client._validate_channels_config()
                assert result is True, f"Valid channel config should pass: {config['telegram']['channels']}"
                assert client.config_error is None
                
                # Verify channels are stored as integers
                channels = client.config['telegram']['channels']
                for channel in channels:
                    assert isinstance(channel, int), f"Channel ID should be integer: {channel}"
                    assert not isinstance(channel, bool), "Channel ID should not be boolean"
            finally:
                config_path.unlink()
    
    def test_validate_channels_config_string_to_integer_conversion(self, create_temp_config):
        """Test that _validate_channels_config converts string channel IDs to integers."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        string_channel_configs = [
            {'telegram': {'bot_token': 'test_token', 'channels': ['-1002345', '-1002346']}},
            {'telegram': {'bot_token': 'test_token', 'channels': ['1002345', '1002346']}},
            {'telegram': {'bot_token': 'test_token', 'channels': ['-1002345', 1002346]}},  # Mixed string/int
            {'telegram': {'bot_token': 'test_token', 'channels': ['0', '-1', '1']}}  # Edge values as strings
        ]
        
        expected_results = [
            [-1002345, -1002346],
            [1002345, 1002346],
            [-1002345, 1002346],
            [0, -1, 1]
        ]
        
        for config, expected in zip(string_channel_configs, expected_results):
            config_path = create_temp_config(config)
            
            try:
                client = TelegramClient(config_path)
                
                result = client._validate_channels_config()
                assert result is True, f"String channel config should be converted: {config['telegram']['channels']}"
                assert client.config_error is None
                
                # Verify string channels were converted to integers
                channels = client.config['telegram']['channels']
                assert channels == expected, f"Channels should be converted to integers: {channels} != {expected}"
                
                for channel in channels:
                    assert isinstance(channel, int), f"Converted channel should be integer: {channel}"
            finally:
                config_path.unlink()
    
    def test_validate_channels_config_missing_channels_defaults_empty(self, create_temp_config):
        """Test that _validate_channels_config defaults to empty list when channels missing."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        configs_without_channels = [
            {'telegram': {'bot_token': 'test_token'}},
            {'telegram': {'bot_token': 'test_token'}},
            {'telegram': {'bot_token': 'test_token', 'channels': None}}  # Explicit None
        ]
        
        for config in configs_without_channels:
            config_path = create_temp_config(config)
            
            try:
                client = TelegramClient(config_path)
                
                result = client._validate_channels_config()
                assert result is True, "Missing channels should default to empty list"
                assert client.config_error is None
                
                # Should default channels to empty list for backward compatibility
                channels = client.config['telegram'].get('channels', [])
                assert channels == [], f"Missing channels should default to empty list: {channels}"
            finally:
                config_path.unlink()
    
    def test_validate_channels_config_rejects_non_list_channels(self, create_temp_config):
        """Test that _validate_channels_config rejects non-list channel configurations."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        invalid_channel_configs = [
            {'telegram': {'channels': 'not_a_list'}},
            {'telegram': {'channels': {'channel1': -1002345}}},
            {'telegram': {'channels': 123456}},
            {'telegram': {'channels': True}}
        ]
        
        for config in invalid_channel_configs:
            config_path = create_temp_config(config)
            
            try:
                client = TelegramClient(config_path)
                
                result = client._validate_channels_config()
                assert result is False, f"Non-list channels should be rejected: {type(config['telegram']['channels'])}"
                assert client.config_error is not None
                assert "list" in client.config_error.lower()
            finally:
                config_path.unlink()
    
    def test_validate_channels_config_rejects_invalid_channel_ids(self, create_temp_config):
        """Test that _validate_channels_config rejects invalid channel ID types."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        invalid_channel_id_configs = [
            {'telegram': {'channels': ['not_a_number']}},
            {'telegram': {'channels': ['@channel_name']}},
            {'telegram': {'channels': [123.45]}},  # Float
            {'telegram': {'channels': [True, False]}},  # Booleans
            {'telegram': {'channels': [[]]}},  # Nested list
            {'telegram': {'channels': [{}]}},  # Dict in list
            {'telegram': {'channels': [None]}},  # None values
            {'telegram': {'channels': [-1002345, 'invalid', 1002346]}}  # Mixed valid/invalid
        ]
        
        for config in invalid_channel_id_configs:
            config_path = create_temp_config(config)
            
            try:
                client = TelegramClient(config_path)
                
                result = client._validate_channels_config()
                assert result is False, f"Invalid channel IDs should be rejected: {config['telegram']['channels']}"
                assert client.config_error is not None
                assert "channel" in client.config_error.lower()
                assert "invalid" in client.config_error.lower() or "numeric" in client.config_error.lower()
            finally:
                config_path.unlink()
    
    def test_validate_channels_config_boundary_values(self, create_temp_config):
        """Test that _validate_channels_config handles boundary channel ID values."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        boundary_configs = [
            {'telegram': {'bot_token': 'test_token', 'channels': [0]}},  # Zero
            {'telegram': {'bot_token': 'test_token', 'channels': [-1, 1]}},  # ±1
            {'telegram': {'bot_token': 'test_token', 'channels': [-9223372036854775808, 9223372036854775807]}},  # Max/min int64
            {'telegram': {'bot_token': 'test_token', 'channels': ['-9223372036854775808', '9223372036854775807']}}  # As strings
        ]
        
        for config in boundary_configs:
            config_path = create_temp_config(config)
            
            try:
                client = TelegramClient(config_path)
                
                result = client._validate_channels_config()
                # Should handle boundary values gracefully (may accept or reject based on Telegram API limits)
                if result:
                    assert client.config_error is None
                    channels = client.config['telegram']['channels']
                    for channel in channels:
                        assert isinstance(channel, int)
                else:
                    assert client.config_error is not None
                    assert "channel" in client.config_error.lower()
            finally:
                config_path.unlink()
    
    def test_validate_channels_config_large_channel_list_performance(self, create_temp_config):
        """Test that _validate_channels_config handles large channel lists efficiently."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        # Create config with 1000 channels
        large_channels = list(range(-1000000, -1000000 + 1000))
        config = {'telegram': {'channels': large_channels}}
        config_path = create_temp_config(config)
        
        try:
            import time
            start_time = time.time()
            
            client = TelegramClient(config_path)
            result = client._validate_channels_config()
            
            validation_time = time.time() - start_time
            
            assert result is True, "Large channel list should be validated successfully"
            assert validation_time < 1.0, f"Validation should be fast even with large lists: {validation_time:.2f}s"
            assert len(client.config['telegram']['channels']) == 1000
        finally:
            config_path.unlink()


class TestActionsConfigValidation:
    """Test suite for _validate_actions_config() method."""
    
    def test_validate_actions_config_valid_actions(self, create_temp_config):
        """Test that _validate_actions_config accepts valid action configurations."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        valid_configs = [
            # Basic action
            {
                'telegram': {'bot_token': 'test_token'},
                'actions': {
                    'deploy': {
                        'command': 'docker-compose up -d'
                    }
                }
            },
            # Action with description and working_dir
            {
                'telegram': {'bot_token': 'test_token'},
                'actions': {
                    'build': {
                        'command': 'npm run build',
                        'description': 'Build the application',
                        'working_dir': '/app'
                    }
                }
            },
            # Multiple actions
            {
                'telegram': {'bot_token': 'test_token'},
                'actions': {
                    'start': {'command': 'systemctl start service'},
                    'stop': {'command': 'systemctl stop service'},
                    'status': {'command': 'systemctl status service'}
                }
            },
            # Empty actions section
            {'telegram': {'bot_token': 'test_token'}, 'actions': {}}
        ]
        
        for config in valid_configs:
            config_path = create_temp_config(config)
            
            try:
                client = TelegramClient(config_path)
                
                result = client._validate_actions_config()
                assert result is True, f"Valid actions config should pass: {list(config['actions'].keys())}"
                assert client.config_error is None
            finally:
                config_path.unlink()
    
    def test_validate_actions_config_missing_actions_section(self, create_temp_config):
        """Test that _validate_actions_config handles missing actions section."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_without_actions = {
            'telegram': {'bot_token': 'test'}
        }
        
        config_path = create_temp_config(config_without_actions)
        
        try:
            client = TelegramClient(config_path)
            
            result = client._validate_actions_config()
            assert result is True, "Missing actions section should be acceptable"
            assert client.config_error is None
            
            # Should default to empty actions
            assert 'actions' in client.config
            assert client.config['actions'] == {}
        finally:
            config_path.unlink()
    
    def test_validate_actions_config_invalid_actions_section_type(self, create_temp_config):
        """Test that _validate_actions_config rejects non-dict actions sections."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        invalid_actions_configs = [
            {'actions': 'string_instead_of_dict'},
            {'actions': ['list', 'of', 'actions']},
            {'actions': 123},
            {'actions': None}
        ]
        
        for config in invalid_actions_configs:
            config_path = create_temp_config(config)
            
            try:
                client = TelegramClient(config_path)
                
                result = client._validate_actions_config()
                assert result is False, f"Invalid actions section type should fail: {type(config['actions'])}"
                assert client.config_error is not None
                assert "actions" in client.config_error.lower()
                assert "dictionary" in client.config_error.lower()
            finally:
                config_path.unlink()
    
    def test_validate_actions_config_rejects_uppercase_action_names(self, create_temp_config):
        """Test that _validate_actions_config rejects action names starting with uppercase (reserved for built-ins)."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        uppercase_action_configs = [
            {
                'actions': {
                    'Deploy': {'command': 'docker up'}  # Starts with uppercase
                }
            },
            {
                'actions': {
                    'Notification': {'command': 'echo test'}  # Built-in action name
                }
            },
            {
                'actions': {
                    'STATUS': {'command': 'uptime'}  # All uppercase
                }
            },
            {
                'actions': {
                    'deploy': {'command': 'docker up'},  # Valid
                    'Build': {'command': 'npm run build'}  # Invalid mixed with valid
                }
            }
        ]
        
        for config in uppercase_action_configs:
            config_path = create_temp_config(config)
            
            try:
                client = TelegramClient(config_path)
                
                result = client._validate_actions_config()
                assert result is False, f"Uppercase action names should be rejected: {list(config['actions'].keys())}"
                assert client.config_error is not None
                assert "uppercase" in client.config_error.lower()
                assert "reserved" in client.config_error.lower() or "built-in" in client.config_error.lower()
            finally:
                config_path.unlink()
    
    def test_validate_actions_config_invalid_action_structure(self, create_temp_config):
        """Test that _validate_actions_config rejects invalid action structures."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        invalid_action_structures = [
            # Action is not a dict
            {
                'actions': {
                    'deploy': 'string_instead_of_dict'
                }
            },
            # Action is a list
            {
                'actions': {
                    'deploy': ['command', 'list']
                }
            },
            # Action is a number
            {
                'actions': {
                    'deploy': 123
                }
            },
            # Action is None
            {
                'actions': {
                    'deploy': None
                }
            }
        ]
        
        for config in invalid_action_structures:
            config_path = create_temp_config(config)
            
            try:
                client = TelegramClient(config_path)
                
                result = client._validate_actions_config()
                assert result is False, f"Invalid action structure should be rejected: {type(list(config['actions'].values())[0])}"
                assert client.config_error is not None
                assert "dictionary" in client.config_error.lower()
            finally:
                config_path.unlink()
    
    def test_validate_actions_config_missing_command_field(self, create_temp_config):
        """Test that _validate_actions_config requires 'command' field in actions."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        missing_command_configs = [
            # No command field
            {
                'telegram': {'bot_token': 'test_token'},
                'actions': {
                    'deploy': {
                        'description': 'Deploy application'
                    }
                }
            },
            # Empty command
            {
                'telegram': {'bot_token': 'test_token'},
                'actions': {
                    'deploy': {
                        'command': ''
                    }
                }
            },
            # Command is None
            {
                'telegram': {'bot_token': 'test_token'},
                'actions': {
                    'deploy': {
                        'command': None
                    }
                }
            },
            # Command is not a string
            {
                'telegram': {'bot_token': 'test_token'},
                'actions': {
                    'deploy': {
                        'command': ['docker', 'up']
                    }
                }
            }
        ]
        
        for config in missing_command_configs:
            config_path = create_temp_config(config)
            
            try:
                client = TelegramClient(config_path)
                
                result = client._validate_actions_config()
                assert result is False, f"Missing/invalid command should be rejected"
                assert client.config_error is not None
                assert "command" in client.config_error.lower()
                assert "required" in client.config_error.lower() or "missing" in client.config_error.lower()
            finally:
                config_path.unlink()
    
    def test_validate_actions_config_optional_fields_accepted(self, create_temp_config):
        """Test that _validate_actions_config accepts optional fields in actions."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        optional_fields_config = {
            'telegram': {'bot_token': 'test_token'},  # Add required telegram config
            'actions': {
                'deploy': {
                    'command': 'docker-compose up -d',
                    'description': 'Deploy the application to production',
                    'working_dir': '/app/production',
                    'timeout': 300,  # Custom field should be ignored but not fail validation
                    'environment': 'production'  # Another custom field
                }
            }
        }
        
        config_path = create_temp_config(optional_fields_config)
        
        try:
            client = TelegramClient(config_path)
            
            result = client._validate_actions_config()
            assert result is True, "Actions with optional fields should pass validation"
            assert client.config_error is None
            
            # Verify action is properly stored
            deploy_action = client.config['actions']['deploy']
            assert deploy_action['command'] == 'docker-compose up -d'
            assert deploy_action['description'] == 'Deploy the application to production'
            assert deploy_action['working_dir'] == '/app/production'
        finally:
            config_path.unlink()
    
    def test_validate_actions_config_error_message_includes_action_name(self, create_temp_config):
        """Test that _validate_actions_config includes action name in error messages."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_with_invalid_action = {
            'actions': {
                'deploy': {'command': 'docker up'},  # Valid
                'invalid_action': {},  # Missing command
                'another_action': {'command': 'ls'}  # Valid
            }
        }
        
        config_path = create_temp_config(config_with_invalid_action)
        
        try:
            client = TelegramClient(config_path)
            
            result = client._validate_actions_config()
            assert result is False, "Invalid action should fail validation"
            assert client.config_error is not None
            
            # Error message should include the specific action name that failed
            assert "invalid_action" in client.config_error
        finally:
            config_path.unlink()


class TestValidationIntegration:
    """Integration tests for the refactored validation methods working together."""
    
    def test_validate_config_calls_all_validation_methods(self, create_temp_config):
        """Test that validate_config calls all individual validation methods."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        from unittest.mock import patch
        
        valid_config = {
            'telegram': {
                'bot_token': 'valid_token_123',
                'channels': [-1002345]
            },
            'actions': {
                'deploy': {'command': 'docker up'}
            }
        }
        
        config_path = create_temp_config(valid_config)
        
        try:
            client = TelegramClient(config_path)
            
            # Mock individual validation methods to track calls
            with patch.object(client, '_validate_config_structure', return_value=True) as mock_structure, \
                 patch.object(client, '_validate_telegram_config', return_value=True) as mock_telegram, \
                 patch.object(client, '_validate_channels_config', return_value=True) as mock_channels, \
                 patch.object(client, '_validate_actions_config', return_value=True) as mock_actions:
                
                client.validate_config()
                
                # All validation methods should be called
                mock_structure.assert_called_once()
                mock_telegram.assert_called_once()
                mock_channels.assert_called_once()
                mock_actions.assert_called_once()
                
                # Overall validation should succeed
                assert client.config_valid is True
                assert client.config_error is None
        finally:
            config_path.unlink()
    
    def test_validate_config_stops_on_first_failure(self, create_temp_config):
        """Test that validate_config stops validation on first failure."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        from unittest.mock import patch
        
        config_path = create_temp_config({})
        
        try:
            client = TelegramClient(config_path)
            
            # Mock validation methods with first one failing
            with patch.object(client, '_validate_config_structure', return_value=False) as mock_structure, \
                 patch.object(client, '_validate_telegram_config', return_value=True) as mock_telegram, \
                 patch.object(client, '_validate_channels_config', return_value=True) as mock_channels, \
                 patch.object(client, '_validate_actions_config', return_value=True) as mock_actions:
                
                client.config_error = "Structure error"  # Set error for first failure
                client.validate_config()
                
                # Only structure validation should be called
                mock_structure.assert_called_once()
                mock_telegram.assert_not_called()
                mock_channels.assert_not_called()
                mock_actions.assert_not_called()
                
                # Overall validation should fail
                assert client.config_valid is False
                assert client.config_error == "Structure error"
        finally:
            config_path.unlink()
    
    def test_validate_config_maintains_backward_compatibility(self, create_temp_config):
        """Test that refactored validate_config maintains exact backward compatibility."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        # Test configs that should work exactly as before
        backward_compatible_configs = [
            # Basic config without channels
            {
                'telegram': {'bot_token': 'test_token'},
                'actions': {'deploy': {'command': 'docker up'}}
            },
            # Config with placeholder token (should fail)
            {
                'telegram': {'bot_token': 'YOUR_BOT_TOKEN_HERE'},
                'actions': {}
            },
            # Config with invalid action name
            {
                'telegram': {'bot_token': 'test_token'},
                'actions': {'Deploy': {'command': 'docker up'}}  # Uppercase
            },
            # Config with mixed channel types
            {
                'telegram': {
                    'bot_token': 'test_token',
                    'channels': [-1002345, '-1002346']
                },
                'actions': {}
            }
        ]
        
        expected_results = [True, False, False, True]
        
        for config, expected_valid in zip(backward_compatible_configs, expected_results):
            config_path = create_temp_config(config)
            
            try:
                client = TelegramClient(config_path)
                
                # Validation result should match expected behavior
                assert client.config_valid == expected_valid, f"Backward compatibility failed for config: {config}"
                
                if expected_valid:
                    assert client.config_error is None
                    # Channels should be properly handled
                    if 'channels' in config.get('telegram', {}):
                        channels = client.config['telegram']['channels']
                        for channel in channels:
                            assert isinstance(channel, int), f"Channel should be converted to int: {channel}"
                else:
                    assert client.config_error is not None
            finally:
                config_path.unlink()
    
    def test_validate_config_error_propagation(self, create_temp_config):
        """Test that validate_config properly propagates errors from individual methods."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        from unittest.mock import patch
        
        config_path = create_temp_config({})
        
        try:
            client = TelegramClient(config_path)
            
            # Test error propagation from each validation method
            error_scenarios = [
                ('_validate_config_structure', "Config structure error"),
                ('_validate_telegram_config', "Telegram config error"),
                ('_validate_channels_config', "Channels config error"),
                ('_validate_actions_config', "Actions config error")
            ]
            
            for failing_method, error_message in error_scenarios:
                # Reset client state
                client.config_valid = False
                client.config_error = None
                
                # Create mocks where only the target method fails
                mock_returns = {method: True for method, _ in error_scenarios}
                mock_returns[failing_method] = False
                
                with patch.object(client, '_validate_config_structure', return_value=mock_returns['_validate_config_structure']) as mock_structure, \
                     patch.object(client, '_validate_telegram_config', return_value=mock_returns['_validate_telegram_config']) as mock_telegram, \
                     patch.object(client, '_validate_channels_config', return_value=mock_returns['_validate_channels_config']) as mock_channels, \
                     patch.object(client, '_validate_actions_config', return_value=mock_returns['_validate_actions_config']) as mock_actions:
                    
                    # Set error when the failing method is called
                    if failing_method == '_validate_config_structure':
                        mock_structure.side_effect = lambda: setattr(client, 'config_error', error_message) or False
                    elif failing_method == '_validate_telegram_config':
                        mock_telegram.side_effect = lambda: setattr(client, 'config_error', error_message) or False
                    elif failing_method == '_validate_channels_config':
                        mock_channels.side_effect = lambda: setattr(client, 'config_error', error_message) or False
                    elif failing_method == '_validate_actions_config':
                        mock_actions.side_effect = lambda: setattr(client, 'config_error', error_message) or False
                    
                    client.validate_config()
                    
                    # Validation should fail with the correct error
                    assert client.config_valid is False, f"Should fail when {failing_method} fails"
                    assert client.config_error == error_message, f"Should propagate error from {failing_method}"
        finally:
            config_path.unlink()


class TestValidationPerformance:
    """Performance tests for validation methods."""
    
    def test_validation_performance_with_large_configs(self, create_temp_config):
        """Test that validation performs well with large configurations."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        import time
        
        # Create large config
        large_config = {
            'telegram': {
                'bot_token': 'test_token_performance',
                'channels': list(range(-1000000, -1000000 + 500))  # 500 channels
            },
            'actions': {
                f'action_{i}': {
                    'command': f'echo action_{i}',
                    'description': f'Description for action {i}',
                    'working_dir': f'/app/action_{i}'
                }
                for i in range(100)  # 100 actions
            }
        }
        
        config_path = create_temp_config(large_config)
        
        try:
            start_time = time.time()
            
            client = TelegramClient(config_path)
            
            validation_time = time.time() - start_time
            
            # Should complete validation quickly even with large config
            assert validation_time < 2.0, f"Validation took too long: {validation_time:.2f}s"
            assert client.config_valid is True, "Large config should be valid"
            assert len(client.config['telegram']['channels']) == 500
            assert len(client.config['actions']) == 100
        finally:
            config_path.unlink()
    
    def test_individual_validation_methods_performance(self, create_temp_config):
        """Test that individual validation methods perform well."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        import time
        
        # Create config optimized for each validation method
        config = {
            'telegram': {
                'bot_token': 'test_token_performance',
                'channels': list(range(-100000, -100000 + 1000))  # 1000 channels for channels validation
            },
            'actions': {
                f'action_{i}': {
                    'command': f'echo action_{i}',
                    'description': f'Description for action {i}'
                }
                for i in range(500)  # 500 actions for actions validation
            }
        }
        
        config_path = create_temp_config(config)
        
        try:
            client = TelegramClient(config_path)
            
            # Test each validation method individually for performance
            validation_methods = [
                ('_validate_config_structure', 0.01),  # Should be very fast
                ('_validate_telegram_config', 0.01),   # Should be very fast
                ('_validate_channels_config', 0.1),    # May take longer due to type conversion
                ('_validate_actions_config', 0.1)      # May take longer due to iteration
            ]
            
            for method_name, max_time in validation_methods:
                start_time = time.time()
                
                method = getattr(client, method_name)
                result = method()
                
                method_time = time.time() - start_time
                
                assert result is True, f"{method_name} should succeed"
                assert method_time < max_time, f"{method_name} took too long: {method_time:.3f}s > {max_time}s"
        finally:
            config_path.unlink()


if __name__ == "__main__":
    # Run tests with pytest if called directly
    import pytest
    pytest.main([__file__, "-v"])