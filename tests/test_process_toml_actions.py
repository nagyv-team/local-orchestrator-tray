#!/usr/bin/env python3
"""
Comprehensive test suite for process_toml_actions() function in TelegramClient.

This test suite covers all code paths and edge cases for the complex process_toml_actions() 
method (CCN 9) to ensure safe refactoring. The function handles:
1. Processing multiple TOML sections from parsed data
2. Distinguishing between built-in actions (uppercase) and custom actions  
3. Executing built-in actions via execute_built_in_action()
4. Executing custom actions via execute_action()
5. Error handling for both action types
6. Replying to Telegram messages with success/failure results
7. Truncating long results for Telegram message limits
8. Handling actions not found in any registry
"""

import asyncio
import pytest
import sys
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
from typing import Dict, Any

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Mock rumps before any imports that might trigger it
sys.modules['rumps'] = Mock()


@pytest.fixture
def mock_telegram():
    """Mock the telegram library components."""
    sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
    
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

        mock_updater = Mock()
        mock_updater.start_polling = AsyncMock()
        mock_updater.stop = AsyncMock()
        mock_app.updater = mock_updater

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
    """Create a temporary test configuration with both built-in and custom actions."""
    config_data = {
        'telegram': {
            'bot_token': '123456789:ABCDEFghijklmnopqrstuvwxyz_test_token'
        },
        'actions': {
            'custom-echo': {
                'command': 'echo',
                'description': 'Echo test command'
            },
            'custom-ls': {
                'command': 'ls',
                'description': 'List files',
                'working_dir': '/tmp'
            }
        }
    }

    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    yaml.dump(config_data, temp_file, default_flow_style=False)
    temp_file.close()

    yield Path(temp_file.name)
    Path(temp_file.name).unlink()


@pytest.fixture
def telegram_client(test_config, mock_telegram):
    """Create a TelegramClient instance for testing."""
    sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
    from telegram_client import TelegramClient
    
    return TelegramClient(test_config)


@pytest.fixture
def mock_message():
    """Create a mock Telegram message for testing."""
    message = Mock()
    message.reply_text = AsyncMock()
    return message


class TestProcessTomlActionsStructure:
    """Test the basic structure and section processing of process_toml_actions()."""

    @pytest.mark.asyncio
    async def test_should_process_empty_toml_data_when_no_sections_provided(self, telegram_client, mock_message):
        """Empty TOML data should complete without errors or replies."""
        toml_data = {}
        
        # Should complete without errors
        await telegram_client.process_toml_actions(mock_message, toml_data)
        
        # No replies should be sent for empty data
        mock_message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_should_process_single_dictionary_section_when_valid_toml_provided(self, telegram_client, mock_message):
        """Single valid dictionary section should be processed."""
        toml_data = {
            'custom-echo': {'message': 'test'}
        }
        
        with patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute:
            
            # Configure custom action exists
            mock_get_action.return_value = {'command': 'echo', 'description': 'test'}
            mock_execute.return_value = 'test output'
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should check for action and execute it
            mock_get_action.assert_called_once_with('custom-echo')
            mock_execute.assert_called_once_with({'command': 'echo', 'description': 'test'}, {'message': 'test'})
            
            # Should send success reply
            mock_message.reply_text.assert_called_once()
            reply_text = mock_message.reply_text.call_args[0][0]
            assert '✅' in reply_text
            assert 'custom-echo' in reply_text
            assert 'completed' in reply_text

    @pytest.mark.asyncio
    async def test_should_process_multiple_dictionary_sections_when_valid_toml_provided(self, telegram_client, mock_message):
        """Multiple valid dictionary sections should all be processed."""
        toml_data = {
            'custom-echo': {'message': 'test1'},
            'custom-ls': {'directory': '/tmp'}
        }
        
        with patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute:
            
            # Configure both actions exist
            mock_get_action.side_effect = [
                {'command': 'echo', 'description': 'test1'},  # First call
                {'command': 'ls', 'description': 'test2'}     # Second call
            ]
            mock_execute.side_effect = ['output1', 'output2']
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should check for both actions
            assert mock_get_action.call_count == 2
            mock_get_action.assert_any_call('custom-echo')
            mock_get_action.assert_any_call('custom-ls')
            
            # Should execute both actions
            assert mock_execute.call_count == 2
            
            # Should send two success replies
            assert mock_message.reply_text.call_count == 2

    @pytest.mark.asyncio
    async def test_should_skip_non_dictionary_sections_when_mixed_toml_provided(self, telegram_client, mock_message):
        """Non-dictionary sections should be skipped with debug logging."""
        toml_data = {
            'string_section': 'just a string',
            'number_section': 42,
            'list_section': ['item1', 'item2'],
            'valid_action': {'param': 'value'}
        }
        
        with patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute, \
             patch('telegram_client.logger') as mock_logger:
            
            # Configure only the valid action exists
            mock_get_action.return_value = {'command': 'echo', 'description': 'test'}
            mock_execute.return_value = 'test output'
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should only process the valid dictionary section
            mock_get_action.assert_called_once_with('valid_action')
            mock_execute.assert_called_once()
            
            # Should send only one reply for the valid action
            mock_message.reply_text.assert_called_once()
            
            # Should log skipping of non-dictionary sections
            debug_calls = [call for call in mock_logger.debug.call_args_list if 'Skipping section' in str(call)]
            assert len(debug_calls) == 3  # string, number, and list sections should be skipped

    @pytest.mark.asyncio
    async def test_should_log_section_processing_details_when_processing_toml(self, telegram_client, mock_message):
        """Verify debug logging shows section names and types during processing."""
        toml_data = {
            'test_action': {'param': 'value'},
            'string_section': 'not a dict'
        }
        
        with patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute, \
             patch('telegram_client.logger') as mock_logger:
            
            mock_get_action.return_value = {'command': 'echo', 'description': 'test'}
            mock_execute.return_value = 'test output'
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should log the number of sections being processed
            mock_logger.debug.assert_any_call(f"Processing {len(toml_data)} TOML sections: {list(toml_data.keys())}")
            
            # Should log details for each section
            mock_logger.debug.assert_any_call("Processing section 'test_action': <class 'dict'>")
            mock_logger.debug.assert_any_call("Processing section 'string_section': <class 'str'>")
            
            # Should log skipping non-dictionary section
            mock_logger.debug.assert_any_call("Skipping section 'string_section' - not a dictionary")


