"""Import boundaries and lazy namespace discovery."""
from pathlib import Path
import subprocess
import sys


def test_core_import_has_no_optional_dependencies():
    root = Path(__file__).resolve().parents[3]
    code = (
        "import sys; sys.path.insert(0, " + repr(str(root)) + "); "
        "import _sphinx_ext; from _sphinx_ext import _sphinx_ai_learn; "
        "assert '_sphinx_ai_learn' in dir(_sphinx_ext); "
        "assert callable(_sphinx_ai_learn.load_content_tree); assert callable(_sphinx_ai_learn.materialize); "
        "assert not any(k.split('.')[0] in ('sphinx','docutils','bs4','fastapi') for k in sys.modules)"
    )
    subprocess.run([sys.executable, "-I", "-c", code], check=True)
