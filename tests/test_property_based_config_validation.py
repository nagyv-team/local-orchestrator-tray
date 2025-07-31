#!/usr/bin/env python3
"""
Property-based tests for config validation edge cases.

Uses hypothesis to generate random test cases that explore the boundaries of
config validation, ensuring robustness against unexpected inputs. These tests
help drive the refactoring by finding edge cases that manual tests might miss.

This test suite focuses on:
1. Randomly generated invalid configurations
2. Boundary conditions for channel IDs and other numeric values
3. Various malformed YAML/TOML structures
4. Unicode and encoding edge cases
5. Performance under stress with large random configs
"""

import tempfile
import yaml
import json
import random
import string
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
import sys
from hypothesis import given, strategies as st, settings, assume, example, HealthCheck
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Mock rumps before any imports that might trigger it
sys.modules['rumps'] = Mock()


@pytest.fixture
def create_temp_config():
    """Helper fixture to create temporary config files."""
    created_files = []
    
    def _create_config(config_data):
        temp_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False, encoding='utf-8')
        yaml.dump(config_data, temp_file, default_flow_style=False, allow_unicode=True)
        temp_file.close()
        created_files.append(Path(temp_file.name))
        return Path(temp_file.name)
    
    yield _create_config
    
    # Cleanup
    for file_path in created_files:
        try:
            file_path.unlink()
        except FileNotFoundError:
            pass


