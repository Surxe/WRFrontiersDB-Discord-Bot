"""Build codes: the short strings in the Site's `/models?a=<code>&b=<code>` links.

Both the format and the codec belong to WRFrontiersDB-Data: its registry
(`index/build_codes.json`) and its reference codec (`tools/wrfdb_data/build_code.py`)
are loaded from the `DATA_DIR` clone, so the bot never has its own copy. A
decoded build is `{slot key: Module id}` (`chassis`, `torso`, `Shoulder_L`,
`Shoulder_L.Shoulder_Weapon_0`, ...).

A code made from newer data than `DATA_DIR` holds raises `BuildCodes.TooNew`.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

CODEC_REL = Path('tools') / 'wrfdb_data' / 'build_code.py'
"""The reference codec in a Data clone; standalone (no package imports)."""

Build = dict[str, str]


class BuildCodesError(RuntimeError):
    """The Data clone's codec or registry could not be loaded."""


def load_codec_module(data_dir: Path) -> ModuleType:
    """Import Data's codec from the clone by path, without touching sys.path."""
    path = Path(data_dir) / CODEC_REL
    spec = importlib.util.spec_from_file_location('wrfdb_data_build_code', path)
    if spec is None or spec.loader is None:
        raise BuildCodesError(f'No build-code codec at {path}')
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except (OSError, SyntaxError) as e:
        raise BuildCodesError(f'Could not load the build-code codec {path}: {e}') from e
    return module


class BuildCodes:
    """Data's codec over one registry document."""

    def __init__(self, codec_module: ModuleType, registry: dict):
        self.registry = registry
        self._codec = codec_module.BuildCodec(registry)
        self.Error: type[Exception] = codec_module.BuildCodeError
        """Not a build code (or not one this registry can read)."""
        self.TooNew: type[Exception] = codec_module.TooNew
        """A code from newer data than this registry; a subclass of Error."""

    def decode(self, code: str) -> Build:
        return self._codec.decode(code)
