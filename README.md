# local-orchestrator-tray
A Mac app that sits in the system tray and listens for events in a Telegram chat. Starts various actions based on the chat messages.

## Local build

```
nix-shell -p pkgs.python3 pkgs.python312Packages.pip
rm -rf build dist
pip -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python setup.py py2app --no-strip
```

Finally copy the resulting app from dist to Applications or just launch it from the terminal at path `./dist/Local\ Orchestrator\ Tray.app/Contents/MacOS/Local\ Orchestrator\ Tray`