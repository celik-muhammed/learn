"""
Sphinx wiring for the shared collection assets.

Registers the CSS and JS from :mod:`.assets` exactly once, whichever
collection directive asks for them first, when a consuming extension initializes.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from sphinx.util import logging

logger = logging.getLogger(__name__)

from .assets import ASSET_CSS, ASSET_JS

__all__ = ["ensure_assets", "mark_used"]

_CSS_NAME = "sk-collection.css"
_JS_NAME = "sk-collection.js"
_FLAG = "_sk_collection_assets_registered"


def _write_asset_atomic(path: Path, content: str) -> None:
    """Replace one generated browser asset atomically only when bytes changed."""
    data = content.encode("utf-8")
    try:
        if path.is_file() and path.read_bytes() == data:
            return
    except OSError:
        # The normal write path below will surface the actionable warning.
        pass
    fd, temporary = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:  # ruff: ignore[suppressible-exception]
            os.close(fd)
        except OSError:
            pass
        try:  # ruff: ignore[suppressible-exception]
            os.unlink(temporary)
        except OSError:
            pass
        raise


def ensure_assets(app: Any) -> None:
    """
    Register the collection stylesheet and script once per application.

    Parameters
    ----------
    app : sphinx.application.Sphinx
        The Sphinx application.

    Notes
    -----
    Idempotent: several directives call this during their own ``setup()``,
    and registering the same file twice would emit it twice into every page.

    Filesystem failures produce warnings and allow a retry. The assets are
    progressive enhancement -- the
    gallery is complete without them -- so a read-only static directory or
    an unusual builder should degrade to a plain grid, not break the build.
    """
    if getattr(app, _FLAG, False):
        return
    if getattr(getattr(app, "builder", None), "format", None) != "html":
        return

    try:
        static_dir = Path(app.outdir) / "_static"
        static_dir.mkdir(parents=True, exist_ok=True)
        _write_asset_atomic(static_dir / _CSS_NAME, ASSET_CSS)
        _write_asset_atomic(static_dir / _JS_NAME, ASSET_JS)
        app.add_css_file(_CSS_NAME)
        # `defer` because the script only rearranges already-rendered DOM;
        # blocking the parser for it would slow down the very pages it
        # exists to speed up.
        app.add_js_file(_JS_NAME, defer="defer")
        setattr(app, _FLAG, True)
    except OSError as exc:
        logger.warning("Could not write gallery assets: %s", exc)


def mark_used(directive: Any) -> None:
    """
    Note that the current document uses a collection directive.

    Parameters
    ----------
    directive : docutils.parsers.rst.Directive
        The directive being executed.

    Notes
    -----
    Currently a no-op hook. It exists so that per-page asset inclusion can
    be added later without changing any call site.
    """
    return
