"""Write extracted account material atomically with owner-only permissions."""

import os
from pathlib import Path
import tempfile


def write_private_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=f".{path.name}-",
                                     delete=False) as handle:
        os.chmod(handle.name, 0o600)
        handle.write(content)
        temporary = handle.name
    os.replace(temporary, path)
