#!/usr/bin/env python3
"""
Concurrent message processing test scenarios.

Tests the system's ability to handle multiple simultaneous messages from
different sources without race conditions, deadlocks, or resource conflicts.
These tests ensure the message processing pipeline is thread-safe and
performs well under concurrent load.

This test suite focuses on:
1. Concurrent processing of multiple regular messages
2. Concurrent processing of channel and regular messages  
3. Race condition detection in shared resources
4. Memory usage and resource cleanup under concurrent load
5. Rate limiting and throttling behavior
6. Deadlock prevention in async operations
"""

import asyncio
import tempfile
import yaml
import time
import random
import threading
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import pytest
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import gc
import weakref

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Mock rumps before any imports that might trigger it
sys.modules['rumps'] = Mock()


@pytest.fixture
def concurrent_config():
    """Create configuration optimized for concurrent testing."""
    return {
        'telegram': {
            'bot_token': 'concurrent_test_token_123',
            'channels': [-1002345, -1002346, -1002347, -1002348, -1002349]
        },
        'actions': {
            'fast_action': {
                'command': 'echo "fast"',
                'description': 'Fast action for testing'
            },
            'slow_action': {
                'command': 'sleep 1 && echo "slow"',
                'description': 'Slow action for testing'
            },
            'cpu_intensive': {
                'command': 'python -c "sum(range(10000))"',
                'description': 'CPU intensive action'
            },
            'io_intensive': {
                'command': 'cat /dev/null',
                'description': 'IO intensive action'
            },
            'memory_action': {
                'command': 'python -c "x = [0] * 1000000"',
                'description': 'Memory intensive action'
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
def mock_variable_delay_subprocess():
    """Mock subprocess with variable delays to simulate real-world conditions."""
    with patch('subprocess.run') as mock_run:
        def variable_delay_run(cmd, **kwargs):
            # Simulate variable execution times
            if 'fast' in ' '.join(cmd):
                time.sleep(0.01)  # Fast command
                return Mock(stdout="fast result", stderr="", returncode=0)
            elif 'slow' in ' '.join(cmd):
                time.sleep(0.5)  # Slow command
                return Mock(stdout="slow result", stderr="", returncode=0)
            elif 'cpu' in ' '.join(cmd):
                time.sleep(0.2)  # CPU intensive
                return Mock(stdout="cpu result", stderr="", returncode=0)
            elif 'memory' in ' '.join(cmd):
                time.sleep(0.1)  # Memory action
                return Mock(stdout="memory result", stderr="", returncode=0)
            else:
                time.sleep(0.05)  # Default delay
                return Mock(stdout="default result", stderr="", returncode=0)
        
        mock_run.side_effect = variable_delay_run
        yield mock_run


class TestBasicConcurrentProcessing:
    """Test basic concurrent message processing scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_regular_messages(self, create_temp_config, concurrent_config, mock_variable_delay_subprocess):
        """Test concurrent processing of multiple regular messages."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(concurrent_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            # Create multiple concurrent messages
            num_messages = 10
            messages = []
            
            for i in range(num_messages):
                mock_message = Mock()
                mock_message.text = f"[fast_action]\nid = {i}\nuser = 'user_{i}'"
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
                
                messages.append((mock_update, mock_context, mock_message))
            
            # Process all messages concurrently
            start_time = time.time()
            tasks = [client.handle_message(update, context) for update, context, _ in messages]
            await asyncio.gather(*tasks)
            total_time = time.time() - start_time
            
            # Verify all messages were processed
            assert mock_variable_delay_subprocess.call_count == num_messages
            
            # Verify all replies were sent
            for _, _, mock_message in messages:
                mock_message.reply_text.assert_called_once()
            
            # Concurrent processing should be faster than sequential
            # With 10 messages * 0.01s each = 0.1s sequential, concurrent should be much faster
            assert total_time < 2.0, f"Concurrent processing took {total_time:.2f}s, too slow"
            
            # Should complete in roughly the time of the slowest operation plus overhead
            assert total_time < 0.5, f"Should benefit from concurrency: {total_time:.2f}s"

    @pytest.mark.asyncio
    async def test_concurrent_channel_and_regular_messages(self, create_temp_config, concurrent_config, mock_variable_delay_subprocess):
        """Test concurrent processing of mixed channel and regular messages."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(concurrent_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            messages = []
            
            # Create mix of regular messages and channel posts
            for i in range(15):
                if i % 3 == 0:  # Every 3rd message is a channel post
                    mock_channel_post = Mock()
                    mock_channel_post.text = f"[slow_action]\nchannel_id = {i}"
                    mock_channel_post.reply_text = AsyncMock()
                    mock_channel_post.chat = Mock()
                    mock_channel_post.chat.id = -1002345  # Allowed channel
                    mock_channel_post.chat.type = 'channel'
                    mock_channel_post.from_user = Mock()
                    mock_channel_post.from_user.first_name = f'ChannelBot{i}'
                    mock_channel_post.from_user.id = f'bot_{i}'
                    
                    mock_update = Mock()
                    mock_update.message = None
                    mock_update.channel_post = mock_channel_post
                    mock_context = Mock()
                    
                    messages.append((mock_update, mock_context, mock_channel_post))
                else:  # Regular messages
                    mock_message = Mock()
                    mock_message.text = f"[fast_action]\nuser_id = {i}"
                    mock_message.reply_text = AsyncMock()
                    mock_message.chat = Mock()
                    mock_message.chat.id = 12345 + i
                    mock_message.chat.type = 'private'
                    mock_message.from_user = Mock()
                    mock_message.from_user.first_name = f'User{i}'
                    mock_message.from_user.id = 200000 + i
                    
                    mock_update = Mock()
                    mock_update.message = mock_message
                    mock_update.channel_post = None
                    mock_context = Mock()
                    
                    messages.append((mock_update, mock_context, mock_message))
            
            # Process mixed messages concurrently
            start_time = time.time()
            tasks = [client.handle_message(update, context) for update, context, _ in messages]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            total_time = time.time() - start_time
            
            # Check for any exceptions
            exceptions = [r for r in results if isinstance(r, Exception)]
            assert len(exceptions) == 0, f"Got exceptions: {exceptions}"
            
            # Verify processing
            assert mock_variable_delay_subprocess.call_count == len(messages)
            
            # All messages should get replies
            for _, _, mock_message in messages:
                mock_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_different_action_types(self, create_temp_config, concurrent_config, mock_variable_delay_subprocess):
        """Test concurrent processing of different action types.""" 
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(concurrent_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            # Create messages with different action types
            action_types = ['fast_action', 'slow_action', 'cpu_intensive', 'io_intensive', 'memory_action']
            messages = []
            
            # Create 5 messages for each action type
            for action_type in action_types:
                for i in range(5):
                    mock_message = Mock()
                    mock_message.text = f"[{action_type}]\niteration = {i}"
                    mock_message.reply_text = AsyncMock()
                    mock_message.chat = Mock()
                    mock_message.chat.id = 12345 + i
                    mock_message.chat.type = 'private'
                    mock_message.from_user = Mock()
                    mock_message.from_user.first_name = f'User{action_type}{i}'
                    mock_message.from_user.id = 300000 + i
                    
                    mock_update = Mock()
                    mock_update.message = mock_message
                    mock_update.channel_post = None
                    mock_context = Mock()
                    
                    messages.append((mock_update, mock_context, mock_message, action_type))
            
            # Shuffle to test random order processing
            random.shuffle(messages)
            
            # Process all action types concurrently
            start_time = time.time()
            tasks = [client.handle_message(update, context) for update, context, _, _ in messages]
            await asyncio.gather(*tasks)
            total_time = time.time() - start_time
            
            # Verify all actions were processed
            assert mock_variable_delay_subprocess.call_count == len(messages)
            
            # Group replies by action type to verify they all completed
            for _, _, mock_message, action_type in messages:
                mock_message.reply_text.assert_called_once()
                reply_text = mock_message.reply_text.call_args[0][0]
                assert action_type in reply_text or 'completed' in reply_text

    @pytest.mark.asyncio
    async def test_concurrent_built_in_and_custom_actions(self, create_temp_config, concurrent_config):
        """Test concurrent processing of built-in and custom actions."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(concurrent_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('local_orchestrator_tray.telegram_client.rumps') as mock_rumps, \
                patch('subprocess.run') as mock_run:
            
            mock_run.return_value = Mock(stdout="custom action output", stderr="", returncode=0)
            
            client = TelegramClient(config_path)
            
            messages = []
            
            # Mix of built-in and custom actions
            for i in range(10):
                if i % 2 == 0:  # Built-in action
                    mock_message = Mock()
                    mock_message.text = f"""
[Notification]
message = "Concurrent notification {i}"
title = "Test {i}"
"""
                    mock_message.reply_text = AsyncMock()
                    mock_message.chat = Mock()
                    mock_message.chat.id = 12345 + i
                    mock_message.chat.type = 'private'
                    mock_message.from_user = Mock()
                    mock_message.from_user.first_name = f'NotifyUser{i}'
                    mock_message.from_user.id = 400000 + i
                    
                    mock_update = Mock()
                    mock_update.message = mock_message
                    mock_update.channel_post = None
                    mock_context = Mock()
                    
                    messages.append((mock_update, mock_context, mock_message, 'builtin'))
                else:  # Custom action
                    mock_message = Mock()
                    mock_message.text = f"[fast_action]\ncustom_param = {i}"
                    mock_message.reply_text = AsyncMock()
                    mock_message.chat = Mock()
                    mock_message.chat.id = 12345 + i
                    mock_message.chat.type = 'private'
                    mock_message.from_user = Mock()
                    mock_message.from_user.first_name = f'CustomUser{i}'
                    mock_message.from_user.id = 500000 + i
                    
                    mock_update = Mock()
                    mock_update.message = mock_message
                    mock_update.channel_post = None
                    mock_context = Mock()
                    
                    messages.append((mock_update, mock_context, mock_message, 'custom'))
            
            # Process mixed action types concurrently
            tasks = [client.handle_message(update, context) for update, context, _, _ in messages]
            await asyncio.gather(*tasks)
            
            # Verify built-in actions executed
            builtin_count = len([msg for msg in messages if msg[3] == 'builtin'])
            assert mock_rumps.notification.call_count == builtin_count
            
            # Verify custom actions executed
            custom_count = len([msg for msg in messages if msg[3] == 'custom'])
            assert mock_run.call_count == custom_count
            
            # All messages should get replies
            for _, _, mock_message, _ in messages:
                mock_message.reply_text.assert_called_once()


class TestConcurrentErrorHandling:
    """Test error handling under concurrent load."""

    @pytest.mark.asyncio
    async def test_concurrent_command_failures(self, create_temp_config, concurrent_config):
        """Test handling of concurrent command failures."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(concurrent_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            # Simulate random failures
            def random_failure_run(cmd, **kwargs):
                if random.random() < 0.3:  # 30% failure rate
                    return Mock(stdout="", stderr="Random failure", returncode=1)
                else:
                    return Mock(stdout="Success", stderr="", returncode=0)
            
            mock_run.side_effect = random_failure_run
            
            client = TelegramClient(config_path)
            
            # Create many concurrent messages
            messages = []
            for i in range(20):
                mock_message = Mock()
                mock_message.text = f"[fast_action]\ntest_id = {i}"
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345 + i
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = f'TestUser{i}'
                mock_message.from_user.id = 600000 + i
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                messages.append((mock_update, mock_context, mock_message))
            
            # Process with expected failures
            tasks = [client.handle_message(update, context) for update, context, _ in messages]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Should handle failures gracefully - no exceptions should propagate
            exceptions = [r for r in results if isinstance(r, Exception)]
            assert len(exceptions) == 0, f"Failures should be handled gracefully: {exceptions}"
            
            # All messages should still get replies (success or error)
            for _, _, mock_message in messages:
                mock_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_timeout_handling(self, create_temp_config, concurrent_config):
        """Test handling of concurrent timeouts."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(concurrent_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            # Simulate timeouts
            def timeout_run(cmd, **kwargs):
                import subprocess
                if random.random() < 0.2:  # 20% timeout rate
                    raise subprocess.TimeoutExpired(' '.join(cmd), 30)
                else:
                    return Mock(stdout="No timeout", stderr="", returncode=0)
            
            mock_run.side_effect = timeout_run
            
            client = TelegramClient(config_path)
            
            # Create concurrent messages that might timeout
            messages = []
            for i in range(15):
                mock_message = Mock()
                mock_message.text = f"[slow_action]\ntimeout_test = {i}"
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345 + i
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = f'TimeoutUser{i}'
                mock_message.from_user.id = 700000 + i
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                messages.append((mock_update, mock_context, mock_message))
            
            # Process with expected timeouts
            tasks = [client.handle_message(update, context) for update, context, _ in messages]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Timeouts should be handled gracefully
            exceptions = [r for r in results if isinstance(r, Exception)]
            assert len(exceptions) == 0, f"Timeouts should be handled gracefully: {exceptions}"
            
            # All messages should get timeout error replies
            for _, _, mock_message in messages:
                mock_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_unknown_actions(self, create_temp_config, concurrent_config):
        """Test handling of concurrent unknown action requests."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(concurrent_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            # Create messages with unknown actions
            unknown_actions = ['nonexistent', 'invalid_action', 'missing_cmd', 'not_found', 'bad_action']
            messages = []
            
            for i, action in enumerate(unknown_actions * 3):  # 15 total messages
                mock_message = Mock()
                mock_message.text = f"[{action}]\ntest_param = {i}"
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345 + i
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = f'UnknownUser{i}'
                mock_message.from_user.id = 800000 + i
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                messages.append((mock_update, mock_context, mock_message, action))
            
            # Process unknown actions concurrently
            tasks = [client.handle_message(update, context) for update, context, _, _ in messages]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Should handle unknown actions gracefully
            exceptions = [r for r in results if isinstance(r, Exception)]
            assert len(exceptions) == 0, f"Unknown actions should be handled gracefully: {exceptions}"
            
            # All should get "not found" error replies
            for _, _, mock_message, action in messages:
                mock_message.reply_text.assert_called_once()
                reply_text = mock_message.reply_text.call_args[0][0].lower()
                assert 'not found' in reply_text or 'unknown' in reply_text


class TestConcurrentResourceManagement:
    """Test resource management under concurrent load."""

    @pytest.mark.asyncio
    async def test_concurrent_memory_usage(self, create_temp_config, concurrent_config, mock_variable_delay_subprocess):
        """Test memory usage remains stable under concurrent load."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(concurrent_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            # Track memory references
            message_refs = []
            
            def create_message_batch(batch_id, batch_size=20):
                """Create a batch of messages and return weak references."""
                messages = []
                for i in range(batch_size):
                    mock_message = Mock()
                    mock_message.text = f"[memory_action]\nbatch = {batch_id}\nid = {i}"
                    mock_message.reply_text = AsyncMock()
                    mock_message.chat = Mock()
                    mock_message.chat.id = 12345 + i
                    mock_message.chat.type = 'private'
                    mock_message.from_user = Mock()
                    mock_message.from_user.first_name = f'MemUser{batch_id}_{i}'
                    mock_message.from_user.id = 900000 + i
                    
                    mock_update = Mock()
                    mock_update.message = mock_message
                    mock_update.channel_post = None
                    mock_context = Mock()
                    
                    messages.append((mock_update, mock_context, mock_message))
                    message_refs.append(weakref.ref(mock_message))
                
                return messages
            
            # Process multiple batches
            for batch_id in range(3):
                messages = create_message_batch(batch_id)
                
                # Process batch concurrently
                tasks = [client.handle_message(update, context) for update, context, _ in messages]
                await asyncio.gather(*tasks)
                
                # Force garbage collection
                del messages
                gc.collect()
            
            # Check that message objects were cleaned up
            gc.collect()
            time.sleep(0.1)  # Allow cleanup
            
            # Most weak references should be dead (objects cleaned up)
            dead_refs = sum(1 for ref in message_refs if ref() is None)
            total_refs = len(message_refs)
            cleanup_ratio = dead_refs / total_refs
            
            # At least 80% of objects should be cleaned up
            assert cleanup_ratio > 0.8, f"Memory cleanup ratio too low: {cleanup_ratio:.2f}"

    @pytest.mark.asyncio
    async def test_concurrent_file_handle_management(self, create_temp_config, concurrent_config):
        """Test that file handles are managed properly under concurrent load."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(concurrent_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            # Track file operations
            file_operations = []
            original_run = mock_run
            
            def track_file_run(cmd, **kwargs):
                file_operations.append(f"run_{len(file_operations)}")
                return Mock(stdout=f"file_op_{len(file_operations)}", stderr="", returncode=0)
            
            mock_run.side_effect = track_file_run
            
            client = TelegramClient(config_path)
            
            # Create many concurrent messages that would open files/processes
            messages = []
            for i in range(50):  # Many concurrent operations
                mock_message = Mock()
                mock_message.text = f"[io_intensive]\nfile_op = {i}"
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345 + i
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = f'FileUser{i}'
                mock_message.from_user.id = 1000000 + i
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                messages.append((mock_update, mock_context, mock_message))
            
            # Process all file operations concurrently
            tasks = [client.handle_message(update, context) for update, context, _ in messages]
            await asyncio.gather(*tasks)
            
            # All file operations should complete successfully
            assert len(file_operations) == len(messages)
            
            # All messages should get replies
            for _, _, mock_message in messages:
                mock_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_rate_limiting_behavior(self, create_temp_config, concurrent_config, mock_variable_delay_subprocess):
        """Test system behavior under high concurrent load (rate limiting scenarios)."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(concurrent_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            # Create burst of messages to test rate limiting
            burst_size = 100
            messages = []
            
            for i in range(burst_size):
                mock_message = Mock()
                mock_message.text = f"[fast_action]\nburst_id = {i}"
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345 + i
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = f'BurstUser{i}'
                mock_message.from_user.id = 1100000 + i
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                messages.append((mock_update, mock_context, mock_message))
            
            # Process burst load
            start_time = time.time()
            tasks = [client.handle_message(update, context) for update, context, _ in messages]
            await asyncio.gather(*tasks)
            total_time = time.time() - start_time
            
            # System should handle burst gracefully
            assert mock_variable_delay_subprocess.call_count == burst_size
            
            # All messages should be processed (may be rate limited but not dropped)
            for _, _, mock_message in messages:
                mock_message.reply_text.assert_called_once()
            
            # Should complete within reasonable time even under burst load
            assert total_time < 10.0, f"Burst processing took {total_time:.2f}s, too slow"


class TestConcurrentChannelFiltering:
    """Test channel filtering behavior under concurrent load."""

    @pytest.mark.asyncio
    async def test_concurrent_channel_filtering_consistency(self, create_temp_config, concurrent_config, mock_variable_delay_subprocess):
        """Test that channel filtering remains consistent under concurrent load."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(concurrent_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            # Create mix of allowed and blocked channel messages
            allowed_channels = [-1002345, -1002346, -1002347]
            blocked_channels = [-1002999, -1003000, -1003001]
            
            messages = []
            expected_processed = 0
            
            for i in range(30):
                if i % 2 == 0:  # Allowed channel
                    channel_id = random.choice(allowed_channels)
                    expected_processed += 1
                    should_process = True
                else:  # Blocked channel
                    channel_id = random.choice(blocked_channels)
                    should_process = False
                
                mock_channel_post = Mock()
                mock_channel_post.text = f"[fast_action]\nconcurrent_test = {i}"
                mock_channel_post.reply_text = AsyncMock()
                mock_channel_post.chat = Mock()
                mock_channel_post.chat.id = channel_id
                mock_channel_post.chat.type = 'channel'
                mock_channel_post.from_user = Mock()
                mock_channel_post.from_user.first_name = f'ChanBot{i}'
                mock_channel_post.from_user.id = f'bot_{i}'
                
                mock_update = Mock()
                mock_update.message = None
                mock_update.channel_post = mock_channel_post
                mock_context = Mock()
                
                messages.append((mock_update, mock_context, mock_channel_post, should_process))
            
            # Process all channel messages concurrently
            tasks = [client.handle_message(update, context) for update, context, _, _ in messages]
            await asyncio.gather(*tasks)
            
            # Verify filtering was applied consistently
            assert mock_variable_delay_subprocess.call_count == expected_processed
            
            # Verify only allowed channels got replies
            processed_count = 0
            for _, _, mock_channel_post, should_process in messages:
                if should_process:
                    mock_channel_post.reply_text.assert_called_once()
                    processed_count += 1
                else:
                    mock_channel_post.reply_text.assert_not_called()
            
            assert processed_count == expected_processed

    @pytest.mark.asyncio
    async def test_concurrent_mixed_channel_and_regular_filtering(self, create_temp_config, concurrent_config, mock_variable_delay_subprocess):
        """Test filtering of mixed message types under concurrent load."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(concurrent_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            client = TelegramClient(config_path)
            
            messages = []
            expected_processed = 0
            
            for i in range(40):
                if i % 3 == 0:  # Regular message (always processed)
                    mock_message = Mock()
                    mock_message.text = f"[fast_action]\nregular_msg = {i}"
                    mock_message.reply_text = AsyncMock()
                    mock_message.chat = Mock()
                    mock_message.chat.id = 12345 + i
                    mock_message.chat.type = 'private'
                    mock_message.from_user = Mock()
                    mock_message.from_user.first_name = f'RegUser{i}'
                    mock_message.from_user.id = 1200000 + i
                    
                    mock_update = Mock()
                    mock_update.message = mock_message
                    mock_update.channel_post = None
                    
                    messages.append((mock_update, Mock(), mock_message, True))
                    expected_processed += 1
                    
                elif i % 3 == 1:  # Allowed channel message
                    mock_channel_post = Mock()
                    mock_channel_post.text = f"[fast_action]\nallowed_chan = {i}"
                    mock_channel_post.reply_text = AsyncMock()
                    mock_channel_post.chat = Mock()
                    mock_channel_post.chat.id = -1002345  # Allowed
                    mock_channel_post.chat.type = 'channel'
                    mock_channel_post.from_user = Mock()
                    mock_channel_post.from_user.first_name = f'AllowedBot{i}'
                    mock_channel_post.from_user.id = f'allowed_bot_{i}'
                    
                    mock_update = Mock()
                    mock_update.message = None
                    mock_update.channel_post = mock_channel_post
                    
                    messages.append((mock_update, Mock(), mock_channel_post, True))
                    expected_processed += 1
                    
                else:  # Blocked channel message
                    mock_channel_post = Mock()
                    mock_channel_post.text = f"[fast_action]\nblocked_chan = {i}"
                    mock_channel_post.reply_text = AsyncMock()
                    mock_channel_post.chat = Mock()
                    mock_channel_post.chat.id = -1002999  # Blocked
                    mock_channel_post.chat.type = 'channel'
                    mock_channel_post.from_user = Mock()
                    mock_channel_post.from_user.first_name = f'BlockedBot{i}'
                    mock_channel_post.from_user.id = f'blocked_bot_{i}'
                    
                    mock_update = Mock()
                    mock_update.message = None
                    mock_update.channel_post = mock_channel_post
                    
                    messages.append((mock_update, Mock(), mock_channel_post, False))
            
            # Process all mixed message types concurrently
            tasks = [client.handle_message(update, context) for update, context, _, _ in messages]
            await asyncio.gather(*tasks)
            
            # Verify consistent filtering behavior
            assert mock_variable_delay_subprocess.call_count == expected_processed
            
            # Verify replies match filtering expectations
            for _, _, mock_message, should_process in messages:
                if should_process:
                    mock_message.reply_text.assert_called_once()
                else:
                    mock_message.reply_text.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])