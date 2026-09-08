"""
YouTube-specific adapter over the shared selection engine.

Filtering, sorting, grouping and pagination are not YouTube concerns; they
are collection concerns. The implementation therefore lives in
:mod:`scikitplot._sphinx_ext.collection.select`, which operates on plain
mappings and knows nothing about videos. This module contributes only what
is genuinely YouTube-specific:

* the mapping from :class:`~.model.VideoRecord` to a queryable record,
* the convenience filters a video page actually wants (``channel``,
  ``playlist``, a publication interval), expressed as ordinary filter terms.

Notes
-----
**Developer-focused.** Keeping this a thin adapter is what guarantees that
``youtube-gallery`` and ``gallery-grid`` sort and group identically. When
they shared no code they were free to diverge -- different tie-breaking,
different treatment of missing values -- and any such difference is a bug
that only shows up as two pages ordering the same data differently.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from ..collection.select import (
    FilterError,
    FilterTerm,
    Selection,
    apply_selection,
)
from ..collection.select import group_records as _group_records
from .model import CatalogError, VideoRecord

__all__ = ["Query", "SORT_KEYS", "GROUP_KEYS", "apply_query", "group_records"]

#: Sort keys a video page may use, mapped to the record field they read.
#: ``position`` is the author's intended teaching sequence and is therefore
#: the only ordering that reflects editorial intent rather than metadata.
SORT_KEYS = ("title", "published", "duration", "position", "channel", "playlist", "none")

#: Grouping keys a video page may use.
GROUP_KEYS = ("playlist", "channel", "year", "none")


def as_record(video: VideoRecord) -> dict[str, Any]:
    """
    Project a :class:`~.model.VideoRecord` into a queryable mapping.

    Parameters
    ----------
    video : VideoRecord
        The normalized video.

    Returns
    -------
    dict
        A mapping the shared engine can filter, sort and group. ``year`` is
        materialised as a field rather than computed during grouping so that
        it is also filterable and sortable, at no extra cost.

    Examples
    --------
    >>> from .model import normalize_record
    >>> record = as_record(normalize_record({"id": "dQw4w9WgXcQ", "title": "X"}))
    >>> record["title"], record["year"]
    ('X', 'unknown')
    """
    return {
        "id": video.id,
        "title": video.title,
        "description": video.description,
        "channel": video.channel,
        "channel_id": video.channel_id,
        "playlist": video.playlist,
        "playlist_id": video.playlist_id,
        "position": video.position,
        "published": video.published,
        "duration": video.duration,
        "tags": video.tags,
        "url": video.url,
        "year": video.year,
        "_video": video,
    }


@dataclass(frozen=True)
class Query:
    """
    A declarative selection over a video catalog.

    A thin, YouTube-shaped face over :class:`~..collection.select.Selection`.
    All fields are optional; an empty :class:`Query` selects every video in
    catalog order.

    Attributes
    ----------
    channel, playlist : str
        Match against the display name or the stable id, case-insensitively.
    tags : sequence of str
        Keep videos carrying **all** of these tags.
    match : str
        Case-insensitive substring over title and description.
    match_regex : str
        Reserved for compatibility; see Notes.
    since, until : datetime.datetime or None
        Half-open publication interval ``[since, until)``.
    sort_by : str
        A key from :data:`SORT_KEYS`, optionally prefixed with ``-``.
    group_by : str
        A key from :data:`GROUP_KEYS`.
    limit : int or None
        Maximum videos to return, applied after sorting.
    offset : int
        Videos to skip, applied after sorting and before ``limit``.

    Notes
    -----
    ``match`` searches title *and* description, which the generic ``~``
    operator cannot express over two fields at once, so it is applied as a
    dedicated term rather than translated. ``match_regex`` is likewise kept
    here: the shared grammar deliberately excludes regular expressions,
    because a catastrophically backtracking pattern in a ``:filter:`` option
    would stall a documentation build.
    """

    channel: str = ""
    playlist: str = ""
    tags: Sequence[str] = ()
    match: str = ""
    match_regex: str = ""
    since: _dt.datetime | None = None
    until: _dt.datetime | None = None
    sort_by: str = "none"
    group_by: str = "none"
    limit: int | None = None
    offset: int = 0

    def __post_init__(self) -> None:
        """
        Validate keys and bounds eagerly.

        Raises
        ------
        CatalogError
            If a sort or group key is unknown, both text matchers are given,
            a bound is negative, or the interval is empty. Reported by name
            with the valid alternatives, so a typo such as ``:sort: titel``
            is an error rather than a silent fallback to catalog order.
        """
        key = self.sort_by.lstrip("-") or "none"
        if key not in SORT_KEYS:
            raise CatalogError(
                f"unknown sort key {self.sort_by!r}; valid keys are "
                f"{sorted(SORT_KEYS)} (prefix with '-' for descending)"
            )
        if self.group_by not in GROUP_KEYS:
            raise CatalogError(
                f"unknown group key {self.group_by!r}; valid keys are "
                f"{sorted(GROUP_KEYS)}"
            )
        if self.match and self.match_regex:
            raise CatalogError(
                "'match' and 'match-regex' are mutually exclusive; use one"
            )
        if self.match_regex:
            import re

            try:
                re.compile(self.match_regex)
            except re.error as exc:
                raise CatalogError(
                    f"invalid match-regex {self.match_regex!r}: {exc}"
                ) from exc
        if self.limit is not None and self.limit < 0:
            raise CatalogError(f"limit must not be negative, got {self.limit}")
        if self.offset < 0:
            raise CatalogError(f"offset must not be negative, got {self.offset}")
        if self.since and self.until and self.since >= self.until:
            raise CatalogError(
                f"since ({self.since.date()}) must be earlier than "
                f"until ({self.until.date()})"
            )

    def to_selection(self) -> Selection:
        """
        Translate into a generic :class:`~..collection.select.Selection`.

        Returns
        -------
        Selection
            The equivalent selection. ``channel`` and ``playlist`` each
            become an "any of" term over the display-name and id fields, so
            a page can filter by whichever identifier its catalog happens to
            record.

        Raises
        ------
        CatalogError
            If a value cannot be expressed as a filter term.
        """
        terms: list[FilterTerm] = []
        for field_name, value in (
            ("channel", self.channel),
            ("playlist", self.playlist),
        ):
            if value:
                terms.append(_AnyOfTerm(f"{field_name}", f"{field_name}_id", value))
        for tag in self.tags:
            terms.append(FilterTerm("tags", "=", tag))
        if self.match:
            terms.append(_TextTerm(self.match))
        if self.match_regex:
            terms.append(_RegexTerm(self.match_regex))
        if self.since or self.until:
            terms.append(_IntervalTerm(self.since, self.until))

        sort_key = self.sort_by.lstrip("-") or "none"
        sort_text = ""
        if sort_key != "none":
            sort_text = f"-{sort_key}" if self.sort_by.startswith("-") else sort_key

        try:
            return Selection(
                terms=terms,
                sort_keys=(
                    [(sort_text.lstrip("-"), sort_text.startswith("-"))]
                    if sort_text
                    else []
                ),
                group_by="" if self.group_by == "none" else self.group_by,
                limit=self.limit,
                offset=self.offset,
            )
        except FilterError as exc:  # pragma: no cover - bounds already checked
            raise CatalogError(str(exc)) from exc


class _AnyOfTerm(FilterTerm):
    """Match a value against either of two fields (name or stable id)."""

    def __init__(self, first: str, second: str, wanted: str) -> None:
        super().__init__(field=first, operator="=", operand=wanted)
        object.__setattr__(self, "_second", second)

    def matches(self, record) -> bool:
        """
        Test the record against both candidate fields.

        Parameters
        ----------
        record : mapping
            The record to test.

        Returns
        -------
        bool
            ``True`` if either field equals the operand.
        """
        wanted = self.operand.casefold()
        return wanted in {
            str(record.get(self.field) or "").casefold(),
            str(record.get(self._second) or "").casefold(),
        }


class _TextTerm(FilterTerm):
    """Case-insensitive substring over title and description together."""

    def __init__(self, needle: str) -> None:
        super().__init__(field="title", operator="~", operand=needle)

    def matches(self, record) -> bool:
        """
        Test the record's title and description.

        Parameters
        ----------
        record : mapping
            The record to test.

        Returns
        -------
        bool
            ``True`` if the needle occurs in either field.
        """
        haystack = f"{record.get('title', '')}\n{record.get('description', '')}"
        return self.operand.casefold() in haystack.casefold()


class _RegexTerm(FilterTerm):
    """Case-insensitive regular expression over title and description."""

    def __init__(self, pattern: str) -> None:
        super().__init__(field="title", operator="~", operand=pattern)

    def matches(self, record) -> bool:
        """
        Test the record's title and description against the pattern.

        Parameters
        ----------
        record : mapping
            The record to test.

        Returns
        -------
        bool
            ``True`` if the pattern matches either field.
        """
        import re

        haystack = f"{record.get('title', '')}\n{record.get('description', '')}"
        return bool(re.search(self.operand, haystack, re.IGNORECASE))


class _IntervalTerm(FilterTerm):
    """Half-open publication interval ``[since, until)``."""

    def __init__(
        self, since: _dt.datetime | None, until: _dt.datetime | None
    ) -> None:
        super().__init__(field="published", operator="", operand="")
        object.__setattr__(self, "_since", since)
        object.__setattr__(self, "_until", until)

    def matches(self, record) -> bool:
        """
        Test whether the record falls inside the interval.

        Parameters
        ----------
        record : mapping
            The record to test.

        Returns
        -------
        bool
            ``True`` if the publication date lies in the interval. A video
            with no publication date is excluded: "unknown date" cannot be
            asserted to fall inside a requested range.
        """
        published = record.get("published")
        if published is None:
            return False
        if self._since and published < self._since:
            return False
        if self._until and published >= self._until:
            return False
        return True


def apply_query(
    videos: Iterable[VideoRecord], query: Query
) -> tuple[list[VideoRecord], int]:
    """
    Filter, sort and paginate a video catalog.

    Parameters
    ----------
    videos : iterable of VideoRecord
        The full catalog.
    query : Query
        The selection to apply.

    Returns
    -------
    selected : list of VideoRecord
        Videos after filtering, sorting, ``offset`` and ``limit``.
    total : int
        How many matched the filters *before* pagination, so a caller can
        report "showing 24 of 1043" rather than silently truncating.

    Examples
    --------
    >>> from .model import normalize_catalog
    >>> catalog = normalize_catalog([
    ...     {"id": "aaaaaaaaaaa", "title": "Beta", "playlist": "P1"},
    ...     {"id": "bbbbbbbbbbb", "title": "alpha", "playlist": "P2"},
    ... ])
    >>> selected, total = apply_query(catalog, Query(sort_by="title"))
    >>> [r.title for r in selected], total
    (['alpha', 'Beta'], 2)
    >>> selected, total = apply_query(catalog, Query(playlist="p1"))
    >>> [r.title for r in selected], total
    (['Beta'], 1)
    >>> selected, total = apply_query(catalog, Query(limit=1))
    >>> len(selected), total
    (1, 2)
    """
    records = [as_record(video) for video in videos]
    selected, total = apply_selection(records, query.to_selection())
    return [record["_video"] for record in selected], total


def group_records(
    videos: Sequence[VideoRecord], query: Query
) -> list[tuple[str, list[VideoRecord]]]:
    """
    Partition videos into labelled sections.

    Parameters
    ----------
    videos : sequence of VideoRecord
        Already filtered, sorted and paginated videos.
    query : Query
        Supplies ``group_by``.

    Returns
    -------
    list of (str, list of VideoRecord)
        Section label paired with its videos. With ``group_by="none"`` this
        is a single ``("", videos)`` pair, so callers have one code path for
        grouped and ungrouped rendering.

    Examples
    --------
    >>> from .model import normalize_catalog
    >>> catalog = normalize_catalog([
    ...     {"id": "aaaaaaaaaaa", "playlist": "Intro"},
    ...     {"id": "bbbbbbbbbbb"},
    ...     {"id": "ccccccccccc", "playlist": "Intro"},
    ... ])
    >>> [(label, len(rs)) for label, rs in
    ...  group_records(catalog, Query(group_by="playlist"))]
    [('Intro', 2), ('Ungrouped', 1)]
    >>> [label for label, _ in group_records(catalog, Query())]
    ['']
    """
    records = [as_record(video) for video in videos]
    sections = _group_records(records, query.to_selection())
    return [
        (label, [record["_video"] for record in group]) for label, group in sections
    ]
