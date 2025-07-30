#!/usr/bin/env python3
"""
Pytest-based tests for Telegram integration functionality.
Tests all features with proper mocking of the telegram library.
"""

import asyncio
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import pytest
import sys
import os

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Mock rumps before any imports that might trigger it
sys.modules['rumps'] = Mock()


@pytest.fixture
def mock_telegram():
    """Mock the telegram library components."""
    # Ensure module path is set
    sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
    
    with patch('telegram_client.Update'), \
            patch('telegram_client.Application') as mock_app_class, \
            patch('telegram_client.MessageHandler'), \
            patch('telegram_client.filters'), \
            patch('telegram_client.ContextTypes'):

        # Mock the Application instance
        mock_app = Mock()
        mock_app.initialize = AsyncMock()
        mock_app.start = AsyncMock()
        mock_app.stop = AsyncMock()
        mock_app.shutdown = AsyncMock()
        mock_app.add_handler = Mock()

        # Mock the updater
        mock_updater = Mock()
        mock_updater.start_polling = AsyncMock()
        mock_updater.stop = AsyncMock()
        mock_app.updater = mock_updater

        # Mock the builder
        mock_builder = Mock()
        mock_builder.token.return_value = mock_builder
        mock_builder.build.return_value = mock_app
        mock_app_class.builder.return_value = mock_builder

        yield {
            'Application': mock_app_class,
            'app_instance': mock_app,
            'updater': mock_updater,
            'builder': mock_builder
        }


@pytest.fixture
def test_config():
    """Create a temporary test configuration."""
    config_data = {
        'telegram': {
            'bot_token': 'test_token_123'
        },
        'actions': {
            'hello': {
                'command': 'echo',
                'description': 'Print hello message'
            },
            'list-files': {
                'command': 'ls',
                'description': 'List files in directory',
                'working_dir': '/tmp'
            }
        }
    }

    temp_file = tempfile.NamedTemporaryFile(
        mode='w', suffix='.yaml', delete=False)
    yaml.dump(config_data, temp_file, default_flow_style=False)
    temp_file.close()

    yield Path(temp_file.name)

    # Cleanup
    Path(temp_file.name).unlink()


class TestActionRegistry:
    """Test the action registry system."""

    def test_action_registration(self):
        """Test registering and retrieving actions."""
        # Import directly from the module to avoid main.py import
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import ActionRegistry

        registry = ActionRegistry()

        # Register an action
        registry.register_action(
            name="test-action",
            command="echo hello",
            description="Test action",
            working_dir="/tmp"
        )

        # Verify action was registered
        action = registry.get_action("test-action")
        assert action is not None
        assert action['command'] == "echo hello"
        assert action['description'] == "Test action"
        assert action['working_dir'] == "/tmp"

        # Test non-existent action
        assert registry.get_action("nonexistent") is None

    def test_action_listing(self):
        """Test listing available actions."""
        # Import directly from the module to avoid main.py import
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import ActionRegistry

        registry = ActionRegistry()

        # Empty registry
        assert registry.list_actions() == []

        # Add some actions
        registry.register_action("action1", "echo 1", "First action")
        registry.register_action("action2", "echo 2", "Second action")

        actions = registry.list_actions()
        assert len(actions) == 2
        assert "action1" in actions
        assert "action2" in actions

        # Test descriptions
        desc = registry.get_actions_description()
        assert "action1" in desc
        assert "action2" in desc
        assert "First action" in desc


