# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Mac system tray application that listens to Telegram chats and executes local commands based on TOML-formatted messages. It uses Python with the `rumps` library for the tray interface, `py2app` for packaging a Mac compatible application, and `python-telegram-bot` for Telegram integration.

## Development Processes

- Always run Python commands in the `.venv` virtual environment.
- Always aim to have small PRs, preferably 1-5 files changed, less than 200 lines of code changes / PR.

### Feature work

1. Every feature should be started with a user prompt mentioning a GitHub issue. (e.g. "Implement issue #3.") Do not work on features without a GitHub issue!
2. Always use dedicated agents for implementing issues:
  - tdd-implementor
  - tdd-test-writer 
3. Always provide short status reports in the GitHub issue as comments
4. Start every issue on its dedicated branch (e.g. issue #4 -> branch: issue-4)

### Code review

1. Every code review should start on an issue specific branch (e.g. issue-4). Do not do code reviews on the `main` branch!
2. Focus on the overall quality of the codebase, not just the changes in the branch, but work on the branch
3. Always use dedicated agents for the code review:
  1. python-code-reviwer
4. Always use dedicated agents to fix issues from the review:
  1. tdd-implementor - for test related files only
  2. tdd-test-writer - for implementation related files only
5. Iterate from (2) until the code reviewer agent is satisfied with the result

### Issue refinement flow

1. Use the "product-manager" agent to discuss requirements with the user, and come up with a PM proposal
1. Use the "ux-designer" agent to review the PM proposal, and optionally suggest usability improvements on the proposal 
1. Use the "lead-engineer" agent to review the PM proposal, and extend it with a high-level breakdown of ordered deliverables
1. Use the "product-manager" agent to review the updated PM proposal, incorporate usability improvements and to create an MVC (Minimal Valuable Change) focused delivery plan

## Development Commands

### Environment Setup
```bash
# Set up virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_telegram_functionality.py

# Run with verbose output
pytest -v
```

### Building Mac App
```bash
# Clean previous builds
rm -rf build dist

# Build the macOS app bundle (requires macOS)
python setup.py py2app --no-strip

# The app will be in dist/Local\ Orchestrator\ Tray.app/
```

### Development Environment (Nix)
```bash
# For Nix users (as mentioned in README)
nix-shell -p pkgs.python312 pkgs.python312Packages.pip
```

## Architecture Overview

### Core Components
- **`main.py`**: Main tray application using `rumps`, handles UI and lifecycle
- **`telegram_client.py`**: Telegram bot integration, TOML parsing, and command execution
- **Configuration**: YAML config at `~/.config/local-orchestrator-tray.yaml`

### Key Architectural Patterns
- **Tray Application**: Uses `rumps` for macOS system tray integration with periodic status updates
- **Telegram Bot**: Asynchronous bot that parses TOML messages and executes shell commands
- **Action System**: YAML-configured actions that map TOML message keys to shell commands
- **Resource Management**: Sophisticated icon loading that works in both development and py2app bundles

### Message Flow
1. Telegram message with TOML format (e.g., `[action_name]\nkey = "value"`)
2. TOML parsing extracts action name and parameters
3. Parameters converted to CLI flags (`camelCase` → `--kebab-case`)
4. Shell command executed with generated flags
5. Results sent back to Telegram chat

### Built-in Actions
Built-in actions start with uppercase (e.g., `Notification`), custom actions should start lowercase.

## Configuration

### Config File Location
`~/.config/local-orchestrator-tray.yaml`

### Required Configuration
```yaml
telegram:
  bot_token: "YOUR_BOT_TOKEN"

actions:
  action_name:
    command: "shell command to run"
    description: "Optional description"
    working_dir: "/optional/working/directory"
```

## Development Notes

### Python Version Support
- Requires Python ≥3.12
- Built with Python 3.12 by default
- Uses `tomllib` (Python 3.11+) with `toml` fallback

### Dependencies
- `rumps`: macOS tray app framework
- `python-telegram-bot`: Telegram Bot API
- `PyYAML`: Configuration parsing
- `py2app`: macOS app bundling

### Testing Framework
Uses `pytest` with `pytest-asyncio` for async Telegram functionality testing.

### Platform Specificity
This is explicitly a macOS-only application due to `rumps` dependency and `py2app` build system.