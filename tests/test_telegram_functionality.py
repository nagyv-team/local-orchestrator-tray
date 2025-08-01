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

    @pytest.mark.asyncio
    async def test_should_call_start_polling_with_allowed_updates_when_running_client(self, test_config, mock_telegram):
        """Test that start_polling is called with allowed_updates for channel message support (Issue #14)."""
        # Import directly from the module to avoid main.py import
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient

        client = TelegramClient(test_config)
        
        # Set up the mock to fail after start_polling so we can verify the call was made correctly
        async def mock_start_polling(*args, **kwargs):
            # This will let us verify the call was made with correct parameters
            raise Exception("Test exception to exit early")
        
        mock_telegram['updater'].start_polling.side_effect = mock_start_polling
        
        # Execute the _async_run_client method - production code catches exceptions gracefully
        await client._async_run_client()
        
        # Verify start_polling was called with the correct allowed_updates parameter
        mock_telegram['updater'].start_polling.assert_called_once_with(
            allowed_updates=["channel_post", "message"]
        )
        
        # Verify the error was handled gracefully (connection_status should reflect the error)
        assert "Connection failed" in client.connection_status

    @pytest.mark.asyncio 
    async def test_should_handle_both_messages_and_channel_posts_when_receiving_updates(self, test_config, mock_telegram):
        """Test that both regular messages and channel posts are processed by the same handler (Issue #14)."""
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

            # Test data - same TOML content for both message types
            toml_content = """
[hello]
name = "test"
"""

            # Test regular message handling
            mock_message = Mock()
            mock_message.text = toml_content
            mock_message.reply_text = AsyncMock()

            mock_update_message = Mock()
            mock_update_message.message = mock_message
            mock_update_message.channel_post = None

            mock_context = Mock()

            await client.handle_message(mock_update_message, mock_context)
            message_reply_call = mock_message.reply_text.call_args

            # Test channel post handling  
            mock_channel_post = Mock()
            mock_channel_post.text = toml_content
            mock_channel_post.reply_text = AsyncMock()

            mock_update_channel = Mock()
            mock_update_channel.message = None
            mock_update_channel.channel_post = mock_channel_post

            mock_context_channel = Mock()

            await client.handle_message(mock_update_channel, mock_context_channel)
            channel_reply_call = mock_channel_post.reply_text.call_args

            # Verify both message types got identical responses
            assert message_reply_call is not None
            assert channel_reply_call is not None
            
            message_response = message_reply_call[0][0] 
            channel_response = channel_reply_call[0][0]
            
            # Both should contain success indicators
            assert "hello" in message_response
            assert "completed" in message_response
            assert "hello" in channel_response
            assert "completed" in channel_response

    @pytest.mark.asyncio
    async def test_should_extract_message_from_correct_update_attribute_when_handling_different_types(self, test_config, mock_telegram):
        """Test that handle_message correctly extracts text from update.message or update.channel_post (Issue #14)."""
        # Import directly from the module to avoid main.py import
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient

        client = TelegramClient(test_config)

        # Test that regular message is extracted from update.message
        mock_message = Mock()
        mock_message.text = "[hello]\nname = 'regular'"
        mock_message.reply_text = AsyncMock()

        mock_update_message = Mock()
        mock_update_message.message = mock_message
        mock_update_message.channel_post = None

        mock_context = Mock()

        # Test regular message - should use update.message.text
        with patch.object(client, 'parse_toml_message') as mock_parse:
            mock_parse.return_value = None  # Simplify test by avoiding action execution
            
            await client.handle_message(mock_update_message, mock_context)
            
            # Verify parse was called with text from update.message
            mock_parse.assert_called_once_with("[hello]\nname = 'regular'")

        # Test that channel post is extracted from update.channel_post
        mock_channel_post = Mock()
        mock_channel_post.text = "[hello]\nname = 'channel'"
        mock_channel_post.reply_text = AsyncMock()

        mock_update_channel = Mock()
        mock_update_channel.message = None
        mock_update_channel.channel_post = mock_channel_post

        mock_context_channel = Mock()

        # Test channel post - should use update.channel_post.text
        with patch.object(client, 'parse_toml_message') as mock_parse_channel:
            mock_parse_channel.return_value = None  # Simplify test by avoiding action execution
            
            await client.handle_message(mock_update_channel, mock_context_channel)
            
            # Verify parse was called with text from update.channel_post
            mock_parse_channel.assert_called_once_with("[hello]\nname = 'channel'")


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
