"""
Data model for the YouTube learning catalog.

This module owns the *only* definition of what a catalog record is. It is
deliberately free of Sphinx and network imports so that it can be exercised
by plain unit tests, by the offline sync tool, and by the Sphinx directive
alike.

Design contract
---------------
The catalog is the single source of truth consumed at documentation build
time. Acquisition (talking to YouTube) happens in a separate, explicitly
invoked step that *writes* a catalog; the Sphinx build only ever *reads*
one. That separation is what makes the docs build deterministic,
reproducible offline, and immune to the quota exhaustion, rate limiting and
socket timeouts that make build-time API calls a recurring source of broken
pipelines.

Notes
-----
**User-focused.** A catalog is an ordinary YAML file you can hand-edit, and
every field except ``id`` is optional. You can start with a three-line file
listing video URLs and grow into a 1000-record generated catalog without
changing any page markup.

**Developer-focused.** Normalization is total and deterministic: the same
input record always yields the same :class:`VideoRecord`, and any record
that cannot be normalized raises :class:`CatalogError` naming the offending
index and field. No field is ever silently dropped or guessed.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "CatalogError",
    "VideoRecord",
    "normalize_record",
    "normalize_catalog",
    "parse_timestamp",
    "parse_duration",
]


class CatalogError(ValueError):
    """
    Raised when a catalog payload cannot be normalized.

    Carries a message that names the record index and the offending field so
    a maintainer can locate the problem in the YAML without a traceback.
    """


#: Canonical YouTube video ids are exactly 11 URL-safe base64 characters.
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

#: ISO-8601 duration as returned by the YouTube Data API, e.g. ``PT1H2M30S``.
_ISO_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?"
    r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)


def parse_video_id(value: Any) -> str:
    """
    Normalize any accepted video reference to its canonical 11-character id.

    Thin wrapper over :func:`~.reference.parse_video_reference`, which owns
    the URL grammar. Kept as a separate name because the catalog only ever
    needs the id, while the reference parser returns the full structure.

    Parameters
    ----------
    value : Any
        A bare id or any YouTube URL that names a single video, including
        watch URLs carrying ``list``/``index``/``t`` parameters, ``youtu.be``
        links, Shorts, live and embed URLs, and bare query fragments.

    Returns
    -------
    str
        The canonical video id.

    Raises
    ------
    CatalogError
        If the value is not a YouTube reference, is malformed, or names a
        playlist or channel rather than one video.

    Examples
    --------
    >>> parse_video_id("dQw4w9WgXcQ")
    'dQw4w9WgXcQ'
    >>> parse_video_id("https://www.youtube.com/watch?v=JXtISpdDPNY&list=PL1x")
    'JXtISpdDPNY'
    >>> parse_video_id("https://youtu.be/JXtISpdDPNY?t=30")
    'JXtISpdDPNY'
    >>> parse_video_id("https://www.youtube.com/shorts/hbT7vzCvEc8")
    'hbT7vzCvEc8'
    """
    from .reference import ReferenceError, parse_video_reference

    try:
        return parse_video_reference(value).video_id
    except ReferenceError as exc:
        raise CatalogError(str(exc)) from exc


def parse_timestamp(value: Any) -> _dt.datetime | None:
    """
    Parse a publication timestamp into a timezone-aware UTC datetime.

    Accepts what both the YouTube Data API (RFC 3339, ``Z``-suffixed) and a
    hand-written catalog (a bare ``YYYY-MM-DD`` date, or a value PyYAML has
    already turned into a ``date``/``datetime``) realistically produce.

    Parameters
    ----------
    value : Any
        ``None``, a string, a :class:`datetime.date`, or a
        :class:`datetime.datetime`.

    Returns
    -------
    datetime.datetime or None
        A timezone-aware UTC datetime, or ``None`` if ``value`` is ``None``.
        Naive inputs are interpreted as UTC, which is what the YouTube API
        reports and what makes ``:since:``/``:until:`` comparisons total.

    Raises
    ------
    CatalogError
        If the value is present but cannot be parsed.

    Examples
    --------
    >>> parse_timestamp("2024-03-01T10:00:00Z").isoformat()
    '2024-03-01T10:00:00+00:00'
    >>> parse_timestamp("2024-03-01").isoformat()
    '2024-03-01T00:00:00+00:00'
    >>> parse_timestamp(None) is None
    True
    """
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        parsed = value
    elif isinstance(value, _dt.date):
        parsed = _dt.datetime(value.year, value.month, value.day)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        # `fromisoformat` gained full RFC 3339 'Z' support only in 3.11;
        # normalizing here keeps the module working on older interpreters
        # across the whole declared support range.
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            parsed = _dt.datetime.fromisoformat(text)
        except ValueError as exc:
            raise CatalogError(
                f"{value!r} is not a valid ISO-8601 date or timestamp: {exc}"
            ) from exc
    else:
        raise CatalogError(
            f"timestamp must be a string or date, got {type(value).__name__}"
        )
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed.astimezone(_dt.timezone.utc)


def parse_duration(value: Any) -> int | None:
    """
    Parse a video duration into whole seconds.

    Parameters
    ----------
    value : Any
        ``None``, an integer number of seconds, an ISO-8601 duration as
        returned by the YouTube Data API (``PT1H2M30S``), or a clock-style
        string (``1:02:30`` or ``2:30``).

    Returns
    -------
    int or None
        Duration in seconds, or ``None`` if ``value`` is ``None``.

    Raises
    ------
    CatalogError
        If the value is present but cannot be parsed.

    Examples
    --------
    >>> parse_duration("PT1H2M30S")
    3750
    >>> parse_duration("2:30")
    150
    >>> parse_duration(90)
    90
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise CatalogError("duration must not be a boolean")
    if isinstance(value, int):
        if value < 0:
            raise CatalogError(f"duration must not be negative, got {value}")
        return value
    if not isinstance(value, str):
        raise CatalogError(
            f"duration must be an int or string, got {type(value).__name__}"
        )
    text = value.strip()
    match = _ISO_DURATION_RE.match(text)
    if match and any(match.groupdict().values()):
        parts = {k: int(v) for k, v in match.groupdict().items() if v}
        return (
            parts.get("days", 0) * 86400
            + parts.get("hours", 0) * 3600
            + parts.get("minutes", 0) * 60
            + parts.get("seconds", 0)
        )
    if ":" in text:
        chunks = text.split(":")
        if len(chunks) > 3 or not all(c.isdigit() for c in chunks):
            raise CatalogError(f"{value!r} is not a valid clock duration")
        total = 0
        for chunk in chunks:
            total = total * 60 + int(chunk)
        return total
    raise CatalogError(
        f"{value!r} is not a valid duration "
        f"(expected seconds, 'PT1H2M30S', or '1:02:30')"
    )


