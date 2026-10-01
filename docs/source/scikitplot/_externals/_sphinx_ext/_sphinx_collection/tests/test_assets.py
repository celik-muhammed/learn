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
    assert ".sk-collection-primary-row--pill-overflow" in css
    assert ".sk-collection-search-field {" in css
    assert ".sk-collection-search-field--pill" in css
    assert ".sk-collection-disclosure {" in css
    assert ".sk-collection-disclosure--overflow" in css
    assert ".sk-collection-overflow {" not in css

    assert "var controls = element('div','sk-collection-controls');" in js
    assert "var searchVariant=config.searchVariant==='classic'?'classic':'pill-overflow';" in js
    assert "sk-collection-primary-row--'+searchVariant" in js
    assert "sk-collection-search-field--pill" in js
    assert "sk-collection-disclosure--overflow" in js
    assert "sk-collection-overflow-icon" in js
    assert "controls.append(status,primary,panel);" in js
    assert "root.insertBefore(controls,root.firstChild);" in js
    assert "sk-collection-overflow='" not in js


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
    assert "if(polyline)polyline.setAttribute('points'" in js
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


def test_search_variant_is_one_shared_presentation_contract() -> None:
    assets = _assets_module()
    browser = (ROOT / "_sphinx_collection" / "_browser.py").read_text(encoding="utf-8")
    gallery = (ROOT / "_sphinx_gallery_grid" / "directive.py").read_text(encoding="utf-8")
    youtube = (ROOT / "_sphinx_youtube_gallery" / "directive.py").read_text(encoding="utf-8")
    conf = (ROOT.parent / "conf.py").read_text(encoding="utf-8")

    assert assets.SEARCH_VARIANTS == ("pill-overflow", "classic")
    assert '"searchVariant": options.get("search-variant", "pill-overflow")' in browser
    assert '"search-variant": search_variant_option' in gallery
    assert '"search_variant": search_variant_option' in gallery
    assert '"interactive": search_variant_option' in gallery
    assert '"searchable": search_variant_option' in gallery
    assert 'app.add_config_value(' in gallery
    assert '"collection_search_variant", "pill-overflow", "env", types=[str]' in gallery
    assert "collection_search_variant must be 'pill-overflow' or 'classic'" in gallery
    assert 'self.config.collection_search_variant' in gallery
    assert '"search-variant": search_variant_option' in youtube
    assert '"search_variant": search_variant_option' in youtube
    assert '"interactive": search_variant_option' in youtube
    assert '"searchable": search_variant_option' in youtube
    assert 'options["search-variant"] = resolve_search_variant(' in youtube
    assert 'collection_search_variant = "pill-overflow"  # alternative: "classic"' in conf


def test_per_directive_search_variant_supports_flags_shorthand_aliases_and_conflict_rejection() -> None:
    import sys

    source_root = ROOT.parent
    sys.path.insert(0, str(source_root))
    try:
        from _sphinx_ext._search_variant import resolve_search_variant, search_variant_option
    finally:
        sys.path.pop(0)

    assert search_variant_option(None) is None
    assert search_variant_option(" CLASSIC ") == "classic"
    assert resolve_search_variant({"interactive": None}, "pill-overflow") == "pill-overflow"
    assert resolve_search_variant({"interactive": "classic"}, "pill-overflow") == "classic"
    assert resolve_search_variant({"searchable": "pill-overflow"}, "classic") == "pill-overflow"
    assert resolve_search_variant({"search_variant": "classic"}, "pill-overflow") == "classic"
    assert resolve_search_variant({"search-variant": "classic", "interactive": "classic"}, "pill-overflow") == "classic"
    assert resolve_search_variant({"interactive": None, "search_variant": "classic"}, "pill-overflow") == "classic"
    assert resolve_search_variant({"searchable": "pill-overflow", "search_variant": "pill-overflow"}, "classic") == "pill-overflow"
    try:
        resolve_search_variant({"interactive": "classic", "search-variant": "pill-overflow"}, "pill-overflow")
    except ValueError as exc:
        assert "conflicting search variants" in str(exc)
    else:
        raise AssertionError("conflicting per-directive search variants must fail closed")


def test_leaf_youtube_layers_remain_search_ui_free() -> None:
    core = (ROOT / "_sphinx_youtube_core" / "__init__.py").read_text(encoding="utf-8")
    contrib = (ROOT / "_sphinxcontrib_youtube" / "__init__.py").read_text(encoding="utf-8")
    assert "owns no browser/search controls" in core
    assert "centralized" in contrib and "_sphinx_collection" in contrib
    assert "search-variant" not in core
    assert "search-variant" not in contrib


def test_collection_assets_are_html_only_and_atomically_written() -> None:
    setup = (ROOT / "_sphinx_collection" / "setup.py").read_text(encoding="utf-8")
    assert 'getattr(getattr(app, "builder", None), "format", None) != "html"' in setup
    assert 'def _write_asset_atomic(path: Path, content: str)' in setup
    assert 'os.replace(temporary, path)' in setup
    assert 'path.read_bytes() == data' in setup
    assert '.write_text(ASSET_CSS' not in setup
    assert '.write_text(ASSET_JS' not in setup


def test_collection_asset_registration_runtime_is_html_only_and_idempotent(tmp_path) -> None:
    import ast
    import os
    import tempfile
    from types import SimpleNamespace

    source_path = ROOT / "_sphinx_collection" / "setup.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    wanted = {"_write_asset_atomic", "ensure_assets"}
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]

    class Logger:
        def warning(self, *args, **kwargs):
            raise AssertionError(f"unexpected asset warning: {args!r}")

    namespace = {
        "Path": Path,
        "os": os,
        "tempfile": tempfile,
        "_FLAG": "_registered",
        "_CSS_NAME": "sk-collection.css",
        "_JS_NAME": "sk-collection.js",
        "ASSET_CSS": "body{display:block}",
        "ASSET_JS": "console.log('ok');",
        "logger": Logger(),
        "Any": object,
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source_path), "exec"), namespace)
    ensure = namespace["ensure_assets"]

    calls = []
    app = SimpleNamespace(
        builder=SimpleNamespace(format="latex"),
        outdir=str(tmp_path / "latex"),
        add_css_file=lambda *args, **kwargs: calls.append(("css", args, kwargs)),
        add_js_file=lambda *args, **kwargs: calls.append(("js", args, kwargs)),
    )
    ensure(app)
    assert calls == []
    assert not (tmp_path / "latex").exists()

    app.builder.format = "html"
    app.outdir = str(tmp_path / "html")
    ensure(app)
    assert [row[0] for row in calls] == ["css", "js"]
    assert (tmp_path / "html" / "_static" / "sk-collection.css").read_text() == "body{display:block}"
    assert (tmp_path / "html" / "_static" / "sk-collection.js").read_text() == "console.log('ok');"
    before = (tmp_path / "html" / "_static" / "sk-collection.js").stat().st_mtime_ns
    ensure(app)
    after = (tmp_path / "html" / "_static" / "sk-collection.js").stat().st_mtime_ns
    assert before == after
    assert [row[0] for row in calls] == ["css", "js"]
