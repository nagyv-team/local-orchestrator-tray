# Local Orchestrator Tray

A Mac app that sits in the system tray and listens for events in configured Telegram chats. Starts various actions based on the chat messages.

## Installation

Grab the app from the releases page and place it inside your applications folder.

## Setup

### Configure Telegram bot

1. If you don't have a Telegram bot yet, create a new bot, and grab its token
1. Open the configuration from the app context menu
1. Add the bot token to the `telegram.bot_token` key
1. Save the configuration
1. Restart the app

In a few seconds, you should see that Telegram status to be connected in the app context menu.

### Add bot to a group

1. Find out the group ID (e.g. `curl https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getUpdates | jq -r '.result[].message.chat.id'`)
1. Add the group id to the `telegram.groups` list

## Usage

Send a message to a chat that the bot can read. The message should have a TOML table format for the app to parse it. 
The table name is the action name. The table attributes are key-value pairs passed to the action.
When getting an unrecognized action, the system responds with a list of all the available actions.

Possible example messages:

```
[test]
```

```
[Notification]
title = "👋 Hello"
message = "This message came through Telegram"
```

### Set up actions

There are a few built-in actions, but the real power of the system is that you can run any command locally from a Telegram message.

Built-in actions always start with an uppercase letter (e.g. Notification). Accordingly, custom actions SHOULD start with a lowercase letter.

#### How actions work

It's easiest to explain through an example:

Given the following message:

```
[hello]
who = "Viktor"
dayOfYear = 14
```

will look for an action key `hello` and call its command argument with flags `--who=Viktor --day-of-year=14`.

#### Configure actions

To configure a new action, open the Configuration file and expand the `actions` dictionary with a new key for your action.
For every action, you can define the following keys:

| Key name | Is required |
| --- | --- |
| command | Yes |
| description | No |
| working_dir | No |

## Local build

```
nix-shell -p pkgs.python312 pkgs.python312Packages.pip
rm -rf build dist
pip -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python setup.py py2app --no-strip
```

Finally copy the resulting app from dist to Applications or just launch it from the terminal at path `./dist/Local\ Orchestrator\ Tray.app/Contents/MacOS/Local\ Orchestrator\ Tray`