def _as_str_list(value: Any, field_name: str) -> list[str]:
    """
    Coerce a scalar-or-list YAML value into a list of strings.

    Parameters
    ----------
    value : Any
        ``None``, a single string, or a list of strings.
    field_name : str
        Field name, used in the error message.

    Returns
    -------
    list of str
        Possibly empty list of stripped, non-empty strings.

    Raises
    ------
    CatalogError
        If the value is neither a string nor a list of strings.
    """
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise CatalogError(
            f"{field_name} must be a string or list of strings, "
            f"got {type(value).__name__}"
        )
    result = []
    for entry in value:
        if not isinstance(entry, str):
            raise CatalogError(
                f"{field_name} entries must be strings, "
                f"got {type(entry).__name__}"
            )
        stripped = entry.strip()
        if stripped:
            result.append(stripped)
    return result


@dataclass(frozen=True)
class VideoRecord:
    """
    One normalized video in the learning catalog.

    All fields except ``id`` are optional so that a hand-written catalog can
    be as small as a list of URLs, while a generated one carries the full
    metadata needed for sorting, filtering and sectioning.

    Attributes
    ----------
    id : str
        Canonical 11-character YouTube video id.
    title : str
        Human-readable title. Defaults to the id when unknown, so a card is
        never rendered with an empty heading.
    description : str
        Free text, used by substring filtering and optionally shown on the
        card.
    channel : str
        Channel display name, used for grouping and filtering.
    channel_id : str
        Stable channel identifier (``UC...``), preferred over ``channel``
        for filtering because display names change.
    playlist : str
        Playlist display name, used for grouping and filtering.
    playlist_id : str
        Stable playlist identifier (``PL...``).
    position : int or None
        Zero-based position within its playlist. ``None`` when the record
        did not come from a playlist. This is the only ordering that
        reflects the *author's* intended teaching sequence, so it is the
        default sort for playlist-scoped queries.
    published : datetime.datetime or None
        Publication timestamp in UTC.
    duration : int or None
        Runtime in whole seconds.
    tags : list of str
        Free-form labels for topical filtering.
    url : str
        Canonical watch URL, derived from ``id`` when not supplied.
    """

    id: str
    title: str = ""
    description: str = ""
    channel: str = ""
    channel_id: str = ""
    playlist: str = ""
    playlist_id: str = ""
    position: int | None = None
    published: _dt.datetime | None = None
    duration: int | None = None
    tags: list[str] = field(default_factory=list)
    url: str = ""

    @property
    def year(self) -> str:
        """
        Publication year as a string, or ``"unknown"``.

        Returns
        -------
        str
            Four-digit year, or ``"unknown"`` when ``published`` is ``None``.
            A string (rather than ``None``) keeps year-grouping keys totally
            ordered and directly usable as section headings.
        """
        return str(self.published.year) if self.published else "unknown"


#: Catalog keys that map onto a :class:`VideoRecord` field. Any other key in
#: a record is rejected rather than ignored: a typo such as ``titel`` would
#: otherwise silently produce a card titled with the bare video id.
_KNOWN_KEYS = frozenset(
    {
        "id",
        "url",
        "title",
        "description",
        "channel",
        "channel_id",
        "playlist",
        "playlist_id",
        "position",
        "published",
        "duration",
        "tags",
    }
)


