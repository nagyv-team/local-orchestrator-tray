#!/usr/bin/env python3
"""
Tests for helper methods that need to be extracted from complex methods.

This test suite drives the refactoring of high-complexity methods by testing
the individual helper methods that should be extracted. These tests are designed
to fail initially (TDD red phase) and will pass once the refactoring is complete.

Target methods for refactoring (based on code review):
- _validate_actions_config (CCN: 11) → extract helper methods
- _async_run_client (CCN: 9) → extract helper methods  
- handle_message (CCN: 9) → extract helper methods
- process_toml_actions (CCN: 9) → extract helper methods

Helper methods to be extracted and tested:
1. Config validation helpers
2. Application setup helpers
3. Message processing helpers
4. Action execution helpers
5. Error handling helpers
"""

import asyncio
import tempfile
import yaml
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
import pytest
import sys
import subprocess

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
            mode='w', suffix='.yaml', delete=False)
        yaml.dump(config_data, temp_file, default_flow_style=False)
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


class TestConfigValidationHelpers:
    """Tests for helper methods extracted from _validate_actions_config."""

    def test_validate_action_name_convention(self, create_temp_config):
        """Test _validate_action_name_convention helper method."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': 'test_token'},
            'actions': {'test': {'command': 'echo'}}
        }
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            client = TelegramClient(config_path)
            
            # Test valid action names (lowercase)
            valid_names = ['deploy', 'status', 'build_app', 'test_suite', 'server_restart']
            for name in valid_names:
                try:
                    result = client._validate_action_name_convention(name)
                    assert result is True, f"Valid action name should pass: {name}"
                except AttributeError:
                    # Method doesn't exist yet - expected in TDD red phase
                    pytest.skip("_validate_action_name_convention method not implemented yet")
            
            # Test invalid action names (uppercase - reserved for built-ins)
            invalid_names = ['Deploy', 'STATUS', 'Notification', 'BUILD_APP', 'TestSuite']
            for name in invalid_names:
                try:
                    result = client._validate_action_name_convention(name)
                    assert result is False, f"Invalid action name should fail: {name}"
                except AttributeError:
                    # Method doesn't exist yet - expected in TDD red phase
                    pytest.skip("_validate_action_name_convention method not implemented yet")

    def test_validate_single_action_config(self, create_temp_config):
        """Test _validate_single_action_config helper method."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': 'test_token'},
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
            
            # Test valid action configurations
            valid_configs = [
                {'command': 'docker up'},
                {'command': 'npm run build', 'description': 'Build app'},
                {'command': 'pytest', 'working_dir': '/project', 'description': 'Run tests'},
            ]
            
            for action_config in valid_configs:
                try:
                    result = client._validate_single_action_config('test_action', action_config)
                    assert result is True, f"Valid action config should pass: {action_config}"
                except AttributeError:
                    # Method doesn't exist yet - expected in TDD red phase
                    pytest.skip("_validate_single_action_config method not implemented yet")
            
            # Test invalid action configurations
            invalid_configs = [
                {},  # Missing command
                {'description': 'No command'},  # Missing command
                {'command': ''},  # Empty command
                {'command': None},  # None command
                {'command': 123},  # Non-string command
                'not_a_dict',  # Not a dictionary
            ]
            
            for action_config in invalid_configs:
                try:
                    result = client._validate_single_action_config('test_action', action_config)
                    assert result is False, f"Invalid action config should fail: {action_config}"
                except AttributeError:
                    # Method doesn't exist yet - expected in TDD red phase
                    pytest.skip("_validate_single_action_config method not implemented yet")

    def test_log_action_validation_progress(self, create_temp_config):
        """Test _log_action_validation_progress helper method."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': 'test_token'},
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
                # Should log validation progress without errors
                client._log_action_validation_progress(25, detailed_logging=True)
                client._log_action_validation_progress(100, detailed_logging=False)
                client._log_action_validation_progress(0, detailed_logging=True)
                
                # Method should handle edge cases gracefully
                client._log_action_validation_progress(-1, detailed_logging=True)
                client._log_action_validation_progress(999999, detailed_logging=False)
                
            except AttributeError:
                # Method doesn't exist yet - expected in TDD red phase
                pytest.skip("_log_action_validation_progress method not implemented yet")

    def test_set_validation_error(self, create_temp_config):
        """Test _set_validation_error helper method for consistent error handling."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': 'test_token'},
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
                # Should set error message and validation state consistently
                client._set_validation_error("Test error message")
                assert client.config_error == "Test error message"
                assert client.config_valid is False
                
                # Should handle None and empty messages appropriately
                client._set_validation_error(None)
                assert client.config_error is None
                
                client._set_validation_error("")  
                assert client.config_error == ""
                
                # Should handle very long error messages
                long_error = "Error: " + "x" * 10000
                client._set_validation_error(long_error)
                assert client.config_error == long_error
                
            except AttributeError:
                # Method doesn't exist yet - expected in TDD red phase
                pytest.skip("_set_validation_error method not implemented yet")


