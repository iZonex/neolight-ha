"""Build a private NeoLight app profile from an owner's Android capture.

The capture and signing key are read locally and are never printed. This tool
does not log in, publish data points, or contact the vendor API.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from private_output import write_private_text


ROOT = Path(__file__).resolve().parents[1]
STATIC_FIELDS = ("appVersion", "chKey", "clientId", "deviceId", "lang", "os", "ttid")


def _load_function(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(f"neolight_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, name)


def read_signing_key(path: Path) -> str:
    """Accept a key-only file or the private .env written by the Frida helper."""
    content = path.read_text().strip()
    if "\n" not in content and "=" not in content and content:
        return content
    matches = [line.partition("=")[2].strip() for line in content.splitlines()
               if line.startswith("NEOLIGHT_TUYA_SIGNING_KEY=")]
    if len(matches) != 1 or not matches[0]:
        raise ValueError("Expected one NEOLIGHT_TUYA_SIGNING_KEY in the key file")
    return matches[0]


def paired_device_id(schema_path: Path, index: int | None = None) -> str:
    devices = json.loads(schema_path.read_text())
    if not isinstance(devices, list) or not devices:
        raise ValueError("Device file contains no paired device")
    if index is None:
        if len(devices) != 1:
            raise ValueError("Choose --device-index for one of the paired devices")
        index = 0
    if index < 0 or index >= len(devices):
        raise ValueError("Device index is out of range")
    device_id = devices[index].get("device_id") if isinstance(devices[index], dict) else None
    if not isinstance(device_id, str) or not device_id:
        raise ValueError("Schema file has no paired device ID")
    return device_id


def build_profile(capture: dict, signing_key: str, device_id: str) -> dict:
    """Reject a mismatched key or incomplete capture before creating a profile."""
    if not isinstance(capture, dict):
        raise ValueError("Request capture must be a JSON object")
    url = urlsplit(capture.get("url", ""))
    if url.scheme != "https" or not url.hostname or url.path != "/api.json":
        raise ValueError("Capture must be an HTTPS /api.json request")
    pairs = parse_qsl(capture.get("body", ""), keep_blank_values=True)
    fields = dict(pairs)
    if len(fields) != len(pairs) or any(not fields.get(key) for key in STATIC_FIELDS):
        raise ValueError("Capture has duplicate or missing app fields")
    captured_sign = fields.get("sign")
    if not captured_sign or not signing_key:
        raise ValueError("Capture signature or signing key is missing")
    sign = _load_function(ROOT / "custom_components/neolight/mobile_api.py",
                          "sign_mobile_request")
    import hmac
    if not hmac.compare_digest(sign(fields, signing_key), captured_sign):
        raise ValueError("Signing key does not match the captured request")
    profile = {"api_host": url.hostname, "signing_key": signing_key,
               "paired_device_id": device_id,
               "static_fields": {key: fields[key] for key in STATIC_FIELDS}}
    validate = _load_function(ROOT / "custom_components/neolight/profile.py",
                              "parse_app_profile")
    validate(json.dumps(profile))
    return profile


def write_private(path: Path, profile: dict) -> None:
    write_private_text(path, json.dumps(profile, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True,
                        help="Private JSON capture of one signed app request")
    parser.add_argument("--key-file", type=Path, required=True,
                        help="Private signing-key file or helper .env")
    parser.add_argument("--schema", type=Path, required=True,
                        help="Private runtime schema JSON for one paired device")
    parser.add_argument("--device-index", type=int,
                        help="Zero-based index when several devices are paired")
    parser.add_argument("--output", type=Path, required=True,
                        help="Destination outside the public repository")
    args = parser.parse_args()
    destination = args.output.resolve()
    if destination == ROOT or ROOT in destination.parents:
        parser.error("Write the private profile outside the repository")
    profile = build_profile(json.loads(args.request.read_text()),
                            read_signing_key(args.key_file),
                            paired_device_id(args.schema, args.device_index))
    write_private(destination, profile)
    print(f"Wrote private profile to {destination}")


if __name__ == "__main__":
    main()