def normalize_record(raw: Any, index: int = 0) -> VideoRecord:
    """
    Normalize one raw catalog entry into a :class:`VideoRecord`.

    Parameters
    ----------
    raw : Any
        A mapping of catalog keys, or a bare string treated as a video
        reference (so that the simplest possible catalog is a list of URLs).
    index : int, optional
        Position of this record in the catalog, used in error messages.

    Returns
    -------
    VideoRecord
        The normalized record.

    Raises
    ------
    CatalogError
        If the entry is not a mapping or string, carries an unknown key, or
        any field fails to parse. The message always names ``index``.

    Examples
    --------
    >>> normalize_record("https://youtu.be/JXtISpdDPNY").id
    'JXtISpdDPNY'
    >>> record = normalize_record({"id": "JXtISpdDPNY", "title": "PCA"})
    >>> record.title, record.url
    ('PCA', 'https://www.youtube.com/watch?v=JXtISpdDPNY')
    """
    if isinstance(raw, str):
        raw = {"id": raw}
    if not isinstance(raw, dict):
        raise CatalogError(
            f"record {index}: expected a mapping or a video URL string, "
            f"got {type(raw).__name__}"
        )

    unknown = set(raw) - _KNOWN_KEYS
    if unknown:
        raise CatalogError(
            f"record {index}: unknown key(s) {sorted(unknown)}; "
            f"valid keys are {sorted(_KNOWN_KEYS)}"
        )

    reference = raw.get("id") or raw.get("url")
    if reference is None:
        raise CatalogError(f"record {index}: missing required key 'id' (or 'url')")

    try:
        video_id = parse_video_id(reference)
        published = parse_timestamp(raw.get("published"))
        duration = parse_duration(raw.get("duration"))
        tags = _as_str_list(raw.get("tags"), "tags")
    except CatalogError as exc:
        raise CatalogError(f"record {index}: {exc}") from exc

    position = raw.get("position")
    if position is not None:
        if isinstance(position, bool) or not isinstance(position, int):
            raise CatalogError(
                f"record {index}: position must be an integer, "
                f"got {type(position).__name__}"
            )
        if position < 0:
            raise CatalogError(
                f"record {index}: position must not be negative, got {position}"
            )

    def _text(key: str) -> str:
        """Return a stripped string for ``key``, rejecting non-strings."""
        value = raw.get(key)
        if value is None:
            return ""
        if not isinstance(value, str):
            raise CatalogError(
                f"record {index}: {key} must be a string, "
                f"got {type(value).__name__}"
            )
        return value.strip()

    return VideoRecord(
        id=video_id,
        # Falling back to the id keeps every card titled: an untitled card in
        # a grid is indistinguishable from a broken one.
        title=_text("title") or video_id,
        description=_text("description"),
        channel=_text("channel"),
        channel_id=_text("channel_id"),
        playlist=_text("playlist"),
        playlist_id=_text("playlist_id"),
        position=position,
        published=published,
        duration=duration,
        tags=tags,
        url=_text("url") or f"https://www.youtube.com/watch?v={video_id}",
    )


def normalize_catalog(payload: Any, origin: str = "catalog") -> list[VideoRecord]:
    """
    Normalize a whole catalog payload into records, de-duplicating by id.

    Accepts either a bare list of records or a mapping with a ``videos``
    key, so that a generated catalog can carry sibling metadata (such as the
    sync timestamp and source query) alongside the records without the
    reader needing to know which shape it was handed.

    Parameters
    ----------
    payload : Any
        The value parsed from a catalog YAML/JSON document.
    origin : str, optional
        Description of where the payload came from, used in error messages.

    Returns
    -------
    list of VideoRecord
        Records in source order. When the same video id appears more than
        once, the *first* occurrence wins and later duplicates are dropped:
        a video legitimately appears in several playlists, and merging those
        catalogs must stay deterministic and order-stable.

    Raises
    ------
    CatalogError
        If the payload shape is wrong or any record fails to normalize.

    Examples
    --------
    >>> len(normalize_catalog(["https://youtu.be/JXtISpdDPNY"]))
    1
    >>> len(normalize_catalog({"videos": ["JXtISpdDPNY", "JXtISpdDPNY"]}))
    1
    """
    if payload is None:
        return []
    if isinstance(payload, dict):
        if "videos" not in payload:
            raise CatalogError(
                f"{origin}: mapping payload must contain a 'videos' key, "
                f"found {sorted(payload)}"
            )
        payload = payload["videos"]
        if payload is None:
            return []
    if not isinstance(payload, list):
        raise CatalogError(
            f"{origin}: expected a list of records (or a mapping with a "
            f"'videos' list), got {type(payload).__name__}"
        )

    records: list[VideoRecord] = []
    seen: set[str] = set()
    for index, raw in enumerate(payload):
        try:
            record = normalize_record(raw, index)
        except CatalogError as exc:
            raise CatalogError(f"{origin}: {exc}") from exc
        if record.id in seen:
            continue
        seen.add(record.id)
        records.append(record)
    return records
