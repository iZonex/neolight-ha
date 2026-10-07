"""Read paired device IDs from the owner's logged-in Android app.

Only Java getters are called; no relay or call command is sent.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from private_output import write_private_text


SOURCE = r"""
Java.perform(function () {
  const devices = [];
  Java.choose('com.thingclips.smart.sdk.bean.DeviceBean', {
    onMatch: function (device) {
      try {
        const schema = device.getSchemaMap();
        if (schema && schema.size() > 0)
          devices.push({device_id: String(device.getDevId()), name: String(device.getName())});
      } catch (_) {}
    },
    onComplete: function () { send({devices: devices}); }
  });
});
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
        parser.error("Write the private device list outside the repository")
    device = frida.get_usb_device(timeout=10)
    process = next((item for item in device.enumerate_processes()
                    if item.name.lower() in {"neolight", "com.neolight.neo"}), None)
    if process is None:
        parser.error("Start and log in to NeoLight on the Android device first")
    session = device.attach(process.pid)
    result = None

    def on_message(message, _data):
        nonlocal result
        if message.get("type") == "send":
            payload = message.get("payload")
            if isinstance(payload, dict) and isinstance(payload.get("devices"), list):
                result = payload["devices"]

    bridge = Path(frida.__file__).resolve().parent.parent / "frida_tools/bridges/java.js"
    script = session.create_script(bridge.read_text() + "\nvar Java=bridge;\n" + SOURCE)
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
    if not result:
        raise SystemExit("No paired device with a schema is loaded in NeoLight")
    write_private_text(destination, json.dumps(result))
    print(f"Saved {len(result)} private paired-device record(s) to {destination}")
    for index, item in enumerate(result):
        print(f"{index}: {item.get('name', 'Unnamed device')}")


if __name__ == "__main__":
    main()
