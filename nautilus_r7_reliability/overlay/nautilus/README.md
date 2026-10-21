# The Nautilus 1.3.0-R7

See `../README_START_HERE.md` for installation, current R7 startup behavior,
candle provenance, derived-cache scope and validation limitations.

The inherited `adapter.py` remains exactly the integrated 1.2.0-R7 source.
`server.py` loads the UI-only subclass in `reliability.py`; the independent candle
worker is in `candle_history.py`. Existing chart interactions and Bridge modes are
preserved. No trading modules are imported.

```text
python -B server.py --build R7
python -B server.py --check --build R7
python -B server.py --review --run PATH_TO_EXTRACTED_RUN --no-cache
```

`--check` is a bounded initial adapter/schema/accounting check; it does not wait
for historical backfill to finish. The browser reports that worker separately.
Runtime source files are always read-only. Optional UI-derived output is outside
the source run. Fullscreen and tablet/phone remain layout features, not remote
network access.
