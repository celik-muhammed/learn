"""YouTube learning catalog: data model, query layer and Sphinx directive."""

from __future__ import annotations

__all__ = ["setup"]


def setup(app):
    """
    Register the ``youtube-gallery`` directive with a Sphinx application.

    Parameters
    ----------
    app : sphinx.application.Sphinx
        The Sphinx application to extend.

    Returns
    -------
    dict
        Extension metadata declaring parallel read/write safety.
    """
    from .directive import setup as _setup

    return _setup(app)
