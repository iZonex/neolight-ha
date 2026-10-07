"""Extract the app signing key from the owner's running NeoLight Android app.

The complete key is saved privately and never printed. The profile builder
later checks it against a signed request captured from the same app.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import time

from private_output import write_private_text


PACKAGE = "com.neolight.neo"

SOURCE = r"""
const prefix = 'com.neolight.neo_';
const pattern = Array.from(prefix, c => c.charCodeAt(0).toString(16).padStart(2, '0')).join(' ');
let found = null;
for (const range of Process.enumerateRanges({protection: 'rw-', coalesce: true})) {
  if (range.size > 134217728) continue;
  for (const match of Memory.scanSync(range.base, range.size, pattern)) {
    try {
      const value = match.address.readCString(260);
      if (/^com\.neolight\.neo_[A-F0-9:]{95}_[a-z0-9]{32}_[a-z0-9]{32}$/.test(value)) {
        found = value;
        break;
      }
    } catch (_) {}
  }
  if (found) break;
}
send({found: found});
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        import frida
    except ImportError:
        parser.error("Install frida-tools in this Python environment first")
    root = Path(__file__).resolve().parents[1]
    destination = args.output.resolve()
    if destination == root or root in destination.parents:
        parser.error("Write the private key outside the repository")
    device = frida.get_usb_device(timeout=10)
    process = next((item for item in device.enumerate_processes()
                    if item.name.lower() in {"neolight", PACKAGE}), None)
    if process is None:
        parser.error("Start and log in to NeoLight on the Android device first")
    session = device.attach(process.pid)
    result = None

    def on_message(message, _data):
        nonlocal result
        if message.get("type") == "send":
            payload = message.get("payload")
            if isinstance(payload, dict) and "found" in payload:
                result = payload["found"]

    script = session.create_script(SOURCE)
    script.on("message", on_message)
    script.load()
    try:
        for _ in range(300):
            if result is not None:
                break
            time.sleep(0.1)
    finally:
        script.unload()
        session.detach()
    if not isinstance(result, str) or not result:
        raise SystemExit("Signing key not found in the running app")
    if not re.fullmatch(r"com\.neolight\.neo_[A-F0-9:]{95}_[a-z0-9]{32}_[a-z0-9]{32}",
                        result):
        raise SystemExit("Extracted key failed format validation")
    write_private_text(destination, result + "\n")
    print(f"Saved private signing key to {destination}")


if __name__ == "__main__":
    main()
