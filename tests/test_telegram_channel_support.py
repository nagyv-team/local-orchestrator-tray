#!/usr/bin/env python3
"""
Comprehensive test suite for Telegram channel support (Issue #14).
Tests channel message listening, channel ID filtering, and configuration handling.

This test suite focuses on:
1. Channel configuration parsing and validation
2. Telegram application setup with channel support
3. Channel message handling and filtering
4. Integration with existing message processing
5. Backward compatibility with non-channel configurations

This file is part of a comprehensive test suite that includes:
- Config validation tests (test_config_validation_refactoring.py)
- Integration tests (test_integration_message_pipeline.py)
- Helper method tests (test_helper_method_extraction.py)
- Security tests (test_security_token_validation.py)
- Performance tests (test_performance_and_load.py)
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

# Test configuration
TEST_CHANNEL_IDS = [-1002345, -1002346, -1002347, -1002348, -1002349]
BLOCKED_CHANNEL_IDS = [-1002999, -1003000, -1003001]
TEST_MESSAGE_TIMEOUT = 10.0  # seconds


@pytest.fixture
def basic_config():
    """Create a basic test configuration without channels."""
    return {
        'telegram': {
            'bot_token': 'test_token_123'
        },
        'actions': {
            'hello': {
                'command': 'echo',
                'description': 'Print hello message'
            }
        }
    }


@pytest.fixture
def channel_config():
    """Create a test configuration with channel support."""
    return {
        'telegram': {
            'bot_token': 'test_token_123',
            'channels': [-1002345, -1002346]
        },
        'actions': {
            'deploy': {
                'command': 'docker-compose up -d',
                'description': 'Deploy application'
            },
            'status': {
                'command': 'uptime',
                'description': 'Check system status'
            }
        }
    }


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
def mock_telegram_with_channels():
    """Mock the telegram library components with channel support."""
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

        # Mock the updater with channel support
        mock_updater = Mock()
        mock_updater.start_polling = AsyncMock()
        mock_updater.stop = AsyncMock()
        mock_app.updater = mock_updater

        # Mock the builder
        mock_builder = Mock()
        mock_builder.token.return_value = mock_builder
        mock_builder.allowed_updates.return_value = mock_builder
        mock_builder.build.return_value = mock_app
        mock_app_class.builder.return_value = mock_builder

        yield {
            'Application': mock_app_class,
            'app_instance': mock_app,
            'updater': mock_updater,
            'builder': mock_builder
        }


class TestChannelConfiguration:
    """Test channel configuration parsing and validation."""

    def test_channel_config_parsing_valid_channels(self, create_temp_config, channel_config):
        """Test parsing valid channel configuration."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(channel_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'):
                
                client = TelegramClient(config_path)
                
                # Verify config was loaded with channels
                assert client.config_valid
                assert 'telegram' in client.config
                assert 'channels' in client.config['telegram']
                assert client.config['telegram']['channels'] == [-1002345, -1002346]
                
                # Verify channels are accessible via getter method (to be implemented)
                # This tests the interface the implementation should provide
                channels = client.config['telegram'].get('channels', [])
                assert len(channels) == 2
                assert -1002345 in channels
                assert -1002346 in channels
        finally:
            config_path.unlink()

    def test_channel_config_parsing_empty_channels(self, create_temp_config, basic_config):
        """Test parsing config without channels section."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(basic_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'):
                
                client = TelegramClient(config_path)
                
                # Should still be valid config
                assert client.config_valid
                assert 'telegram' in client.config
                
                # Channels should default to empty list
                channels = client.config['telegram'].get('channels', [])
                assert channels == []
        finally:
            config_path.unlink()

    def test_channel_config_validation_invalid_channel_ids(self, create_temp_config):
        """Test validation of invalid channel IDs."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        invalid_config = {
            'telegram': {
                'bot_token': 'test_token_123',
                'channels': ['not_a_number', 'also_invalid']
            },
            'actions': {}
        }
        
        config_path = create_temp_config(invalid_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'):
                
                client = TelegramClient(config_path)
                
                # Should fail validation due to invalid channel IDs
                assert not client.config_valid
                assert client.config_error is not None
                assert 'channel' in client.config_error.lower() or 'invalid' in client.config_error.lower()
        finally:
            config_path.unlink()

    def test_channel_config_validation_mixed_types(self, create_temp_config):
        """Test validation of mixed channel ID types (strings and integers)."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        # Mix of valid integer and string representation of integer
        mixed_config = {
            'telegram': {
                'bot_token': 'test_token_123',
                'channels': [-1002345, '-1002346']  # One int, one string
            },
            'actions': {}
        }
        
        config_path = create_temp_config(mixed_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'):
                
                client = TelegramClient(config_path)
                
                # Should be valid - numeric strings should be accepted and converted
                # (This defines the expected behavior for the implementation)
                assert client.config_valid
                
                # Both should be accessible as integers
                channels = client.config['telegram'].get('channels', [])
                assert len(channels) == 2
                # Test that string numeric values are handled appropriately
                assert any(str(ch) == '-1002345' or ch == -1002345 for ch in channels)
                assert any(str(ch) == '-1002346' or ch == -1002346 for ch in channels)
        finally:
            config_path.unlink()

    def test_channel_config_defaults_to_empty_list(self, create_temp_config, basic_config):
        """Test that missing channels config defaults to empty list."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(basic_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'):
                
                client = TelegramClient(config_path)
                
                # Config should be valid
                assert client.config_valid
                
                # Channels should default to empty list for backward compatibility
                channels = client.config['telegram'].get('channels', [])
                assert isinstance(channels, list)
                assert len(channels) == 0
        finally:
            config_path.unlink()

    def test_channel_config_validation_empty_list(self, create_temp_config):
        """Test validation of explicitly empty channels list."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        empty_channels_config = {
            'telegram': {
                'bot_token': 'test_token_123',
                'channels': []
            },
            'actions': {}
        }
        
        config_path = create_temp_config(empty_channels_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'):
                
                client = TelegramClient(config_path)
                
                # Should be valid
                assert client.config_valid
                assert client.config['telegram']['channels'] == []
        finally:
            config_path.unlink()

    def test_channel_config_validation_not_list(self, create_temp_config):
        """Test validation fails when channels is not a list."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        invalid_config = {
            'telegram': {
                'bot_token': 'test_token_123',
                'channels': 'not_a_list'
            },
            'actions': {}
        }
        
        config_path = create_temp_config(invalid_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'):
                
                client = TelegramClient(config_path)
                
                # Should fail validation
                assert not client.config_valid
                assert client.config_error is not None
                assert 'list' in client.config_error.lower() or 'channel' in client.config_error.lower()
        finally:
            config_path.unlink()


class TestTelegramApplicationSetup:
    """Test Telegram application setup with channel support."""

    def test_application_builder_includes_allowed_updates(self, create_temp_config, channel_config, mock_telegram_with_channels):
        """Test that Application.builder() is called with allowed_updates for channels."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(channel_config)
        
        try:
            client = TelegramClient(config_path)
            
            # Start the client to trigger application setup
            client.start_client()
            
            # Give it a moment for the async setup to trigger
            import time
            time.sleep(0.1)
            
            # Verify that allowed_updates was called with channel support
            mock_builder = mock_telegram_with_channels['builder']
            
            # The builder should have been called with allowed_updates when channels are configured
            # This test defines the expected API - implementation should call:
            # builder.allowed_updates(["channel_post", "message"])
            mock_builder.allowed_updates.assert_called_once_with(["channel_post", "message"])
            
            client.stop_client()
        finally:
            config_path.unlink()

    def test_application_builder_without_channels_no_allowed_updates(self, create_temp_config, basic_config, mock_telegram_with_channels):
        """Test that Application.builder() is called without allowed_updates when no channels."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(basic_config)
        
        try:
            client = TelegramClient(config_path)
            
            # Start the client to trigger application setup
            client.start_client()
            
            # Give it a moment for the async setup to trigger
            import time
            time.sleep(0.1)
            
            # Verify that allowed_updates was NOT called when no channels configured
            mock_builder = mock_telegram_with_channels['builder']
            
            # When no channels are configured, allowed_updates should not be called
            # This maintains backward compatibility
            mock_builder.allowed_updates.assert_not_called()
            
            client.stop_client()
        finally:
            config_path.unlink()

    def test_message_handler_registration_with_channels(self, create_temp_config, channel_config, mock_telegram_with_channels):
        """Test that message handlers are registered correctly for channel support."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(channel_config)
        
        try:
            client = TelegramClient(config_path)
            
            # Start the client to trigger handler registration
            client.start_client()
            
            # Give it a moment for the async setup to trigger
            import time
            time.sleep(0.1)
            
            # Verify that message handlers were registered
            mock_app = mock_telegram_with_channels['app_instance']
            
            # Should have called add_handler at least once for message handling
            # The exact calls depend on implementation, but should include handlers for both
            # regular messages and channel posts
            assert mock_app.add_handler.called
            assert mock_app.add_handler.call_count >= 1
            
            # Verify the handler was added (exact filter verification would be implementation-specific)
            call_args = mock_app.add_handler.call_args_list
            assert len(call_args) >= 1
            
            client.stop_client()
        finally:
            config_path.unlink()

    def test_application_builder_chain_correct_order(self, create_temp_config, channel_config, mock_telegram_with_channels):
        """Test that application builder methods are called in correct order."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(channel_config)
        
        try:
            client = TelegramClient(config_path)
            
            # Start the client to trigger application setup
            client.start_client()
            
            # Give it a moment for the async setup to trigger
            import time
            time.sleep(0.1)
            
            # Verify correct order: token() -> allowed_updates() -> build()
            mock_builder = mock_telegram_with_channels['builder']
            
            # Token should be called first
            mock_builder.token.assert_called_once()
            
            # allowed_updates should be called with correct parameters
            mock_builder.allowed_updates.assert_called_once_with(["channel_post", "message"])
            
            # build should be called to create the application
            mock_builder.build.assert_called_once()
            
            client.stop_client()
        finally:
            config_path.unlink()

    def test_application_builder_with_empty_channels_list(self, create_temp_config, mock_telegram_with_channels):
        """Test application setup with explicitly empty channels list."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        empty_channels_config = {
            'telegram': {
                'bot_token': 'test_token_123',
                'channels': []
            },
            'actions': {}
        }
        
        config_path = create_temp_config(empty_channels_config)
        
        try:
            client = TelegramClient(config_path)
            
            # Start the client to trigger application setup
            client.start_client()
            
            # Give it a moment for the async setup to trigger
            import time
            time.sleep(0.1)
            
            # With empty channels list, allowed_updates should not be called
            # This maintains backward compatibility
            mock_builder = mock_telegram_with_channels['builder']
            mock_builder.allowed_updates.assert_not_called()
            
            client.stop_client()
        finally:
            config_path.unlink()


class TestChannelMessageHandling:
    """Test handling of channel messages (channel_post events)."""

    @pytest.mark.asyncio
    async def test_handle_channel_post_message(self, create_temp_config, channel_config):
        """Test handling of channel_post messages."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(channel_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'), \
                    patch('subprocess.run') as mock_run:
                
                # Mock successful command execution
                mock_run.return_value = Mock(
                    stdout="deployment successful",
                    stderr="",
                    returncode=0
                )
                
                client = TelegramClient(config_path)
                
                # Create mock channel_post message from allowed channel
                mock_channel_post = Mock()
                mock_channel_post.text = """
[deploy]
environment = "production"
"""
                mock_channel_post.reply_text = AsyncMock()
                mock_channel_post.chat = Mock()
                mock_channel_post.chat.id = -1002345  # Allowed channel
                mock_channel_post.chat.type = 'channel'
                mock_channel_post.from_user = Mock()
                mock_channel_post.from_user.first_name = 'Channel'
                mock_channel_post.from_user.id = 'channel_bot'
                
                # Create mock update with channel_post
                mock_update = Mock()
                mock_update.channel_post = mock_channel_post
                mock_update.message = None  # This is a channel_post, not a message
                
                mock_context = Mock()
                
                # Test channel_post handling - implementation should handle both update.message and update.channel_post
                await client.handle_message(mock_update, mock_context)
                
                # Verify command was executed
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                assert 'docker-compose' in call_args
                assert 'up' in call_args
                assert '-d' in call_args
                assert '--environment' in call_args
                assert 'production' in call_args
                
                # Verify reply was sent
                mock_channel_post.reply_text.assert_called_once()
                call_args = mock_channel_post.reply_text.call_args[0][0]
                assert 'deploy' in call_args
                assert 'completed' in call_args
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_channel_post_toml_parsing(self, create_temp_config, channel_config):
        """Test TOML parsing works for channel messages same as chat messages."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(channel_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'):
                
                client = TelegramClient(config_path)
                
                # Test various TOML formats that should work identically for channel_post
                toml_messages = [
                    """
[deploy]
environment = "staging"
replicas = 3
""",
                    """
[status]
verbose = true
""",
                    """
[deploy]
environment = "production"

[status]
quick = true
"""
                ]
                
                for toml_text in toml_messages:
                    result = client.parse_toml_message(toml_text)
                    assert result is not None, f"Failed to parse TOML: {toml_text}"
                    assert isinstance(result, dict)
                    assert len(result) > 0
                    
                    # Verify the parsed structure makes sense
                    for section_name, section_data in result.items():
                        assert isinstance(section_data, dict)
                        assert section_name in ['deploy', 'status']
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_channel_post_action_execution(self, create_temp_config, channel_config):
        """Test that actions execute correctly from channel messages."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(channel_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'), \
                    patch('subprocess.run') as mock_run:
                
                # Mock successful command execution
                mock_run.return_value = Mock(
                    stdout="System uptime: 5 days",
                    stderr="",
                    returncode=0
                )
                
                client = TelegramClient(config_path)
                
                # Create mock channel_post message
                mock_channel_post = Mock()
                mock_channel_post.text = """
[status]
detailed = true
"""
                mock_channel_post.reply_text = AsyncMock()
                mock_channel_post.chat = Mock()
                mock_channel_post.chat.id = -1002345  # Allowed channel
                mock_channel_post.chat.type = 'channel'
                mock_channel_post.from_user = Mock()
                mock_channel_post.from_user.first_name = 'Channel'
                mock_channel_post.from_user.id = 'channel_bot'
                
                # Test action execution from channel_post
                toml_data = {'status': {'detailed': True}}
                await client.process_toml_actions(mock_channel_post, toml_data)
                
                # Verify command was executed with correct parameters
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                assert 'uptime' in call_args
                assert '--detailed' in call_args
                assert 'true' in call_args
                
                # Verify reply was sent
                mock_channel_post.reply_text.assert_called_once()
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_channel_post_reply_handling(self, create_temp_config, channel_config):
        """Test that replies to channel messages work correctly."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(channel_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'), \
                    patch('subprocess.run') as mock_run:
                
                # Mock command that fails
                mock_run.return_value = Mock(
                    stdout="",
                    stderr="Command failed",
                    returncode=1
                )
                
                client = TelegramClient(config_path)
                
                # Create mock channel_post message
                mock_channel_post = Mock()
                mock_channel_post.text = """
[nonexistent_action]
param = "value"
"""
                mock_channel_post.reply_text = AsyncMock()
                mock_channel_post.chat = Mock()
                mock_channel_post.chat.id = -1002345  # Allowed channel
                mock_channel_post.chat.type = 'channel'
                mock_channel_post.from_user = Mock()
                mock_channel_post.from_user.first_name = 'Channel'
                mock_channel_post.from_user.id = 'channel_bot'
                
                # Create mock update with channel_post
                mock_update = Mock()
                mock_update.channel_post = mock_channel_post
                mock_update.message = None
                
                mock_context = Mock()
                
                # Test error handling and reply for channel_post
                await client.handle_message(mock_update, mock_context)
                
                # Verify error reply was sent
                mock_channel_post.reply_text.assert_called_once()
                call_args = mock_channel_post.reply_text.call_args[0][0]
                assert 'not found' in call_args
                assert 'actions' in call_args.lower()
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_channel_post_built_in_actions(self, create_temp_config, channel_config):
        """Test that built-in actions work from channel messages."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(channel_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'), \
                    patch('local_orchestrator_tray.telegram_client.rumps') as mock_rumps:
                
                client = TelegramClient(config_path)
                
                # Create mock channel_post message with built-in action
                mock_channel_post = Mock()
                mock_channel_post.text = """
[Notification]
message = "Deployment complete"
title = "System Alert"
"""
                mock_channel_post.reply_text = AsyncMock()
                mock_channel_post.chat = Mock()
                mock_channel_post.chat.id = -1002345  # Allowed channel
                mock_channel_post.chat.type = 'channel'
                mock_channel_post.from_user = Mock()
                mock_channel_post.from_user.first_name = 'Channel'
                mock_channel_post.from_user.id = 'channel_bot'
                
                # Test built-in action execution from channel_post
                toml_data = {'Notification': {'message': 'Deployment complete', 'title': 'System Alert'}}
                await client.process_toml_actions(mock_channel_post, toml_data)
                
                # Verify notification was shown
                mock_rumps.notification.assert_called_once_with(
                    title='System Alert',
                    subtitle='',
                    message='Deployment complete'
                )
                
                # Verify reply was sent
                mock_channel_post.reply_text.assert_called_once()
                call_args = mock_channel_post.reply_text.call_args[0][0]
                assert 'Built-in action \'Notification\' completed' in call_args
        finally:
            config_path.unlink()


class TestChannelIDFiltering:
    """Test filtering of messages by channel ID."""

    @pytest.mark.asyncio 
    async def test_message_processing_allowed_channel(self, create_temp_config, channel_config):
        """Test that messages from configured channels are processed."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(channel_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'), \
                    patch('subprocess.run') as mock_run:
                
                # Mock successful command execution
                mock_run.return_value = Mock(
                    stdout="status output",
                    stderr="",
                    returncode=0
                )
                
                client = TelegramClient(config_path)
                
                # Test first allowed channel (-1002345)
                mock_channel_post = Mock()
                mock_channel_post.text = """
[status]
quick = true
"""
                mock_channel_post.reply_text = AsyncMock()
                mock_channel_post.chat = Mock()
                mock_channel_post.chat.id = -1002345  # First allowed channel
                mock_channel_post.chat.type = 'channel'
                mock_channel_post.from_user = Mock()
                mock_channel_post.from_user.first_name = 'Channel'
                mock_channel_post.from_user.id = 'channel_bot'
                
                mock_update = Mock()
                mock_update.channel_post = mock_channel_post
                mock_update.message = None
                mock_context = Mock()
                
                # Implementation should process this message (allowed channel)
                await client.handle_message(mock_update, mock_context)
                
                # Verify command was executed (message was processed)
                mock_run.assert_called_once()
                
                # Reset mock for second test
                mock_run.reset_mock()
                mock_channel_post.reply_text.reset_mock()
                
                # Test second allowed channel (-1002346)
                mock_channel_post.chat.id = -1002346  # Second allowed channel
                await client.handle_message(mock_update, mock_context)
                
                # Verify command was executed again (second allowed channel)
                mock_run.assert_called_once()
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_message_processing_blocked_channel(self, create_temp_config, channel_config):
        """Test that messages from non-configured channels are ignored."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(channel_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'), \
                    patch('subprocess.run') as mock_run:
                
                client = TelegramClient(config_path)
                
                # Create message from non-allowed channel
                mock_channel_post = Mock()
                mock_channel_post.text = """
[status]
quick = true
"""
                mock_channel_post.reply_text = AsyncMock()
                mock_channel_post.chat = Mock()
                mock_channel_post.chat.id = -1002999  # NOT in allowed channels list
                mock_channel_post.chat.type = 'channel'
                mock_channel_post.from_user = Mock()
                mock_channel_post.from_user.first_name = 'Channel'
                mock_channel_post.from_user.id = 'channel_bot'
                
                mock_update = Mock()
                mock_update.channel_post = mock_channel_post
                mock_update.message = None
                mock_context = Mock()
                
                # Implementation should ignore this message (not allowed channel)
                await client.handle_message(mock_update, mock_context)
                
                # Verify command was NOT executed (message was ignored)
                mock_run.assert_not_called()
                
                # Verify NO reply was sent (message was completely ignored)
                mock_channel_post.reply_text.assert_not_called()
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_channel_id_validation_positive_and_negative(self, create_temp_config):
        """Test handling of both positive and negative channel IDs."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        # Test config with both positive and negative channel IDs
        mixed_channel_config = {
            'telegram': {
                'bot_token': 'test_token_123',
                'channels': [-1002345, 1002346, -1002347, 1002348]  # Mix of positive and negative
            },
            'actions': {
                'test': {'command': 'echo test'}
            }
        }
        
        config_path = create_temp_config(mixed_channel_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'), \
                    patch('subprocess.run') as mock_run:
                
                mock_run.return_value = Mock(stdout="test", stderr="", returncode=0)
                
                client = TelegramClient(config_path)
                
                # Test each channel ID type
                test_channels = [-1002345, 1002346, -1002347, 1002348]
                
                for channel_id in test_channels:
                    mock_run.reset_mock()
                    
                    mock_channel_post = Mock()
                    mock_channel_post.text = "[test]\nparam = 'value'"
                    mock_channel_post.reply_text = AsyncMock()
                    mock_channel_post.chat = Mock()
                    mock_channel_post.chat.id = channel_id
                    mock_channel_post.chat.type = 'channel'
                    mock_channel_post.from_user = Mock()
                    mock_channel_post.from_user.first_name = 'Channel'
                    mock_channel_post.from_user.id = 'channel_bot'
                    
                    mock_update = Mock()
                    mock_update.channel_post = mock_channel_post
                    mock_update.message = None
                    mock_context = Mock()
                    
                    # Each allowed channel should process the message
                    await client.handle_message(mock_update, mock_context)
                    mock_run.assert_called_once(), f"Channel {channel_id} should be allowed"
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_empty_channels_list_processes_all_messages(self, create_temp_config, basic_config):
        """Test that empty channels list allows all messages (backward compatibility)."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(basic_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'), \
                    patch('subprocess.run') as mock_run:
                
                mock_run.return_value = Mock(stdout="hello", stderr="", returncode=0)
                
                client = TelegramClient(config_path)
                
                # Test various channel IDs - all should be processed when no channels configured
                test_channel_ids = [-1002345, 1002346, -9999999, 123456]
                
                for channel_id in test_channel_ids:
                    mock_run.reset_mock()
                    
                    mock_channel_post = Mock()
                    mock_channel_post.text = "[hello]\nname = 'world'"
                    mock_channel_post.reply_text = AsyncMock()
                    mock_channel_post.chat = Mock()
                    mock_channel_post.chat.id = channel_id
                    mock_channel_post.chat.type = 'channel'
                    mock_channel_post.from_user = Mock()
                    mock_channel_post.from_user.first_name = 'Channel'
                    mock_channel_post.from_user.id = 'channel_bot'
                    
                    mock_update = Mock()
                    mock_update.channel_post = mock_channel_post
                    mock_update.message = None
                    mock_context = Mock()
                    
                    # With no channels configured, all messages should be processed
                    await client.handle_message(mock_update, mock_context)
                    mock_run.assert_called_once(), f"Channel {channel_id} should be processed (backward compatibility)"
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_regular_messages_not_affected_by_channel_filter(self, create_temp_config, channel_config):
        """Test that regular chat messages are not affected by channel filtering."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(channel_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'), \
                    patch('subprocess.run') as mock_run:
                
                mock_run.return_value = Mock(stdout="status output", stderr="", returncode=0)
                
                client = TelegramClient(config_path)
                
                # Create regular message (not channel_post) from any chat ID
                mock_message = Mock()
                mock_message.text = """
[status]
quick = true
"""
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 99999  # Random chat ID, not in channels list
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = 'User'
                mock_message.from_user.id = 12345
                
                mock_update = Mock()
                mock_update.message = mock_message  # Regular message, not channel_post
                mock_update.channel_post = None
                mock_context = Mock()
                
                # Regular messages should always be processed regardless of channel filtering
                await client.handle_message(mock_update, mock_context)
                
                # Verify command was executed (regular message processed)
                mock_run.assert_called_once()
                mock_message.reply_text.assert_called_once()
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_channel_filtering_with_string_channel_ids(self, create_temp_config):
        """Test channel filtering works with string representations of channel IDs."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        # Config with string channel IDs (should be converted to integers)
        string_channel_config = {
            'telegram': {
                'bot_token': 'test_token_123',
                'channels': ['-1002345', '1002346']  # String representations
            },
            'actions': {
                'test': {'command': 'echo test'}
            }
        }
        
        config_path = create_temp_config(string_channel_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'), \
                    patch('subprocess.run') as mock_run:
                
                mock_run.return_value = Mock(stdout="test", stderr="", returncode=0)
                
                client = TelegramClient(config_path)
                
                # Test with integer channel ID that matches string config
                mock_channel_post = Mock()
                mock_channel_post.text = "[test]\nparam = 'value'"
                mock_channel_post.reply_text = AsyncMock()
                mock_channel_post.chat = Mock()
                mock_channel_post.chat.id = -1002345  # Integer matching string '-1002345'
                mock_channel_post.chat.type = 'channel'
                mock_channel_post.from_user = Mock()
                mock_channel_post.from_user.first_name = 'Channel'
                mock_channel_post.from_user.id = 'channel_bot'
                
                mock_update = Mock()
                mock_update.channel_post = mock_channel_post
                mock_update.message = None
                mock_context = Mock()
                
                # Should process message (string config should match integer ID)
                await client.handle_message(mock_update, mock_context)
                mock_run.assert_called_once()
        finally:
            config_path.unlink()


class TestRegularMessageCompatibility:
    """Test that regular message handling still works with channel support."""

    @pytest.mark.asyncio
    async def test_regular_message_handling_with_channel_config(self, create_temp_config, channel_config):
        """Test that regular chat messages still work when channels are configured."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(channel_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'), \
                    patch('subprocess.run') as mock_run:
                
                mock_run.return_value = Mock(stdout="deployment started", stderr="", returncode=0)
                
                client = TelegramClient(config_path)
                
                # Create regular message (private chat, group, etc.)
                mock_message = Mock()
                mock_message.text = """
[deploy]
environment = "staging"
"""
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345  # Regular chat ID
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = 'User'
                mock_message.from_user.id = 67890
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                # Regular messages should work normally even with channel config
                await client.handle_message(mock_update, mock_context)
                
                # Verify command was executed
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                assert 'docker-compose' in call_args
                assert '--environment' in call_args
                assert 'staging' in call_args
                
                # Verify reply was sent
                mock_message.reply_text.assert_called_once()
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_mixed_regular_and_channel_messages(self, create_temp_config, channel_config):
        """Test handling both regular messages and channel messages."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(channel_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'), \
                    patch('subprocess.run') as mock_run:
                
                mock_run.return_value = Mock(stdout="command output", stderr="", returncode=0)
                
                client = TelegramClient(config_path)
                
                # Test 1: Regular message
                mock_message = Mock()
                mock_message.text = "[status]\nquick = true"
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = 'User'
                mock_message.from_user.id = 67890
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                await client.handle_message(mock_update, mock_context)
                mock_run.assert_called_once()
                mock_message.reply_text.assert_called_once()
                
                # Reset mocks for second test
                mock_run.reset_mock()
                
                # Test 2: Channel message from allowed channel
                mock_channel_post = Mock()
                mock_channel_post.text = "[deploy]\nenvironment = 'test'"
                mock_channel_post.reply_text = AsyncMock()
                mock_channel_post.chat = Mock()
                mock_channel_post.chat.id = -1002345  # Allowed channel
                mock_channel_post.chat.type = 'channel'
                mock_channel_post.from_user = Mock()
                mock_channel_post.from_user.first_name = 'Channel'
                mock_channel_post.from_user.id = 'channel_bot'
                
                mock_update.message = None
                mock_update.channel_post = mock_channel_post
                
                await client.handle_message(mock_update, mock_context)
                mock_run.assert_called_once()
                mock_channel_post.reply_text.assert_called_once()
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_message_type_detection(self, create_temp_config, channel_config):
        """Test proper detection of message vs channel_post events."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(channel_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'), \
                    patch('subprocess.run') as mock_run:
                
                mock_run.return_value = Mock(stdout="output", stderr="", returncode=0)
                
                client = TelegramClient(config_path)
                
                # Test various update scenarios
                test_scenarios = [
                    {
                        'name': 'regular_message_only',
                        'message': Mock(text='[status]\ntest = true', reply_text=AsyncMock(), 
                                     chat=Mock(id=123, type='private'),
                                     from_user=Mock(first_name='User', id=456)),
                        'channel_post': None,
                        'should_process': True
                    },
                    {
                        'name': 'channel_post_allowed',
                        'message': None,
                        'channel_post': Mock(text='[status]\ntest = true', reply_text=AsyncMock(),
                                           chat=Mock(id=-1002345, type='channel'),
                                           from_user=Mock(first_name='Channel', id='bot')),
                        'should_process': True
                    },
                    {
                        'name': 'channel_post_blocked',
                        'message': None,
                        'channel_post': Mock(text='[status]\ntest = true', reply_text=AsyncMock(),
                                           chat=Mock(id=-1002999, type='channel'),
                                           from_user=Mock(first_name='Channel', id='bot')),
                        'should_process': False
                    },
                    {
                        'name': 'both_present_message_priority',
                        'message': Mock(text='[status]\ntest = true', reply_text=AsyncMock(),
                                     chat=Mock(id=123, type='private'),
                                     from_user=Mock(first_name='User', id=456)),
                        'channel_post': Mock(text='[deploy]\nenv = prod', reply_text=AsyncMock(),
                                           chat=Mock(id=-1002345, type='channel'),
                                           from_user=Mock(first_name='Channel', id='bot')),
                        'should_process': True  # Should process message, not channel_post
                    }
                ]
                
                for scenario in test_scenarios:
                    mock_run.reset_mock()
                    
                    mock_update = Mock()
                    mock_update.message = scenario['message']
                    mock_update.channel_post = scenario['channel_post']
                    mock_context = Mock()
                    
                    # Test the scenario
                    await client.handle_message(mock_update, mock_context)
                    
                    if scenario['should_process']:
                        mock_run.assert_called_once(), f"Scenario '{scenario['name']}' should process message"
                    else:
                        mock_run.assert_not_called(), f"Scenario '{scenario['name']}' should NOT process message"
        finally:
            config_path.unlink()


class TestChannelSupportEdgeCases:
    """Test edge cases and error scenarios for channel support."""

    def test_malformed_channel_configuration(self, create_temp_config):
        """Test handling of malformed channel configuration."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        malformed_configs = [
            {
                'telegram': {
                    'bot_token': 'test_token_123',
                    'channels': 'should_be_list'  # String instead of list
                },
                'actions': {}
            },
            {
                'telegram': {
                    'bot_token': 'test_token_123',
                    'channels': {'invalid': 'dict'}  # Dict instead of list
                },
                'actions': {}
            },
            {
                'telegram': {
                    'bot_token': 'test_token_123',
                    'channels': [None, 123, None]  # Contains None values
                },
                'actions': {}
            }
        ]
        
        for i, config in enumerate(malformed_configs):
            config_path = create_temp_config(config)
            
            try:
                with patch('telegram_client.Update'), \
                        patch('telegram_client.Application'), \
                        patch('telegram_client.MessageHandler'), \
                        patch('telegram_client.filters'), \
                        patch('telegram_client.ContextTypes'):
                    
                    client = TelegramClient(config_path)
                    
                    # Should fail validation for malformed channel configs
                    assert not client.config_valid, f"Config {i} should fail validation"
                    assert client.config_error is not None, f"Config {i} should have error message"
            finally:
                config_path.unlink()

    def test_non_numeric_channel_ids_validation(self, create_temp_config):
        """Test validation rejects non-numeric channel IDs."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        invalid_channel_configs = [
            [-1002345, 'not_a_number'],
            ['@channel_name'],  # Channel username instead of ID
            [123.45],  # Float instead of integer
            [True, False],  # Boolean values
            [[]],  # Nested list
        ]
        
        for invalid_channels in invalid_channel_configs:
            config = {
                'telegram': {
                    'bot_token': 'test_token_123',
                    'channels': invalid_channels
                },
                'actions': {}
            }
            
            config_path = create_temp_config(config)
            
            try:
                with patch('telegram_client.Update'), \
                        patch('telegram_client.Application'), \
                        patch('telegram_client.MessageHandler'), \
                        patch('telegram_client.filters'), \
                        patch('telegram_client.ContextTypes'):
                    
                    client = TelegramClient(config_path)
                    
                    # Should fail validation for non-numeric channel IDs
                    assert not client.config_valid, f"Should reject channels: {invalid_channels}"
                    assert 'channel' in client.config_error.lower(), f"Error should mention channels: {client.config_error}"
            finally:
                config_path.unlink()

    @pytest.mark.asyncio
    async def test_channel_access_errors(self, create_temp_config, channel_config):
        """Test handling of channel access errors (bot not in channel, etc.)."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(channel_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application') as mock_app_class, \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'):
                
                # Mock application that throws error during startup (simulating bot not in channel)
                mock_app = Mock()
                mock_app.initialize = AsyncMock()
                mock_app.start = AsyncMock(side_effect=Exception("Bot not in channel"))
                mock_app.stop = AsyncMock()
                mock_app.shutdown = AsyncMock()
                mock_app.add_handler = Mock()
                
                mock_builder = Mock()
                mock_builder.token.return_value = mock_builder
                mock_builder.allowed_updates.return_value = mock_builder
                mock_builder.build.return_value = mock_app
                mock_app_class.builder.return_value = mock_builder
                
                client = TelegramClient(config_path)
                
                # Start client - should handle channel access errors gracefully
                success = client.start_client()
                
                # Implementation should handle the error and return False or update status
                # This test defines expected behavior for channel access issues
                assert not success or "error" in client.get_connection_status().lower()
        finally:
            config_path.unlink()

    def test_large_channel_id_list_performance(self, create_temp_config):
        """Test performance with large number of configured channels."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        # Create config with many channels (simulate real-world scenario)
        large_channels_config = {
            'telegram': {
                'bot_token': 'test_token_123',
                'channels': list(range(-1000000, -1000000 + 100))  # 100 channels
            },
            'actions': {
                'test': {'command': 'echo test'}
            }
        }
        
        config_path = create_temp_config(large_channels_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'):
                
                import time
                start_time = time.time()
                
                client = TelegramClient(config_path)
                
                # Should complete initialization in reasonable time (< 1 second)
                initialization_time = time.time() - start_time
                assert initialization_time < 1.0, f"Initialization took {initialization_time:.2f}s, too slow"
                
                # Should be valid config despite large channel list
                assert client.config_valid
                assert len(client.config['telegram']['channels']) == 100
        finally:
            config_path.unlink()

    def test_duplicate_channel_ids_handled(self, create_temp_config):
        """Test that duplicate channel IDs in config are handled gracefully."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        duplicate_channels_config = {
            'telegram': {
                'bot_token': 'test_token_123',
                'channels': [-1002345, -1002346, -1002345, -1002346, -1002345]  # Duplicates
            },
            'actions': {
                'test': {'command': 'echo test'}
            }
        }
        
        config_path = create_temp_config(duplicate_channels_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'):
                
                client = TelegramClient(config_path)
                
                # Should be valid config - duplicates are acceptable
                assert client.config_valid
                
                # Implementation can choose to deduplicate or keep duplicates
                # Both behaviors are acceptable as long as filtering works correctly
                channels = client.config['telegram']['channels']
                assert len(channels) >= 2  # At least the unique channels should be present
                assert -1002345 in channels
                assert -1002346 in channels
        finally:
            config_path.unlink()

    def test_zero_and_boundary_channel_ids(self, create_temp_config):
        """Test handling of edge case channel ID values."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        boundary_channels_config = {
            'telegram': {
                'bot_token': 'test_token_123',
                'channels': [0, -1, 1, -9223372036854775808, 9223372036854775807]  # Edge values
            },
            'actions': {
                'test': {'command': 'echo test'}
            }
        }
        
        config_path = create_temp_config(boundary_channels_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'):
                
                client = TelegramClient(config_path)
                
                # Should handle boundary values gracefully
                # Zero might be invalid for Telegram, but implementation should handle it
                assert client.config_valid or 'channel' in (client.config_error or '').lower()
        finally:
            config_path.unlink()


class TestChannelIntegration:
    """Integration tests for complete channel functionality."""

    @pytest.mark.asyncio
    async def test_end_to_end_channel_message_processing(self, create_temp_config, channel_config):
        """Test complete flow: channel message -> TOML parsing -> action execution -> reply."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(channel_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application') as mock_app_class, \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'), \
                    patch('subprocess.run') as mock_run:
                
                # Mock successful command execution
                mock_run.return_value = Mock(
                    stdout="Docker containers started successfully",
                    stderr="",
                    returncode=0
                )
                
                # Setup complete mock application
                mock_app = Mock()
                mock_app.initialize = AsyncMock()
                mock_app.start = AsyncMock()
                mock_app.stop = AsyncMock()
                mock_app.shutdown = AsyncMock()
                mock_app.add_handler = Mock()
                
                mock_builder = Mock()
                mock_builder.token.return_value = mock_builder
                mock_builder.allowed_updates.return_value = mock_builder
                mock_builder.build.return_value = mock_app
                mock_app_class.builder.return_value = mock_builder
                
                client = TelegramClient(config_path)
                
                # Complete TOML message with multiple parameters
                toml_message = """
[deploy]
environment = "production"
replicas = 3
timeout = 300
force = true
"""
                
                # Create channel_post message from allowed channel
                mock_channel_post = Mock()
                mock_channel_post.text = toml_message
                mock_channel_post.reply_text = AsyncMock()
                mock_channel_post.chat = Mock()
                mock_channel_post.chat.id = -1002345  # Allowed channel
                mock_channel_post.chat.type = 'channel'
                mock_channel_post.from_user = Mock()
                mock_channel_post.from_user.first_name = 'CI/CD Bot'
                mock_channel_post.from_user.id = 'cicd_bot'
                
                mock_update = Mock()
                mock_update.channel_post = mock_channel_post
                mock_update.message = None
                mock_context = Mock()
                
                # Execute complete flow
                await client.handle_message(mock_update, mock_context)
                
                # Verify TOML parsing worked
                parsed_toml = client.parse_toml_message(toml_message)
                assert parsed_toml is not None
                assert 'deploy' in parsed_toml
                assert parsed_toml['deploy']['environment'] == 'production'
                
                # Verify command execution with all parameters
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                assert 'docker-compose' in call_args
                assert 'up' in call_args
                assert '-d' in call_args
                assert '--environment' in call_args
                assert 'production' in call_args
                assert '--replicas' in call_args
                assert '3' in call_args
                assert '--timeout' in call_args
                assert '300' in call_args
                assert '--force' in call_args
                assert 'true' in call_args
                
                # Verify success reply was sent
                mock_channel_post.reply_text.assert_called_once()
                reply_text = mock_channel_post.reply_text.call_args[0][0]
                assert 'deploy' in reply_text
                assert 'completed' in reply_text
                assert 'Docker containers started successfully' in reply_text
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_built_in_actions_work_in_channels(self, create_temp_config, channel_config):
        """Test that built-in actions (like Notification) work from channel messages."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(channel_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'), \
                    patch('local_orchestrator_tray.telegram_client.rumps') as mock_rumps:
                
                client = TelegramClient(config_path)
                
                # Built-in action message
                toml_message = """
[Notification]
message = "Deployment to production completed successfully"
title = "Production Alert"
"""
                
                mock_channel_post = Mock()
                mock_channel_post.text = toml_message
                mock_channel_post.reply_text = AsyncMock()
                mock_channel_post.chat = Mock()
                mock_channel_post.chat.id = -1002345  # Allowed channel
                mock_channel_post.chat.type = 'channel'
                mock_channel_post.from_user = Mock()
                mock_channel_post.from_user.first_name = 'Monitor Bot'
                mock_channel_post.from_user.id = 'monitor_bot'
                
                mock_update = Mock()
                mock_update.channel_post = mock_channel_post
                mock_update.message = None
                mock_context = Mock()
                
                # Execute built-in action from channel
                await client.handle_message(mock_update, mock_context)
                
                # Verify notification was shown
                mock_rumps.notification.assert_called_once_with(
                    title='Production Alert',
                    subtitle='',
                    message='Deployment to production completed successfully'
                )
                
                # Verify success reply
                mock_channel_post.reply_text.assert_called_once()
                reply_text = mock_channel_post.reply_text.call_args[0][0]
                assert 'Built-in action \'Notification\' completed' in reply_text
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_custom_actions_work_in_channels(self, create_temp_config, channel_config):
        """Test that custom configured actions work from channel messages."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(channel_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'), \
                    patch('subprocess.run') as mock_run:
                
                mock_run.return_value = Mock(
                    stdout="System Status: All services operational",
                    stderr="",
                    returncode=0
                )
                
                client = TelegramClient(config_path)
                
                # Custom action message
                toml_message = """
[status]
format = "detailed"
include_logs = true
"""
                
                mock_channel_post = Mock()
                mock_channel_post.text = toml_message
                mock_channel_post.reply_text = AsyncMock()
                mock_channel_post.chat = Mock()
                mock_channel_post.chat.id = -1002346  # Second allowed channel
                mock_channel_post.chat.type = 'channel'
                mock_channel_post.from_user = Mock()
                mock_channel_post.from_user.first_name = 'Status Bot'
                mock_channel_post.from_user.id = 'status_bot'
                
                mock_update = Mock()
                mock_update.channel_post = mock_channel_post
                mock_update.message = None
                mock_context = Mock()
                
                # Execute custom action from channel
                await client.handle_message(mock_update, mock_context)
                
                # Verify command execution
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                assert 'uptime' in call_args
                assert '--format' in call_args
                assert 'detailed' in call_args
                assert '--include-logs' in call_args
                assert 'true' in call_args
                
                # Verify success reply
                mock_channel_post.reply_text.assert_called_once()
                reply_text = mock_channel_post.reply_text.call_args[0][0]
                assert 'Custom action \'status\' completed' in reply_text
                assert 'System Status: All services operational' in reply_text
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_channel_error_handling_and_replies(self, create_temp_config, channel_config):
        """Test error handling and reply behavior for channel messages."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(channel_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'), \
                    patch('subprocess.run') as mock_run:
                
                # Mock command failure
                mock_run.return_value = Mock(
                    stdout="",
                    stderr="Command failed: Permission denied",
                    returncode=1
                )
                
                client = TelegramClient(config_path)
                
                # Test various error scenarios
                error_scenarios = [
                    {
                        'name': 'command_failure',
                        'message': '[deploy]\nenvironment = "production"',
                        'expected_error': 'failed'
                    },
                    {
                        'name': 'invalid_toml',
                        'message': '[deploy\ninvalid toml syntax',
                        'expected_error': None  # Should be ignored (not valid TOML)
                    },
                    {
                        'name': 'unknown_action',
                        'message': '[unknown_action]\nparam = "value"',
                        'expected_error': 'not found'
                    }
                ]
                
                for scenario in error_scenarios:
                    mock_run.reset_mock()
                    
                    mock_channel_post = Mock()
                    mock_channel_post.text = scenario['message']
                    mock_channel_post.reply_text = AsyncMock()
                    mock_channel_post.chat = Mock()
                    mock_channel_post.chat.id = -1002345  # Allowed channel
                    mock_channel_post.chat.type = 'channel'
                    mock_channel_post.from_user = Mock()
                    mock_channel_post.from_user.first_name = 'Test Bot'
                    mock_channel_post.from_user.id = 'test_bot'
                    
                    mock_update = Mock()
                    mock_update.channel_post = mock_channel_post
                    mock_update.message = None
                    mock_context = Mock()
                    
                    # Execute scenario
                    await client.handle_message(mock_update, mock_context)
                    
                    if scenario['expected_error']:
                        # Should send error reply
                        mock_channel_post.reply_text.assert_called_once()
                        reply_text = mock_channel_post.reply_text.call_args[0][0]
                        assert scenario['expected_error'] in reply_text.lower()
                    elif scenario['expected_error'] is None:
                        # Should be ignored (invalid TOML)
                        mock_channel_post.reply_text.assert_not_called()
        finally:
            config_path.unlink()


class TestBackwardCompatibility:
    """Test that channel support doesn't break existing functionality."""

    def test_existing_configs_still_work(self, create_temp_config, basic_config):
        """Test that existing configurations without channels still work."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(basic_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'):
                
                # Should initialize successfully with old config format
                client = TelegramClient(config_path)
                
                # Config should be valid
                assert client.config_valid
                assert client.config_error is None
                
                # Should have telegram section
                assert 'telegram' in client.config
                assert client.config['telegram']['bot_token'] == 'test_token_123'
                
                # Channels should default to empty list
                channels = client.config['telegram'].get('channels', [])
                assert channels == []
                
                # Actions should work as before
                assert 'actions' in client.config
                assert 'hello' in client.config['actions']
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_existing_message_flows_unchanged(self, create_temp_config, basic_config):
        """Test that existing message processing flows are unchanged."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(basic_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'), \
                    patch('subprocess.run') as mock_run:
                
                mock_run.return_value = Mock(stdout="hello world", stderr="", returncode=0)
                
                client = TelegramClient(config_path)
                
                # Test regular message processing (should work exactly as before)
                mock_message = Mock()
                mock_message.text = """
[hello]
name = "world"
greeting = "Hi there"
"""
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = 'User'
                mock_message.from_user.id = 67890
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None  # No channel_post in old flows
                mock_context = Mock()
                
                # Process message (should work exactly as before)
                await client.handle_message(mock_update, mock_context)
                
                # Verify command was executed with camelCase conversion
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                assert 'echo' in call_args
                assert '--name' in call_args
                assert 'world' in call_args
                assert '--greeting' in call_args
                assert 'Hi there' in call_args
                
                # Verify reply was sent
                mock_message.reply_text.assert_called_once()
                reply_text = mock_message.reply_text.call_args[0][0]
                assert 'hello' in reply_text
                assert 'completed' in reply_text
        finally:
            config_path.unlink()

    def test_config_migration_not_required(self, create_temp_config, basic_config):
        """Test that no config migration is required for existing setups."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        # Test various old config formats that should still work
        old_config_formats = [
            # Minimal config
            {
                'telegram': {'bot_token': 'test_token'},
                'actions': {}
            },
            # Config with only actions
            {
                'telegram': {'bot_token': 'test_token'},
                'actions': {
                    'test': {'command': 'echo test'}
                }
            },
            # Config with extra sections (should be ignored)
            {
                'telegram': {'bot_token': 'test_token'},
                'actions': {'test': {'command': 'echo test'}},
                'extra_section': {'some': 'data'}
            }
        ]
        
        for i, config in enumerate(old_config_formats):
            config_path = create_temp_config(config)
            
            try:
                with patch('telegram_client.Update'), \
                        patch('telegram_client.Application'), \
                        patch('telegram_client.MessageHandler'), \
                        patch('telegram_client.filters'), \
                        patch('telegram_client.ContextTypes'):
                    
                    # Should work without any migration
                    client = TelegramClient(config_path)
                    
                    # Should be valid
                    assert client.config_valid, f"Old config format {i} should be valid"
                    
                    # Should have expected structure
                    assert 'telegram' in client.config
                    assert 'actions' in client.config
                    
                    # Channels should default to empty (backward compatible)
                    channels = client.config['telegram'].get('channels', [])
                    assert channels == [], f"Old config {i} should have empty channels list"
            finally:
                config_path.unlink()

    @pytest.mark.asyncio
    async def test_application_setup_unchanged_without_channels(self, create_temp_config, basic_config):
        """Test that application setup is unchanged when no channels are configured."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(basic_config)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application') as mock_app_class, \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'):
                
                mock_app = Mock()
                mock_app.initialize = AsyncMock()
                mock_app.start = AsyncMock()
                mock_app.stop = AsyncMock()
                mock_app.shutdown = AsyncMock()
                mock_app.add_handler = Mock()
                
                mock_builder = Mock()
                mock_builder.token.return_value = mock_builder
                mock_builder.allowed_updates.return_value = mock_builder
                mock_builder.build.return_value = mock_app
                mock_app_class.builder.return_value = mock_builder
                
                client = TelegramClient(config_path)
                
                # Start client
                client.start_client()
                
                # Give it a moment for the async setup to trigger
                import time
                time.sleep(0.1)
                
                # Should call token() and build() but NOT allowed_updates()
                mock_builder.token.assert_called_once()
                mock_builder.build.assert_called_once()
                
                # Should NOT call allowed_updates when no channels configured (backward compatibility)
                mock_builder.allowed_updates.assert_not_called()
                
                client.stop_client()
        finally:
            config_path.unlink()

    def test_example_config_remains_compatible(self):
        """Test that the example config format remains compatible."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        # Load actual example config
        example_config_path = Path(__file__).parent.parent / "example-config.yaml"
        
        if example_config_path.exists():
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'):
                
                # Should work with the actual example config
                client = TelegramClient(example_config_path)
                
                # Should be valid (or have meaningful error if bot token is placeholder)
                if 'YOUR_BOT_TOKEN_HERE' not in str(client.config.get('telegram', {})):
                    assert client.config_valid
                else:
                    # Expected to fail validation due to placeholder token
                    assert not client.config_valid
                    assert 'token' in client.config_error.lower()
                
                # Should have proper structure
                assert 'telegram' in client.config
                assert 'actions' in client.config


if __name__ == "__main__":
    # Run tests with pytest if called directly
    pytest.main([__file__, "-v"])