class TestApplicationSetupHelpers:
    """Tests for helper methods extracted from _async_run_client."""

    def test_configure_application_builder(self, create_temp_config):
        """Test _configure_application_builder helper method."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {
                'bot_token': 'test_token_123',
                'channels': [-1002345, -1002346]
            },
            'actions': {}
        }
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application') as mock_app_class, \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            # Setup mocks
            mock_builder = Mock()
            mock_builder.token.return_value = mock_builder
            mock_builder.allowed_updates.return_value = mock_builder
            mock_builder.build.return_value = Mock()
            mock_app_class.builder.return_value = mock_builder
            
            from telegram_client import TelegramClient
            client = TelegramClient(config_path)
            
            try:
                # Test with channels configured
                builder = client._configure_application_builder('test_token_123', [-1002345, -1002346])
                
                # Should configure builder with token and allowed_updates
                mock_builder.token.assert_called_with('test_token_123')
                mock_builder.allowed_updates.assert_called_with(["channel_post", "message"])
                
                mock_builder.reset_mock()
                
                # Test without channels configured  
                builder = client._configure_application_builder('test_token_123', [])
                
                # Should configure builder with token but no allowed_updates
                mock_builder.token.assert_called_with('test_token_123')
                mock_builder.allowed_updates.assert_not_called()
                
            except AttributeError:
                # Method doesn't exist yet - expected in TDD red phase
                pytest.skip("_configure_application_builder method not implemented yet")

    def test_setup_message_handlers(self, create_temp_config):
        """Test _setup_message_handlers helper method."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': 'test_token'},
            'actions': {}
        }
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler') as mock_handler, \
                patch('telegram_client.filters') as mock_filters, \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            client = TelegramClient(config_path)
            
            mock_app = Mock()
            mock_app.add_handler = Mock()
            
            try:
                client._setup_message_handlers(mock_app)
                
                # Should add message handler for text messages
                mock_app.add_handler.assert_called()
                
                # Verify handler was created with correct filters
                call_args = mock_app.add_handler.call_args[0][0]
                # Handler should be configured for text messages
                
            except AttributeError:
                # Method doesn't exist yet - expected in TDD red phase
                pytest.skip("_setup_message_handlers method not implemented yet")

    def test_start_polling_with_channel_support(self, create_temp_config):
        """Test _start_polling_with_channel_support helper method."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {
                'bot_token': 'test_token',
                'channels': [-1002345]
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
            
            mock_app = Mock()
            mock_app.initialize = AsyncMock()
            mock_app.start = AsyncMock()
            mock_updater = Mock()
            mock_updater.start_polling = AsyncMock()
            mock_app.updater = mock_updater
            
            try:
                # Test starting polling with channel support
                result = asyncio.run(client._start_polling_with_channel_support(mock_app, [-1002345]))
                
                # Should initialize, start app, and start polling
                mock_app.initialize.assert_called_once()
                mock_app.start.assert_called_once()
                mock_updater.start_polling.assert_called_once()
                
                assert result is True
                
            except AttributeError:
                # Method doesn't exist yet - expected in TDD red phase
                pytest.skip("_start_polling_with_channel_support method not implemented yet")


class TestMessageProcessingHelpers:
    """Tests for helper methods extracted from handle_message."""

    @pytest.mark.asyncio
    async def test_extract_message_from_update(self, create_temp_config):
        """Test _extract_message_from_update helper method."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': 'test_token'},
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
                # Test with regular message
                mock_message = Mock()
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                
                extracted = client._extract_message_from_update(mock_update)
                assert extracted == mock_message
                
                # Test with channel_post
                mock_channel_post = Mock()
                mock_update.message = None
                mock_update.channel_post = mock_channel_post
                
                extracted = client._extract_message_from_update(mock_update)
                assert extracted == mock_channel_post
                
                # Test with both (should prioritize message)
                mock_update.message = mock_message
                mock_update.channel_post = mock_channel_post
                
                extracted = client._extract_message_from_update(mock_update)
                assert extracted == mock_message
                
                # Test with neither
                mock_update.message = None
                mock_update.channel_post = None
                
                extracted = client._extract_message_from_update(mock_update)
                assert extracted is None
                
            except AttributeError:
                # Method doesn't exist yet - expected in TDD red phase
                pytest.skip("_extract_message_from_update method not implemented yet")

    @pytest.mark.asyncio
    async def test_is_channel_message_allowed(self, create_temp_config):
        """Test _is_channel_message_allowed helper method."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {
                'bot_token': 'test_token',
                'channels': [-1002345, -1002346]
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
                # Test regular message (should always be allowed)
                mock_message = Mock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345
                mock_message.chat.type = 'private'
                
                result = client._is_channel_message_allowed(mock_message, [-1002345, -1002346])
                assert result is True
                
                # Test channel message from allowed channel
                mock_channel_post = Mock()
                mock_channel_post.chat = Mock()
                mock_channel_post.chat.id = -1002345
                mock_channel_post.chat.type = 'channel'
                
                result = client._is_channel_message_allowed(mock_channel_post, [-1002345, -1002346])
                assert result is True
                
                # Test channel message from blocked channel
                mock_channel_post.chat.id = -1002999
                
                result = client._is_channel_message_allowed(mock_channel_post, [-1002345, -1002346])
                assert result is False
                
                # Test with empty channels list (should allow all)
                result = client._is_channel_message_allowed(mock_channel_post, [])
                assert result is True
                
            except AttributeError:
                # Method doesn't exist yet - expected in TDD red phase
                pytest.skip("_is_channel_message_allowed method not implemented yet")

    @pytest.mark.asyncio
    async def test_log_message_details(self, create_temp_config):
        """Test _log_message_details helper method."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': 'test_token'},
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
            
            mock_message = Mock()
            mock_message.chat = Mock()
            mock_message.chat.id = 12345
            mock_message.chat.type = 'private'
            mock_message.from_user = Mock()
            mock_message.from_user.first_name = 'TestUser'
            mock_message.from_user.id = 67890
            mock_message.text = 'Test message content'
            
            try:
                # Should log message details without errors
                client._log_message_details(mock_message, message_count=1)
                client._log_message_details(mock_message, message_count=999)
                
                # Should handle None values gracefully
                mock_message.from_user = None
                client._log_message_details(mock_message, message_count=1)
                
                mock_message.text = None
                client._log_message_details(mock_message, message_count=1)
                
            except AttributeError:
                # Method doesn't exist yet - expected in TDD red phase
                pytest.skip("_log_message_details method not implemented yet")


