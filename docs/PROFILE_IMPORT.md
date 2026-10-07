# Build an app profile from your own NeoLight Android installation

The cloud controls need an app profile in addition to your NeoLight email and
password. The integration does not contain NeoLight's app key, any account
secret, or a device ID. This local helper builds the JSON for the HA setup
form from an app installation that you own or are authorized to inspect.

The profile builder was checked against a private capture from NeoLight
Android 1.1.0. The Frida collection helpers still need a fresh end-to-end
check on another installation. Other app versions may change request fields
or key format. Local camera setup in HA does not need these steps.

## Prepare the app

On a computer with Python 3.11 or later, install the local helper dependencies:

```sh
python3 -m venv ~/.config/neolight-venv
. ~/.config/neolight-venv/bin/activate
python -m pip install frida-tools aiohttp cryptography
```

Run the NeoLight Android app on your
own phone or emulator, sign in, and connect Frida to it. Open the paired
monitor once so its device object is loaded. See the
[Frida Android guide](https://frida.re/docs/android/) for device setup.
Keep the files below **outside this repository**:

```sh
mkdir -p ~/.config/neolight
chmod 700 ~/.config/neolight
python tools/extract_key.py --output ~/.config/neolight/signing.key
python tools/capture_device.py --output ~/.config/neolight/devices.json
python tools/capture_request.py --output ~/.config/neolight/request.json
```

While `capture_request.py` waits, open the paired monitor in NeoLight again
to generate a signed, read-only property request. It stops after one matching
request. `capture_device.py` prints only device names and zero-based indexes;
it saves device IDs in its private file. If several monitors are paired, use
the desired index in the next command.

```sh
python tools/build_profile.py \
  --request ~/.config/neolight/request.json \
  --key-file ~/.config/neolight/signing.key \
  --schema ~/.config/neolight/devices.json \
  --output ~/.config/neolight/profile.json
```

Add `--device-index N` if `devices.json` contains more than one device. The
builder verifies the signing key against the captured request before writing
the profile with owner-only file permissions. It never sends a network
request. Paste `profile.json` into **NeoLight → Link NeoLight account** in HA,
then enter your account email, password, and country calling code there.

Do not post the generated profile, request capture, key, or device file in an
issue or pull request. The [reverse engineering guide](REVERSE_ENGINEERING.md)
explains what to record when adding another model.
