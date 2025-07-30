#!/usr/bin/env python3
"""
Test suite for built-in actions functionality.
Tests the implementation of issue #4: Built-in actions support.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import asyncio
import sys

# Mock rumps before importing local_orchestrator_tray modules
sys.modules['rumps'] = Mock()

# Import the classes we need to test
from local_orchestrator_tray.telegram_client import (
    BuiltInActionRegistry,
    TelegramClient,
    ActionRegistry
)


class TestBuiltInActionRegistry:
    """Test the BuiltInActionRegistry class."""

    def test_initialization(self):
        """Test that BuiltInActionRegistry initializes correctly."""
        registry = BuiltInActionRegistry()
        
        # Should have Notification action
        assert 'Notification' in registry.actions
        assert registry.is_built_in_action('Notification')
        assert not registry.is_built_in_action('custom_action')
        
        # Check Notification action config
        notification_config = registry.get_action('Notification')
        assert notification_config is not None
        assert 'handler' in notification_config
        assert 'description' in notification_config
        assert 'required_params' in notification_config
        assert 'message' in notification_config['required_params']
        assert 'title' in notification_config['optional_params']

    def test_list_actions(self):
        """Test listing built-in actions."""
        registry = BuiltInActionRegistry()
        actions = registry.list_actions()
        
        assert isinstance(actions, list)
        assert 'Notification' in actions

    def test_get_actions_description(self):
        """Test getting formatted description of built-in actions."""
        registry = BuiltInActionRegistry()
        description = registry.get_actions_description()
        
        assert 'Built-in actions:' in description
        assert 'Notification' in description
        assert 'Show a system notification' in description
        assert 'Required: message' in description
        assert 'Optional: title' in description

    @pytest.mark.asyncio
    async def test_notification_handler_with_title(self):
        """Test notification handler with title parameter."""
        registry = BuiltInActionRegistry()
        
        with patch('local_orchestrator_tray.telegram_client.rumps') as mock_rumps:
            params = {'message': 'Test message', 'title': 'Test title'}
            result = await registry._handle_notification(params)
            
            mock_rumps.notification.assert_called_once_with(
                title='Test title',
                subtitle='',
                message='Test message'
            )
            assert 'Notification shown: Test title - Test message' in result

    @pytest.mark.asyncio
    async def test_notification_handler_without_title(self):
        """Test notification handler with default title."""
        registry = BuiltInActionRegistry()
        
        with patch('local_orchestrator_tray.telegram_client.rumps') as mock_rumps:
            params = {'message': 'Test message'}
            result = await registry._handle_notification(params)
            
            mock_rumps.notification.assert_called_once_with(
                title='Local Orchestrator',
                subtitle='',
                message='Test message'
            )
            assert 'Notification shown: Local Orchestrator - Test message' in result

    @pytest.mark.asyncio
    async def test_notification_handler_missing_message(self):
        """Test notification handler with missing message parameter."""
        registry = BuiltInActionRegistry()
        
        with pytest.raises(ValueError, match="Notification action requires 'message' parameter"):
            await registry._handle_notification({})

    @pytest.mark.asyncio
    async def test_notification_handler_no_rumps(self):
        """Test notification handler when rumps is not available."""
        registry = BuiltInActionRegistry()
        
        with patch('local_orchestrator_tray.telegram_client.rumps', None):
            params = {'message': 'Test message', 'title': 'Test title'}
            result = await registry._handle_notification(params)
            
            assert 'Notification would show: Test title - Test message (rumps not available)' in result


class TestTelegramClientBuiltInActions:
    """Test TelegramClient integration with built-in actions."""

    def create_temp_config(self, config_data):
        """Helper to create temporary config file."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(config_data, temp_file, default_flow_style=False)
        temp_file.close()
        return Path(temp_file.name)

    def test_client_initialization_with_built_in_registry(self):
        """Test that TelegramClient initializes with BuiltInActionRegistry."""
        config = {
            'telegram': {'bot_token': 'test_token'},
            'actions': {}
        }
        config_path = self.create_temp_config(config)
        
        try:
            client = TelegramClient(config_path)
            assert hasattr(client, 'built_in_action_registry')
            assert isinstance(client.built_in_action_registry, BuiltInActionRegistry)
            assert client.config_valid  # Should be valid
        finally:
            config_path.unlink()

    def test_config_validation_rejects_uppercase_custom_actions(self):
        """Test that config validation rejects custom actions starting with uppercase."""
        config = {
            'telegram': {'bot_token': 'test_token'},
            'actions': {
                'Uppercase': {'command': 'echo test'},  # Should be rejected
                'lowercase': {'command': 'echo test'}   # Should be accepted
            }
        }
        config_path = self.create_temp_config(config)
        
        try:
            client = TelegramClient(config_path)
            assert not client.config_valid
            assert 'starts with uppercase letter' in client.config_error
            assert 'reserved for built-in actions' in client.config_error
        finally:
            config_path.unlink()

    def test_config_validation_accepts_lowercase_custom_actions(self):
        """Test that config validation accepts custom actions starting with lowercase."""
        config = {
            'telegram': {'bot_token': 'test_token'},
            'actions': {
                'lowercase': {'command': 'echo test'},
                'another_action': {'command': 'ls -la'}
            }
        }
        config_path = self.create_temp_config(config)
        
        try:
            client = TelegramClient(config_path)
            assert client.config_valid
            assert client.config_error is None
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_execute_built_in_action(self):
        """Test executing a built-in action."""
        config = {
            'telegram': {'bot_token': 'test_token'},
            'actions': {}
        }
        config_path = self.create_temp_config(config)
        
        try:
            client = TelegramClient(config_path)
            
            with patch('local_orchestrator_tray.telegram_client.rumps') as mock_rumps:
                params = {'message': 'Test notification', 'title': 'Test'}
                result = await client.execute_built_in_action('Notification', params)
                
                mock_rumps.notification.assert_called_once_with(
                    title='Test',
                    subtitle='',
                    message='Test notification'
                )
                assert 'Notification shown: Test - Test notification' in result
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_execute_built_in_action_missing_params(self):
        """Test executing built-in action with missing required parameters."""
        config = {
            'telegram': {'bot_token': 'test_token'},
            'actions': {}
        }
        config_path = self.create_temp_config(config)
        
        try:
            client = TelegramClient(config_path)
            
            with pytest.raises(ValueError, match="requires parameter 'message'"):
                await client.execute_built_in_action('Notification', {})
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_execute_built_in_action_not_found(self):
        """Test executing non-existent built-in action."""
        config = {
            'telegram': {'bot_token': 'test_token'},
            'actions': {}
        }
        config_path = self.create_temp_config(config)
        
        try:
            client = TelegramClient(config_path)
            
            with pytest.raises(Exception, match="Built-in action 'NonExistent' not found"):
                await client.execute_built_in_action('NonExistent', {})
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_process_toml_actions_built_in_priority(self):
        """Test that built-in actions are processed before custom actions."""
        config = {
            'telegram': {'bot_token': 'test_token'},
            'actions': {
                'test_action': {'command': 'echo custom'}
            }
        }
        config_path = self.create_temp_config(config)
        
        try:
            client = TelegramClient(config_path)
            
            # Create mock message
            mock_message = Mock()
            mock_message.reply_text = AsyncMock()
            
            # Test built-in action (should use built-in registry)
            toml_data = {'Notification': {'message': 'Test'}}
            
            with patch('local_orchestrator_tray.telegram_client.rumps') as mock_rumps:
                await client.process_toml_actions(mock_message, toml_data)
                
                # Should call rumps.notification
                mock_rumps.notification.assert_called_once()
                
                # Should reply with built-in action message
                mock_message.reply_text.assert_called_once()
                call_args = mock_message.reply_text.call_args[0][0]
                assert 'Built-in action \'Notification\' completed' in call_args
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_process_toml_actions_custom_action_fallback(self):
        """Test that custom actions are processed when built-in not found."""
        config = {
            'telegram': {'bot_token': 'test_token'},
            'actions': {
                'test_action': {'command': 'echo custom'}
            }
        }
        config_path = self.create_temp_config(config)
        
        try:
            client = TelegramClient(config_path)
            
            # Create mock message
            mock_message = Mock()
            mock_message.reply_text = AsyncMock()
            
            # Test custom action
            toml_data = {'test_action': {'param': 'value'}}
            
            with patch('subprocess.run') as mock_subprocess:
                mock_subprocess.return_value.returncode = 0
                mock_subprocess.return_value.stdout = 'custom output'
                mock_subprocess.return_value.stderr = ''
                
                await client.process_toml_actions(mock_message, toml_data)
                
                # Should call subprocess.run for custom action
                mock_subprocess.assert_called_once()
                
                # Should reply with custom action message
                mock_message.reply_text.assert_called_once()
                call_args = mock_message.reply_text.call_args[0][0]
                assert 'Custom action \'test_action\' completed' in call_args
        finally:
            config_path.unlink()

    @pytest.mark.asyncio
    async def test_process_toml_actions_not_found_shows_all_actions(self):
        """Test that action not found shows both built-in and custom actions."""
        config = {
            'telegram': {'bot_token': 'test_token'},
            'actions': {
                'custom_action': {'command': 'echo test'}
            }
        }
        config_path = self.create_temp_config(config)
        
        try:
            client = TelegramClient(config_path)
            
            # Create mock message
            mock_message = Mock()
            mock_message.reply_text = AsyncMock()
            
            # Test non-existent action
            toml_data = {'nonexistent': {'param': 'value'}}
            
            await client.process_toml_actions(mock_message, toml_data)
            
            # Should reply with combined action descriptions
            mock_message.reply_text.assert_called_once()
            call_args = mock_message.reply_text.call_args[0][0]
            assert 'Action \'nonexistent\' not found' in call_args
            assert 'Built-in actions:' in call_args
            assert 'Notification' in call_args
            assert 'Custom actions:' in call_args
            assert 'custom_action' in call_args
        finally:
            config_path.unlink()


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v'])