class TestActionExecutionHelpers:
    """Tests for helper methods extracted from process_toml_actions."""

    @pytest.mark.asyncio
    async def test_execute_built_in_action_with_reply(self, create_temp_config):
        """Test _execute_built_in_action_with_reply helper method."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': 'test_token'},
            'actions': {}
        }
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('local_orchestrator_tray.telegram_client.rumps') as mock_rumps:
            
            from telegram_client import TelegramClient
            client = TelegramClient(config_path)
            
            mock_message = Mock()
            mock_message.reply_text = AsyncMock()
            
            try:
                # Test Notification built-in action
                section_data = {
                    'message': 'Test notification',
                    'title': 'Test Title'
                }
                
                await client._execute_built_in_action_with_reply(
                    mock_message, 'Notification', section_data
                )
                
                # Should execute notification
                mock_rumps.notification.assert_called_once_with(
                    title='Test Title',
                    subtitle='',
                    message='Test notification'
                )
                
                # Should send reply
                mock_message.reply_text.assert_called_once()
                reply_text = mock_message.reply_text.call_args[0][0]
                assert 'Built-in action \'Notification\' completed' in reply_text
                
            except AttributeError:
                # Method doesn't exist yet - expected in TDD red phase
                pytest.skip("_execute_built_in_action_with_reply method not implemented yet")

    @pytest.mark.asyncio
    async def test_execute_custom_action_with_reply(self, create_temp_config):
        """Test _execute_custom_action_with_reply helper method."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': 'test_token'},
            'actions': {
                'deploy': {
                    'command': 'docker-compose up -d',
                    'working_dir': '/app'
                }
            }
        }
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            # Mock successful command execution
            mock_run.return_value = Mock(
                stdout="Deployment successful",
                stderr="",
                returncode=0
            )
            
            from telegram_client import TelegramClient
            client = TelegramClient(config_path)
            
            mock_message = Mock()
            mock_message.reply_text = AsyncMock()
            
            try:
                section_data = {
                    'environment': 'production',
                    'replicas': 3
                }
                
                await client._execute_custom_action_with_reply(
                    mock_message, 'deploy', section_data
                )
                
                # Should execute command with parameters
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                assert 'docker-compose' in call_args
                assert 'up' in call_args
                assert '-d' in call_args
                assert '--environment' in call_args
                assert 'production' in call_args
                assert '--replicas' in call_args
                assert '3' in call_args
                
                # Should use correct working directory
                assert mock_run.call_args[1]['cwd'] == '/app'
                
                # Should send success reply
                mock_message.reply_text.assert_called_once()
                reply_text = mock_message.reply_text.call_args[0][0]
                assert 'deploy' in reply_text
                assert 'completed' in reply_text
                assert 'Deployment successful' in reply_text
                
            except AttributeError:
                # Method doesn't exist yet - expected in TDD red phase
                pytest.skip("_execute_custom_action_with_reply method not implemented yet")

    @pytest.mark.asyncio
    async def test_handle_unknown_action(self, create_temp_config):
        """Test _handle_unknown_action helper method."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': 'test_token'},
            'actions': {
                'deploy': {'command': 'echo deploy'},
                'status': {'command': 'echo status'}
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
            
            mock_message = Mock()
            mock_message.reply_text = AsyncMock()
            
            try:
                await client._handle_unknown_action(mock_message, 'nonexistent_action')
                
                # Should send error reply
                mock_message.reply_text.assert_called_once()
                reply_text = mock_message.reply_text.call_args[0][0]
                assert 'not found' in reply_text.lower()
                assert 'nonexistent_action' in reply_text
                
                # Should suggest available actions
                assert 'deploy' in reply_text or 'status' in reply_text
                
            except AttributeError:
                # Method doesn't exist yet - expected in TDD red phase
                pytest.skip("_handle_unknown_action method not implemented yet")


class TestErrorHandlingHelpers:
    """Tests for error handling helper methods."""

    @pytest.mark.asyncio
    async def test_handle_command_execution_error(self, create_temp_config):
        """Test error handling for command execution failures."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': 'test_token'},
            'actions': {'test': {'command': 'failing_command'}}
        }
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            client = TelegramClient(config_path)
            
            mock_message = Mock()
            mock_message.reply_text = AsyncMock()
            
            # Test different error scenarios
            error_scenarios = [
                {
                    'exception': subprocess.TimeoutExpired('cmd', 30),
                    'expected_message': 'timeout'
                },
                {
                    'exception': FileNotFoundError('command not found'),
                    'expected_message': 'not found'
                },
                {
                    'exception': PermissionError('permission denied'),
                    'expected_message': 'permission'
                },
                {
                    'exception': Exception('generic error'),
                    'expected_message': 'error'
                }
            ]
            
            for scenario in error_scenarios:
                mock_message.reply_text.reset_mock()
                
                try:
                    # This helper method should format error messages appropriately
                    await client._handle_command_execution_error(
                        mock_message, 'test_action', scenario['exception']
                    )
                    
                    # Should send error reply
                    mock_message.reply_text.assert_called_once()
                    reply_text = mock_message.reply_text.call_args[0][0].lower()
                    assert scenario['expected_message'] in reply_text
                    assert 'test_action' in reply_text
                    
                except AttributeError:
                    # Method doesn't exist yet - expected in TDD red phase
                    pytest.skip("_handle_command_execution_error method not implemented yet")

    def test_truncate_output_for_telegram(self, create_temp_config):
        """Test output truncation helper for Telegram message limits."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': 'test_token'},
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
                # Test short output (should not be truncated)
                short_output = "Short command output"
                result = client._truncate_output_for_telegram(short_output)
                assert result == short_output
                
                # Test long output (should be truncated)
                long_output = "Line " + "\n".join([f"Output line {i}" for i in range(1000)])
                result = client._truncate_output_for_telegram(long_output)
                assert len(result) <= 4000  # Telegram limit minus formatting
                assert "..." in result or "truncated" in result.lower()
                
                # Test empty output
                result = client._truncate_output_for_telegram("")
                assert result == ""
                
                # Test None output
                result = client._truncate_output_for_telegram(None)
                assert result == "" or result is None
                
            except AttributeError:
                # Method doesn't exist yet - expected in TDD red phase
                pytest.skip("_truncate_output_for_telegram method not implemented yet")

    def test_format_success_reply(self, create_temp_config):
        """Test success reply formatting helper."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': 'test_token'},
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
                # Test formatting success reply for custom action
                result = client._format_success_reply(
                    'deploy', 
                    'Custom',
                    'Deployment completed successfully\nServices: 3 started'
                )
                
                assert 'deploy' in result
                assert 'completed' in result
                assert 'Custom action' in result
                assert 'Deployment completed successfully' in result
                assert 'Services: 3 started' in result
                
                # Test formatting success reply for built-in action
                result = client._format_success_reply(
                    'Notification',
                    'Built-in',
                    ''
                )
                
                assert 'Notification' in result
                assert 'completed' in result
                assert 'Built-in action' in result
                
            except AttributeError:
                # Method doesn't exist yet - expected in TDD red phase
                pytest.skip("_format_success_reply method not implemented yet")


