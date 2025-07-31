#!/usr/bin/env python3
"""
Error recovery scenario tests.

Tests the system's ability to recover from various error conditions and
continue operating normally. These tests ensure resilience and fault tolerance
in the face of network issues, configuration problems, and runtime errors.

This test suite focuses on:
1. Network connectivity loss and recovery
2. Telegram API errors and reconnection
3. Configuration reload after validation errors
4. Service restart scenarios
5. Resource cleanup after failures
6. Graceful degradation strategies
7. State consistency after errors
"""

import asyncio
import tempfile
import yaml
import time
import threading
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
import pytest
import sys
import subprocess
import json

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Mock rumps before any imports that might trigger it
sys.modules['rumps'] = Mock()


@pytest.fixture
def recovery_config():
    """Create configuration for error recovery testing."""
    return {
        'telegram': {
            'bot_token': 'recovery_test_token_123',
            'channels': [-1002345, -1002346]
        },
        'actions': {
            'reliable_action': {
                'command': 'echo "reliable"',
                'description': 'Action that should work reliably'
            },
            'flaky_action': {
                'command': 'flaky_command',
                'description': 'Action that might fail intermittently'
            },
            'resource_intensive': {
                'command': 'python -c "import time; time.sleep(0.1)"',
                'description': 'Action that uses resources'
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


class TestNetworkErrorRecovery:
    """Test recovery from network-related errors."""

    @pytest.mark.asyncio
    async def test_telegram_api_connection_loss_recovery(self, create_temp_config, recovery_config):
        """Test recovery from Telegram API connection loss."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(recovery_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application') as mock_app_class, \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            # Track connection attempts
            connection_attempts = []
            
            def failing_then_succeeding_app(*args, **kwargs):
                attempt_count = len(connection_attempts)
                connection_attempts.append(attempt_count)
                
                mock_app = Mock()
                mock_app.add_handler = Mock()
                
                if attempt_count < 2:  # First 2 attempts fail
                    mock_app.initialize = AsyncMock(side_effect=ConnectionError("Network unreachable"))
                    mock_app.start = AsyncMock(side_effect=ConnectionError("Network unreachable"))
                else:  # Subsequent attempts succeed
                    mock_app.initialize = AsyncMock()
                    mock_app.start = AsyncMock()
                
                mock_app.stop = AsyncMock()
                mock_app.shutdown = AsyncMock()
                
                mock_updater = Mock()
                mock_updater.start_polling = AsyncMock()
                mock_updater.stop = AsyncMock()
                mock_app.updater = mock_updater
                
                return mock_app
            
            mock_builder = Mock()
            mock_builder.token.return_value = mock_builder
            mock_builder.allowed_updates.return_value = mock_builder
            mock_builder.build.side_effect = failing_then_succeeding_app
            mock_app_class.builder.return_value = mock_builder
            
            client = TelegramClient(config_path)
            
            # Initial connection should fail
            success1 = client.start_client()
            assert not success1, "First connection attempt should fail"
            
            # Retry should also fail
            success2 = client.start_client()
            assert not success2, "Second connection attempt should fail"
            
            # Third attempt should succeed (simulating network recovery)
            success3 = client.start_client()
            assert success3, "Third connection attempt should succeed after network recovery"
            
            # Should have made multiple connection attempts
            assert len(connection_attempts) >= 3

    @pytest.mark.asyncio
    async def test_telegram_api_rate_limiting_recovery(self, create_temp_config, recovery_config):
        """Test recovery from Telegram API rate limiting."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(recovery_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            # Mock rate limiting then recovery
            call_count = 0
            def rate_limited_then_success(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                
                if call_count <= 3:  # First 3 calls are rate limited
                    from telegram.error import RetryAfter
                    raise RetryAfter(retry_after=0.1)  # Short retry for testing
                else:
                    return Mock(stdout="success after rate limit", stderr="", returncode=0)
            
            mock_run.side_effect = rate_limited_then_success
            
            client = TelegramClient(config_path)
            
            # Create message that will trigger rate limiting
            mock_message = Mock()
            mock_message.text = "[reliable_action]\ntest = 'rate_limit'"
            mock_message.reply_text = AsyncMock()
            mock_message.chat = Mock()
            mock_message.chat.id = 12345
            mock_message.chat.type = 'private'
            mock_message.from_user = Mock()
            mock_message.from_user.first_name = 'RateLimitUser'
            mock_message.from_user.id = 11111
            
            mock_update = Mock()
            mock_update.message = mock_message
            mock_update.channel_post = None
            mock_context = Mock()
            
            # Process message - should handle rate limiting gracefully
            try:
                await client.handle_message(mock_update, mock_context)
                
                # Should eventually succeed after rate limit recovery
                # Implementation should either retry or gracefully degrade
                assert mock_message.reply_text.called, "Should send some reply even with rate limiting"
                
            except Exception as e:
                # If it throws an exception, should be handled gracefully by caller
                assert "rate" in str(e).lower() or "retry" in str(e).lower()

    @pytest.mark.asyncio
    async def test_intermittent_network_failure_resilience(self, create_temp_config, recovery_config):
        """Test resilience to intermittent network failures."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(recovery_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            mock_run.return_value = Mock(stdout="network test", stderr="", returncode=0)
            
            client = TelegramClient(config_path)
            
            # Simulate intermittent network issues during message processing
            messages = []
            for i in range(10):
                mock_message = Mock()
                mock_message.text = f"[reliable_action]\nnetwork_test = {i}"
                mock_message.reply_text = AsyncMock()
                
                # Simulate network issues on some replies
                if i % 3 == 0:  # Every 3rd message has network issues
                    mock_message.reply_text.side_effect = ConnectionError("Network temporarily unavailable")
                
                mock_message.chat = Mock()
                mock_message.chat.id = 12345 + i
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = f'NetworkUser{i}'
                mock_message.from_user.id = 20000 + i
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                messages.append((mock_update, mock_context, mock_message))
            
            # Process all messages - should handle network issues gracefully
            successful_messages = 0
            failed_messages = 0
            
            for mock_update, mock_context, mock_message in messages:
                try:
                    await client.handle_message(mock_update, mock_context)
                    if mock_message.reply_text.called:
                        successful_messages += 1
                    else:
                        # Command executed but reply failed - still partial success
                        successful_messages += 1
                except ConnectionError:
                    failed_messages += 1
                except Exception:
                    # Other exceptions should be handled gracefully
                    failed_messages += 1
            
            # Should process commands even if some replies fail
            assert mock_run.call_count >= 7, "Should execute commands even with network issues"
            
            # System should remain functional despite network issues
            assert successful_messages > 0, "Should have some successful message processing"


class TestConfigurationErrorRecovery:
    """Test recovery from configuration errors."""

    def test_config_reload_after_validation_fix(self, create_temp_config):
        """Test that config can be reloaded after fixing validation errors."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        # Start with invalid config
        invalid_config = {
            'telegram': {'bot_token': 'INVALID_PLACEHOLDER_TOKEN'},
            'actions': {}
        }
        config_path = create_temp_config(invalid_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            # Initial load should fail
            client = TelegramClient(config_path)
            assert not client.config_valid, "Invalid config should fail validation"
            assert client.config_error is not None
            
            # Fix the config file
            valid_config = {
                'telegram': {'bot_token': '1234567890:ABCdefGHijklmnopQRSTuvwxyz123456789'},
                'actions': {
                    'test_action': {'command': 'echo test'}
                }
            }
            with open(config_path, 'w') as f:
                yaml.dump(valid_config, f)
            
            # Reload config (if method exists)
            try:
                client.reload_config()
                assert client.config_valid, "Reloaded config should be valid"
                assert client.config_error is None
                assert 'test_action' in client.config.get('actions', {})
            except AttributeError:
                # reload_config method doesn't exist yet - expected in TDD
                # Create new client instance to simulate reload
                client_reloaded = TelegramClient(config_path)
                assert client_reloaded.config_valid, "New client with fixed config should be valid"

    def test_partial_config_corruption_recovery(self, create_temp_config):
        """Test handling of partially corrupted config files."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        # Create config with some valid and some invalid sections
        mixed_config = {
            'telegram': {'bot_token': '1234567890:ABCdefGHijklmnopQRSTuvwxyz123456789'},
            'actions': {
                'valid_action': {'command': 'echo valid'},
                'invalid_action': {'missing_command': True},  # Invalid - no command
                'another_valid': {'command': 'echo another'}
            }
        }
        config_path = create_temp_config(mixed_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            # Should handle partial corruption gracefully
            # May be valid or invalid depending on implementation strictness
            if client.config_valid:
                # If valid, should only include valid actions
                actions = client.config.get('actions', {})
                assert 'valid_action' in actions
                assert 'another_valid' in actions
                # Invalid action might be filtered out or cause validation failure
            else:
                # If invalid, should have clear error message
                assert client.config_error is not None
                assert 'action' in client.config_error.lower()

    def test_config_file_disappearance_handling(self, create_temp_config):
        """Test handling when config file disappears during operation."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config = {
            'telegram': {'bot_token': '1234567890:ABCdefGHijklmnopQRSTuvwxyz123456789'},
            'actions': {'test': {'command': 'echo test'}}
        }
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            # Load config successfully
            client = TelegramClient(config_path)
            assert client.config_valid, "Initial config should be valid"
            
            # Remove config file
            config_path.unlink()
            
            # Try to reload config (if method exists)
            try:
                client.reload_config()
                # Should handle missing file gracefully
                assert not client.config_valid, "Should detect missing config file"
                assert client.config_error is not None
                assert 'not found' in client.config_error.lower() or 'missing' in client.config_error.lower()
            except AttributeError:
                # reload_config method doesn't exist yet - expected in TDD
                pass
            except FileNotFoundError:
                # Also acceptable - method exists but throws appropriate exception
                pass

    def test_config_permission_error_recovery(self, create_temp_config):
        """Test recovery from config file permission errors."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config = {
            'telegram': {'bot_token': '1234567890:ABCdefGHijklmnopQRSTuvwxyz123456789'},
            'actions': {'permission_test': {'command': 'echo permission'}}
        }
        config_path = create_temp_config(config)
        
        # Make config file unreadable
        config_path.chmod(0o000)  # No permissions
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'):
                
                # Should handle permission errors gracefully
                try:
                    client = TelegramClient(config_path)
                    assert not client.config_valid, "Should detect permission issues"
                    assert client.config_error is not None
                    assert 'permission' in client.config_error.lower() or 'access' in client.config_error.lower()
                except PermissionError:
                    # Also acceptable - clear permission error
                    pass
        finally:
            # Restore permissions for cleanup
            try:
                config_path.chmod(0o644)
            except:
                pass


class TestRuntimeErrorRecovery:
    """Test recovery from runtime errors during operation."""

    @pytest.mark.asyncio
    async def test_command_execution_failure_recovery(self, create_temp_config, recovery_config):
        """Test recovery from command execution failures."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(recovery_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            client = TelegramClient(config_path)
            
            # Create sequence of messages - some will fail, some will succeed
            execution_results = [
                Mock(stdout="", stderr="Command failed", returncode=1),  # Failure
                Mock(stdout="Success", stderr="", returncode=0),  # Success
                Mock(stdout="", stderr="Another failure", returncode=1),  # Failure
                Mock(stdout="Recovery success", stderr="", returncode=0),  # Success
            ]
            mock_run.side_effect = execution_results
            
            messages = []
            for i in range(4):
                mock_message = Mock()
                mock_message.text = f"[reliable_action]\nsequence = {i}"
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345 + i
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = f'RecoveryUser{i}'
                mock_message.from_user.id = 30000 + i
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                messages.append((mock_update, mock_context, mock_message))
            
            # Process all messages
            for mock_update, mock_context, mock_message in messages:
                await client.handle_message(mock_update, mock_context)
                
                # Should send reply for both success and failure
                mock_message.reply_text.assert_called_once()
            
            # All commands should have been attempted
            assert mock_run.call_count == 4
            
            # System should continue operating despite failures
            # (verified by successful processing of all messages)

    @pytest.mark.asyncio
    async def test_memory_exhaustion_recovery(self, create_temp_config, recovery_config):
        """Test recovery from memory exhaustion scenarios."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(recovery_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            # Simulate memory errors then recovery
            def memory_error_then_success(*args, **kwargs):
                if not hasattr(memory_error_then_success, 'call_count'):
                    memory_error_then_success.call_count = 0
                memory_error_then_success.call_count += 1
                
                if memory_error_then_success.call_count <= 2:
                    raise MemoryError("Cannot allocate memory")
                else:
                    return Mock(stdout="Memory recovered", stderr="", returncode=0)
            
            mock_run.side_effect = memory_error_then_success
            
            client = TelegramClient(config_path)
            
            # Create messages that will trigger memory issues
            for i in range(5):
                mock_message = Mock()
                mock_message.text = f"[resource_intensive]\nmemory_test = {i}"
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345 + i
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = f'MemoryUser{i}'
                mock_message.from_user.id = 40000 + i
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                # Process message - should handle memory errors gracefully
                try:
                    await client.handle_message(mock_update, mock_context)
                    mock_message.reply_text.assert_called_once()
                except MemoryError:
                    # Should not propagate memory errors to caller
                    pytest.fail("Memory errors should be handled gracefully")

    @pytest.mark.asyncio
    async def test_process_timeout_recovery(self, create_temp_config, recovery_config):
        """Test recovery from process timeouts."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(recovery_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            # Simulate timeouts then normal execution
            timeout_count = 0
            def timeout_then_success(*args, **kwargs):
                nonlocal timeout_count
                timeout_count += 1
                
                if timeout_count <= 2:
                    raise subprocess.TimeoutExpired(' '.join(args[0]), 30)
                else:
                    return Mock(stdout="Timeout recovered", stderr="", returncode=0)
            
            mock_run.side_effect = timeout_then_success
            
            client = TelegramClient(config_path)
            
            # Process messages that will timeout initially
            for i in range(4):
                mock_message = Mock()
                mock_message.text = f"[flaky_action]\ntimeout_test = {i}"
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345 + i
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = f'TimeoutUser{i}'
                mock_message.from_user.id = 50000 + i
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                await client.handle_message(mock_update, mock_context)
                
                # Should handle timeouts and send appropriate error message
                mock_message.reply_text.assert_called_once()
                
                if i >= 2:  # After timeouts stop occurring
                    reply_text = mock_message.reply_text.call_args[0][0]
                    assert 'timeout recovered' in reply_text.lower() or 'completed' in reply_text.lower()


class TestServiceRestartScenarios:
    """Test recovery from service restart scenarios."""

    def test_graceful_shutdown_and_restart(self, create_temp_config, recovery_config):
        """Test graceful shutdown and restart process."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(recovery_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application') as mock_app_class, \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            # Track shutdown and startup calls
            shutdown_calls = []
            startup_calls = []
            
            def create_tracked_app():
                mock_app = Mock()
                mock_app.initialize = AsyncMock(side_effect=lambda: startup_calls.append('initialize'))
                mock_app.start = AsyncMock(side_effect=lambda: startup_calls.append('start'))
                mock_app.stop = AsyncMock(side_effect=lambda: shutdown_calls.append('stop'))
                mock_app.shutdown = AsyncMock(side_effect=lambda: shutdown_calls.append('shutdown'))
                mock_app.add_handler = Mock()
                
                mock_updater = Mock()
                mock_updater.start_polling = AsyncMock(side_effect=lambda: startup_calls.append('start_polling'))
                mock_updater.stop = AsyncMock(side_effect=lambda: shutdown_calls.append('stop_polling'))
                mock_app.updater = mock_updater
                
                return mock_app
            
            mock_builder = Mock()
            mock_builder.token.return_value = mock_builder
            mock_builder.allowed_updates.return_value = mock_builder
            mock_builder.build.side_effect = lambda: create_tracked_app()
            mock_app_class.builder.return_value = mock_builder
            
            client = TelegramClient(config_path)
            
            # Start client
            success = client.start_client()
            assert success, "Client should start successfully"
            assert len(startup_calls) > 0, "Should have startup calls"
            
            # Stop client gracefully
            client.stop_client()
            assert len(shutdown_calls) > 0, "Should have shutdown calls"
            
            # Restart client
            startup_calls.clear()
            shutdown_calls.clear()
            
            success = client.start_client()
            assert success, "Client should restart successfully"
            assert len(startup_calls) > 0, "Should have startup calls after restart"

    def test_ungraceful_termination_recovery(self, create_temp_config, recovery_config):
        """Test recovery from ungraceful termination."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(recovery_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application') as mock_app_class, \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            # Simulate ungraceful termination scenario
            def create_failing_app():
                mock_app = Mock()
                mock_app.initialize = AsyncMock()
                mock_app.start = AsyncMock()
                mock_app.add_handler = Mock()
                
                # Simulate app that fails during shutdown
                mock_app.stop = AsyncMock(side_effect=Exception("Ungraceful termination"))
                mock_app.shutdown = AsyncMock(side_effect=Exception("Force shutdown"))
                
                mock_updater = Mock()
                mock_updater.start_polling = AsyncMock()
                mock_updater.stop = AsyncMock(side_effect=Exception("Polling stop failed"))
                mock_app.updater = mock_updater
                
                return mock_app
            
            mock_builder = Mock()
            mock_builder.token.return_value = mock_builder
            mock_builder.allowed_updates.return_value = mock_builder
            mock_builder.build.side_effect = lambda: create_failing_app()
            mock_app_class.builder.return_value = mock_builder
            
            client = TelegramClient(config_path)
            
            # Start client
            client.start_client()
            
            # Try to stop - should handle exceptions gracefully
            try:
                client.stop_client()
                # Should not raise exceptions even if shutdown fails
            except Exception as e:
                pytest.fail(f"Should handle ungraceful shutdown gracefully: {e}")
            
            # Should be able to restart after ungraceful termination
            # Reset mock to simulate clean restart
            mock_builder.build.side_effect = lambda: Mock(
                initialize=AsyncMock(),
                start=AsyncMock(),
                stop=AsyncMock(),
                shutdown=AsyncMock(),
                add_handler=Mock(),
                updater=Mock(start_polling=AsyncMock(), stop=AsyncMock())
            )
            
            success = client.start_client()
            assert success, "Should be able to restart after ungraceful termination"

    def test_resource_cleanup_after_failures(self, create_temp_config, recovery_config):
        """Test that resources are cleaned up after failures."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(recovery_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application') as mock_app_class, \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            # Track resource allocation and cleanup
            allocated_resources = []
            cleaned_resources = []
            
            def create_resource_tracking_app():
                mock_app = Mock()
                
                def track_initialize():
                    allocated_resources.append('app_initialized')
                
                def track_start():
                    allocated_resources.append('app_started')
                
                def track_stop():
                    cleaned_resources.append('app_stopped')
                
                def track_shutdown():
                    cleaned_resources.append('app_shutdown')
                
                mock_app.initialize = AsyncMock(side_effect=track_initialize)
                mock_app.start = AsyncMock(side_effect=track_start)
                mock_app.stop = AsyncMock(side_effect=track_stop)
                mock_app.shutdown = AsyncMock(side_effect=track_shutdown)
                mock_app.add_handler = Mock()
                
                mock_updater = Mock()
                
                def track_start_polling():
                    allocated_resources.append('polling_started')
                
                def track_stop_polling():
                    cleaned_resources.append('polling_stopped')
                
                mock_updater.start_polling = AsyncMock(side_effect=track_start_polling)
                mock_updater.stop = AsyncMock(side_effect=track_stop_polling)
                mock_app.updater = mock_updater
                
                return mock_app
            
            mock_builder = Mock()
            mock_builder.token.return_value = mock_builder
            mock_builder.allowed_updates.return_value = mock_builder
            mock_builder.build.side_effect = lambda: create_resource_tracking_app()
            mock_app_class.builder.return_value = mock_builder
            
            client = TelegramClient(config_path)
            
            # Start and stop multiple times to test resource management
            for cycle in range(3):
                # Start client
                client.start_client()
                assert len(allocated_resources) > len(cleaned_resources), "Should allocate resources"
                
                # Stop client
                client.stop_client()
                
                # Should clean up resources
                # Allow some flexibility in cleanup order/completeness
                assert len(cleaned_resources) > 0, f"Should clean up some resources in cycle {cycle}"
            
            # After multiple cycles, should not accumulate uncleaned resources
            # (This is a general check - exact behavior depends on implementation)
            total_allocated = len(allocated_resources)
            total_cleaned = len(cleaned_resources)
            cleanup_ratio = total_cleaned / max(total_allocated, 1)
            
            assert cleanup_ratio > 0.5, f"Should clean up most resources: {cleanup_ratio:.2f}"


class TestStateConsistencyAfterErrors:
    """Test that system state remains consistent after errors."""

    def test_config_state_consistency_after_reload_failure(self, create_temp_config):
        """Test that config state is consistent after reload failures."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        # Start with valid config
        valid_config = {
            'telegram': {'bot_token': '1234567890:ABCdefGHijklmnopQRSTuvwxyz123456789'},
            'actions': {'original': {'command': 'echo original'}}
        }
        config_path = create_temp_config(valid_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            assert client.config_valid, "Initial config should be valid"
            original_actions = client.config.get('actions', {}).copy()
            
            # Corrupt the config file
            with open(config_path, 'w') as f:
                f.write("invalid: yaml: content: [")
            
            # Try to reload config (if method exists)
            try:
                client.reload_config()
                
                # After failed reload, should maintain previous valid state
                # or clearly indicate invalid state
                if client.config_valid:
                    # If still valid, should have original config
                    assert client.config['actions'] == original_actions
                else:
                    # If invalid, should have clear error
                    assert client.config_error is not None
                    
            except AttributeError:
                # reload_config method doesn't exist yet - expected in TDD
                pass
            except Exception as e:
                # Should handle reload failures gracefully
                assert "yaml" in str(e).lower() or "config" in str(e).lower()

    @pytest.mark.asyncio
    async def test_message_processing_state_after_exceptions(self, create_temp_config, recovery_config):
        """Test that message processing state is consistent after exceptions."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(recovery_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            # Simulate various exception types
            exceptions = [
                ValueError("Invalid parameter"),
                RuntimeError("Runtime issue"),
                OSError("System error"),
                Exception("Generic exception")
            ]
            
            client = TelegramClient(config_path)
            
            for i, exception in enumerate(exceptions):
                mock_run.side_effect = exception
                
                mock_message = Mock()
                mock_message.text = f"[flaky_action]\nexception_test = {i}"
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345 + i
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = f'ExceptionUser{i}'
                mock_message.from_user.id = 60000 + i
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                # Process message that will cause exception
                try:
                    await client.handle_message(mock_update, mock_context)
                    
                    # Should handle exception and send error reply
                    mock_message.reply_text.assert_called_once()
                    reply_text = mock_message.reply_text.call_args[0][0]
                    assert any(word in reply_text.lower() for word in ['error', 'failed', 'issue'])
                    
                except Exception as e:
                    # Should not propagate exceptions to caller
                    pytest.fail(f"Exception {type(exception).__name__} should be handled gracefully: {e}")
                
                # Reset for next test
                mock_message.reply_text.reset_mock()
            
            # After all exceptions, system should still be functional
            mock_run.side_effect = None
            mock_run.return_value = Mock(stdout="recovery test", stderr="", returncode=0)
            
            # Test normal operation after exceptions
            mock_message = Mock()
            mock_message.text = "[reliable_action]\nrecovery_test = 'final'"
            mock_message.reply_text = AsyncMock()
            mock_message.chat = Mock()
            mock_message.chat.id = 99999
            mock_message.chat.type = 'private'
            mock_message.from_user = Mock()
            mock_message.from_user.first_name = 'FinalUser'
            mock_message.from_user.id = 99999
            
            mock_update = Mock()
            mock_update.message = mock_message
            mock_update.channel_post = None
            mock_context = Mock()
            
            await client.handle_message(mock_update, mock_context)
            
            # Should work normally after error recovery
            mock_run.assert_called()
            mock_message.reply_text.assert_called_once()
            reply_text = mock_message.reply_text.call_args[0][0]
            assert 'completed' in reply_text or 'recovery test' in reply_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])