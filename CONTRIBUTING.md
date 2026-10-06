# Contributing

This integration is an alpha. Reports from other NeoLight models are useful
when they include the exact model, firmware, wiring type, and which behavior
was physically checked. Separate an API acknowledgement from a physical
relay or audio result.

For a new monitor, panel, firmware, or wiring setup, follow the
[research and evidence guide](docs/REVERSE_ENGINEERING.md) and use the
[new-model issue template](.github/ISSUE_TEMPLATE/new-model.yml). Include a
capability matrix and sanitized traces so maintainers can distinguish a
confirmed device feature from a generic SDK path.

Do not post account credentials, app signing keys, session tokens, device
identifiers, raw packet captures, camera images, or authenticated RTSP URLs in
issues or pull requests. Redact logs before sharing them.

Run the protocol and profile tests with Python, `aiohttp`, and `cryptography`:

```sh
python -m unittest discover -s tests -p 'test_*.py'
PYTHONPATH=native_bridge python -m unittest discover -s native_bridge -p 'test_*.py'
python -m compileall -q custom_components/neolight native_bridge
```

The Scrypted plugin checks with `npm ci`, `npm run check`, and `npm run build`.
Pull requests also run HACS and Home Assistant hassfest validation.
The native media bridge needs a Linux host and an authorized paired monitor
for integration testing. Never infer a successful door opening from an API
success response alone.
