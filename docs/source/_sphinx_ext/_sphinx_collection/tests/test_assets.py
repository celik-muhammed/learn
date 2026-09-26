from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSETS_PATH = ROOT / "_sphinx_collection" / "assets.py"


def _assets_module():
    spec = importlib.util.spec_from_file_location("_sphinx_collection_assets_test", ASSETS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_compact_controls_use_one_inline_shell() -> None:
    assets = _assets_module()
    css = assets.ASSET_CSS
    js = assets.ASSET_JS

    assert ".sk-collection-controls {" in css
    assert ".sk-collection-primary-row {" in css
    assert ".sk-collection-search-field {" in css
    assert ".sk-collection-disclosure {" in css
    assert ".sk-collection-overflow" not in css

    assert "var controls = element('div','sk-collection-controls');" in js
    assert "var primary=element('div','sk-collection-primary-row');" in js
    assert "var searchField=element('div','sk-collection-search-field');" in js
    assert "var toggle=element('button','sk-collection-disclosure','');" in js
    assert "controls.append(status,primary,panel);" in js
    assert "root.insertBefore(controls,root.firstChild);" in js
    assert "sk-collection-overflow" not in js


def test_search_is_live_and_ime_safe() -> None:
    js = _assets_module().ASSET_JS

    assert "input.addEventListener('input',function(event){if(!event.isComposing)apply();});" in js
    assert "input.addEventListener('compositionend',apply);" in js
    assert "searchWrap.addEventListener('submit',function(event){event.preventDefault();apply();input.focus();});" in js
    assert "if(event.key==='Enter' && event.isComposing)event.preventDefault();" in js


def test_disclosure_is_inline_not_popup_autoclose() -> None:
    js = _assets_module().ASSET_JS

    assert "toggle.setAttribute('aria-haspopup','true')" in js
    assert "toggle.setAttribute('aria-expanded','false')" in js
    assert "polyline.setAttribute('points','6 9 12 15 18 9')" in js
    assert "panel.hidden=!open" in js
    assert "open?'6 15 12 9 18 15':'6 9 12 15 18 9'" in js
    assert "document.addEventListener('pointerdown'" not in js
    assert "More options" in js


def test_youtube_layers_keep_collection_as_browser_ui_owner() -> None:
    collection = (ROOT / "_sphinx_collection" / "README.md").read_text(encoding="utf-8")
    core = (ROOT / "_sphinx_youtube_core" / "__init__.py").read_text(encoding="utf-8")
    gallery = (ROOT / "_sphinx_youtube_gallery" / "README.md").read_text(encoding="utf-8")
    contrib = (ROOT / "_sphinxcontrib_youtube" / "__init__.py").read_text(encoding="utf-8")
    directive = (ROOT / "_sphinx_youtube_gallery" / "directive.py").read_text(encoding="utf-8")

    assert "owns the progressive browser UI" in collection
    assert "owns no browser/search controls" in core
    assert "same compact search/disclosure interaction as" in gallery
    assert "centralized" in contrib and "_sphinx_collection" in contrib
    assert "one implementation" in directive
    assert "for key in (\"searchable\", \"interactive\")" in directive


def test_expanded_panel_has_grouped_information_architecture() -> None:
    assets = _assets_module()
    css = assets.ASSET_CSS
    js = assets.ASSET_JS

    assert ".sk-collection-panel-section {" in css
    assert ".sk-collection-view-grid {" in css
    assert ".sk-collection-tools-grid {" in css
    assert ".sk-collection-tool[open] { grid-column:1 / -1;" in css
    assert ".sk-collection-tool-body {" in css
    assert "sk-collection-close" not in css

    assert "sk-collection-panel-title','View'" in js
    assert "sk-collection-panel-title','Gallery tools'" in js
    assert "sk-collection-tool sk-collection-add-details" in js
    assert "sk-collection-tool sk-collection-preferences" in js
    assert "sk-collection-tool sk-collection-export" in js
    assert "Restore original gallery" in js
    assert "tool.addEventListener('toggle'" in js
    assert "other!==tool&&other.parentElement===toolsGrid" in js
    assert "Close options" not in js
    assert "Reset view clears search, filters and sorting" not in js


def test_expanded_panel_keeps_escape_as_single_close_path() -> None:
    js = _assets_module().ASSET_JS

    assert "panel.addEventListener('keydown',function(event){if(event.key==='Escape')" in js
    assert "toggle.focus()" in js
    assert "close.addEventListener" not in js