class TestTelegramClient:
    """Test the Telegram client functionality."""

    def test_config_loading(self, test_config):
        """Test configuration loading."""
        # Import directly from the module to avoid main.py import  
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient

        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):

            client = TelegramClient(test_config)

            # Verify config was loaded
            assert 'telegram' in client.config
            assert 'actions' in client.config
            assert client.config['telegram']['bot_token'] == 'test_token_123'

            # Verify actions were registered
            actions = client.action_registry.list_actions()
            assert 'hello' in actions
            assert 'list-files' in actions

            hello_action = client.action_registry.get_action('hello')
            assert hello_action['command'] == 'echo'

    def test_toml_parsing(self, test_config):
        """Test TOML message parsing."""
        # Import directly from the module to avoid main.py import
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient

        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):

            client = TelegramClient(test_config)

            # Test valid TOML
            toml_text = """
[hello]
name = "world"
count = 3

[list-files]
directory = "/home"
"""

            result = client.parse_toml_message(toml_text)
            assert result is not None
            assert 'hello' in result
            assert 'list-files' in result
            assert result['hello']['name'] == "world"
            assert result['hello']['count'] == 3

            # Test invalid TOML
            invalid_toml = "this is not toml [broken"
            result = client.parse_toml_message(invalid_toml)
            assert result is None

            # Test non-TOML text
            plain_text = "Hello, this is just plain text"
            result = client.parse_toml_message(plain_text)
            assert result is None

    @pytest.mark.asyncio
    async def test_action_execution(self, test_config):
        """Test action execution with parameters."""
        # Import directly from the module to avoid main.py import
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient

        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:

            # Mock successful command execution
            mock_run.return_value = Mock(
                stdout="hello world",
                stderr="",
                returncode=0
            )

            client = TelegramClient(test_config)

            # Test simple echo command
            action_config = {'command': 'echo hello world'}
            params = {}

            result = await client.execute_action(action_config, params)
            assert result.strip() == "hello world"

            # Verify subprocess was called correctly
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == ['echo', 'hello', 'world']

    @pytest.mark.asyncio
    async def test_action_execution_with_params(self, test_config):
        """Test action execution with parameters."""
        # Import directly from the module to avoid main.py import
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient

        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:

            # Mock successful command execution
            mock_run.return_value = Mock(
                stdout="command executed",
                stderr="",
                returncode=0
            )

            client = TelegramClient(test_config)

            # Test command with parameters
            action_config = {'command': 'echo'}
            params = {'message': 'test', 'count': '2'}

            result = await client.execute_action(action_config, params)
            assert "command executed" in result

            # Verify parameters were converted to CLI args
            call_args = mock_run.call_args[0][0]
            assert 'echo' in call_args
            assert '--message' in call_args
            assert 'test' in call_args
            assert '--count' in call_args
            assert '2' in call_args

    @pytest.mark.asyncio
    async def test_camel_case_to_kebab_case_conversion(self, test_config):
        """Test that camelCase parameters are converted to kebab-case CLI args (issue #8)."""
        # Import directly from the module to avoid main.py import
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient

        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:

            # Mock successful command execution
            mock_run.return_value = Mock(
                stdout="command executed",
                stderr="",
                returncode=0
            )

            client = TelegramClient(test_config)

            # Test cases for camelCase to kebab-case conversion
            test_cases = [
                ("myKey", "my-key"),
                ("dayOfYear", "day-of-year"),
                ("someVeryLongVariableName", "some-very-long-variable-name"),
                ("userName", "user-name"),
                ("firstName", "first-name"),
                ("lastName", "last-name"),
                ("accessToken", "access-token"),
                ("baseUrl", "base-url"),
                ("configFile", "config-file"),
                ("timeStamp", "time-stamp"),
                # Edge cases
                ("a", "a"),  # Single letter
                ("aB", "a-b"),  # Two letters
                ("camelCaseExample", "camel-case-example"),
                # Already kebab-case or snake_case should work too
                ("already-kebab", "already-kebab"),
                ("snake_case", "snake-case"),  # Should convert underscores
                ("mixed_caseExample", "mixed-case-example"),  # Mixed formats
            ]

            action_config = {'command': 'echo'}

            for input_param, expected_cli_arg in test_cases:
                # Reset mock for each test case
                mock_run.reset_mock()
                
                # Test with single parameter
                params = {input_param: 'testValue'}
                
                await client.execute_action(action_config, params)
                
                # Verify the command was called with correct kebab-case argument
                call_args = mock_run.call_args[0][0]
                expected_flag = f'--{expected_cli_arg}'
                
                assert expected_flag in call_args, \
                    f"Parameter '{input_param}' should become '{expected_flag}' but got {call_args}"
                assert 'testValue' in call_args, \
                    f"Parameter value should be preserved in {call_args}"

            # Test the specific issue #8 example: myKey should become --my-key
            mock_run.reset_mock()
            params = {'myKey': 'myValue'}
            await client.execute_action(action_config, params)
            
            call_args = mock_run.call_args[0][0]
            assert '--my-key' in call_args, \
                f"Issue #8: 'myKey' should become '--my-key' but got {call_args}"
            assert '--mykey' not in call_args, \
                f"Issue #8: Should NOT have '--mykey' in {call_args}"

    def test_connection_status(self, test_config):
        """Test connection status tracking."""
        # Import directly from the module to avoid main.py import
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient

        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):

            client = TelegramClient(test_config)

            # Initial status
            status = client.get_connection_status()
            assert status is not None

            # Test status changes
            client.connection_status = "Connected"
            assert "Connected" in client.get_connection_status()

            client.stop_client()
            assert "Disconnected" in client.get_connection_status()

    @pytest.mark.asyncio
    async def test_message_handling(self, test_config, mock_telegram):
        """Test complete message handling flow."""
        # Import directly from the module to avoid main.py import
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient

        with patch('subprocess.run') as mock_run:
            # Mock successful command execution
            mock_run.return_value = Mock(
                stdout="hello world",
                stderr="",
                returncode=0
            )

            client = TelegramClient(test_config)

            # Mock Telegram message and update
            mock_message = Mock()
            mock_message.text = """
[hello]
name = "test"
"""
            mock_message.reply_text = AsyncMock()
            mock_message.chat.id = 12345  # Private chat
            mock_message.chat.type = "private"
            mock_message.from_user.first_name = "TestUser"
            mock_message.from_user.id = 12345

            mock_update = Mock()
            mock_update.message = mock_message

            mock_context = Mock()

            # Test message handling
            await client.handle_message(mock_update, mock_context)

            # Verify reply was sent
            mock_message.reply_text.assert_called_once()
            call_args = mock_message.reply_text.call_args[0][0]
            assert "hello" in call_args
            assert "completed" in call_args

    @pytest.mark.asyncio
    async def test_message_handling_unknown_action(self, test_config, mock_telegram):
        """Test handling of unknown actions."""
        # Import directly from the module to avoid main.py import
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient

        client = TelegramClient(test_config)

        # Mock Telegram message with unknown action
        mock_message = Mock()
        mock_message.text = """
[unknown-action]
param = "value"
"""
        mock_message.reply_text = AsyncMock()
        mock_message.chat.id = 12345  # Private chat
        mock_message.chat.type = "private"
        mock_message.from_user.first_name = "TestUser"
        mock_message.from_user.id = 12345

        mock_update = Mock()
        mock_update.message = mock_message

        mock_context = Mock()

        # Test message handling
        await client.handle_message(mock_update, mock_context)

        # Verify error reply was sent
        mock_message.reply_text.assert_called_once()
        call_args = mock_message.reply_text.call_args[0][0]
        assert "not found" in call_args
        assert "Built-in actions" in call_args
        assert "Custom actions" in call_args