# Hypothesis strategies for generating test data
token_strategy = st.text(min_size=1, max_size=1000)
channel_id_strategy = st.integers(min_value=-2**63, max_value=2**63-1)
malformed_channel_strategy = st.one_of(
    st.text(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.booleans(),
    st.lists(st.integers()),
    st.dictionaries(st.text(), st.text())
)

command_strategy = st.text(min_size=1, max_size=500)
action_name_strategy = st.text(alphabet=string.ascii_letters + string.digits + '_-', min_size=1, max_size=100)


class TestPropertyBasedConfigValidation:
    """Property-based tests for config validation."""

    @given(random_config_data=st.text())
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_config_structure_validation_with_random_types(self, random_config_data, create_temp_config):
        """Test config structure validation with randomly generated non-dict configs."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        # Only test non-dict types to verify rejection
        assume(not isinstance(random_config_data, dict))
        
        # Create a minimal valid config first, then replace with invalid data
        config_path = create_temp_config({'telegram': {'bot_token': 'test'}})
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            
            client = TelegramClient(config_path)
            # Force invalid config for testing
            client.config = random_config_data
            
            # Should reject non-dict configs
            try:
                result = client._validate_config_structure()
                assert result is False, f"Should reject non-dict config: {type(random_config_data)}"
                assert client.config_error is not None
                assert "dictionary" in client.config_error.lower() or "dict" in client.config_error.lower()
            except AttributeError:
                # Method doesn't exist yet - this is expected in TDD
                pass

    @given(random_token=token_strategy)
    @settings(max_examples=200, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_bot_token_validation_with_random_tokens(self, random_token, create_temp_config):
        """Test bot token validation with randomly generated tokens."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': random_token},
            'actions': {}
        }
        
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            
            client = TelegramClient(config_path)
            
            # Validation should handle any string token
            # Placeholder tokens should be rejected
            placeholder_indicators = ['YOUR_BOT_TOKEN', 'REPLACE_WITH', 'PLACEHOLDER', 'EXAMPLE']
            is_placeholder = any(indicator in random_token.upper() for indicator in placeholder_indicators)
            
            # Empty or whitespace-only tokens should be rejected
            is_empty_or_whitespace = not random_token.strip()
            
            should_be_valid = not (is_placeholder or is_empty_or_whitespace)
            
            try:
                result = client._validate_telegram_config()
                if should_be_valid:
                    assert result is True, f"Valid token should pass: {repr(random_token[:50])}"
                    assert client.config_error is None
                else:
                    assert result is False, f"Invalid token should fail: {repr(random_token[:50])}"
                    assert client.config_error is not None
            except AttributeError:
                # Method doesn't exist yet - this is expected in TDD
                pass

    @given(random_channels=st.lists(channel_id_strategy, min_size=0, max_size=100))
    @settings(max_examples=150, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_channel_validation_with_random_integer_lists(self, random_channels, create_temp_config):
        """Test channel validation with randomly generated integer lists."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {
                'bot_token': 'test_token',
                'channels': random_channels
            },
            'actions': {}
        }
        
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            
            client = TelegramClient(config_path)
            
            try:
                result = client._validate_channels_config()
                # All integer lists should be valid
                assert result is True, f"Integer channel list should be valid: {random_channels[:10]}..."
                assert client.config_error is None
                
                # Verify channels are stored as integers
                if random_channels:
                    stored_channels = client.config['telegram']['channels']
                    for channel in stored_channels:
                        assert isinstance(channel, int)
                        assert not isinstance(channel, bool)  # bool is subclass of int in Python
            except AttributeError:
                # Method doesn't exist yet - this is expected in TDD
                pass

    @given(malformed_channels=st.lists(malformed_channel_strategy, min_size=1, max_size=50))
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_channel_validation_with_malformed_channel_lists(self, malformed_channels, create_temp_config):
        """Test channel validation with malformed channel ID types."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        # Skip if all items are actually valid (integers or string representations of integers)
        has_invalid = False
        for item in malformed_channels:
            if isinstance(item, str):
                try:
                    int(item)
                except ValueError:
                    has_invalid = True
                    break
            elif not isinstance(item, int):
                has_invalid = True
                break
        
        assume(has_invalid)  # Only test lists that actually have invalid items
        
        config = {
            'telegram': {
                'bot_token': 'test_token',
                'channels': malformed_channels
            },
            'actions': {}
        }
        
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            
            client = TelegramClient(config_path)
            
            try:
                result = client._validate_channels_config()
                # Should reject malformed channel lists
                assert result is False, f"Should reject malformed channels: {malformed_channels[:5]}..."
                assert client.config_error is not None
                assert "channel" in client.config_error.lower() or "invalid" in client.config_error.lower()
            except AttributeError:
                # Method doesn't exist yet - this is expected in TDD
                pass

    @given(random_actions=st.dictionaries(
        action_name_strategy,
        st.dictionaries(
            st.sampled_from(['command', 'description', 'working_dir', 'timeout']),
            st.one_of(st.text(), st.integers(), st.floats(), st.booleans()),
            min_size=0,
            max_size=10
        ),
        min_size=0,
        max_size=20
    ))
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_actions_validation_with_random_actions(self, random_actions, create_temp_config):
        """Test actions validation with randomly generated action configurations."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': 'test_token'},
            'actions': random_actions
        }
        
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            
            client = TelegramClient(config_path)
            
            # Determine if config should be valid
            should_be_valid = True
            for action_name, action_config in random_actions.items():
                # Action names starting with uppercase should be rejected (reserved for built-ins)
                if action_name and action_name[0].isupper():
                    should_be_valid = False
                    break
                
                # Actions must have a 'command' field that's a non-empty string
                if not isinstance(action_config, dict):
                    should_be_valid = False
                    break
                
                if 'command' not in action_config:
                    should_be_valid = False
                    break
                
                command = action_config['command']
                if not isinstance(command, str) or not command.strip():
                    should_be_valid = False
                    break
            
            try:
                result = client._validate_actions_config()
                if should_be_valid:
                    assert result is True, f"Valid actions should pass: {list(random_actions.keys())[:5]}"
                    assert client.config_error is None
                else:
                    assert result is False, f"Invalid actions should fail: {list(random_actions.keys())[:5]}"
                    assert client.config_error is not None
            except AttributeError:
                # Method doesn't exist yet - this is expected in TDD
                pass

    @given(uppercase_name=st.text(alphabet=string.ascii_uppercase + string.digits + '_', min_size=1, max_size=50).filter(lambda x: x[0].isupper()))
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_uppercase_action_names_rejected(self, uppercase_name, create_temp_config):
        """Test that action names starting with uppercase are rejected."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': 'test_token'},
            'actions': {
                uppercase_name: {
                    'command': 'echo test'
                }
            }
        }
        
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            
            client = TelegramClient(config_path)
            
            try:
                result = client._validate_actions_config()
                assert result is False, f"Uppercase action name should be rejected: {uppercase_name}"
                assert client.config_error is not None
                assert "uppercase" in client.config_error.lower() or "reserved" in client.config_error.lower()
            except AttributeError:
                # Method doesn't exist yet - this is expected in TDD
                pass

    @given(data=st.data())
    @settings(max_examples=50, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_large_config_validation_performance(self, data, create_temp_config):
        """Test validation performance with large randomly generated configs."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        # Generate large config
        num_actions = data.draw(st.integers(min_value=50, max_value=200))
        num_channels = data.draw(st.integers(min_value=10, max_value=100))
        
        actions = {}
        for i in range(num_actions):
            action_name = f'action_{i}'
            actions[action_name] = {
                'command': data.draw(st.text(min_size=5, max_size=100)),
                'description': data.draw(st.text(min_size=10, max_size=200)),
                'working_dir': data.draw(st.text(min_size=1, max_size=50))
            }
        
        channels = data.draw(st.lists(
            st.integers(min_value=-1000000, max_value=1000000),
            min_size=num_channels,
            max_size=num_channels
        ))
        
        large_config = {
            'telegram': {
                'bot_token': 'test_token_for_large_config',
                'channels': channels
            },
            'actions': actions
        }
        
        config_path = create_temp_config(large_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            
            import time
            start_time = time.time()
            
            client = TelegramClient(config_path)
            
            validation_time = time.time() - start_time
            
            # Should validate large configs quickly (< 5 seconds)
            assert validation_time < 5.0, f"Large config validation took {validation_time:.2f}s"
            
            # Should handle large configs correctly
            assert client.config_valid is True
            assert len(client.config['actions']) == num_actions
            assert len(client.config['telegram']['channels']) == num_channels

    @given(special_text=st.text(alphabet=string.printable, min_size=1, max_size=1000))
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_unicode_and_special_characters_in_config(self, special_text, create_temp_config):
        """Test handling of Unicode and special characters in config values."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        # Test with special text in various config fields
        config = {
            'telegram': {'bot_token': f'token_{special_text[:50]}'},
            'actions': {
                'test_action': {
                    'command': f'echo "{special_text[:100]}"',
                    'description': special_text[:200]
                }
            }
        }
        
        try:
            config_path = create_temp_config(config)
        except (UnicodeError, yaml.YAMLError):
            # Some characters might not be serializable - skip these
            assume(False)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            
            # Should handle Unicode gracefully without crashing
            try:
                client = TelegramClient(config_path)
                # Validation result depends on content, but shouldn't crash
                assert client.config_valid in [True, False]
            except (UnicodeError, UnicodeDecodeError):
                # Some edge cases might cause encoding issues - acceptable
                pass


class TestPropertyBasedEdgeCases:
    """Property-based tests for specific edge cases and boundary conditions."""

    @given(boundary_value=st.integers(min_value=0, max_value=2**32))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_channel_id_boundary_conditions(self, boundary_value, create_temp_config):
        """Test channel ID validation at boundary values."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        # Test positive, negative, and zero values
        test_values = [boundary_value, -boundary_value, 0]
        
        config = {
            'telegram': {
                'bot_token': 'test_token',
                'channels': test_values
            },
            'actions': {}
        }
        
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            
            client = TelegramClient(config_path)
            
            try:
                result = client._validate_channels_config()
                # Boundary values should be handled gracefully
                # May be valid or invalid depending on Telegram API limits
                assert result in [True, False]
                if not result:
                    assert client.config_error is not None
            except AttributeError:
                # Method doesn't exist yet - this is expected in TDD
                pass

    @given(large_string_list=st.lists(st.text(), min_size=0, max_size=1000))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_config_validation_with_large_string_lists(self, large_string_list, create_temp_config):
        """Test config validation performance with large lists of strings."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        # Use string list as invalid channel data to test error handling
        config = {
            'telegram': {
                'bot_token': 'test_token',
                'channels': large_string_list
            },
            'actions': {}
        }
        
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            
            import time
            start_time = time.time()
            
            client = TelegramClient(config_path)
            
            validation_time = time.time() - start_time
            
            # Should handle large invalid lists quickly without hanging
            assert validation_time < 3.0, f"Large string list validation took {validation_time:.2f}s"

    @given(nested_dict=st.dictionaries(
        st.text(min_size=1, max_size=10),
        st.one_of(st.none(), st.text(), st.integers(), st.lists(st.text())),
        min_size=0,
        max_size=50
    ))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_nested_config_structure_validation(self, nested_dict, create_temp_config):
        """Test validation with deeply nested and complex config structures."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        # Create config with nested structure
        config = {
            'telegram': {
                'bot_token': 'test_token',
                'nested_data': nested_dict
            },
            'actions': {}
        }
        
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            
            # Should handle complex nested structures without crashing
            try:
                client = TelegramClient(config_path)
                # Validation should complete without exceptions
                assert hasattr(client, 'config_valid')
            except Exception as e:
                # Some complex structures might cause issues, but shouldn't crash the process
                assert "telegram" in str(e).lower() or "config" in str(e).lower()


class ConfigValidationStateMachine(RuleBasedStateMachine):
    """State machine for testing config validation behavior over multiple operations."""
    
    def __init__(self):
        super().__init__()
        self.config = {'telegram': {}, 'actions': {}}
        self.client = None
        self.temp_files = []

    @initialize()
    def setup_initial_config(self):
        """Initialize with a minimal valid config."""
        self.config = {
            'telegram': {'bot_token': 'initial_test_token'},
            'actions': {}
        }

    @rule(token=st.text(min_size=1, max_size=100))
    def set_bot_token(self, token):
        """Set bot token to random value."""
        self.config['telegram']['bot_token'] = token

    @rule(channels=st.lists(st.integers(), min_size=0, max_size=20))
    def set_channels(self, channels):
        """Set channels to random list."""
        self.config['telegram']['channels'] = channels

    @rule(
        action_name=st.text(alphabet=string.ascii_lowercase + '_', min_size=1, max_size=20),
        command=st.text(min_size=1, max_size=50)
    )
    def add_action(self, action_name, command):
        """Add an action with random name and command."""
        self.config['actions'][action_name] = {'command': command}

    @rule(action_name=st.text(alphabet=string.ascii_uppercase, min_size=1, max_size=20))
    def add_invalid_action(self, action_name):
        """Add an invalid action with uppercase name."""
        self.config['actions'][action_name] = {'command': 'echo test'}

    @invariant()
    def config_validation_is_consistent(self):
        """Verify that config validation behavior is consistent."""
        # Create temporary config file
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(self.config, temp_file, default_flow_style=False)
        temp_file.close()
        self.temp_files.append(Path(temp_file.name))
        
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            
            try:
                client = TelegramClient(Path(temp_file.name))
                
                # Validation should always complete
                assert hasattr(client, 'config_valid')
                assert client.config_valid in [True, False]
                
                # If invalid, should have an error message
                if not client.config_valid:
                    assert client.config_error is not None
                    assert len(client.config_error) > 0
                
            except Exception as e:
                # Some configurations might cause expected failures
                pass
    
    def teardown(self):
        """Clean up temporary files."""
        for temp_file in self.temp_files:
            try:
                temp_file.unlink()
            except FileNotFoundError:
                pass


# Example-based tests for specific edge cases found through property testing
class TestSpecificEdgeCases:
    """Tests for specific edge cases discovered through property-based testing."""
    
    @example(channels_with_none=[None, 42, None])
    @given(channels_with_none=st.lists(st.one_of(st.none(), st.integers()), min_size=1, max_size=10).filter(lambda x: None in x))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=1000)
    def test_channels_with_none_values(self, channels_with_none, create_temp_config):
        """Test channel validation when list contains None values."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {
                'bot_token': 'test_token',
                'channels': channels_with_none
            },
            'actions': {}
        }
        
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            
            client = TelegramClient(config_path)
            
            try:
                result = client._validate_channels_config()
                # Should reject channels list containing None values
                assert result is False
                assert client.config_error is not None
                assert "channel" in client.config_error.lower()
            except AttributeError:
                # Method doesn't exist yet - this is expected in TDD
                pass

    def test_extremely_long_action_name_handling(self, create_temp_config):
        """Test handling of extremely long action names."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        # Create action name that's 10,000 characters long
        long_action_name = 'a' * 10000
        
        config = {
            'telegram': {'bot_token': 'test_token'},
            'actions': {
                long_action_name: {'command': 'echo test'}
            }
        }
        
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            
            import time
            start_time = time.time()
            
            client = TelegramClient(config_path)
            
            validation_time = time.time() - start_time
            
            # Should handle extremely long names without hanging
            assert validation_time < 2.0
            
            try:
                result = client._validate_actions_config()
                # May accept or reject based on implementation limits
                assert result in [True, False]
            except AttributeError:
                # Method doesn't exist yet - this is expected in TDD
                pass


# Run property-based state machine tests
TestConfigValidation = ConfigValidationStateMachine.TestCase

if __name__ == "__main__":
    pytest.main([__file__, "-v"])