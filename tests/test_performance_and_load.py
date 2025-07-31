#!/usr/bin/env python3
"""
Performance and load tests.

Tests the system's performance characteristics under various load conditions
to ensure it can handle real-world usage scenarios without degradation.
These tests help identify performance bottlenecks and resource constraints.

This test suite focuses on:
1. Response time under normal and high load
2. Memory usage patterns and potential leaks
3. CPU utilization during intensive operations
4. Scalability with large configurations
5. Throughput measurements
6. Resource cleanup efficiency
7. Performance regression detection
"""

import asyncio
import tempfile
import yaml
import time
import threading
import gc
import resource
import statistics
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import pytest
import sys
import subprocess
import psutil
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import weakref

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Mock rumps before any imports that might trigger it
sys.modules['rumps'] = Mock()


@pytest.fixture
def performance_config():
    """Create configuration optimized for performance testing."""
    return {
        'telegram': {
            'bot_token': 'perf_test_token_123456789',
            'channels': list(range(-1002345, -1002295))  # 50 channels
        },
        'actions': {
            f'perf_action_{i}': {
                'command': f'echo "performance test {i}"',
                'description': f'Performance test action {i}',
                'working_dir': '/tmp'
            }
            for i in range(100)  # 100 actions
        }
    }


@pytest.fixture
def large_config():
    """Create large configuration for scalability testing."""
    return {
        'telegram': {
            'bot_token': 'large_config_token_987654321',
            'channels': list(range(-1003000, -1002000))  # 1000 channels
        },
        'actions': {
            f'action_{i:04d}': {
                'command': f'python -c "print(\'Action {i} executed\')"',
                'description': f'Large config test action {i}',
                'working_dir': f'/tmp/action_{i % 10}',
                'timeout': 30,
                'retry_count': 3
            }
            for i in range(500)  # 500 actions
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


def measure_memory_usage():
    """Measure current memory usage of the process."""
    try:
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024  # MB
    except:
        # Fallback if psutil not available
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # MB on Linux


def measure_cpu_usage():
    """Measure current CPU usage percentage."""
    try:
        process = psutil.Process(os.getpid())
        return process.cpu_percent(interval=0.1)
    except:
        return 0.0  # Fallback


class TestResponseTimePerformance:
    """Test response time performance under various conditions."""

    @pytest.mark.asyncio
    async def test_single_message_response_time(self, create_temp_config, performance_config):
        """Test response time for single message processing."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(performance_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            mock_run.return_value = Mock(stdout="fast response", stderr="", returncode=0)
            
            client = TelegramClient(config_path)
            
            # Measure response times for single messages
            response_times = []
            
            for i in range(20):
                mock_message = Mock()
                mock_message.text = f"[perf_action_0]\ntest_id = {i}"
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345 + i
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = f'PerfUser{i}'
                mock_message.from_user.id = 100000 + i
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                # Measure response time
                start_time = time.time()
                await client.handle_message(mock_update, mock_context)
                response_time = time.time() - start_time
                
                response_times.append(response_time)
                
                # Verify message was processed
                mock_message.reply_text.assert_called_once()
                mock_message.reply_text.reset_mock()
            
            # Analyze response times
            avg_response_time = statistics.mean(response_times)
            median_response_time = statistics.median(response_times)
            max_response_time = max(response_times)
            
            # Performance assertions
            assert avg_response_time < 0.1, f"Average response time too slow: {avg_response_time:.3f}s"
            assert median_response_time < 0.05, f"Median response time too slow: {median_response_time:.3f}s"
            assert max_response_time < 0.5, f"Max response time too slow: {max_response_time:.3f}s"
            
            # Response times should be consistent (low variance)
            if len(response_times) > 1:
                response_variance = statistics.variance(response_times)
                assert response_variance < 0.01, f"Response time variance too high: {response_variance:.3f}"

    @pytest.mark.asyncio
    async def test_bulk_message_processing_performance(self, create_temp_config, performance_config):
        """Test performance when processing multiple messages in bulk."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(performance_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            mock_run.return_value = Mock(stdout="bulk response", stderr="", returncode=0)
            
            client = TelegramClient(config_path)
            
            # Create bulk messages
            num_messages = 100
            messages = []
            
            for i in range(num_messages):
                mock_message = Mock()
                mock_message.text = f"[perf_action_{i % 10}]\nbulk_id = {i}"
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 20000 + i
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = f'BulkUser{i}'
                mock_message.from_user.id = 200000 + i
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                messages.append((mock_update, mock_context, mock_message))
            
            # Measure bulk processing performance
            start_time = time.time()
            initial_memory = measure_memory_usage()
            
            # Process all messages concurrently
            tasks = [client.handle_message(update, context) for update, context, _ in messages]
            await asyncio.gather(*tasks)
            
            total_time = time.time() - start_time
            final_memory = measure_memory_usage()
            memory_increase = final_memory - initial_memory
            
            # Performance assertions
            throughput = num_messages / total_time
            assert throughput > 50, f"Throughput too low: {throughput:.1f} messages/second"
            assert total_time < 5.0, f"Bulk processing too slow: {total_time:.2f}s"
            
            # Memory usage should be reasonable
            assert memory_increase < 50, f"Memory increase too high: {memory_increase:.2f}MB"
            
            # All messages should be processed
            assert mock_run.call_count == num_messages
            for _, _, mock_message in messages:
                mock_message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_channel_filtering_performance(self, create_temp_config, performance_config):
        """Test performance of channel filtering with many channels."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(performance_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            mock_run.return_value = Mock(stdout="channel filter test", stderr="", returncode=0)
            
            client = TelegramClient(config_path)
            
            # Test filtering performance with allowed and blocked channels
            allowed_channels = list(range(-1002345, -1002295))  # From config
            blocked_channels = list(range(-1003000, -1002950))  # Not in config
            
            filtering_times = []
            
            # Test with allowed channels (should be processed)
            for i, channel_id in enumerate(allowed_channels[:20]):
                mock_channel_post = Mock()
                mock_channel_post.text = f"[perf_action_0]\nchannel_test = {i}"
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
                
                # Measure filtering time
                start_time = time.time()
                await client.handle_message(mock_update, mock_context)
                filtering_time = time.time() - start_time
                
                filtering_times.append(filtering_time)
                mock_channel_post.reply_text.assert_called_once()
            
            # Test with blocked channels (should be filtered out quickly)
            for i, channel_id in enumerate(blocked_channels[:20]):
                mock_channel_post = Mock()
                mock_channel_post.text = f"[perf_action_0]\nblocked_test = {i}"
                mock_channel_post.reply_text = AsyncMock()
                mock_channel_post.chat = Mock()
                mock_channel_post.chat.id = channel_id
                mock_channel_post.chat.type = 'channel'
                mock_channel_post.from_user = Mock()
                mock_channel_post.from_user.first_name = f'BlockedBot{i}'
                mock_channel_post.from_user.id = f'blocked_bot_{i}'
                
                mock_update = Mock()
                mock_update.message = None
                mock_update.channel_post = mock_channel_post
                mock_context = Mock()
                
                # Measure filtering time (should be very fast)
                start_time = time.time()
                await client.handle_message(mock_update, mock_context)
                filtering_time = time.time() - start_time
                
                filtering_times.append(filtering_time)
                # Blocked channels should not get replies
                mock_channel_post.reply_text.assert_not_called()
            
            # Channel filtering should be very fast
            avg_filtering_time = statistics.mean(filtering_times)
            max_filtering_time = max(filtering_times)
            
            assert avg_filtering_time < 0.02, f"Channel filtering too slow: {avg_filtering_time:.3f}s"
            assert max_filtering_time < 0.1, f"Max filtering time too slow: {max_filtering_time:.3f}s"

    def test_config_loading_performance(self, create_temp_config, large_config):
        """Test performance of loading large configurations."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(large_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            # Measure config loading performance
            loading_times = []
            memory_usages = []
            
            for i in range(5):  # Test multiple loads
                initial_memory = measure_memory_usage()
                
                start_time = time.time()
                client = TelegramClient(config_path)
                loading_time = time.time() - start_time
                
                final_memory = measure_memory_usage()
                memory_usage = final_memory - initial_memory
                
                loading_times.append(loading_time)
                memory_usages.append(memory_usage)
                
                # Verify config was loaded correctly
                assert client.config_valid, f"Large config should be valid (attempt {i+1})"
                assert len(client.config['actions']) == 500
                assert len(client.config['telegram']['channels']) == 1000
                
                # Force cleanup for next iteration
                del client
                gc.collect()
            
            # Performance assertions
            avg_loading_time = statistics.mean(loading_times)
            max_loading_time = max(loading_times)
            avg_memory_usage = statistics.mean(memory_usages)
            
            assert avg_loading_time < 2.0, f"Config loading too slow: {avg_loading_time:.2f}s"
            assert max_loading_time < 5.0, f"Max loading time too slow: {max_loading_time:.2f}s"
            assert avg_memory_usage < 100, f"Memory usage too high: {avg_memory_usage:.2f}MB"


class TestMemoryUsagePerformance:
    """Test memory usage characteristics and potential leaks."""

    @pytest.mark.asyncio
    async def test_memory_usage_under_sustained_load(self, create_temp_config, performance_config):
        """Test memory usage during sustained message processing."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(performance_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            mock_run.return_value = Mock(stdout="memory test", stderr="", returncode=0)
            
            client = TelegramClient(config_path)
            
            # Track memory usage over time
            memory_measurements = []
            initial_memory = measure_memory_usage()
            memory_measurements.append(initial_memory)
            
            # Process messages in batches to simulate sustained load
            batch_size = 50
            num_batches = 10
            
            for batch in range(num_batches):
                # Process batch of messages
                for i in range(batch_size):
                    msg_id = batch * batch_size + i
                    
                    mock_message = Mock()
                    mock_message.text = f"[perf_action_{i % 10}]\nmemory_test = {msg_id}"
                    mock_message.reply_text = AsyncMock()
                    mock_message.chat = Mock()
                    mock_message.chat.id = 30000 + msg_id
                    mock_message.chat.type = 'private'
                    mock_message.from_user = Mock()
                    mock_message.from_user.first_name = f'MemUser{msg_id}'
                    mock_message.from_user.id = 300000 + msg_id
                    
                    mock_update = Mock()
                    mock_update.message = mock_message
                    mock_update.channel_post = None
                    mock_context = Mock()
                    
                    await client.handle_message(mock_update, mock_context)
                
                # Measure memory after each batch
                gc.collect()  # Force garbage collection
                current_memory = measure_memory_usage()
                memory_measurements.append(current_memory)
                
                # Small delay to simulate realistic timing
                await asyncio.sleep(0.01)
            
            # Analyze memory usage patterns
            final_memory = memory_measurements[-1]
            memory_growth = final_memory - initial_memory
            max_memory = max(memory_measurements)
            
            # Memory assertions
            assert memory_growth < 50, f"Memory growth too high: {memory_growth:.2f}MB"
            assert max_memory - initial_memory < 100, f"Peak memory usage too high: {max_memory - initial_memory:.2f}MB"
            
            # Check for memory leaks (memory should stabilize)
            if len(memory_measurements) >= 5:
                recent_measurements = memory_measurements[-5:]
                memory_variance = statistics.variance(recent_measurements)
                assert memory_variance < 25, f"Memory usage not stable (possible leak): variance {memory_variance:.2f}"

    def test_memory_cleanup_after_client_shutdown(self, create_temp_config, performance_config):
        """Test that memory is properly cleaned up after client shutdown."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(performance_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            initial_memory = measure_memory_usage()
            memory_after_startup = []
            memory_after_shutdown = []
            
            # Test multiple startup/shutdown cycles
            for cycle in range(3):
                # Create and start client
                client = TelegramClient(config_path)
                client.start_client()
                
                # Measure memory after startup
                gc.collect()
                startup_memory = measure_memory_usage()
                memory_after_startup.append(startup_memory)
                
                # Stop and cleanup client
                client.stop_client()
                del client
                
                # Force cleanup
                gc.collect()
                shutdown_memory = measure_memory_usage()
                memory_after_shutdown.append(shutdown_memory)
                
                # Brief pause between cycles
                time.sleep(0.1)
            
            # Analyze memory cleanup
            avg_startup_memory = statistics.mean(memory_after_startup)
            avg_shutdown_memory = statistics.mean(memory_after_shutdown)
            final_memory = memory_after_shutdown[-1]
            
            # Memory should be cleaned up after shutdown
            cleanup_efficiency = (avg_startup_memory - avg_shutdown_memory) / max(avg_startup_memory - initial_memory, 1)
            memory_accumulation = final_memory - initial_memory
            
            assert cleanup_efficiency > 0.7, f"Memory cleanup efficiency too low: {cleanup_efficiency:.2f}"
            assert memory_accumulation < 20, f"Memory accumulation after cycles: {memory_accumulation:.2f}MB"

    async def test_large_message_memory_handling(self, create_temp_config, performance_config):
        """Test memory handling with large message content."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(performance_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            # Mock large output
            large_output = "Large output data: " + "x" * 100000  # ~100KB output
            mock_run.return_value = Mock(stdout=large_output, stderr="", returncode=0)
            
            client = TelegramClient(config_path)
            
            initial_memory = measure_memory_usage()
            
            # Process messages with large content
            for i in range(10):
                # Create message with large TOML content
                large_toml = f"[perf_action_0]\n" + "\n".join([
                    f"param_{j} = \"{'x' * 1000}\""  # Large parameter values
                    for j in range(50)  # 50 large parameters
                ])
                
                mock_message = Mock()
                mock_message.text = large_toml
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 40000 + i
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = f'LargeUser{i}'
                mock_message.from_user.id = 400000 + i
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                # Process large message
                await client.handle_message(mock_update, mock_context)
                
                # Verify processing succeeded
                mock_message.reply_text.assert_called_once()
                mock_message.reply_text.reset_mock()
            
            # Check memory usage after processing large messages
            gc.collect()
            final_memory = measure_memory_usage()
            memory_increase = final_memory - initial_memory
            
            # Should handle large messages without excessive memory usage
            assert memory_increase < 100, f"Memory increase too high for large messages: {memory_increase:.2f}MB"


class TestCPUUsagePerformance:
    """Test CPU usage characteristics."""

    @pytest.mark.asyncio
    async def test_cpu_usage_during_intensive_processing(self, create_temp_config, performance_config):
        """Test CPU usage during CPU-intensive operations."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(performance_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            # Simulate CPU-intensive operation
            def cpu_intensive_mock(*args, **kwargs):
                # Simulate some CPU work
                sum(i**2 for i in range(1000))
                return Mock(stdout="cpu intensive result", stderr="", returncode=0)
            
            mock_run.side_effect = cpu_intensive_mock
            
            client = TelegramClient(config_path)
            
            # Measure CPU usage during processing
            cpu_measurements = []
            
            # Process messages and measure CPU
            for i in range(20):
                mock_message = Mock()
                mock_message.text = f"[perf_action_{i % 5}]\ncpu_test = {i}"
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 50000 + i
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = f'CPUUser{i}'
                mock_message.from_user.id = 500000 + i
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                # Process message and measure CPU
                start_time = time.time()
                await client.handle_message(mock_update, mock_context)
                processing_time = time.time() - start_time
                
                cpu_usage = measure_cpu_usage()
                cpu_measurements.append(cpu_usage)
                
                # Should complete processing in reasonable time
                assert processing_time < 1.0, f"CPU intensive processing too slow: {processing_time:.2f}s"
            
            # CPU usage should be reasonable (not constantly maxed out)
            if cpu_measurements:
                avg_cpu = statistics.mean([cpu for cpu in cpu_measurements if cpu > 0])
                max_cpu = max(cpu_measurements)
                
                # Note: These limits may need adjustment based on system capabilities
                if avg_cpu > 0:  # Only check if we got valid CPU measurements
                    assert avg_cpu < 80, f"Average CPU usage too high: {avg_cpu:.1f}%"
                if max_cpu > 0:
                    assert max_cpu < 95, f"Peak CPU usage too high: {max_cpu:.1f}%"

    def test_config_validation_cpu_efficiency(self, create_temp_config, large_config):
        """Test CPU efficiency of config validation with large configs."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(large_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            # Measure CPU usage during config validation
            validation_times = []
            
            for i in range(5):
                start_time = time.time()
                start_cpu = measure_cpu_usage()
                
                # Load and validate large config
                client = TelegramClient(config_path)
                
                validation_time = time.time() - start_time
                end_cpu = measure_cpu_usage()
                
                validation_times.append(validation_time)
                
                # Config should be valid
                assert client.config_valid, f"Large config validation failed (attempt {i+1})"
                
                # Cleanup for next iteration
                del client
                gc.collect()
            
            # Validation should be efficient
            avg_validation_time = statistics.mean(validation_times)
            max_validation_time = max(validation_times)
            
            assert avg_validation_time < 1.0, f"Config validation too slow: {avg_validation_time:.2f}s"
            assert max_validation_time < 3.0, f"Max validation time too slow: {max_validation_time:.2f}s"


class TestScalabilityPerformance:
    """Test system scalability with increasing load."""

    @pytest.mark.asyncio
    async def test_scalability_with_increasing_message_volume(self, create_temp_config, performance_config):
        """Test performance scalability with increasing message volume."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(performance_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            mock_run.return_value = Mock(stdout="scalability test", stderr="", returncode=0)
            
            client = TelegramClient(config_path)
            
            # Test with increasing message volumes
            message_volumes = [10, 25, 50, 100, 200]
            performance_metrics = []
            
            for volume in message_volumes:
                # Create messages for this volume test
                messages = []
                for i in range(volume):
                    mock_message = Mock()
                    mock_message.text = f"[perf_action_{i % 10}]\nscalability_test = {i}"
                    mock_message.reply_text = AsyncMock()
                    mock_message.chat = Mock()
                    mock_message.chat.id = 60000 + i
                    mock_message.chat.type = 'private'
                    mock_message.from_user = Mock()
                    mock_message.from_user.first_name = f'ScaleUser{i}'
                    mock_message.from_user.id = 600000 + i
                    
                    mock_update = Mock()
                    mock_update.message = mock_message
                    mock_update.channel_post = None
                    mock_context = Mock()
                    
                    messages.append((mock_update, mock_context, mock_message))
                
                # Measure performance for this volume
                initial_memory = measure_memory_usage()
                start_time = time.time()
                
                # Process all messages concurrently
                tasks = [client.handle_message(update, context) for update, context, _ in messages]
                await asyncio.gather(*tasks)
                
                processing_time = time.time() - start_time
                final_memory = measure_memory_usage()
                memory_used = final_memory - initial_memory
                
                # Calculate metrics
                throughput = volume / processing_time
                memory_per_message = memory_used / volume if volume > 0 else 0
                
                performance_metrics.append({
                    'volume': volume,
                    'processing_time': processing_time,
                    'throughput': throughput,
                    'memory_used': memory_used,
                    'memory_per_message': memory_per_message
                })
                
                # Verify all messages were processed
                assert mock_run.call_count >= volume
                mock_run.reset_mock()
                
                # Brief pause between tests
                await asyncio.sleep(0.1)
                gc.collect()
            
            # Analyze scalability
            throughputs = [m['throughput'] for m in performance_metrics]
            memory_per_msg = [m['memory_per_message'] for m in performance_metrics]
            
            # Throughput should not degrade significantly with increased load
            min_throughput = min(throughputs)
            max_throughput = max(throughputs)
            throughput_degradation = (max_throughput - min_throughput) / max_throughput
            
            assert min_throughput > 20, f"Minimum throughput too low: {min_throughput:.1f} msg/s"
            assert throughput_degradation < 0.5, f"Throughput degradation too high: {throughput_degradation:.2f}"
            
            # Memory usage per message should remain reasonable
            avg_memory_per_msg = statistics.mean([m for m in memory_per_msg if m > 0])
            if avg_memory_per_msg > 0:
                assert avg_memory_per_msg < 5, f"Memory per message too high: {avg_memory_per_msg:.2f}MB"

    def test_scalability_with_large_action_count(self, create_temp_config):
        """Test performance scalability with large number of actions."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        # Test with increasing numbers of actions
        action_counts = [50, 100, 250, 500, 1000]
        loading_times = []
        memory_usages = []
        
        for action_count in action_counts:
            # Create config with specified number of actions
            large_action_config = {
                'telegram': {
                    'bot_token': 'scalability_test_token',
                    'channels': [-1002345]
                },
                'actions': {
                    f'scale_action_{i:04d}': {
                        'command': f'echo "Action {i}"',
                        'description': f'Scalability test action {i}'
                    }
                    for i in range(action_count)
                }
            }
            
            config_path = create_temp_config(large_action_config)
            
            try:
                with patch('telegram_client.Update'), \
                        patch('telegram_client.Application'), \
                        patch('telegram_client.MessageHandler'), \
                        patch('telegram_client.filters'), \
                        patch('telegram_client.ContextTypes'):
                    
                    # Measure loading performance
                    initial_memory = measure_memory_usage()
                    start_time = time.time()
                    
                    client = TelegramClient(config_path)
                    
                    loading_time = time.time() - start_time
                    final_memory = measure_memory_usage()
                    memory_usage = final_memory - initial_memory
                    
                    loading_times.append(loading_time)
                    memory_usages.append(memory_usage)
                    
                    # Verify config loaded correctly
                    assert client.config_valid, f"Config with {action_count} actions should be valid"
                    assert len(client.config['actions']) == action_count
                    
                    # Cleanup
                    del client
                    gc.collect()
                    
            finally:
                config_path.unlink()
        
        # Analyze scalability with action count
        # Loading time should scale sub-linearly with action count
        for i, (count, time_taken) in enumerate(zip(action_counts, loading_times)):
            time_per_action = time_taken / count
            assert time_per_action < 0.01, f"Loading time per action too high: {time_per_action:.4f}s at {count} actions"
        
        # Memory usage should scale reasonably
        for i, (count, memory) in enumerate(zip(action_counts, memory_usages)):
            memory_per_action = memory / count if count > 0 else 0
            if memory_per_action > 0:
                assert memory_per_action < 0.5, f"Memory per action too high: {memory_per_action:.3f}MB at {count} actions"

    @pytest.mark.asyncio
    async def test_concurrent_user_scalability(self, create_temp_config, performance_config):
        """Test scalability with multiple concurrent users."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        from telegram_client import TelegramClient
        
        config_path = create_temp_config(performance_config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            mock_run.return_value = Mock(stdout="concurrent user test", stderr="", returncode=0)
            
            client = TelegramClient(config_path)
            
            # Simulate different numbers of concurrent users
            user_counts = [5, 10, 20, 30]
            concurrent_performance = []
            
            for user_count in user_counts:
                # Create messages from different users
                user_messages = []
                for user_id in range(user_count):
                    # Each user sends multiple messages
                    for msg_id in range(5):  # 5 messages per user
                        mock_message = Mock()
                        mock_message.text = f"[perf_action_{msg_id}]\nuser_id = {user_id}\nmsg_id = {msg_id}"
                        mock_message.reply_text = AsyncMock()
                        mock_message.chat = Mock()
                        mock_message.chat.id = 70000 + user_id
                        mock_message.chat.type = 'private'
                        mock_message.from_user = Mock()
                        mock_message.from_user.first_name = f'ConcurrentUser{user_id}'
                        mock_message.from_user.id = 700000 + user_id
                        
                        mock_update = Mock()
                        mock_update.message = mock_message
                        mock_update.channel_post = None
                        mock_context = Mock()
                        
                        user_messages.append((mock_update, mock_context, mock_message))
                
                # Process all user messages concurrently
                start_time = time.time()
                initial_memory = measure_memory_usage()
                
                tasks = [client.handle_message(update, context) for update, context, _ in user_messages]
                await asyncio.gather(*tasks)
                
                processing_time = time.time() - start_time
                final_memory = measure_memory_usage()
                memory_used = final_memory - initial_memory
                
                total_messages = len(user_messages)
                throughput = total_messages / processing_time
                
                concurrent_performance.append({
                    'user_count': user_count,
                    'total_messages': total_messages,
                    'processing_time': processing_time,
                    'throughput': throughput,
                    'memory_used': memory_used
                })
                
                # Verify all messages were processed
                for _, _, mock_message in user_messages:
                    mock_message.reply_text.assert_called_once()
                
                # Reset for next test
                mock_run.reset_mock()
                for _, _, mock_message in user_messages:
                    mock_message.reply_text.reset_mock()
                
                gc.collect()
            
            # Analyze concurrent user performance
            throughputs = [p['throughput'] for p in concurrent_performance]
            processing_times = [p['processing_time'] for p in concurrent_performance]
            
            # Should maintain reasonable performance with concurrent users
            min_throughput = min(throughputs)
            assert min_throughput > 10, f"Concurrent user throughput too low: {min_throughput:.1f} msg/s"
            
            max_processing_time = max(processing_times)
            assert max_processing_time < 10, f"Concurrent processing too slow: {max_processing_time:.2f}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])