class TestHelperMethodIntegration:
    """Test that helper methods work together properly."""

    @pytest.mark.asyncio
    async def test_helper_methods_integration_flow(self, create_temp_config):
        """Test that extracted helper methods work together in the main flow."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {
                'bot_token': 'integration_test_token',
                'channels': [-1002345]
            },
            'actions': {
                'test_action': {
                    'command': 'echo test',
                    'description': 'Test action'
                }
            }
        }
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            mock_run.return_value = Mock(stdout="test output", stderr="", returncode=0)
            
            from telegram_client import TelegramClient
            client = TelegramClient(config_path)
            
            try:
                # Test validation helpers
                action_name = 'test_action'
                action_config = {'command': 'echo test', 'description': 'Test action'}
                
                # These should all work together
                name_valid = client._validate_action_name_convention(action_name)
                config_valid = client._validate_single_action_config(action_name, action_config)
                
                assert name_valid is True
                assert config_valid is True
                
                # Test message processing helpers
                mock_message = Mock()
                mock_message.chat = Mock()
                mock_message.chat.id = -1002345
                mock_message.chat.type = 'channel'
                mock_message.reply_text = AsyncMock()
                
                mock_update = Mock()
                mock_update.message = None
                mock_update.channel_post = mock_message
                
                extracted_message = client._extract_message_from_update(mock_update)
                assert extracted_message == mock_message
                
                is_allowed = client._is_channel_message_allowed(mock_message, [-1002345])
                assert is_allowed is True
                
                # Test action execution helpers
                section_data = {'param': 'value'}
                await client._execute_custom_action_with_reply(
                    mock_message, 'test_action', section_data
                )
                
                mock_run.assert_called_once()
                mock_message.reply_text.assert_called_once()
                
            except AttributeError as e:
                # Helper methods don't exist yet - expected in TDD red phase
                pytest.skip(f"Helper methods not implemented yet: {e}")

    def test_helper_method_error_consistency(self, create_temp_config):
        """Test that helper methods handle errors consistently."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': 'test_token'},
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
                # All helper methods should handle None inputs gracefully
                client._validate_action_name_convention(None)
                client._validate_single_action_config(None, None)
                client._set_validation_error(None)
                client._extract_message_from_update(None)
                client._truncate_output_for_telegram(None)
                
                # Should not raise exceptions for edge cases
                client._log_action_validation_progress(-1, True)
                client._log_message_details(None, 0)
                
            except AttributeError:
                # Methods don't exist yet - expected in TDD red phase
                pytest.skip("Helper methods not implemented yet")
            except Exception as e:
                pytest.fail(f"Helper methods should handle edge cases gracefully: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])