class TestTelegramGroupsSupport:
    """Test Telegram groups support functionality (Issue #10)."""

    @pytest.fixture
    def test_config_with_groups(self):
        """Create a test configuration with groups support."""
        config_data = {
            'telegram': {
                'bot_token': 'test_token_123',
                'groups': [-1234, -5678]  # Test group IDs
            },
            'actions': {
                'hello': {
                    'command': 'echo',
                    'description': 'Print hello message'
                }
            }
        }

        temp_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False)
        yaml.dump(config_data, temp_file, default_flow_style=False)
        temp_file.close()

        yield Path(temp_file.name)

        # Cleanup
        Path(temp_file.name).unlink()

    def test_groups_config_validation_valid(self, test_config_with_groups):
        """Test that valid groups configuration passes validation."""
        # Import directly from the module to avoid main.py import
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient

        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):

            client = TelegramClient(test_config_with_groups)
            
            # Should be valid with groups array
            assert client.config_valid is True
            assert client.config_error is None
            
            # Should have groups in config
            assert 'groups' in client.config['telegram']
            assert client.config['telegram']['groups'] == [-1234, -5678]

    def test_groups_config_validation_invalid_type(self):
        """Test that invalid groups configuration fails validation."""
        config_data = {
            'telegram': {
                'bot_token': 'test_token_123',
                'groups': 'not-a-list'  # Invalid: should be a list
            },
            'actions': {}
        }

        temp_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False)
        yaml.dump(config_data, temp_file, default_flow_style=False)
        temp_file.close()

        try:
            # Import directly from the module to avoid main.py import
            sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
            from telegram_client import TelegramClient

            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'):

                client = TelegramClient(Path(temp_file.name))
                
                # Should be invalid with non-list groups
                assert client.config_valid is False
                assert "groups must be a list" in client.config_error

        finally:
            # Cleanup
            Path(temp_file.name).unlink()

    def test_groups_config_validation_invalid_group_ids(self):
        """Test that invalid group IDs fail validation."""
        config_data = {
            'telegram': {
                'bot_token': 'test_token_123',
                'groups': ['not-a-number', -1234]  # Invalid: should be integers
            },
            'actions': {}
        }

        temp_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False)
        yaml.dump(config_data, temp_file, default_flow_style=False)
        temp_file.close()

        try:
            # Import directly from the module to avoid main.py import
            sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))  
            from telegram_client import TelegramClient

            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'):

                client = TelegramClient(Path(temp_file.name))
                
                # Should be invalid with non-integer group IDs
                assert client.config_valid is False
                assert "group IDs must be integers" in client.config_error

        finally:
            # Cleanup
            Path(temp_file.name).unlink()

    @pytest.mark.asyncio
    async def test_group_message_handling(self, test_config_with_groups):
        """Test handling messages from configured groups."""
        # Import directly from the module to avoid main.py import
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient

        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:

            # Mock successful command execution
            mock_run.return_value = Mock(
                stdout="hello group",
                stderr="",
                returncode=0
            )

            client = TelegramClient(test_config_with_groups)

            # Mock group message
            mock_message = Mock()
            mock_message.text = """
[hello]
name = "group-test"
"""
            mock_message.reply_text = AsyncMock()
            mock_message.chat.id = -1234  # Configured group ID
            mock_message.chat.type = "group"
            mock_message.from_user.first_name = "TestUser"
            mock_message.from_user.id = 12345

            mock_update = Mock()
            mock_update.message = mock_message

            mock_context = Mock()

            # Test group message handling
            await client.handle_message(mock_update, mock_context)

            # Verify reply was sent (group message should be processed)
            mock_message.reply_text.assert_called_once()
            call_args = mock_message.reply_text.call_args[0][0]
            assert "hello" in call_args
            assert "completed" in call_args

    @pytest.mark.asyncio  
    async def test_unauthorized_group_message_ignored(self, test_config_with_groups):
        """Test that messages from unconfigured groups are ignored.""" 
        # Import directly from the module to avoid main.py import
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient

        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:

            client = TelegramClient(test_config_with_groups)

            # Mock message from unconfigured group
            mock_message = Mock()
            mock_message.text = """
[hello]
name = "unauthorized"
"""
            mock_message.reply_text = AsyncMock()
            mock_message.chat.id = -9999  # NOT in configured groups
            mock_message.chat.type = "group" 
            mock_message.from_user.first_name = "TestUser"
            mock_message.from_user.id = 12345

            mock_update = Mock()
            mock_update.message = mock_message

            mock_context = Mock()

            # Test unauthorized group message handling
            await client.handle_message(mock_update, mock_context)

            # Verify NO reply was sent (unauthorized group should be ignored)
            mock_message.reply_text.assert_not_called()
            # Verify NO command was executed
            mock_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_private_message_still_works(self, test_config_with_groups):
        """Test that private messages still work when groups are configured."""
        # Import directly from the module to avoid main.py import
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient

        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:

            # Mock successful command execution
            mock_run.return_value = Mock(
                stdout="hello private",
                stderr="",
                returncode=0
            )

            client = TelegramClient(test_config_with_groups)

            # Mock private message
            mock_message = Mock()
            mock_message.text = """
[hello]
name = "private-test"
"""
            mock_message.reply_text = AsyncMock()
            mock_message.chat.id = 54321  # Positive ID = private chat
            mock_message.chat.type = "private"
            mock_message.from_user.first_name = "TestUser"
            mock_message.from_user.id = 54321

            mock_update = Mock()
            mock_update.message = mock_message

            mock_context = Mock()

            # Test private message handling
            await client.handle_message(mock_update, mock_context)

            # Verify reply was sent (private messages should always work)
            mock_message.reply_text.assert_called_once()
            call_args = mock_message.reply_text.call_args[0][0]
            assert "hello" in call_args
            assert "completed" in call_args

    def test_groups_status_reporting(self, test_config_with_groups):
        """Test that groups configuration affects status reporting."""
        # Import directly from the module to avoid main.py import
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient

        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):

            client = TelegramClient(test_config_with_groups)
            
            # Should report groups information in debug stats
            stats = client.get_debug_stats()
            assert 'groups_configured' in stats
            assert stats['groups_configured'] == 2  # Two groups configured


class TestIntegration:
    """Integration tests."""

    def test_configuration_example(self):
        """Test that the example configuration is valid."""
        config_path = Path(__file__).parent.parent / "example-config.yaml"
        assert config_path.exists(), "Example config file should exist"

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        assert 'telegram' in config
        assert 'actions' in config
        assert isinstance(config['actions'], dict)

        # Verify action structure
        for action_name, action_config in config['actions'].items():
            assert 'command' in action_config
            assert 'description' in action_config

    def test_headless_operation(self, test_config):
        """Test that the system works without GUI dependencies."""
        # Import directly from the module to avoid main.py import
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient

        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):

            # Should be able to create client without GUI
            client = TelegramClient(test_config)
            assert client is not None

            # Should have actions loaded
            actions = client.action_registry.list_actions()
            assert len(actions) > 0


if __name__ == "__main__":
    # Run tests with pytest if called directly
    pytest.main([__file__, "-v"])
