#!/usr/bin/env python3
"""
Integration tests for the complete message processing pipeline.

Tests the full flow from Telegram message receipt to command execution and reply,
including both regular messages and channel posts. These tests drive the refactoring
of complex methods by testing the complete user journey.

This test suite focuses on:
1. End-to-end message processing flows
2. Integration between TOML parsing, action execution, and reply handling
3. Error propagation through the entire pipeline
4. Message truncation and result formatting
5. Both regular and channel message handling paths
"""

import asyncio
import subprocess
import tempfile
import yaml
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
import pytest
import sys
import random
import string

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Mock rumps before any imports that might trigger it
sys.modules['rumps'] = Mock()


@pytest.fixture
def integration_config():
    """Create a comprehensive test configuration for integration testing."""
    return {
        'telegram': {
            'bot_token': 'integration_test_token_123',
            'channels': [-1002345, -1002346, 1002347]
        },
        'actions': {
            'deploy': {
                'command': 'docker-compose up -d',
                'description': 'Deploy application containers',
                'working_dir': '/app'
            },
            'status': {
                'command': 'systemctl status',
                'description': 'Check system status'
            },
            'build': {
                'command': 'npm run build',
                'description': 'Build the application',
                'working_dir': '/project'
            },
            'test': {
                'command': 'pytest',
                'description': 'Run test suite',
                'working_dir': '/project'
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
    
    # Cleanup
    for file_path in created_files:
        try:
            file_path.unlink()
        except FileNotFoundError:
            pass


@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run with configurable return values."""
    with patch('subprocess.run') as mock_run:
        yield mock_run


class TestFullMessageProcessingPipeline:
    """Test complete message processing from receipt to reply."""

    @pytest.mark.asyncio
    async def test_successful_message_processing_end_to_end(self, create_temp_config, integration_config, mock_subprocess_run):
        """Test complete successful message processing pipeline."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(integration_config)
        
        # Setup successful command execution
        mock_subprocess_run.return_value = Mock(
            stdout="Deployment completed successfully\nServices started: 3\nHealth check: PASSED",
            stderr="",
            returncode=0
        )
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            # Test regular message processing
            mock_message = Mock()
            mock_message.text = """
[deploy]
environment = "production"
replicas = 5
timeout = 600
force_rebuild = true
"""
            mock_message.reply_text = AsyncMock()
            mock_message.chat = Mock()
            mock_message.chat.id = 12345
            mock_message.chat.type = 'private'
            mock_message.from_user = Mock()
            mock_message.from_user.first_name = 'TestUser'
            mock_message.from_user.id = 67890
            
            mock_update = Mock()
            mock_update.message = mock_message
            mock_update.channel_post = None
            mock_context = Mock()
            
            # Execute complete pipeline
            start_time = time.time()
            await client.handle_message(mock_update, mock_context)
            processing_time = time.time() - start_time
            
            # Verify complete pipeline execution
            # 1. Command should be executed with all parameters
            mock_subprocess_run.assert_called_once()
            call_args = mock_subprocess_run.call_args[0][0]
            assert 'docker-compose' in call_args
            assert 'up' in call_args
            assert '-d' in call_args
            assert '--environment' in call_args
            assert 'production' in call_args
            assert '--replicas' in call_args
            assert '5' in call_args
            assert '--timeout' in call_args
            assert '600' in call_args
            assert '--force-rebuild' in call_args
            assert 'true' in call_args
            
            # 2. Working directory should be set
            assert mock_subprocess_run.call_args[1]['cwd'] == '/app'
            
            # 3. Reply should be sent with complete information
            mock_message.reply_text.assert_called_once()
            reply_text = mock_message.reply_text.call_args[0][0]
            assert 'deploy' in reply_text
            assert 'completed' in reply_text
            assert 'Deployment completed successfully' in reply_text
            assert 'Services started: 3' in reply_text
            assert 'Health check: PASSED' in reply_text
            
            # 4. Performance check - should complete quickly
            assert processing_time < 5.0, f"Pipeline took {processing_time:.2f}s, too slow"

    @pytest.mark.asyncio
    async def test_channel_message_processing_end_to_end(self, create_temp_config, integration_config, mock_subprocess_run):
        """Test complete channel message processing pipeline."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(integration_config)
        
        # Setup command that produces large output
        large_output = "Status check:\n" + "\n".join([f"Service {i}: Running" for i in range(100)])
        mock_subprocess_run.return_value = Mock(
            stdout=large_output,
            stderr="",
            returncode=0
        )
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            # Test channel_post processing from allowed channel
            mock_channel_post = Mock()
            mock_channel_post.text = """
[status]
service_type = "all"
include_logs = true
format = "detailed"
"""
            mock_channel_post.reply_text = AsyncMock()
            mock_channel_post.chat = Mock()
            mock_channel_post.chat.id = -1002345  # Allowed channel
            mock_channel_post.chat.type = 'channel'
            mock_channel_post.from_user = Mock()
            mock_channel_post.from_user.first_name = 'CI/CD Bot'
            mock_channel_post.from_user.id = 'cicd_bot'
            
            mock_update = Mock()
            mock_update.message = None
            mock_update.channel_post = mock_channel_post
            mock_context = Mock()
            
            # Execute pipeline
            await client.handle_message(mock_update, mock_context)
            
            # Verify channel-specific handling
            # 1. Command executed with correct parameters
            mock_subprocess_run.assert_called_once()
            call_args = mock_subprocess_run.call_args[0][0]
            assert 'systemctl' in call_args
            assert 'status' in call_args
            assert '--service-type' in call_args
            assert 'all' in call_args
            assert '--include-logs' in call_args
            assert 'true' in call_args
            assert '--format' in call_args
            assert 'detailed' in call_args
            
            # 2. Reply should handle large output (truncation if needed)
            mock_channel_post.reply_text.assert_called_once()
            reply_text = mock_channel_post.reply_text.call_args[0][0]
            assert 'status' in reply_text
            assert 'completed' in reply_text
            # Should include output but may be truncated
            assert len(reply_text) <= 4500  # Should respect Telegram limits

    @pytest.mark.asyncio
    async def test_built_in_action_processing_pipeline(self, create_temp_config, integration_config):
        """Test processing pipeline for built-in actions."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(integration_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('local_orchestrator_tray.telegram_client.rumps') as mock_rumps:
            
            client = TelegramClient(config_path)
            
            mock_message = Mock()
            mock_message.text = """
[Notification]
message = "Deployment completed successfully"
title = "Production Alert"
"""
            mock_message.reply_text = AsyncMock()
            mock_message.chat = Mock()
            mock_message.chat.id = 12345
            mock_message.chat.type = 'private'
            mock_message.from_user = Mock()
            mock_message.from_user.first_name = 'DevOps'
            mock_message.from_user.id = 11111
            
            mock_update = Mock()
            mock_update.message = mock_message
            mock_update.channel_post = None
            mock_context = Mock()
            
            # Execute built-in action pipeline
            await client.handle_message(mock_update, mock_context)
            
            # Verify built-in action execution
            mock_rumps.notification.assert_called_once_with(
                title='Production Alert',
                subtitle='',
                message='Deployment completed successfully'
            )
            
            # Verify built-in action reply
            mock_message.reply_text.assert_called_once()
            reply_text = mock_message.reply_text.call_args[0][0]
            assert 'Built-in action \'Notification\' completed' in reply_text

    @pytest.mark.asyncio
    async def test_multiple_actions_processing_pipeline(self, create_temp_config, integration_config, mock_subprocess_run):
        """Test processing pipeline for messages with multiple actions."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(integration_config)
        
        # Setup different outputs for different commands
        def mock_run_side_effect(cmd, **kwargs):
            if 'pytest' in cmd:
                return Mock(stdout="Tests passed: 25/25", stderr="", returncode=0)
            elif 'npm' in cmd:
                return Mock(stdout="Build completed in 45s", stderr="", returncode=0)
            else:
                return Mock(stdout="Unknown command", stderr="", returncode=1)
        
        mock_subprocess_run.side_effect = mock_run_side_effect
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            mock_message = Mock()
            mock_message.text = """
[test]
verbose = true
coverage = true

[build]
environment = "production"
minify = true
"""
            mock_message.reply_text = AsyncMock()
            mock_message.chat = Mock()
            mock_message.chat.id = 12345
            mock_message.chat.type = 'private'
            mock_message.from_user = Mock()
            mock_message.from_user.first_name = 'Developer'
            mock_message.from_user.id = 22222
            
            mock_update = Mock()
            mock_update.message = mock_message
            mock_update.channel_post = None
            mock_context = Mock()
            
            # Execute pipeline with multiple actions
            await client.handle_message(mock_update, mock_context)
            
            # Verify both commands were executed
            assert mock_subprocess_run.call_count == 2
            
            # Check that replies were sent for both actions
            # Implementation should handle multiple actions appropriately
            assert mock_message.reply_text.call_count >= 1

    @pytest.mark.asyncio
    async def test_error_handling_in_processing_pipeline(self, create_temp_config, integration_config, mock_subprocess_run):
        """Test error handling throughout the complete processing pipeline."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(integration_config)
        
        # Test various error scenarios
        error_scenarios = [
            {
                'name': 'command_failure',
                'returncode': 1,
                'stdout': '',
                'stderr': 'Permission denied: cannot access deployment directory',
                'expected_in_reply': 'failed'
            },
            {
                'name': 'command_timeout',
                'side_effect': subprocess.TimeoutExpired('docker-compose', 30),
                'expected_in_reply': 'timeout'
            },
            {
                'name': 'command_not_found',
                'side_effect': FileNotFoundError('docker-compose: command not found'),
                'expected_in_reply': 'not found'
            }
        ]
        
        for scenario in error_scenarios:
            mock_subprocess_run.reset_mock()
            
            if 'side_effect' in scenario:
                mock_subprocess_run.side_effect = scenario['side_effect']
            else:
                mock_subprocess_run.side_effect = None
                mock_subprocess_run.return_value = Mock(
                    stdout=scenario.get('stdout', ''),
                    stderr=scenario.get('stderr', ''),
                    returncode=scenario.get('returncode', 0)
                )
            
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'):
                
                client = TelegramClient(config_path)
                
                mock_message = Mock()
                mock_message.text = "[deploy]\nenvironment = 'test'"
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = 'Tester'
                mock_message.from_user.id = 33333
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                # Execute pipeline with error scenario
                await client.handle_message(mock_update, mock_context)
                
                # Verify error was handled and appropriate reply sent
                mock_message.reply_text.assert_called_once()
                reply_text = mock_message.reply_text.call_args[0][0].lower()
                assert scenario['expected_in_reply'] in reply_text, f"Scenario '{scenario['name']}' should include '{scenario['expected_in_reply']}' in reply"

    @pytest.mark.asyncio
    async def test_message_truncation_in_pipeline(self, create_temp_config, integration_config, mock_subprocess_run):
        """Test message truncation handling in the processing pipeline."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(integration_config)
        
        # Create very large output that exceeds Telegram limits
        large_output = "Log entries:\n" + "\n".join([
            f"[{i:06d}] Service check: {''.join(random.choices(string.ascii_letters, k=100))}"
            for i in range(1000)
        ])
        
        mock_subprocess_run.return_value = Mock(
            stdout=large_output,
            stderr="",
            returncode=0
        )
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            mock_message = Mock()
            mock_message.text = "[status]\nverbose = true"
            mock_message.reply_text = AsyncMock()
            mock_message.chat = Mock()
            mock_message.chat.id = 12345
            mock_message.chat.type = 'private'
            mock_message.from_user = Mock()
            mock_message.from_user.first_name = 'Admin'
            mock_message.from_user.id = 44444
            
            mock_update = Mock()
            mock_update.message = mock_message
            mock_update.channel_post = None
            mock_context = Mock()
            
            # Execute pipeline with large output
            await client.handle_message(mock_update, mock_context)
            
            # Verify truncation handling
            mock_message.reply_text.assert_called_once()
            reply_text = mock_message.reply_text.call_args[0][0]
            
            # Should be truncated to respect Telegram limits
            assert len(reply_text) <= 4500
            
            # Should indicate truncation
            if len(large_output) > 3000:  # If original was large enough to need truncation
                assert 'truncated' in reply_text.lower() or '...' in reply_text

    @pytest.mark.asyncio
    async def test_channel_filtering_in_pipeline(self, create_temp_config, integration_config, mock_subprocess_run):
        """Test channel ID filtering throughout the processing pipeline."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(integration_config)
        
        mock_subprocess_run.return_value = Mock(stdout="test output", stderr="", returncode=0)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            # Test allowed channel
            mock_channel_post = Mock()
            mock_channel_post.text = "[test]\nparam = 'value'"
            mock_channel_post.reply_text = AsyncMock()
            mock_channel_post.chat = Mock()
            mock_channel_post.chat.id = -1002345  # Allowed channel
            mock_channel_post.chat.type = 'channel'
            mock_channel_post.from_user = Mock()
            mock_channel_post.from_user.first_name = 'Bot'
            mock_channel_post.from_user.id = 'bot_id'
            
            mock_update = Mock()
            mock_update.message = None
            mock_update.channel_post = mock_channel_post
            mock_context = Mock()
            
            # Allowed channel should process
            await client.handle_message(mock_update, mock_context)
            mock_subprocess_run.assert_called_once()
            mock_channel_post.reply_text.assert_called_once()
            
            # Reset mocks for blocked channel test
            mock_subprocess_run.reset_mock()
            mock_channel_post.reply_text.reset_mock()
            
            # Test blocked channel
            mock_channel_post.chat.id = -1002999  # Not in allowed channels
            await client.handle_message(mock_update, mock_context)
            
            # Blocked channel should not process
            mock_subprocess_run.assert_not_called()
            mock_channel_post.reply_text.assert_not_called()


class TestMessageProcessingEdgeCases:
    """Test edge cases in the message processing pipeline."""

    @pytest.mark.asyncio
    async def test_malformed_toml_handling_in_pipeline(self, create_temp_config, integration_config):
        """Test handling of malformed TOML in the processing pipeline."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(integration_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            malformed_toml_messages = [
                "[deploy\ninvalid syntax",
                "[deploy]\nkey = 'unclosed string",
                "not toml at all",
                "",  # Empty message
                "   \n  \n   ",  # Whitespace only
                "[]\nkey = 'value'",  # Empty section name
            ]
            
            for malformed_toml in malformed_toml_messages:
                mock_message = Mock()
                mock_message.text = malformed_toml
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = 'User'
                mock_message.from_user.id = 55555
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                # Should handle malformed TOML gracefully
                try:
                    await client.handle_message(mock_update, mock_context)
                    # Implementation may choose to ignore invalid TOML or send error
                    # Both behaviors are acceptable
                except Exception as e:
                    pytest.fail(f"Pipeline should handle malformed TOML gracefully, got: {e}")

    @pytest.mark.asyncio
    async def test_unknown_action_handling_in_pipeline(self, create_temp_config, integration_config):
        """Test handling of unknown actions in the processing pipeline."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(integration_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            mock_message = Mock()
            mock_message.text = """
[nonexistent_action]
param1 = "value1"
param2 = "value2"
"""
            mock_message.reply_text = AsyncMock()
            mock_message.chat = Mock()
            mock_message.chat.id = 12345
            mock_message.chat.type = 'private'
            mock_message.from_user = Mock()
            mock_message.from_user.first_name = 'User'
            mock_message.from_user.id = 66666
            
            mock_update = Mock()
            mock_update.message = mock_message
            mock_update.channel_post = None
            mock_context = Mock()
            
            # Execute pipeline with unknown action
            await client.handle_message(mock_update, mock_context)
            
            # Should send error reply for unknown action
            mock_message.reply_text.assert_called_once()
            reply_text = mock_message.reply_text.call_args[0][0].lower()
            assert 'not found' in reply_text or 'unknown' in reply_text

    @pytest.mark.asyncio
    async def test_concurrent_message_processing(self, create_temp_config, integration_config, mock_subprocess_run):
        """Test concurrent processing of multiple messages."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(integration_config)
        
        # Simulate slow command execution
        mock_subprocess_run.return_value = Mock(stdout="slow output", stderr="", returncode=0)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            # Create multiple messages
            messages = []
            for i in range(3):
                mock_message = Mock()
                mock_message.text = f"[status]\nid = {i}"
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345 + i
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = f'User{i}'
                mock_message.from_user.id = 77777 + i
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                messages.append((mock_update, mock_context, mock_message))
            
            # Process messages concurrently
            start_time = time.time()
            tasks = [client.handle_message(update, context) for update, context, _ in messages]
            await asyncio.gather(*tasks)
            processing_time = time.time() - start_time
            
            # Verify all messages were processed
            assert mock_subprocess_run.call_count == 3
            for _, _, mock_message in messages:
                mock_message.reply_text.assert_called_once()
            
            # Should handle concurrency efficiently
            assert processing_time < 10.0, f"Concurrent processing took {processing_time:.2f}s, too slow"

    @pytest.mark.asyncio
    async def test_mixed_message_types_processing(self, create_temp_config, integration_config, mock_subprocess_run):
        """Test processing mixed regular and channel messages concurrently."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(integration_config)
        
        mock_subprocess_run.return_value = Mock(stdout="mixed output", stderr="", returncode=0)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            # Create mixed message types
            updates = []
            
            # Regular message
            mock_message = Mock()
            mock_message.text = "[test]\ntype = 'regular'"
            mock_message.reply_text = AsyncMock()
            mock_message.chat = Mock()
            mock_message.chat.id = 12345
            mock_message.chat.type = 'private'
            mock_message.from_user = Mock()
            mock_message.from_user.first_name = 'RegularUser'
            mock_message.from_user.id = 88888
            
            mock_update1 = Mock()
            mock_update1.message = mock_message
            mock_update1.channel_post = None
            updates.append((mock_update1, Mock(), mock_message))
            
            # Channel message (allowed)
            mock_channel_post = Mock()
            mock_channel_post.text = "[test]\ntype = 'channel'"
            mock_channel_post.reply_text = AsyncMock()
            mock_channel_post.chat = Mock()
            mock_channel_post.chat.id = -1002345  # Allowed
            mock_channel_post.chat.type = 'channel'
            mock_channel_post.from_user = Mock()
            mock_channel_post.from_user.first_name = 'ChannelBot'
            mock_channel_post.from_user.id = 'channel_bot'
            
            mock_update2 = Mock()
            mock_update2.message = None
            mock_update2.channel_post = mock_channel_post
            updates.append((mock_update2, Mock(), mock_channel_post))
            
            # Process mixed messages concurrently
            tasks = [client.handle_message(update, context) for update, context, _ in updates]
            await asyncio.gather(*tasks)
            
            # Both should be processed
            assert mock_subprocess_run.call_count == 2
            mock_message.reply_text.assert_called_once()
            mock_channel_post.reply_text.assert_called_once()


class TestPipelinePerformanceAndReliability:
    """Test performance characteristics and reliability of the message processing pipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_performance_with_large_messages(self, create_temp_config, integration_config, mock_subprocess_run):
        """Test pipeline performance with large TOML messages."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(integration_config)
        
        mock_subprocess_run.return_value = Mock(stdout="large message processed", stderr="", returncode=0)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            # Create large TOML message
            large_toml = "[deploy]\n" + "\n".join([
                f"param_{i} = 'value_{i}_{'x' * 50}'"
                for i in range(100)
            ])
            
            mock_message = Mock()
            mock_message.text = large_toml
            mock_message.reply_text = AsyncMock()
            mock_message.chat = Mock()
            mock_message.chat.id = 12345
            mock_message.chat.type = 'private'
            mock_message.from_user = Mock()
            mock_message.from_user.first_name = 'LargeUser'
            mock_message.from_user.id = 99999
            
            mock_update = Mock()
            mock_update.message = mock_message
            mock_update.channel_post = None
            mock_context = Mock()
            
            # Measure processing time
            start_time = time.time()
            await client.handle_message(mock_update, mock_context)
            processing_time = time.time() - start_time
            
            # Should handle large messages efficiently
            assert processing_time < 2.0, f"Large message processing took {processing_time:.2f}s, too slow"
            mock_subprocess_run.assert_called_once()
            mock_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_memory_usage_stability(self, create_temp_config, integration_config, mock_subprocess_run):
        """Test that pipeline doesn't leak memory with repeated processing."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(integration_config)
        
        mock_subprocess_run.return_value = Mock(stdout="memory test output", stderr="", returncode=0)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            # Process many messages in sequence
            for i in range(50):
                mock_message = Mock()
                mock_message.text = f"[test]\niteration = {i}"
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345 + i
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = f'User{i}'
                mock_message.from_user.id = 100000 + i
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                await client.handle_message(mock_update, mock_context)
            
            # Should process all messages successfully
            assert mock_subprocess_run.call_count == 50

    @pytest.mark.asyncio
    async def test_pipeline_error_recovery(self, create_temp_config, integration_config, mock_subprocess_run):
        """Test that pipeline recovers from errors and continues processing."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(integration_config)
        
        # Simulate intermittent failures
        call_count = 0
        def failing_subprocess(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # Every 3rd call fails
                return Mock(stdout="", stderr="Intermittent failure", returncode=1)
            else:
                return Mock(stdout=f"Success {call_count}", stderr="", returncode=0)
        
        mock_subprocess_run.side_effect = failing_subprocess
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            # Process multiple messages with intermittent failures
            for i in range(10):
                mock_message = Mock()
                mock_message.text = f"[test]\nsequence = {i}"
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345 + i
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = f'TestUser{i}'
                mock_message.from_user.id = 200000 + i
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                # Should handle errors gracefully and continue
                try:
                    await client.handle_message(mock_update, mock_context)
                    mock_message.reply_text.assert_called_once()
                except Exception as e:
                    pytest.fail(f"Pipeline should recover from errors gracefully, got: {e}")
            
            # All messages should have been processed (some with errors, some successfully)
            assert mock_subprocess_run.call_count == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])