class TestProcessTomlActionsBuiltInActions:
    """Test built-in action detection and execution flow."""

    @pytest.mark.asyncio
    async def test_should_detect_built_in_action_when_section_name_matches_registry(self, telegram_client, mock_message):
        """Built-in actions should be detected via built_in_action_registry.is_built_in_action()."""
        toml_data = {
            'Notification': {'message': 'test notification'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client, 'execute_built_in_action') as mock_execute:
            
            mock_is_builtin.return_value = True
            mock_execute.return_value = 'notification shown'
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should check if action is built-in
            mock_is_builtin.assert_called_once_with('Notification')
            
            # Should not check custom registry (we'll verify this doesn't get called)
            # This is implicit - if built-in is detected, custom registry isn't checked

    @pytest.mark.asyncio
    async def test_should_execute_built_in_action_when_detected_as_built_in(self, telegram_client, mock_message):
        """Built-in actions should be executed via execute_built_in_action()."""
        toml_data = {
            'Notification': {'message': 'test notification', 'title': 'Test'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client, 'execute_built_in_action') as mock_execute:
            
            mock_is_builtin.return_value = True
            mock_execute.return_value = 'notification shown'
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should execute the built-in action with correct parameters
            mock_execute.assert_called_once_with('Notification', {'message': 'test notification', 'title': 'Test'})

    @pytest.mark.asyncio
    async def test_should_reply_success_message_when_built_in_action_succeeds(self, telegram_client, mock_message):
        """Successful built-in action execution should send success reply with checkmark emoji."""
        toml_data = {
            'Notification': {'message': 'test notification'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client, 'execute_built_in_action') as mock_execute:
            
            mock_is_builtin.return_value = True
            mock_execute.return_value = 'notification displayed successfully'
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should send success reply with checkmark emoji
            mock_message.reply_text.assert_called_once()
            reply_text = mock_message.reply_text.call_args[0][0]
            assert '✅' in reply_text  # ✅ checkmark emoji
            assert 'Built-in action' in reply_text
            assert 'Notification' in reply_text
            assert 'completed' in reply_text
            assert 'notification displayed successfully' in reply_text

    @pytest.mark.asyncio
    async def test_should_continue_to_next_section_when_built_in_action_processed(self, telegram_client, mock_message):
        """After processing built-in action, should continue to next section without checking custom registry."""
        toml_data = {
            'Notification': {'message': 'test notification'},
            'custom-echo': {'message': 'test'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_built_in_action') as mock_execute_builtin, \
             patch.object(telegram_client, 'execute_action') as mock_execute_custom:
            
            # First section is built-in, second is custom
            mock_is_builtin.side_effect = [True, False]  # Notification=True, custom-echo=False
            mock_execute_builtin.return_value = 'notification shown'
            mock_get_action.return_value = {'command': 'echo', 'description': 'test'}
            mock_execute_custom.return_value = 'echo output'
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should check both sections for built-in status
            assert mock_is_builtin.call_count == 2
            mock_is_builtin.assert_any_call('Notification')
            mock_is_builtin.assert_any_call('custom-echo')
            
            # Should execute built-in action
            mock_execute_builtin.assert_called_once_with('Notification', {'message': 'test notification'})
            
            # Should check custom registry only for the second action
            mock_get_action.assert_called_once_with('custom-echo')
            mock_execute_custom.assert_called_once()
            
            # Should send two replies (one for each action)
            assert mock_message.reply_text.call_count == 2

    @pytest.mark.asyncio
    async def test_should_log_built_in_action_execution_details_when_executing(self, telegram_client, mock_message):
        """Built-in action execution should log parameters, results, and completion status."""
        toml_data = {
            'Notification': {'message': 'test notification', 'title': 'Test Title'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client, 'execute_built_in_action') as mock_execute, \
             patch('telegram_client.logger') as mock_logger:
            
            mock_is_builtin.return_value = True
            mock_execute.return_value = 'notification displayed'
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should log execution details
            mock_logger.info.assert_any_call(
                "Executing built-in action 'Notification' with parameters: {'message': 'test notification', 'title': 'Test Title'}"
            )
            
            # Should log completion
            mock_logger.info.assert_any_call(
                "Built-in action 'Notification' completed successfully, result: notification displayed"
            )


class TestProcessTomlActionsCustomActions:
    """Test custom action execution flow."""

    @pytest.mark.asyncio
    async def test_should_check_custom_registry_when_not_built_in_action(self, telegram_client, mock_message):
        """When action not built-in, should check action_registry.get_action()."""
        toml_data = {
            'custom-echo': {'message': 'test'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute:
            
            mock_is_builtin.return_value = False  # Not a built-in action
            mock_get_action.return_value = {'command': 'echo', 'description': 'test action'}
            mock_execute.return_value = 'command output'
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should check built-in registry first
            mock_is_builtin.assert_called_once_with('custom-echo')
            
            # Should then check custom registry
            mock_get_action.assert_called_once_with('custom-echo')

    @pytest.mark.asyncio
    async def test_should_execute_custom_action_when_found_in_registry(self, telegram_client, mock_message):
        """Custom actions should be executed via execute_action()."""
        toml_data = {
            'custom-ls': {'directory': '/tmp', 'long': True}
        }
        
        action_config = {'command': 'ls', 'description': 'list files', 'working_dir': '/tmp'}
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute:
            
            mock_is_builtin.return_value = False
            mock_get_action.return_value = action_config
            mock_execute.return_value = 'file1\nfile2\nfile3'
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should execute custom action with correct parameters
            mock_execute.assert_called_once_with(action_config, {'directory': '/tmp', 'long': True})

    @pytest.mark.asyncio
    async def test_should_reply_success_with_result_when_custom_action_succeeds_with_output(self, telegram_client, mock_message):
        """Successful custom action with output should send formatted success reply."""
        toml_data = {
            'custom-echo': {'message': 'hello world'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute:
            
            mock_is_builtin.return_value = False
            mock_get_action.return_value = {'command': 'echo', 'description': 'test'}
            mock_execute.return_value = 'hello world\noutput line 2'
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should send success reply with code block formatting
            mock_message.reply_text.assert_called_once()
            reply_text = mock_message.reply_text.call_args[0][0]
            assert '✅' in reply_text  # checkmark emoji
            assert 'Custom action' in reply_text
            assert 'custom-echo' in reply_text
            assert 'completed' in reply_text
            assert '```' in reply_text  # code block formatting
            assert 'hello world\noutput line 2' in reply_text

    @pytest.mark.asyncio
    async def test_should_reply_success_without_result_when_custom_action_succeeds_with_empty_output(self, telegram_client, mock_message):
        """Successful custom action with empty output should send simple success reply."""
        toml_data = {
            'custom-touch': {'filename': 'test.txt'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute:
            
            mock_is_builtin.return_value = False
            mock_get_action.return_value = {'command': 'touch', 'description': 'create file'}
            mock_execute.return_value = '   '  # whitespace-only output (empty after strip)
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should send simple success reply without code blocks
            mock_message.reply_text.assert_called_once()
            reply_text = mock_message.reply_text.call_args[0][0]
            assert '✅' in reply_text  # checkmark emoji
            assert 'Custom action' in reply_text
            assert 'custom-touch' in reply_text
            assert 'completed successfully' in reply_text
            assert '```' not in reply_text  # no code block formatting

    @pytest.mark.asyncio
    async def test_should_truncate_long_results_when_custom_action_output_exceeds_limit(self, telegram_client, mock_message):
        """Custom action results longer than 4000 chars should be truncated with truncation notice."""
        toml_data = {
            'custom-large-output': {'count': '5000'}
        }
        
        # Create output longer than 4000 characters
        long_output = 'A' * 4500  # 4500 characters
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute:
            
            mock_is_builtin.return_value = False
            mock_get_action.return_value = {'command': 'generate-data', 'description': 'generate large output'}
            mock_execute.return_value = long_output
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should send truncated reply
            mock_message.reply_text.assert_called_once()
            reply_text = mock_message.reply_text.call_args[0][0]
            assert '✅' in reply_text
            assert 'custom-large-output' in reply_text
            assert '[Output truncated - see logs for full result]' in reply_text
            
            # Extract the content within code blocks to verify truncation
            start_idx = reply_text.find('```\n') + 4
            end_idx = reply_text.rfind('\n```')
            code_content = reply_text[start_idx:end_idx]
            
            # Should be truncated to 4000 chars plus truncation notice
            assert len(code_content) < len(long_output)
            assert code_content.startswith('A' * 100)  # starts with original content
            assert '[Output truncated - see logs for full result]' in code_content

    @pytest.mark.asyncio
    async def test_should_log_custom_action_execution_details_when_executing(self, telegram_client, mock_message):
        """Custom action execution should log parameters, result length, and completion status."""
        toml_data = {
            'custom-echo': {'message': 'test', 'repeat': '3'}
        }
        
        output = 'test\ntest\ntest'
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute, \
             patch('telegram_client.logger') as mock_logger:
            
            mock_is_builtin.return_value = False
            mock_get_action.return_value = {'command': 'echo', 'description': 'test'}
            mock_execute.return_value = output
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should log execution details
            mock_logger.info.assert_any_call(
                "Executing custom action 'custom-echo' with parameters: {'message': 'test', 'repeat': '3'}"
            )
            
            # Should log completion with result length
            mock_logger.info.assert_any_call(
                f"Custom action 'custom-echo' completed successfully, result length: {len(output)} chars"
            )


class TestProcessTomlActionsActionNotFound:
    """Test handling of actions not found in any registry."""

    @pytest.mark.asyncio
    async def test_should_reply_action_not_found_when_action_missing_from_both_registries(self, telegram_client, mock_message):
        """Actions not in either registry should trigger 'not found' reply."""
        toml_data = {
            'unknown-action': {'param': 'value'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action:
            
            mock_is_builtin.return_value = False  # Not a built-in action
            mock_get_action.return_value = None   # Not in custom registry either
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should send not found reply
            mock_message.reply_text.assert_called_once()
            reply_text = mock_message.reply_text.call_args[0][0]
            assert "Action 'unknown-action' not found" in reply_text

    @pytest.mark.asyncio
    async def test_should_include_combined_descriptions_when_action_not_found(self, telegram_client, mock_message):
        """Not found reply should include descriptions from both built-in and custom registries."""
        toml_data = {
            'missing-action': {'param': 'value'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client.built_in_action_registry, 'get_actions_description') as mock_builtin_desc, \
             patch.object(telegram_client.action_registry, 'get_actions_description') as mock_custom_desc:
            
            mock_is_builtin.return_value = False
            mock_get_action.return_value = None
            mock_builtin_desc.return_value = "Built-in actions:\n• Notification: Show notification"
            mock_custom_desc.return_value = "Custom actions:\n• custom-echo: Echo command"
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should get descriptions from both registries
            mock_builtin_desc.assert_called_once()
            mock_custom_desc.assert_called_once()
            
            # Should include both descriptions in reply
            mock_message.reply_text.assert_called_once()
            reply_text = mock_message.reply_text.call_args[0][0] 
            assert "Built-in actions:" in reply_text
            assert "Custom actions:" in reply_text
            assert "Notification: Show notification" in reply_text
            assert "custom-echo: Echo command" in reply_text

    @pytest.mark.asyncio
    async def test_should_log_warning_when_action_not_found_in_any_registry(self, telegram_client, mock_message):
        """Missing actions should generate warning log entries."""
        toml_data = {
            'nonexistent-action': {'param': 'value'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client.built_in_action_registry, 'get_actions_description') as mock_builtin_desc, \
             patch.object(telegram_client.action_registry, 'get_actions_description') as mock_custom_desc, \
             patch('telegram_client.logger') as mock_logger:
            
            mock_is_builtin.return_value = False
            mock_get_action.return_value = None
            mock_builtin_desc.return_value = "Built-in actions available"
            mock_custom_desc.return_value = "Custom actions available"
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should log warning about missing action
            mock_logger.warning.assert_called_once_with(
                "Action 'nonexistent-action' not found in any registry"
            )

    @pytest.mark.asyncio
    async def test_should_continue_processing_other_sections_when_one_action_not_found(self, telegram_client, mock_message):
        """If one action not found, should continue processing remaining sections."""
        toml_data = {
            'missing-action': {'param': 'value'},
            'custom-echo': {'message': 'test'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client.built_in_action_registry, 'get_actions_description') as mock_builtin_desc, \
             patch.object(telegram_client.action_registry, 'get_actions_description') as mock_custom_desc, \
             patch.object(telegram_client, 'execute_action') as mock_execute:
            
            mock_is_builtin.return_value = False  # Neither action is built-in
            # First action missing, second action exists
            mock_get_action.side_effect = [None, {'command': 'echo', 'description': 'test'}]
            mock_builtin_desc.return_value = "Built-in actions"
            mock_custom_desc.return_value = "Custom actions"
            mock_execute.return_value = 'echo output'
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should check both actions
            assert mock_get_action.call_count == 2
            mock_get_action.assert_any_call('missing-action')
            mock_get_action.assert_any_call('custom-echo')
            
            # Should execute the found action
            mock_execute.assert_called_once()
            
            # Should send two replies (one 'not found', one success)
            assert mock_message.reply_text.call_count == 2


class TestProcessTomlActionsErrorHandling:
    """Test error handling for both built-in and custom action types."""

    @pytest.mark.asyncio
    async def test_should_handle_built_in_action_execution_exception_gracefully(self, telegram_client, mock_message):
        """Built-in action exceptions should be caught and replied with error message."""
        toml_data = {
            'Notification': {'message': 'test'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client, 'execute_built_in_action') as mock_execute:
            
            mock_is_builtin.return_value = True
            mock_execute.side_effect = Exception("Built-in action failed")
            
            # Should not raise exception
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should still send a reply (error message)
            mock_message.reply_text.assert_called_once()
            reply_text = mock_message.reply_text.call_args[0][0]
            assert '❌' in reply_text  # X emoji for error
            assert 'Built-in action' in reply_text
            assert 'Notification' in reply_text
            assert 'failed' in reply_text
            assert 'Built-in action failed' in reply_text

    @pytest.mark.asyncio
    async def test_should_handle_custom_action_execution_exception_gracefully(self, telegram_client, mock_message):
        """Custom action exceptions should be caught and replied with error message."""
        toml_data = {
            'custom-failing': {'param': 'value'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute:
            
            mock_is_builtin.return_value = False
            mock_get_action.return_value = {'command': 'failing-command', 'description': 'test'}
            mock_execute.side_effect = Exception("Custom action failed")
            
            # Should not raise exception
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should still send a reply (error message)
            mock_message.reply_text.assert_called_once()
            reply_text = mock_message.reply_text.call_args[0][0]
            assert '❌' in reply_text  # X emoji for error
            assert 'Custom action' in reply_text
            assert 'custom-failing' in reply_text
            assert 'failed' in reply_text
            assert 'Custom action failed' in reply_text

    @pytest.mark.asyncio  
    async def test_should_reply_error_message_with_x_emoji_when_built_in_action_fails(self, telegram_client, mock_message):
        """Built-in action failures should send error reply with X emoji."""
        toml_data = {
            'Notification': {'message': 'test'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client, 'execute_built_in_action') as mock_execute:
            
            mock_is_builtin.return_value = True
            mock_execute.side_effect = ValueError("Invalid parameter")
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            mock_message.reply_text.assert_called_once()
            reply_text = mock_message.reply_text.call_args[0][0]
            
            # Should match exact format: "❌ Built-in action '{name}' failed: {error}"
            expected_format = "❌ Built-in action 'Notification' failed: Invalid parameter"
            assert reply_text == expected_format

    @pytest.mark.asyncio
    async def test_should_reply_error_message_with_x_emoji_when_custom_action_fails(self, telegram_client, mock_message):
        """Custom action failures should send error reply with X emoji."""
        toml_data = {
            'custom-error': {'param': 'value'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute:
            
            mock_is_builtin.return_value = False
            mock_get_action.return_value = {'command': 'error-command', 'description': 'test'}
            mock_execute.side_effect = RuntimeError("Command not found")
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            mock_message.reply_text.assert_called_once()
            reply_text = mock_message.reply_text.call_args[0][0]
            
            # Should match exact format: "❌ Custom action '{name}' failed: {error}"
            expected_format = "❌ Custom action 'custom-error' failed: Command not found"
            assert reply_text == expected_format

    @pytest.mark.asyncio
    async def test_should_log_error_details_with_traceback_when_built_in_action_fails(self, telegram_client, mock_message):
        """Built-in action errors should log error message and full traceback."""
        toml_data = {
            'Notification': {'message': 'test'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client, 'execute_built_in_action') as mock_execute, \
             patch('telegram_client.logger') as mock_logger, \
             patch('telegram_client.traceback') as mock_traceback:
            
            error = Exception("Test error")
            mock_is_builtin.return_value = True
            mock_execute.side_effect = error
            mock_traceback.format_exc.return_value = "Traceback (most recent call last):\n  File test, line 1\n    raise Exception\nException: Test error"
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should log error message
            mock_logger.error.assert_any_call("Built-in action 'Notification' failed: Test error")
            
            # Should log traceback details
            mock_logger.error.assert_any_call("Built-in action failure details: Traceback (most recent call last):\n  File test, line 1\n    raise Exception\nException: Test error")

    @pytest.mark.asyncio
    async def test_should_log_error_details_with_traceback_when_custom_action_fails(self, telegram_client, mock_message):
        """Custom action errors should log error message and full traceback."""
        toml_data = {
            'custom-error': {'param': 'value'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute, \
             patch('telegram_client.logger') as mock_logger, \
             patch('telegram_client.traceback') as mock_traceback:
            
            error = RuntimeError("Command failed")
            mock_is_builtin.return_value = False
            mock_get_action.return_value = {'command': 'failing-cmd', 'description': 'test'}
            mock_execute.side_effect = error
            mock_traceback.format_exc.return_value = "Traceback (most recent call last):\n  File test, line 1\n    raise RuntimeError\nRuntimeError: Command failed"
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should log error message
            mock_logger.error.assert_any_call("Custom action 'custom-error' failed: Command failed")
            
            # Should log traceback details
            mock_logger.error.assert_any_call("Custom action failure details: Traceback (most recent call last):\n  File test, line 1\n    raise RuntimeError\nRuntimeError: Command failed")

    @pytest.mark.asyncio
    async def test_should_continue_processing_other_sections_when_one_action_fails(self, telegram_client, mock_message):
        """If one action fails, should continue processing remaining sections."""
        toml_data = {
            'failing-action': {'param': 'value'},
            'working-action': {'message': 'test'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute:
            
            mock_is_builtin.return_value = False  # Both are custom actions
            mock_get_action.side_effect = [
                {'command': 'failing-cmd', 'description': 'failing'},  # First action config
                {'command': 'echo', 'description': 'working'}          # Second action config
            ]
            mock_execute.side_effect = [
                Exception("First action failed"),  # First action fails
                'success output'                    # Second action succeeds
            ]
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should execute both actions
            assert mock_execute.call_count == 2
            
            # Should send two replies (one error, one success)
            assert mock_message.reply_text.call_count == 2
            
            # Verify error reply
            error_reply = mock_message.reply_text.call_args_list[0][0][0]
            assert '❌' in error_reply
            assert 'failing-action' in error_reply
            
            # Verify success reply
            success_reply = mock_message.reply_text.call_args_list[1][0][0]
            assert '✅' in success_reply
            assert 'working-action' in success_reply


class TestProcessTomlActionsMessageReplies:
    """Test Telegram message reply behavior and formatting."""

    @pytest.mark.asyncio
    async def test_should_format_built_in_success_reply_correctly(self, telegram_client, mock_message):
        """Built-in success replies should follow '✅ Built-in action '{name}' completed: {result}' format."""
        toml_data = {
            'Notification': {'message': 'test notification'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client, 'execute_built_in_action') as mock_execute:
            
            mock_is_builtin.return_value = True
            mock_execute.return_value = 'Notification displayed: test notification'
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            mock_message.reply_text.assert_called_once()
            reply_text = mock_message.reply_text.call_args[0][0]
            
            # Should match exact format
            expected = "✅ Built-in action 'Notification' completed: Notification displayed: test notification"
            assert reply_text == expected

    @pytest.mark.asyncio
    async def test_should_format_custom_success_reply_with_code_blocks_when_output_present(self, telegram_client, mock_message):
        """Custom success with output should use code block formatting."""
        toml_data = {
            'custom-ls': {'directory': '/tmp'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute:
            
            mock_is_builtin.return_value = False
            mock_get_action.return_value = {'command': 'ls', 'description': 'list files'}
            mock_execute.return_value = 'file1.txt\nfile2.txt\nfile3.txt'
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            mock_message.reply_text.assert_called_once()
            reply_text = mock_message.reply_text.call_args[0][0]
            
            # Should use code block format
            expected = "✅ Custom action 'custom-ls' completed:\n```\nfile1.txt\nfile2.txt\nfile3.txt\n```"
            assert reply_text == expected

    @pytest.mark.asyncio
    async def test_should_format_custom_success_reply_without_code_blocks_when_no_output(self, telegram_client, mock_message):
        """Custom success without output should use simple completion message."""
        toml_data = {
            'custom-mkdir': {'directory': 'test_dir'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute:
            
            mock_is_builtin.return_value = False
            mock_get_action.return_value = {'command': 'mkdir', 'description': 'create directory'}
            mock_execute.return_value = ''  # Empty output
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            mock_message.reply_text.assert_called_once()
            reply_text = mock_message.reply_text.call_args[0][0]
            
            # Should use simple format without code blocks
            expected = "✅ Custom action 'custom-mkdir' completed successfully"
            assert reply_text == expected

    @pytest.mark.asyncio
    async def test_should_include_truncation_notice_in_reply_when_result_truncated(self, telegram_client, mock_message):
        """Truncated results should include '[Output truncated - see logs for full result]' notice."""
        toml_data = {
            'custom-large': {'size': '5000'}
        }
        
        # Create output longer than 4000 characters  
        long_output = 'X' * 4200
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute:
            
            mock_is_builtin.return_value = False
            mock_get_action.return_value = {'command': 'generate', 'description': 'generate large data'}
            mock_execute.return_value = long_output
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            mock_message.reply_text.assert_called_once()
            reply_text = mock_message.reply_text.call_args[0][0]
            
            # Should include truncation notice
            assert '[Output truncated - see logs for full result]' in reply_text
            
            # Should be properly formatted with code blocks
            assert '✅ Custom action' in reply_text
            assert '```' in reply_text
            
            # Extract content between code blocks to verify truncation
            start = reply_text.find('```\n') + 4
            end = reply_text.rfind('\n```')
            code_content = reply_text[start:end]
            
            # Should be truncated (original was 4200 chars, limit is 4000)
            assert len(code_content) < len(long_output)
            assert code_content.startswith('X' * 100)  # Starts with original content

    @pytest.mark.asyncio
    async def test_should_format_error_replies_consistently_for_both_action_types(self, telegram_client, mock_message):
        """Error replies should follow '❌ {Action type} action '{name}' failed: {error}' format."""
        # Test both built-in and custom action error formats
        
        # Test built-in action error format
        toml_data = {'Notification': {'message': 'test'}}
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client, 'execute_built_in_action') as mock_execute_builtin:
            
            mock_is_builtin.return_value = True
            mock_execute_builtin.side_effect = Exception("Built-in error")
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            built_in_reply = mock_message.reply_text.call_args[0][0]
            assert built_in_reply == "❌ Built-in action 'Notification' failed: Built-in error"
        
        # Reset mock for second test
        mock_message.reply_text.reset_mock()
        
        # Test custom action error format
        toml_data = {'custom-fail': {'param': 'value'}}
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute_custom:
            
            mock_is_builtin.return_value = False
            mock_get_action.return_value = {'command': 'fail', 'description': 'test'}
            mock_execute_custom.side_effect = Exception("Custom error")
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            custom_reply = mock_message.reply_text.call_args[0][0]
            assert custom_reply == "❌ Custom action 'custom-fail' failed: Custom error"


class TestProcessTomlActionsComplexScenarios:
    """Test complex scenarios with multiple sections and mixed action types."""

    @pytest.mark.asyncio
    async def test_should_process_mixed_built_in_and_custom_actions_in_single_toml(self, telegram_client, mock_message):
        """Single TOML with both built-in and custom actions should process all correctly."""
        toml_data = {
            'Notification': {'message': 'notification text', 'title': 'Test'},
            'custom-echo': {'message': 'echo text'},
            'custom-ls': {'directory': '/'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_built_in_action') as mock_execute_builtin, \
             patch.object(telegram_client, 'execute_action') as mock_execute_custom:
            
            # First action is built-in, others are custom
            mock_is_builtin.side_effect = [True, False, False]
            mock_execute_builtin.return_value = 'notification shown'
            
            mock_get_action.side_effect = [
                {'command': 'echo', 'description': 'echo command'},
                {'command': 'ls', 'description': 'list files'}
            ]
            mock_execute_custom.side_effect = ['echo text', 'file1\nfile2']
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should execute built-in action once
            mock_execute_builtin.assert_called_once_with('Notification', {'message': 'notification text', 'title': 'Test'})
            
            # Should execute custom actions twice
            assert mock_execute_custom.call_count == 2
            
            # Should send three replies
            assert mock_message.reply_text.call_count == 3

    @pytest.mark.asyncio
    async def test_should_handle_mix_of_successful_and_failed_actions_appropriately(self, telegram_client, mock_message):
        """Mix of successful and failed actions should handle each independently."""
        toml_data = {
            'success-action': {'param': 'value'},
            'fail-action': {'param': 'value'},
            'another-success': {'param': 'value'}
        }
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute:
            
            mock_is_builtin.return_value = False  # All custom actions
            mock_get_action.side_effect = [
                {'command': 'success', 'description': 'success cmd'},
                {'command': 'fail', 'description': 'fail cmd'},
                {'command': 'success2', 'description': 'success cmd 2'}
            ]
            # First succeeds, second fails, third succeeds
            mock_execute.side_effect = [
                'success output',
                Exception("Command failed"),
                'another success'
            ]
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should send three replies (2 success, 1 error)
            assert mock_message.reply_text.call_count == 3
            
            # Verify reply types
            replies = [call[0][0] for call in mock_message.reply_text.call_args_list]
            success_replies = [r for r in replies if '✅' in r]
            error_replies = [r for r in replies if '❌' in r]
            
            assert len(success_replies) == 2
            assert len(error_replies) == 1

    @pytest.mark.asyncio
    async def test_should_process_actions_in_toml_section_order(self, telegram_client, mock_message):
        """Actions should be processed in the order they appear in TOML sections."""
        from collections import OrderedDict
        
        # Use OrderedDict to ensure predictable order
        toml_data = OrderedDict([
            ('first-action', {'step': '1'}),
            ('second-action', {'step': '2'}),
            ('third-action', {'step': '3'})
        ])
        
        execution_order = []
        
        def track_execution(action_config, params):
            execution_order.append(params['step'])
            return f"executed step {params['step']}"
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute:
            
            mock_is_builtin.return_value = False
            mock_get_action.return_value = {'command': 'echo', 'description': 'test'}
            mock_execute.side_effect = track_execution
            
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should execute in order
            assert execution_order == ['1', '2', '3']

    @pytest.mark.asyncio
    async def test_should_handle_large_number_of_sections_efficiently(self, telegram_client, mock_message):
        """Large number of TOML sections should be processed without performance issues."""
        # Create 50 actions to test performance
        toml_data = {f'action-{i}': {'index': str(i)} for i in range(50)}
        
        with patch.object(telegram_client.built_in_action_registry, 'is_built_in_action') as mock_is_builtin, \
             patch.object(telegram_client.action_registry, 'get_action') as mock_get_action, \
             patch.object(telegram_client, 'execute_action') as mock_execute:
            
            mock_is_builtin.return_value = False
            mock_get_action.return_value = {'command': 'echo', 'description': 'test'}
            mock_execute.return_value = 'output'
            
            # Should complete without timeout (pytest default timeout)
            await telegram_client.process_toml_actions(mock_message, toml_data)
            
            # Should process all sections
            assert mock_execute.call_count == 50
            assert mock_message.reply_text.call_count == 50


if __name__ == "__main__":
    # Run tests with pytest if called directly
    pytest.main([__file__, "-v"])