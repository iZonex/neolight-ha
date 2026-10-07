"""Capture one signed read-only request from the owner's logged-in Android app.

Requires Frida connected to a device or emulator running NeoLight. The output
contains a session signature and must remain private.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from private_output import write_private_text


SOURCE = r"""
Java.perform(function () {
  const RealCall = Java.use('okhttp3.internal.connection.RealCall');
  const Buffer = Java.use('okio.Buffer');
  const enqueue = RealCall.enqueue.overload('okhttp3.Callback');
  enqueue.implementation = function (callback) {
    try {
      const request = this.request();
      if (String(request.url().encodedPath()) === '/api.json') {
        const body = request.body();
        if (body && !body.isDuplex() && !body.isOneShot()) {
          const buffer = Buffer.$new();
          body.writeTo(buffer);
          const raw = String(buffer.readUtf8());
          if (raw.indexOf('s.m.dev.property.get') >= 0)
            send({url: String(request.url()), body: raw});
        }
      }
    } catch (_) {}
    return enqueue.call(this, callback);
  };
  send({ready: true});
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
        parser.error("Write the private capture outside the repository")
    device = frida.get_usb_device(timeout=10)
    process = next((item for item in device.enumerate_processes()
                    if item.name.lower() in {"neolight", "com.neolight.neo"}), None)
    if process is None:
        parser.error("Start and log in to NeoLight on the Android device first")
    session = device.attach(process.pid)
    capture = None
    ready = False

    def on_message(message, _data):
        nonlocal capture, ready
        if message.get("type") != "send":
            return
        payload = message.get("payload")
        if isinstance(payload, dict) and payload.get("ready"):
            ready = True
        elif isinstance(payload, dict) and "url" in payload and "body" in payload:
            capture = payload

    bridge = Path(frida.__file__).resolve().parent.parent / "frida_tools/bridges/java.js"
    script = session.create_script(bridge.read_text() + "\nvar Java=bridge;\n" + SOURCE)
    script.on("message", on_message)
    script.load()
    try:
        import time
        for _ in range(900):
            if capture:
                break
            time.sleep(0.1)
    finally:
        script.unload()
        session.detach()
    if not capture:
        raise SystemExit("No signed read-only request observed; open the paired device in NeoLight")
    write_private_text(destination, json.dumps(capture))
    print(f"Saved private signed request to {destination}")


if __name__ == "__main__":
    main()
