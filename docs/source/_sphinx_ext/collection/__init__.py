"""
Domain-agnostic selection engine for Sphinx collection directives.

Filtering, sorting, grouping and pagination over plain mappings, with no
knowledge of what the mappings describe. ``gallery-grid`` and
``youtube-gallery`` are both consumers; so is anything else that renders a
list of YAML records.
"""

from .assets import CONTAINER_CLASS, SEARCHABLE_CLASS
from .sections import SECTION_STYLES, render_sections, sections_allowed
from .setup import ensure_assets
from .select import (
    FilterError,
    Selection,
    apply_selection,
    group_records,
    parse_filter,
)

__all__ = [
    "CONTAINER_CLASS",
    "SEARCHABLE_CLASS",
    "ensure_assets",
    "SECTION_STYLES",
    "render_sections",
    "sections_allowed",
    "FilterError",
    "Selection",
    "apply_selection",
    "group_records",
    "parse_filter",
]
