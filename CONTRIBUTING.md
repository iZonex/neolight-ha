# Contributing

This integration is an alpha. Reports from other NeoLight models are useful
when they include the exact model, firmware, wiring type, and which behavior
was physically checked. Separate an API acknowledgement from a physical
relay or audio result.

Do not post account credentials, app signing keys, session tokens, device
identifiers, raw packet captures, camera images, or authenticated RTSP URLs in
issues or pull requests. Redact logs before sharing them.

Run Python tests in an environment with Home Assistant dependencies:

```sh
python -m pytest -q tests native_bridge/test_protocol.py
python -m compileall -q custom_components/neolight native_bridge
```

The Scrypted plugin checks with `npm ci`, `npm run check`, and `npm run build`.
The native media bridge needs a Linux host and an authorized paired monitor
for integration testing. Never infer a successful door opening from an API
success response alone.
