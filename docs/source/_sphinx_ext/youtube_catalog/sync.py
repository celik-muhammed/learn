"""
Offline acquisition tool for the YouTube learning catalog.

This module is the *only* place that talks to YouTube, and it is never
imported by the Sphinx build. Run it deliberately -- by hand or on a
schedule -- to refresh a catalog file, review the diff, and commit it::

    python -m scikitplot._sphinx_ext.youtube_catalog.sync \\
        --playlist PLxxxxxxxxxxxxxxxxxx \\
        --output docs/_data/youtube.yaml

Notes
-----
**User-focused.** Without an API key the tool falls back to YouTube's public
RSS feeds, which need no credentials but only expose roughly the 15 most
recent items per channel or playlist. With ``YOUTUBE_API_KEY`` set it uses
the Data API v3 and pages through the full history.

**Developer-focused.** The output is deterministic and idempotent: records
are sorted by a stable key, timestamps are normalized to UTC, and re-running
against unchanged upstream data rewrites a byte-identical file. That is what
makes "did this sync actually change anything?" answerable from
``git diff`` rather than from trust, and what keeps the tool safe to run in
CI on a schedule.

The API key is read from the environment only. It is never accepted as a
command-line argument, because arguments leak into shell history, process
listings and CI logs.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Iterator, Sequence

from .model import CatalogError, VideoRecord, normalize_catalog
from .reference import (
    CHANNEL,
    CLIP,
    FEED,
    HASHTAG,
    PLAYLIST,
    POST,
    SEARCH,
    VIDEO,
    ReferenceError,
    YouTubeReference,
    parse_reference,
)

__all__ = [
    "fetch_playlist",
    "fetch_channel",
    "fetch_channel_playlists",
    "resolve_source",
    "write_catalog",
    "main",
]

#: YouTube Data API v3 base URL.
API_BASE = "https://www.googleapis.com/youtube/v3"

#: Public RSS feed used when no API key is available.
RSS_BASE = "https://www.youtube.com/feeds/videos.xml"

#: Connect and read timeout, in seconds, for every outbound request. Every
#: network call is bounded: an unbounded one turns a scheduled refresh into a
#: job that hangs until the CI runner is killed.
TIMEOUT = (5, 30)

#: Maximum result pages to walk before giving up. A bound is required
#: because a paging loop driven by a server-supplied token is otherwise
#: unbounded if the server ever returns a cycle.
MAX_PAGES = 200


def _require_requests():
    """
    Import ``requests`` lazily, with an actionable error if it is absent.

    Returns
    -------
    module
        The ``requests`` module.

    Raises
    ------
    CatalogError
        If ``requests`` is not installed. It is deliberately not a hard
        dependency of the documentation build, only of this optional tool.
    """
    try:
        import requests
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise CatalogError(
            "the sync tool needs 'requests' (pip install 'requests>=2.28'); "
            "it is not required to build the documentation"
        ) from exc
    return requests


def _api_pages(endpoint: str, params: dict[str, Any], api_key: str) -> Iterator[dict]:
    """
    Yield successive pages from a YouTube Data API v3 endpoint.

    Parameters
    ----------
    endpoint : str
        Endpoint name, e.g. ``"playlistItems"``.
    params : dict
        Query parameters, excluding ``key`` and ``pageToken``.
    api_key : str
        Data API v3 key.

    Yields
    ------
    dict
        One decoded response page.

    Raises
    ------
    CatalogError
        On any transport or HTTP error, or if paging exceeds
        :data:`MAX_PAGES`.
    """
    requests = _require_requests()
    token = None
    for _ in range(MAX_PAGES):
        query = dict(params, key=api_key, maxResults=50)
        if token:
            query["pageToken"] = token
        try:
            response = requests.get(
                f"{API_BASE}/{endpoint}", params=query, timeout=TIMEOUT
            )
            response.raise_for_status()
            page = response.json()
        except Exception as exc:  # requests.RequestException or JSON error
            raise CatalogError(f"YouTube API request to {endpoint} failed: {exc}") from exc
        yield page
        token = page.get("nextPageToken")
        if not token:
            return
    raise CatalogError(
        f"YouTube API paging exceeded {MAX_PAGES} pages for {endpoint}; "
        f"refusing to continue"
    )


def _rss_items(feed_param: str, value: str) -> list[dict[str, Any]]:
    """
    Fetch and parse a public YouTube RSS feed.

    Parameters
    ----------
    feed_param : str
        Either ``"channel_id"`` or ``"playlist_id"``.
    value : str
        The identifier to request.

    Returns
    -------
    list of dict
        Raw catalog records. RSS carries no duration, so ``duration`` is
        absent rather than guessed.

    Raises
    ------
    CatalogError
        On any transport, HTTP or XML parsing error.
    """
    import xml.etree.ElementTree as ET

    requests = _require_requests()
    try:
        response = requests.get(
            RSS_BASE, params={feed_param: value}, timeout=TIMEOUT
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except Exception as exc:
        raise CatalogError(f"RSS fetch for {value} failed: {exc}") from exc

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "media": "http://search.yahoo.com/mrss/",
    }
    records = []
    channel = root.findtext("atom:title", default="", namespaces=ns)
    for entry in root.findall("atom:entry", ns):
        video_id = entry.findtext("yt:videoId", default="", namespaces=ns)
        if not video_id:
            continue
        group = entry.find("media:group", ns)
        description = ""
        if group is not None:
            description = group.findtext("media:description", default="", namespaces=ns)
        records.append(
            {
                "id": video_id,
                "title": entry.findtext("atom:title", default="", namespaces=ns),
                "description": description,
                "channel": channel,
                "channel_id": entry.findtext(
                    "yt:channelId", default="", namespaces=ns
                ),
                "published": entry.findtext(
                    "atom:published", default="", namespaces=ns
                ),
            }
        )
    return records


def fetch_playlist(playlist_id: str, api_key: str = "") -> list[dict[str, Any]]:
    """
    Fetch every video in a playlist as raw catalog records.

    Parameters
    ----------
    playlist_id : str
        A ``PL...`` playlist identifier.
    api_key : str, optional
        Data API v3 key. When empty, the public RSS feed is used instead,
        which returns only the most recent items.

    Returns
    -------
    list of dict
        Raw records, ready for :func:`~.model.normalize_catalog`.
    """
    if not api_key:
        return _rss_items("playlist_id", playlist_id)

    records = []
    for page in _api_pages(
        "playlistItems",
        {"part": "snippet,contentDetails", "playlistId": playlist_id},
        api_key,
    ):
        for item in page.get("items", []):
            snippet = item.get("snippet", {})
            resource = snippet.get("resourceId", {})
            if resource.get("kind") != "youtube#video":
                continue
            records.append(
                {
                    "id": resource.get("videoId", ""),
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "channel": snippet.get("videoOwnerChannelTitle", "")
                    or snippet.get("channelTitle", ""),
                    "channel_id": snippet.get("videoOwnerChannelId", ""),
                    "playlist": snippet.get("channelTitle", ""),
                    "playlist_id": playlist_id,
                    "position": snippet.get("position"),
                    "published": item.get("contentDetails", {}).get(
                        "videoPublishedAt"
                    )
                    or snippet.get("publishedAt"),
                }
            )
    return records


def fetch_channel(channel_id: str, api_key: str = "") -> list[dict[str, Any]]:
    """
    Fetch a channel's uploads as raw catalog records.

    Parameters
    ----------
    channel_id : str
        A ``UC...`` channel identifier.
    api_key : str, optional
        Data API v3 key. When empty, the public RSS feed is used.

    Returns
    -------
    list of dict
        Raw records.

    Notes
    -----
    With an API key this resolves the channel's ``uploads`` playlist and
    pages through it, which is the documented way to enumerate a channel's
    full upload history.
    """
    if not api_key:
        return _rss_items("channel_id", channel_id)

    for page in _api_pages(
        "channels", {"part": "contentDetails", "id": channel_id}, api_key
    ):
        for item in page.get("items", []):
            uploads = (
                item.get("contentDetails", {})
                .get("relatedPlaylists", {})
                .get("uploads")
            )
            if uploads:
                records = fetch_playlist(uploads, api_key)
                for record in records:
                    # The uploads pseudo-playlist is an implementation
                    # detail, not something a reader should ever see as a
                    # section heading.
                    record["playlist"] = ""
                    record["playlist_id"] = ""
                    record["position"] = None
                return records
    raise CatalogError(f"channel {channel_id!r} has no uploads playlist")


#: Channel tabs the Data API can enumerate, and how.
#:
#: The API has no endpoint for a channel's *tabs*. What it exposes is the
#: uploads playlist and the channel's playlist list, and every tab is a view
#: over one of those two. Stating the mapping explicitly here -- rather than
#: pretending the tabs are first-class -- is what keeps the tool honest about
#: what it can actually deliver.
#:
#: ``videos``, ``streams``, ``shorts``, ``live``, ``""``
#:     the uploads playlist. Shorts and live streams are *in* uploads but
#:     carry no flag distinguishing them, so these tabs cannot be isolated;
#:     the tool says so rather than returning a wrong subset.
#: ``playlists``, ``podcasts``, ``courses``, ``releases``
#:     the channel's playlists. Podcast/course/release groupings are
#:     presentation metadata the API does not expose, so all four resolve to
#:     every public playlist; narrow with an explicit playlist URL.
_TAB_STRATEGY = {
    "": "uploads",
    "videos": "uploads",
    "streams": "uploads",
    "shorts": "uploads",
    "live": "uploads",
    "playlists": "playlists",
    "podcasts": "playlists",
    "courses": "playlists",
    "releases": "playlists",
}

#: Tabs that resolve to a superset of what the reader asked for.
_INEXACT_TABS = {
    "shorts": "Shorts are not distinguishable from other uploads in the "
              "Data API; all uploads are returned",
    "streams": "live streams are not distinguishable from other uploads in "
               "the Data API; all uploads are returned",
    "live": "live streams are not distinguishable from other uploads in the "
            "Data API; all uploads are returned",
    "podcasts": "the Data API does not label podcast playlists; all public "
                "playlists are returned",
    "courses": "the Data API does not label course playlists; all public "
               "playlists are returned",
    "releases": "the Data API does not label release playlists; all public "
                "playlists are returned",
}


def resolve_channel_id(reference: YouTubeReference, api_key: str = "") -> str:
    """
    Resolve any channel reference to a canonical ``UC…`` id.

    Parameters
    ----------
    reference : YouTubeReference
        A reference whose kind is :data:`~.reference.CHANNEL`.
    api_key : str, optional
        Data API v3 key.

    Returns
    -------
    str
        The canonical channel id.

    Raises
    ------
    CatalogError
        If the channel cannot be resolved. Without an API key, only an
        explicit ``UC…`` id can be used: handles and vanity names are
        resolvable *only* through the API, and scraping the channel page for
        them would make a scheduled sync depend on YouTube's HTML, which
        changes without notice. Failing with an instruction beats a
        pipeline that breaks silently six months from now.
    """
    if reference.channel_id:
        return reference.channel_id

    target = reference.handle or reference.channel_name
    if not api_key:
        raise CatalogError(
            f"cannot resolve {reference.describe()} without an API key. "
            f"Either set YOUTUBE_API_KEY, or pass the canonical channel URL "
            f"(https://www.youtube.com/channel/UC…), which you can read off "
            f"the channel page."
        )

    # `forHandle` accepts the handle with or without '@'; `forUsername` is
    # the legacy path for pre-handle vanity names. Both are tried because a
    # bare `/NAME` URL is ambiguous between the two.
    attempts = []
    if reference.handle:
        attempts.append({"forHandle": f"@{reference.handle}"})
    if reference.channel_name:
        attempts.append({"forHandle": f"@{reference.channel_name}"})
        attempts.append({"forUsername": reference.channel_name})

    for params in attempts:
        for page in _api_pages("channels", dict(params, part="id"), api_key):
            for item in page.get("items", []):
                if item.get("id"):
                    return item["id"]
    raise CatalogError(f"channel {target!r} not found on YouTube")


def fetch_channel_playlists(channel_id: str, api_key: str) -> list[dict[str, Any]]:
    """
    Fetch every video in every public playlist of a channel.

    Parameters
    ----------
    channel_id : str
        A ``UC…`` channel id.
    api_key : str
        Data API v3 key. Required: there is no RSS feed listing a channel's
        playlists.

    Returns
    -------
    list of dict
        Raw records across all of the channel's playlists, each tagged with
        its own playlist name and id so ``:group-by: playlist`` produces one
        section per playlist without further configuration.

    Raises
    ------
    CatalogError
        If no API key is supplied.
    """
    if not api_key:
        raise CatalogError(
            "listing a channel's playlists requires YOUTUBE_API_KEY; "
            "the public RSS feeds expose videos but not playlist lists"
        )
    records: list[dict[str, Any]] = []
    for page in _api_pages(
        "playlists", {"part": "snippet", "channelId": channel_id}, api_key
    ):
        for item in page.get("items", []):
            playlist_id = item.get("id")
            title = item.get("snippet", {}).get("title", "")
            if not playlist_id:
                continue
            for record in fetch_playlist(playlist_id, api_key):
                # The per-item `playlist` from the API snippet is the channel
                # title, not the playlist title; overwrite it with the real
                # one so section headings read correctly.
                record["playlist"] = title
                record["playlist_id"] = playlist_id
                records.append(record)
    return records


def resolve_source(source: str, api_key: str = "") -> list[dict[str, Any]]:
    """
    Fetch raw records for any YouTube URL or identifier.

    This is the entry point that makes the tool link-driven: paste the URL
    from the address bar and the right acquisition strategy is chosen from
    its structure.

    Parameters
    ----------
    source : str
        Any YouTube reference: a video, a playlist, a channel, or a channel
        tab, in any URL form.
    api_key : str, optional
        Data API v3 key.

    Returns
    -------
    list of dict
        Raw catalog records.

    Raises
    ------
    CatalogError
        If the reference cannot be parsed or cannot be resolved.

    Notes
    -----
    A ``watch?v=…&list=…`` URL is deliberately treated as **the playlist**
    here, not as the single video. On the command line the user's intent is
    "ingest this collection"; the video component is the one they happened
    to be watching when they copied the link. The single-video reading is
    what the ``youtube`` *directive* uses, and the two consumers differ on
    purpose -- which is exactly why the parser returns both identifiers
    instead of choosing for them.
    """
    try:
        reference = parse_reference(source)
    except ReferenceError as exc:
        raise CatalogError(str(exc)) from exc

    if reference.kind in (CLIP, POST, SEARCH, HASHTAG, FEED):
        raise CatalogError(
            f"{source!r} names {reference.describe()}, which is not an "
            f"enumerable collection of videos. Use a video, playlist or "
            f"channel URL."
        )

    if reference.kind == CHANNEL and reference.tab and not reference.tab_known:
        # A tab this build has never seen is a signal that YouTube shipped
        # something new, not a reason to guess. Guessing 'uploads' would
        # quietly ingest the wrong videos.
        raise CatalogError(
            f"{source!r} names {reference.describe()}. This build does not "
            f"know how to enumerate that tab; use the channel root, its "
            f"'videos' tab, or its 'playlists' tab, and please report the "
            f"new tab name."
        )

    if reference.ephemeral:
        raise CatalogError(
            f"{source!r} names {reference.describe()}, which YouTube "
            f"generates per viewer and per session. It is not stable content "
            f"and must not be committed to a catalog."
        )

    # A collection identifier on a video URL wins: see Notes.
    if reference.playlist_id:
        return fetch_playlist(reference.playlist_id, api_key)

    if reference.kind == PLAYLIST:
        return fetch_playlist(reference.playlist_id, api_key)

    if reference.kind == VIDEO:
        return [{"id": reference.video_id}]

    if reference.kind == CHANNEL:
        strategy = _TAB_STRATEGY.get(reference.tab)
        if strategy is None:
            raise CatalogError(
                f"{source!r}: the {reference.tab!r} tab holds no videos to "
                f"ingest; use the channel root, or its 'videos' or "
                f"'playlists' tab"
            )
        caveat = _INEXACT_TABS.get(reference.tab)
        if caveat:
            print(f"note: {source} -- {caveat}", file=sys.stderr)
        channel_id = resolve_channel_id(reference, api_key)
        if strategy == "playlists":
            return fetch_channel_playlists(channel_id, api_key)
        return fetch_channel(channel_id, api_key)

    raise CatalogError(f"{source!r}: unsupported reference kind {reference.kind!r}")


def _sort_key(record: VideoRecord) -> tuple:
    """
    Stable, total ordering key for catalog serialization.

    Parameters
    ----------
    record : VideoRecord
        The record to key.

    Returns
    -------
    tuple
        A tuple ordering by playlist, then position, then publication date,
        then id. The trailing id makes the ordering total, so two runs over
        the same upstream data always serialize in the same order and an
        unchanged sync produces an empty diff.
    """
    return (
        record.playlist_id or record.playlist,
        record.position if record.position is not None else 1 << 30,
        record.published.isoformat() if record.published else "",
        record.id,
    )


def write_catalog(records: Sequence[VideoRecord], path: Path) -> bool:
    """
    Serialize records to a catalog file, idempotently.

    Parameters
    ----------
    records : sequence of VideoRecord
        Normalized records.
    path : pathlib.Path
        Destination file. Parent directories are created if needed.

    Returns
    -------
    bool
        ``True`` if the file's contents changed, ``False`` if the sync was a
        no-op. The file is not rewritten when unchanged, so its mtime stays
        put and Sphinx does not needlessly invalidate every page that reads
        it.
    """
    from yaml import safe_dump

    payload = {
        "videos": [
            {
                key: value
                for key, value in (
                    ("id", record.id),
                    ("title", record.title),
                    ("description", record.description),
                    ("channel", record.channel),
                    ("channel_id", record.channel_id),
                    ("playlist", record.playlist),
                    ("playlist_id", record.playlist_id),
                    ("position", record.position),
                    (
                        "published",
                        record.published.isoformat() if record.published else None,
                    ),
                    ("duration", record.duration),
                    ("tags", record.tags or None),
                )
                # Omitting empty fields keeps the committed file readable and
                # its diffs small.
                if value not in (None, "", [])
            }
            for record in sorted(records, key=_sort_key)
        ]
    }
    text = safe_dump(
        payload, default_flow_style=False, allow_unicode=True, sort_keys=False
    )
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def main(argv: Sequence[str] | None = None) -> int:
    """
    Command-line entry point.

    Parameters
    ----------
    argv : sequence of str, optional
        Arguments to parse. Defaults to ``sys.argv[1:]``.

    Returns
    -------
    int
        ``0`` on success, ``1`` on a handled acquisition or validation
        failure.
    """
    parser = argparse.ArgumentParser(
        prog="youtube-catalog-sync",
        description=(
            "Fetch YouTube metadata into a catalog file for the docs build. "
            "Set YOUTUBE_API_KEY for full history; without it, public RSS "
            "feeds are used and only recent items are returned."
        ),
    )
    parser.add_argument(
        "--source", action="append", default=[], metavar="URL",
        help=(
            "any YouTube URL or id: a video, playlist, channel, handle "
            "(@name) or channel tab. Repeatable. This is the recommended "
            "form -- paste the link from the address bar."
        ),
    )
    parser.add_argument(
        "--playlist", action="append", default=[], metavar="PL...",
        help="playlist id to fetch; repeatable",
    )
    parser.add_argument(
        "--channel", action="append", default=[], metavar="UC...",
        help="channel id to fetch; repeatable",
    )
    parser.add_argument(
        "--output", required=True, type=Path, help="catalog file to write",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="fail if the catalog would change; for CI drift detection",
    )
    args = parser.parse_args(argv)

    if not (args.source or args.playlist or args.channel):
        parser.error("give at least one --source, --playlist or --channel")

    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if not api_key:
        print(
            "note: YOUTUBE_API_KEY is unset; using public RSS feeds "
            "(recent items only)",
            file=sys.stderr,
        )

    raw: list[dict[str, Any]] = []
    try:
        for source in args.source:
            raw.extend(resolve_source(source, api_key))
        for playlist_id in args.playlist:
            raw.extend(fetch_playlist(playlist_id, api_key))
        for channel_id in args.channel:
            raw.extend(fetch_channel(channel_id, api_key))
        records = normalize_catalog(raw, "youtube sync")
    except CatalogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.check:
        from yaml import safe_load

        existing = []
        if args.output.exists():
            existing = normalize_catalog(
                safe_load(args.output.read_text(encoding="utf-8")), str(args.output)
            )
        if {r.id for r in existing} != {r.id for r in records}:
            print(
                f"error: {args.output} is out of date "
                f"({len(existing)} stored, {len(records)} upstream)",
                file=sys.stderr,
            )
            return 1
        print(f"{args.output} is up to date ({len(records)} videos)")
        return 0

    changed = write_catalog(records, args.output)
    verb = "updated" if changed else "unchanged"
    print(f"{args.output} {verb} ({len(records)} videos)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
