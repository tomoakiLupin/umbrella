# Test helpers

This folder contains offline tests for the bot's state-management logic.

Run from the repository root:

```powershell
python -m unittest discover -s tests
```

The tests use temporary SQLite databases and do not connect to Discord.
