"""Work around @scrypted/sdk's webpack export reference in a legacy plugin.

The SDK writes to ``exports.sdk`` inside its CommonJS fallback. Webpack 5
rewrites the export declaration to ``__webpack_exports__.sdk`` but leaves two
Object.assign calls unchanged. In Scrypted's legacy eval loader ``exports`` is
the outer module, so the SDK object remains undefined. Keep this narrow fix
until the SDK build is corrected upstream.
"""

from pathlib import Path
import zipfile


root = Path(__file__).resolve().parent
output = root / "out"
bundle_path = output / "main.nodejs.js"
bundle = bundle_path.read_text()
old = "Object.assign(exports.sdk,"
if bundle.count(old) != 3:
    raise RuntimeError("Unexpected Scrypted SDK bundle shape")
bundle = bundle.replace(old, "Object.assign(__webpack_exports__.sdk,")
old_default = "exports.default = exports.sdk;"
if bundle.count(old_default) != 1:
    raise RuntimeError("Unexpected Scrypted SDK default export shape")
bundle = bundle.replace(old_default, "__webpack_exports__.default = __webpack_exports__.sdk;")
bundle_path.write_text(bundle)

with zipfile.ZipFile(output / "plugin.zip", "w", zipfile.ZIP_DEFLATED) as archive:
    archive.write(bundle_path, "main.nodejs.js")
    archive.write(output / "main.nodejs.js.map", "main.nodejs.js.map")
print("Scrypted SDK bundle prepared")
