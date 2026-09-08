"""
The ``youtube-gallery`` Sphinx directive.

Renders a queried slice of a YouTube catalog as a Sphinx Design grid, a
thumbnail wall, or a compact link list, from either a ``.md`` (MyST) or a
``.rst`` page.

Architecture
------------
The directive is the *render* layer only. It performs no network access and
holds no knowledge of the YouTube API::

    tools/youtube_sync.py   -->   _data/youtube/*.yaml   -->   youtube-gallery
    (explicit, online)            (committed, reviewed)        (build, offline)

Keeping acquisition out of the build is what makes documentation builds
deterministic and reproducible: the same commit always produces the same
HTML, a Read the Docs build never fails because of an API quota or a socket
timeout, and a reviewer can see in the diff exactly which videos a pull
request adds.

Rendering is delegated to the existing ``gallery-grid`` directive rather
than emitting Sphinx Design markup a second time, so the grid stays
byte-identical to the rest of the site and the MyST fence-safety handling
lives in exactly one place.

Notes
-----
**User-focused.** One directive covers every scenario: the whole catalog
sorted and filtered, sections per playlist, a single channel or playlist, a
date interval, or an inline list of links written straight into the page.

**Developer-focused.** Every option is validated before any output is
produced, and every failure is reported through docutils with a file and
line number so a bad option never aborts the build.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any, ClassVar

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.statemachine import StringList
from sphinx.application import Sphinx
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective
from yaml import YAMLError, safe_dump, safe_load

from ..collection import (
    CONTAINER_CLASS,
    SEARCHABLE_CLASS,
    SECTION_STYLES,
    ensure_assets,
    render_sections,
)
from .model import CatalogError, VideoRecord, normalize_catalog
from .query import Query, apply_query, group_records

logger = logging.getLogger(__name__)

__all__ = ["YouTubeGalleryDirective", "setup"]

#: Presentation modes, in increasing order of page weight.
#:
#: ``list``
#:     A plain bullet list of links. No images, no iframes. The only mode
#:     that stays usable at four-figure record counts.
#: ``thumbnail``
#:     A grid of cards, each a remote thumbnail image linking out to
#:     YouTube. One image request per card, no third-party player code.
#: ``embed``
#:     A grid of cards, each an inline ``youtube`` player.
#: ``auto``
#:     ``embed`` at or below :data:`DEFAULT_MAX_EMBEDS` records, otherwise
#:     ``thumbnail``.
MODES = ("auto", "embed", "thumbnail", "list")

#: Default ceiling on inline players per page.
#:
#: Each embed is a third-party iframe that loads the YouTube player. Even
#: with ``loading="lazy"``, a page of several hundred embeds is slow to
#: parse, heavy on memory, and hostile to assistive technology, which has to
#: traverse every frame. Above this ceiling ``auto`` degrades to thumbnails,
#: which look the same in a grid but cost one static image each.
DEFAULT_MAX_EMBEDS = 24

#: Remote thumbnail URL template. ``hqdefault`` is used rather than
#: ``maxresdefault`` because it is generated for *every* video, including
#: older and lower-resolution uploads; ``maxresdefault`` 404s for many and
#: would leave broken images scattered through a large gallery.
THUMBNAIL_URL = "https://i.ytimg.com/vi/{id}/hqdefault.jpg"


def _mode_choice(argument: str) -> str:
    """
    Validate the ``:mode:`` option.

    Parameters
    ----------
    argument : str
        Raw option text.

    Returns
    -------
    str
        One of :data:`MODES`.

    Raises
    ------
    ValueError
        If the value is not a known mode. Docutils turns this into a located
        directive error.
    """
    return directives.choice(argument.strip().lower(), MODES)


def _comma_list(argument: str) -> list[str]:
    """
    Split a comma-separated option value into a list of trimmed strings.

    Parameters
    ----------
    argument : str
        Raw option text, e.g. ``"pca, clustering"``.

    Returns
    -------
    list of str
        Non-empty, whitespace-trimmed entries.
    """
    if not argument:
        return []
    return [part.strip() for part in argument.split(",") if part.strip()]


def _format_duration(seconds: int | None) -> str:
    """
    Render a duration in seconds as a compact clock string.

    Parameters
    ----------
    seconds : int or None
        Runtime in seconds.

    Returns
    -------
    str
        ``"H:MM:SS"``, ``"M:SS"``, or ``""`` when ``seconds`` is ``None``.

    Examples
    --------
    >>> _format_duration(3750)
    '1:02:30'
    >>> _format_duration(150)
    '2:30'
    >>> _format_duration(None)
    ''
    """
    if seconds is None:
        return ""
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


class YouTubeGalleryDirective(SphinxDirective):
    """
    Render a queried slice of a YouTube catalog.

    The directive takes an optional argument naming a catalog file, relative
    to the current document. With no argument it falls back to the
    ``youtube_catalog_path`` configuration value, and with directive content
    it treats that content as an inline catalog, which is how an author
    writes a short, explicit list of links without maintaining a data file.

    Options
    -------
    catalog : path
        Catalog file, equivalent to the positional argument.
    channel, playlist : str
        Restrict to one channel or playlist, by display name or by stable
        id.
    tags : comma-separated str
        Keep records carrying all of the given tags.
    match : str
        Case-insensitive substring over title and description.
    match-regex : str
        Case-insensitive regular expression over title and description.
    since, until : ISO date
        Half-open publication interval.
    sort : str
        ``title``, ``published``, ``duration``, ``position``, ``channel``,
        ``playlist`` or ``none``; prefix with ``-`` to reverse.
    group-by : str
        ``playlist``, ``channel``, ``year`` or ``none``.
    limit, offset : int
        Pagination over the sorted result.
    mode : str
        One of :data:`MODES`.
    columns : str
        Responsive column counts passed through to ``gallery-grid``.
    show-duration, show-description : flag
        Include the runtime / description on each card.
    class-card, class-container : str
        Extra CSS classes, passed through to ``gallery-grid``.
    """

    name = "youtube-gallery"
    has_content = True
    required_arguments = 0
    optional_arguments = 1
    final_argument_whitespace = True
    option_spec: ClassVar[dict[str, Any]] = {
        "catalog": directives.unchanged,
        "channel": directives.unchanged,
        "playlist": directives.unchanged,
        "tags": _comma_list,
        "match": directives.unchanged,
        "match-regex": directives.unchanged,
        "since": directives.unchanged,
        "until": directives.unchanged,
        "sort": directives.unchanged,
        "group-by": directives.unchanged,
        "limit": directives.nonnegative_int,
        "offset": directives.nonnegative_int,
        "mode": _mode_choice,
        "columns": directives.unchanged,
        "show-duration": directives.flag,
        "show-description": directives.flag,
        "class-card": directives.unchanged,
        "class-container": directives.unchanged,
        "section-style": lambda argument: directives.choice(
            (argument or "auto").strip().lower(), SECTION_STYLES
        ),
        "searchable": directives.flag,
        "search-label": directives.unchanged,
    }

    # -- input -------------------------------------------------------------

    def _load_records(self) -> list[VideoRecord]:
        """
        Resolve and load the catalog for this directive invocation.

        Precedence is explicit and single-valued: directive content, then
        the positional argument, then the ``:catalog:`` option, then the
        ``youtube_catalog_path`` config value. Exactly one source is used,
        so a page never silently merges two catalogs.

        Returns
        -------
        list of VideoRecord
            The normalized catalog.

        Raises
        ------
        CatalogError
            If no source is configured, the file is missing, the YAML is
            unparseable, or a record fails to normalize.
        """
        if self.content:
            payload = self._parse_yaml(
                "\n".join(self.content), "youtube-gallery directive content"
            )
            return normalize_catalog(payload, "youtube-gallery directive content")

        reference = None
        if self.arguments:
            reference = self.arguments[0].strip()
        elif self.options.get("catalog"):
            reference = self.options["catalog"].strip()

        if reference:
            from .._pydata_sphinx_theme.gallery_directive import (
                _confined_path,
            )

            try:
                path = _confined_path(self, reference)
            except ValueError as exc:
                raise CatalogError(str(exc)) from exc
        else:
            configured = getattr(self.env.config, "youtube_catalog_path", "")
            if not configured:
                raise CatalogError(
                    "no catalog given: pass a path as the directive argument, "
                    "set the ':catalog:' option, write the videos as directive "
                    "content, or set 'youtube_catalog_path' in conf.py"
                )
            path = (Path(self.env.srcdir) / configured).resolve()

        if not path.exists():
            raise CatalogError(f"catalog file not found: {path}")

        # Register before reading so that editing the catalog invalidates
        # this document on an incremental build. Without it the page keeps
        # serving stale HTML until someone runs a clean build -- the single
        # most confusing failure mode of a generated-data pipeline.
        self.env.note_dependency(str(path))
        # A catalog saved as latin-1 or cp1252 otherwise raised an unhandled
        # `UnicodeDecodeError` that aborted the whole build; it is an input
        # problem and belongs in a located directive error.
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            raise CatalogError(
                f"could not read {path}: {exc}. Catalog files must be UTF-8 "
                f"encoded."
            ) from exc
        payload = self._parse_yaml(text, str(path))
        return normalize_catalog(payload, str(path))

    @staticmethod
    def _parse_yaml(text: str, origin: str) -> Any:
        """
        Parse YAML, converting parser errors into :class:`CatalogError`.

        Parameters
        ----------
        text : str
            YAML source.
        origin : str
            Description of where the text came from, for the error message.

        Returns
        -------
        Any
            The parsed payload.

        Raises
        ------
        CatalogError
            If the text is not valid YAML.
        """
        try:
            return safe_load(text)
        except YAMLError as exc:
            raise CatalogError(f"{origin}: could not parse YAML: {exc}") from exc

    def _build_query(self) -> Query:
        """
        Translate directive options into a :class:`Query`.

        Returns
        -------
        Query
            The validated query.

        Raises
        ------
        CatalogError
            If any option value is invalid.
        """
        from .model import parse_timestamp

        def _bound(name: str) -> _dt.datetime | None:
            """Parse a date option, prefixing errors with the option name."""
            raw = self.options.get(name)
            if not raw:
                return None
            try:
                return parse_timestamp(raw.strip())
            except CatalogError as exc:
                raise CatalogError(f"option ':{name}:' -- {exc}") from exc

        def _identifier(name: str, attribute: str) -> str:
            """
            Read a channel/playlist option, accepting a URL or a bare name.

            A page author copying a link has no reason to know which
            substring of it is the id, so a URL is reduced to its identifier
            here. Anything that is not a URL is passed through untouched, so
            filtering by a human-readable display name keeps working.
            """
            raw = self.options.get(name, "").strip()
            if not raw or "/" not in raw:
                return raw
            from .reference import ReferenceError, parse_reference

            try:
                reference = parse_reference(raw)
            except ReferenceError as exc:
                raise CatalogError(f"option ':{name}:' -- {exc}") from exc
            resolved = getattr(reference, attribute, "")
            if not resolved and attribute == "channel_id":
                # A handle or vanity name is a perfectly good filter value
                # when the catalog records it; only a URL with no channel
                # component at all is an error.
                resolved = reference.handle or reference.channel_name
            if not resolved:
                raise CatalogError(
                    f"option ':{name}:' -- {raw!r} names {reference.describe()}, "
                    f"which carries no {name} identifier"
                )
            return resolved

        return Query(
            channel=_identifier("channel", "channel_id"),
            playlist=_identifier("playlist", "playlist_id"),
            tags=tuple(self.options.get("tags", ())),
            match=self.options.get("match", "").strip(),
            match_regex=self.options.get("match-regex", "").strip(),
            since=_bound("since"),
            until=_bound("until"),
            sort_by=self.options.get("sort", "none").strip() or "none",
            group_by=self.options.get("group-by", "none").strip() or "none",
            limit=self.options.get("limit"),
            offset=self.options.get("offset", 0),
        )

    # -- output ------------------------------------------------------------

    def _resolve_mode(self, count: int) -> str:
        """
        Decide the presentation mode for ``count`` records.

        Parameters
        ----------
        count : int
            Number of records that will be rendered.

        Returns
        -------
        str
            A concrete mode: never ``"auto"``.

        Notes
        -----
        An explicit ``:mode: embed`` is always honoured -- the author may
        know something the heuristic does not -- but exceeding the embed
        budget emits a warning naming the count and the ceiling, so the
        cost is visible in the build log rather than only in a browser
        profile.
        """
        budget = getattr(self.env.config, "youtube_catalog_max_embeds", DEFAULT_MAX_EMBEDS)
        requested = self.options.get("mode", "auto")
        if requested == "auto":
            return "embed" if count <= budget else "thumbnail"
        if requested == "embed" and count > budget:
            logger.warning(
                f"youtube-gallery: rendering {count} inline players exceeds "
                f"the budget of {budget} "
                f"(youtube_catalog_max_embeds). Consider ':mode: thumbnail', "
                f"':mode: list', or ':limit:' to keep the page responsive.",
                location=self.get_location(),
            )
        return requested

    def _card(self, record: VideoRecord, mode: str, rst: bool) -> dict[str, Any]:
        """
        Build one ``gallery-grid`` item mapping for a record.

        Parameters
        ----------
        record : VideoRecord
            The video to render.
        mode : str
            ``"embed"`` or ``"thumbnail"``.
        rst : bool
            Whether the calling page is reStructuredText, which decides the
            directive syntax used for an embedded player.

        Returns
        -------
        dict
            An item mapping in the shape ``gallery-grid`` consumes.
        """
        title = record.title
        if "show-duration" in self.options and record.duration is not None:
            title = f"{title} ({_format_duration(record.duration)})"

        item: dict[str, Any] = {"title": title}

        if mode == "embed":
            # `gallery-grid` treats `content` as opaque source text for the
            # page's own markup language, so the player is written in that
            # language rather than as pre-rendered HTML.
            if rst:
                item["content"] = f".. youtube:: {record.id}\n"
            else:
                item["content"] = f"```{{youtube}} {record.id}\n```\n"
            if "show-description" in self.options and record.description:
                item["content"] += f"\n{record.description}\n"
        else:
            item["link"] = record.url
            item["link-alt"] = f"Watch \u201c{record.title}\u201d on YouTube"
            item["img-top"] = THUMBNAIL_URL.format(id=record.id)
            # Without this the thumbnail is emitted as `alt=""`, which marks
            # it *decorative* -- so a screen reader announces nothing at all
            # for the one element that identifies the video. On a
            # thumbnail-mode page the image is the content, not decoration
            # (WCAG 2.1 SC 1.1.1).
            item["img-alt"] = f"Video thumbnail: {record.title}"
            if "show-description" in self.options and record.description:
                item["content"] = record.description

        return item

    def _render_grid(
        self, records: list[VideoRecord], mode: str, rst: bool
    ) -> str:
        """
        Emit ``gallery-grid`` source for a list of records.

        Parameters
        ----------
        records : list of VideoRecord
            Records for this grid.
        mode : str
            ``"embed"`` or ``"thumbnail"``.
        rst : bool
            Whether to emit reStructuredText rather than MyST.

        Returns
        -------
        str
            Directive source ready for ``nested_parse``.

        Notes
        -----
        The item list is serialised with :func:`yaml.safe_dump` rather than
        assembled by string formatting. Titles legitimately contain colons,
        quotes, ``#`` and non-ASCII text, all of which would corrupt
        hand-built YAML; a serialiser makes correct escaping structural
        rather than something each call site has to remember.
        """
        items = [self._card(record, mode, rst) for record in records]
        body = safe_dump(
            items, default_flow_style=False, allow_unicode=True, sort_keys=False
        )

        options = {"grid-columns": self.options.get("columns", "1 2 2 3")}
        for key in ("class-card", "class-container"):
            if self.options.get(key):
                options[key] = self.options[key]

        if rst:
            option_lines = "\n".join(f"   :{k}: {v}" for k, v in options.items())
            indented = "\n".join(
                f"   {line}" if line.strip() else line for line in body.splitlines()
            )
            return f".. gallery-grid::\n{option_lines}\n\n{indented}\n"

        option_lines = "\n".join(f":{k}: {v}" for k, v in options.items())
        # A colon fence cannot be closed by the backtick fences the embedded
        # players use, so the player markup can never terminate this block
        # early however deeply it nests.
        return f":::::{{gallery-grid}}\n{option_lines}\n\n{body}\n:::::\n"

    def _render_list(self, records: list[VideoRecord], rst: bool) -> str:
        """
        Emit a plain bullet list of links.

        Parameters
        ----------
        records : list of VideoRecord
            Records to list.
        rst : bool
            Whether to emit reStructuredText rather than Markdown.

        Returns
        -------
        str
            Markup source ready for ``nested_parse``.

        Notes
        -----
        This mode exists for four-figure catalogs, where a grid of images is
        itself the performance problem. It renders one line per video with
        no external requests at all.
        """
        lines = []
        for record in records:
            suffix = ""
            if "show-duration" in self.options and record.duration is not None:
                suffix = f" — {_format_duration(record.duration)}"
            # Escape the delimiters that would otherwise terminate the link
            # label early when a title legitimately contains one.
            label = record.title.replace("]", "\\]").replace("<", "\\<")
            if rst:
                lines.append(f"* `{label} <{record.url}>`__{suffix}")
            else:
                lines.append(f"- [{label}]({record.url}){suffix}")
        return "\n".join(lines) + "\n"

    def _is_rst(self) -> bool:
        """
        Detect whether the calling document is reStructuredText.

        Uses Sphinx's own ``source_suffix`` mapping -- the same mechanism
        Sphinx uses to choose a parser -- so projects with custom suffix
        mappings are handled correctly.

        Returns
        -------
        bool
            ``True`` for a reStructuredText page.
        """
        suffix = Path(self.env.doc2path(self.env.docname)).suffix
        source_suffix = self.env.config.source_suffix
        parser = source_suffix.get(suffix) if isinstance(source_suffix, dict) else None
        return parser == "restructuredtext" or suffix == ".rst"

    def run(self) -> list[nodes.Node]:
        """
        Execute the directive.

        Returns
        -------
        list of docutils.nodes.Node
            The rendered nodes, or a single error node when the catalog or
            the options are invalid. Errors are always *returned*, never
            raised, so one bad directive cannot abort the build.
        """
        try:
            records = self._load_records()
            query = self._build_query()
        except CatalogError as exc:
            return [
                self.state_machine.reporter.error(
                    f"youtube-gallery: {exc}", line=self.lineno
                )
            ]

        selected, total = apply_query(records, query)

        if not selected:
            # An empty result is far more often a typo in a filter than a
            # deliberate empty section, so it is surfaced -- but as a
            # warning, leaving the page renderable.
            logger.warning(
                f"youtube-gallery: no videos matched "
                f"({len(records)} in catalog, {total} after filtering).",
                location=self.get_location(),
            )
            return []

        rst = self._is_rst()
        mode = self._resolve_mode(len(selected))
        sections = group_records(selected, query)

        # Real document sections where the context allows one, rubrics where
        # it does not -- decided per invocation, never an error. Shared with
        # `gallery-grid` so both group identically. See `collection.sections`.
        parts = [
            (
                label,
                self._render_list(group, rst)
                if mode == "list"
                else self._render_grid(group, mode, rst),
            )
            for label, group in sections
        ]
        rendered = render_sections(
            self, parts, self.options.get("section-style", "auto"), logger
        )

        if query.limit is not None and total > len(selected):
            rendered.append(
                nodes.paragraph(
                    text=f"Showing {len(selected)} of {total} matching videos."
                )
            )

        classes = [CONTAINER_CLASS, "youtube-gallery"]
        if "searchable" in self.options:
            classes.append(SEARCHABLE_CLASS)
        wrapper = nodes.container(classes=classes)
        if "searchable" in self.options:
            # Carried in a hidden node, not a `data-` attribute: docutils'
            # HTML writer emits only known attributes on a container, so a
            # custom one is silently dropped.
            wrapper += nodes.paragraph(
                text=self.options.get("search-label") or "Filter these videos",
                classes=["sk-collection-label"],
            )
        wrapper += rendered
        return [wrapper]


#: Extensions this directive renders through. `youtube-gallery` emits
#: `gallery-grid` and `youtube` markup, so without these a page fails with
#: "Unknown directive type: 'gallery-grid'" -- an error naming a directive
#: the author never wrote, pointing at generated source they cannot see.
#:
#: Declaring them here means enabling `youtube_catalog` is enough: Sphinx
#: loads the rest. The two directives stay independently usable; it is only
#: this one that depends on them.
from importlib.util import resolve_name
from .._extension_setup import check_namespace

REQUIRED_EXTENSIONS = (
    resolve_name(".._pydata_sphinx_theme.gallery_directive", __package__),
    resolve_name(".._sphinxcontrib_youtube", __package__),
)


def _ensure_extensions(app: Sphinx) -> None:
    """Load dependencies in the caller's namespace; propagate setup failures."""
    check_namespace(app, __package__.rsplit(".", 1)[0])
    for name in REQUIRED_EXTENSIONS:
        app.setup_extension(name)


def setup(app: Sphinx) -> dict[str, Any]:
    """
    Register the directive, its configuration values, and its dependencies.

    Parameters
    ----------
    app : sphinx.application.Sphinx
        The Sphinx application to extend.

    Returns
    -------
    dict
        Extension metadata declaring parallel read/write safety. The
        directive is pure with respect to the environment -- it only reads
        the catalog file and notes it as a dependency -- so both are safe.
    """
    _ensure_extensions(app)
    app.add_config_value("youtube_catalog_path", "", "env", types=[str])
    app.add_config_value(
        "youtube_catalog_max_embeds", DEFAULT_MAX_EMBEDS, "env", types=[int]
    )
    app.add_directive("youtube-gallery", YouTubeGalleryDirective)
    app.connect("builder-inited", lambda a: ensure_assets(a))
    return {"parallel_read_safe": True, "parallel_write_safe": True}
