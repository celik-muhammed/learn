---
orphan: true
---

# scikit-plots docs: collection galleries, YouTube pipeline, RST support

This package adds three things to the `scikit-plots/learn` documentation
build, and fixes twenty-five defects found along the way.

1. **`gallery-grid`** — a grid of anything, with filtering, sorting,
   grouping and pagination. Works in `.md` and `.rst`.
2. **`youtube-gallery`** — a video page built from a committed catalog,
   covering every scoping scenario from one video to several thousand.
3. **`youtube`** — accepts any YouTube URL, not just bare video ids.

**New here?** Read [`examples/start-here.md`](examples/start-here.md)
instead. It is ten sections of working examples and assumes nothing.

---

## Architecture

Three layers, and one invariant that drives the whole design:

```
tools sync (explicit, online)  ->  _data/*.yaml (committed)  ->  directives (build, offline)
```

**The HTML build never touches the network.** A build-time API call is
non-deterministic (quota, rate limits, deleted videos), non-idempotent (the
same commit produces different HTML), and is the direct cause of the
"broken pipe" class of CI failure. With a committed catalog, a rebuild is
reproducible and a reviewer sees in the pull-request diff exactly which
videos a change adds.

One exception, stated plainly because an unqualified claim here would be
false: the **latex and texinfo** builders fetch one thumbnail per video,
because a PDF cannot embed a player. That is bounded by
`video_download_limit` (default 200) — per-request timeouts bound each call
but not the aggregate, and 1200 videos at the worst-case read timeout is
over eleven hours, which looks like a hung job rather than a failed one.
Beyond the limit, thumbnails are skipped with one warning naming the count.
`-b html` and `-b dirhtml` make no requests at all.

Second decision: **all scoping scenarios are queries over one dataset**, not
separate pipelines. Whole catalog filtered and sorted, sections per
playlist, a channel-and-playlist intersection, a date interval, an inline
list of links — one engine, five option combinations.

Third: **the query engine is domain-agnostic.**

```
scikitplot/_sphinx_ext/
    collection/          domain-agnostic: filter, sort, group, paginate
        select.py        operates on plain mappings; knows nothing about videos
    youtube_catalog/     a YouTube-shaped adapter over collection/
        reference.py     the URL grammar (one place, three consumers)
        model.py         catalog record normalization
        query.py         thin adapter -- no duplicated logic
        directive.py     youtube-gallery
        sync.py          the offline acquisition tool
```

`gallery-grid` and `youtube-gallery` share `collection/select.py`, so they
cannot drift apart in ordering or tie-breaking. When they shared no code
they were free to diverge, and any such difference is a bug that surfaces
only as two pages ordering the same data differently.

### Independence

Each directive is independently usable, and the dependency runs one way:

| Configuration | Result |
| --- | --- |
| `gallery-grid` alone, `collection` absent | builds; plain galleries render; selection options report a clear error naming the missing package |
| `youtube_catalog` alone | builds; it calls `app.setup_extension()` for its three render dependencies |
| Both | builds |

Vendored files degrade rather than hard-fail, because a vendored file that
hard-imports a sibling package has stopped being vendored.

---

## Defects found and fixed

Every one was reproduced with a real Sphinx 9.1 build before being fixed.
None was inferred from reading.

### Build-breaking

| # | Symptom | Root cause |
| --- | --- | --- |
| A | Empty `{gallery-grid}` body aborts the **whole build** with an unlocated `TypeError: 'NoneType' object is not iterable` | `safe_load()` result iterated with no shape validation |
| B | Mapping-shaped YAML aborts the build with `AttributeError: 'str' object has no attribute 'pop'` | same |

Both now produce a located directive error and the build continues.

### Silent data loss

| # | Symptom | Root cause |
| --- | --- | --- |
| C | Missing YAML renders the literal text `No grid data found at {path_data}.` | missing `f` prefix on the message |
| D | Missing YAML gives `build succeeded`, 0 warnings, gallery silently gone | `logger.info` instead of `logger.warning`; invisible under `-W` |
| E | **Editing the YAML does not rebuild the page.** Stale HTML until a clean build | `env.note_dependency()` never called |
| K | A single data field such as `category:` **silently removes that card from the grid** | every YAML key was forwarded to `grid-item-card`; Sphinx Design rejects unknown options and the rejected card is then dropped |
| L | With `:group-by:` on a list field, an item rendering twice loses its title the second time | `_build_card` popped keys off the item in place |

**E** matters most for a generated pipeline: a catalog that silently never
appears is worse than one that fails loudly. Fixing it initially *broke
idempotency* — noting a dependency on a missing file made that page
perpetually outdated — so the dependency is registered only for files that
exist.

**K** also blocked the whole collection idea: filtering needs per-item data,
and there was no way to carry any without destroying the card. Card options
are now read from the installed `GridItemCardDirective.option_spec` at
runtime; everything else is data.

### Wrong answers that look right

| # | Symptom | Root cause |
| --- | --- | --- |
| F | A pasted watch URL yields `embed/https://www.youtube.com/watch?v=...` -- dead iframe, build succeeds | the id was interpolated raw |
| J | `?v=RDdQw4w9WgXcQabc` silently becomes video `RDdQw4w9WgX` -- **a valid id for a different video** | `v=([A-Za-z0-9_-]{11})` scanned over the whole URL truncates a malformed value |
| Q | `:filter: category ??? tutorial` becomes a presence test on a field of that literal name -- empty gallery, no error | field names were unvalidated |
| R | `:filter: stars >> 5` splits into `>` plus operand `"> 5"`, compared as text | a second operator character was accepted |

**J** is why the parser is structural (`urllib.parse`) rather than a regex
over the URL: a wrong answer no downstream check can catch is worse than a
refusal.

### Accessibility, performance, security

| # | Symptom | Root cause |
| --- | --- | --- |
| G | `<iframe>` has no `title` (WCAG 4.1.2) and no `loading="lazy"` | attributes never emitted |
| H | Fixed `560x345px` iframe overflows a responsive card on mobile | hard-coded px, no fallback |
| I | `requests.get()` with **no timeout**; only `ConnectionError` caught; 404 bodies written as `.jpg` | unbounded build-time network call |
| O | `{gallery-grid} /etc/passwd` **reads the file** and echoes its path into a build error | no confinement to the source tree |

**O** matters beyond `/etc/passwd`: anyone who can edit a `.md` file could
otherwise make CI read a secrets file and quote it into a public build log.
Paths are resolved *before* the check, so an in-tree symlink pointing out is
caught too.

### Integration

| # | Symptom | Root cause |
| --- | --- | --- |
| M | The vendored `gallery_directive.py` no longer imports standalone | it hard-imported the new `collection` package |
| N | `youtube-gallery` fails with `Unknown directive type: 'gallery-grid'` -- an error naming a directive the author never wrote | render dependencies were not declared |
| P | **The vendored test suite could not execute at all**; every test errored with `fixture 'app' not found` | `pytest_plugins = "sphinx.testing.fixtures"` was commented out in `conftest.py` |
| S | A data file saved as latin-1 or cp1252 aborts the **whole build** with an unhandled `UnicodeDecodeError` and a traceback inviting the author to file a Sphinx bug | `read_text(encoding="utf-8")` uncaught |
| T | **`sphinx-build -b epub` fails on the current `conf.py`** with `NotImplementedError: departing unknown node type: PassthroughTextElement` | pre-existing conflict: the epub builder has format `html`, so html-only nodes normally work there by inheritance — but registering *any* explicit `epub=` handler (as the video extension must, since an epub reader cannot run an iframe) gives epub its own handler set, and `sphinx_design`'s html-only nodes are no longer found |
| U | The latex builder issues one unbounded-in-aggregate request per video | per-request timeouts existed; no cap on the total |
| V | Every video thumbnail is emitted as `alt=""` — marked *decorative*, so a screen reader announces nothing for the one element identifying the video (WCAG 1.1.1) | `img-alt` was never set |
| W | 0 of 23 thumbnails carry `loading="lazy"`; the mode chosen *because* the collection is large loads every image on first paint | Sphinx Design emits no `loading`, and Sphinx's HTML writer has no option for it |
| X | A filter matching nothing renders nothing — the reader sees a heading and blank space, indistinguishable from a broken page | the warning went to the build log, which readers never see |
| Y | With `:searchable:`, filtering to one card left all four section headings visible | the hide class goes on the card's *column wrapper*, so a `.sd-card:not(.hidden)` probe always matched |

**T** reproduces with none of this package's code loaded — `sphinx_design` +
`sphinxcontrib-youtube` alone is enough, and `conf.py` already lists both, so
epub builds of the learn site are broken today. Fixed by copying every
`html` handler with no `epub` counterpart into the `epub` set at
`builder-inited`, restoring the inheritance those extensions relied on
without patching `sphinx_design`.

**P** is worth dwelling on: a suite that cannot run reports no failures,
which reads exactly like a passing suite in CI. `pytest_plugins` is only
honoured in a *rootdir* conftest on modern pytest and this one is nested, so
re-enabling the line would not have worked either; the fixtures are now
imported directly.

### Also fixed

- MyST fences were fixed-length (4 for cards, 5 for grids), so nesting a
  same-or-longer fence silently closed the card early. Fences are now sized
  from their own content.
- A backtick in a card title made MyST fail to recognise the fence at all --
  CommonMark forbids backticks in a fence info string. Wrapper fences are
  now tildes.
- `_card_option_names()` rebuilt a frozenset per card -- 1200 times on a
  large gallery. Cached.
- `configure_image_download` used `mkdir(exist_ok=True)` without
  `parents=True`, raising `FileNotFoundError` when `outdir` did not exist
  yet at `builder-inited`.

---

## `gallery-grid`

Renders a YAML list as a Sphinx Design grid. Four keys are rendered --
`title`, `link`, `content`, `img-top` -- plus any real `grid-item-card`
option. Everything else is **data**: invisible on the card, available to the
selection options.

| Option | Meaning |
| --- | --- |
| `:filter:` | comma-separated terms, all must hold |
| `:sort:` | comma-separated fields, `-` prefix for descending |
| `:group-by:` | partition into labelled sections |
| `:limit:` `:offset:` | pagination over the sorted result |
| `:show-count:` | print "Showing N of M items" |
| `:grid-columns:` `:class-card:` `:class-container:` | passed through |

### Filter grammar

`field` / `!field` / `field=x` / `field!=x` / `field~x` / `field!~x` /
`field^x` / `field$x` / `field:a|b` / `field>x` `field>=x` `field<x`
`field<=x`

The obvious way to offer flexible filtering is to evaluate an expression.
That is also **remote code execution in a documentation build**: a
`:filter:` string reaching `eval` turns any pull request that edits a `.md`
file into arbitrary code running in CI. The grammar is therefore closed and
*parsed*, never executed, and an unrecognised operator is an error rather
than a fallback.

### Ordering invariants

- Numbers compare as numbers, ISO dates as dates, everything else as
  case-folded text.
- The interpretation is chosen **once per column, not per value**. Per-value
  coercion gives `"10" < "9"` as text but `10 > 9` as numbers -- a non-total
  order, on which Python's sort silently returns an arbitrary arrangement
  that changes with input order.
- Records missing the sort key sort **last in both directions**: "unknown"
  does not belong at either end of a ranking.
- Ties fall back to source order, so the same input renders
  byte-identically.
- A record whose grouping field is a *list* appears once per element.
  Silently picking the first tag would hide items from sections a reader is
  looking at.

---

## `youtube-gallery`

Same `:sort:`, `:group-by:`, `:limit:`, `:offset:`, plus `:channel:`,
`:playlist:`, `:since:`, `:until:`, `:match:`, `:tags:`, `:mode:`.
`:channel:` and `:playlist:` accept a name, an id, or a pasted URL.

### The embed budget

`:mode: auto` embeds a real player up to 24 videos and switches to thumbnail
facades beyond that. Each embed is a third-party iframe; a page of several
hundred is slow to parse, heavy on memory, and hostile to assistive
technology, which must traverse every frame. Measured on 1200 videos:

| Mode | iframes | HTML | Build |
| --- | --- | --- | --- |
| `auto` -> thumbnail | 0 | 647 KB | 3 s |
| `list` | 0 | 167 KB | 3 s |

An explicit `:mode: embed` over budget is honoured, with a warning naming
the count, the ceiling and three alternatives -- the author may know
something the heuristic does not.

---

## `youtube` -- any link

```rst
..  youtube:: https://www.youtube.com/watch?v=nfYOp3_SyqM&list=PLxxx&index=2
```

Handled: `watch?v=`, `watch/ID`, `youtu.be`, `/embed/`, `/v/`, `/e/`,
`/shorts/`, `/live/`, `watch_videos?video_ids=`, `/playlist?list=`,
`/embed/videoseries?list=`, `/channel/UC...`, `/@handle`, `/c/`, `/user/`,
bare vanity URLs, `/profile?user=`, `/clip/`, `/post/`, `/results?`,
`/hashtag/`, `/feed/`; every YouTube host including `m.`, `music.`,
`-nocookie`, `youtubekids.com` and country domains; the consent, redirect
and attribution wrappers; and paste damage -- angle brackets, quotes, curly
quotes, guillemets, Markdown parens, trailing punctuation, `&amp;`,
zero-width characters, missing scheme, bare `?v=...&` fragments, and URLs
embedded in prose.

### Why a typed reference, not "extract the id"

`watch?v=X&list=Y&index=2` names three things at once. A function returning
one string must discard two of them -- which is how a channel URL becomes a
dead iframe. The parser returns a structure, and the two consumers differ
**on purpose**: the directive reads `video_id` (the author pointed at one
video); the sync tool prefers `playlist_id` (the author pointed at a
collection and happened to be watching one item).

A collection URL is refused with a redirect, not a blank player:

```
ERROR: youtube: 'https://www.youtube.com/@cs50/playlists' names the
'playlists' tab of channel @cs50, not a single video. Use the
'youtube-gallery' directive for collections.
```

### Designed for a moving target

YouTube ships new URL shapes without notice -- `/shorts/` in 2021, the
`podcasts` and `courses` tabs in 2023. Three rules:

1. **"Unknown" is a value, not an exception.** An unrecognised tab yields
   `tab_known=False`; an unfamiliar playlist prefix yields
   `playlist_kind="unknown"`. Pages keep building, and the sync tool says
   *"this build does not know how to enumerate that tab"* rather than
   guessing `uploads` and quietly ingesting the wrong videos.
2. **Playlist ids validated by shape, not by prefix list.** Admission by
   prefix is what made `OLAK5uy_` album playlists unusable in older tooling.
3. **One table, not a conditional chain.** Path handling is a registry;
   supporting a new shape is one entry.

Host matching is by suffix on a dot boundary, so `youtube.com.evil.example`
is refused -- a substring test would make this an open redirect for anything
trusting its verdict.

Mixes (`RD...`), Watch Later and Liked are marked ephemeral and refused for
catalogs: YouTube generates them per viewer per session, so committing one
bakes in something that never reproduces.

---

## Sync tool

```bash
python -m scikitplot._sphinx_ext.youtube_catalog.sync \
    --source https://www.youtube.com/@cs50/playlists \
    --output docs/_data/youtube.yaml
```

`--source` takes any YouTube URL. `--check` fails if the catalog is out of
date, for CI drift detection. `YOUTUBE_API_KEY` is read from the environment
only -- never a command-line argument, which would leak into shell history,
process listings and CI logs.

Output is deterministic and idempotent: records sorted by a stable total
key, timestamps normalised to UTC, and an unchanged sync rewrites nothing
and leaves the mtime alone, so Sphinx does not needlessly invalidate every
consuming page.

Two tabs carry honest caveats, because the Data API has no endpoint for
channel *tabs*:

```
note: @cs50/shorts   -- Shorts are not distinguishable from other uploads
note: @cs50/podcasts -- the Data API does not label podcast playlists
```

Returning a confidently wrong subset would be worse than saying so.

---

## Verification

| Check | Result |
| --- | --- |
| Doctests (`select`, `model`, `query`, `reference`, `directive`) | 70 attempted, 0 failed |
| Vendored `sphinxcontrib.youtube` suite | 8 passed (was 0 runnable) |
| Full site build | succeeded |
| No-op rebuild x2 | `0 changed`, `0 changed` |
| Edit a data file | `1 changed`, content updated |
| MyST/RST structural parity | IDENTICAL |
| `gallery-grid` without `collection` | builds |
| `youtube_catalog` alone | builds |
| Builders: `html`, `dirhtml`, `text`, `epub`, `latex` | all succeed |
| Parallel build `-j 4` | succeeds, same diagnostics as serial |
| Original pages from the source zip | `gallery-md` 28 cards/13 images; `gallery` 17/13; both `youtube-gallery` pages 10 cards/8 iframes -- unchanged |

Pathological inputs handled without hanging or crashing: recursive YAML
aliases, YAML alias amplification (a nine-level "billion laughs" expansion),
non-UTF-8 files, CJK/Arabic/emoji titles, four-level dotted filter paths,
`:limit: 999999999`, `:offset:` past the end, absolute-path and symlink
traversal.

---

## Reader-side experience

Everything above serves the *author*: filters resolved at build time. A
reader facing 200 cards has no way to narrow them. `:searchable:` adds a
filter box that hides non-matching cards as you type.

| Option | Meaning |
| --- | --- |
| `:searchable:` | add a filter box to this collection |
| `:search-label:` | placeholder and accessible name for the box |

It is **progressive enhancement, never load-bearing**. Every card is
rendered into the HTML and visible by default; the script only ever *hides*
things. With JavaScript disabled, before the script runs, if it throws, in a
crawler, in the `text` and `epub` builders, and in a printed PDF, the reader
gets the complete collection.

That rules out the usual approach — render an empty container, populate it
from JSON. Faster to filter, and completely blank in every one of those
situations.

Details that matter and are easy to miss:

- The box gets an `aria-label` (it is generated, so it has no `<label>`),
  and the count is a `role="status"` `aria-live="polite"` region, so a
  screen-reader user hears "3 of 40" as they type.
- `Escape` clears the box — the convention for a search field and the
  fastest route back to the whole collection.
- A section whose cards are all filtered out collapses its heading too.
- Print styles restore everything and hide the box: paper must show the
  whole collection regardless of what was typed.
- Images get `loading="lazy"` and `decoding="async"` from the same script.
  Doing it in the browser is deliberate — patching the writer would mean
  overriding `visit_image` globally and changing how *every* image on the
  site renders, a far larger blast radius than this is worth.

Verified by executing the shipped script against the real built HTML in a
DOM, not by inspection: filter box created with correct label, 6 → 1 → 0 → 6
cards across queries, section headings collapsing and returning, empty
notice appearing only at zero, `Escape` clearing, and 6 of 6 images made
lazy.

## Grouping: real sections, with a safe fallback

`:group-by:` produces **real document sections** — permalinks, local
table-of-contents entries, and headings that "jump to heading" navigation
and screen readers act on. A rubric only looks like a heading; it behaves
like nothing.

But a directive cannot always create a section: docutils accepts one only
where the document structure allows it, and an author is free to put a
gallery inside an admonition, a card, a list item or a table cell. So the
choice is made per invocation:

| `:section-style:` | Behaviour |
| --- | --- |
| `auto` (default) | real sections where valid, rubrics where not — silently |
| `section` | real sections; warns once and falls back if the context refuses |
| `rubric` | always rubrics, for a gallery that must not disturb heading levels |

The fallback is silent under `auto` on purpose. An author who wrote
`:group-by: playlist` inside a dropdown asked for grouping, not for a build
error about docutils' structural model — and the rubric gives them the
reading experience they wanted.

Verified in all four contexts, in both `.md` and `.rst`, with identical
results:

| Context | Result |
| --- | --- |
| top level, `auto` | real `<section>` + `<h3>` + permalinks |
| inside an admonition, `auto` | rubrics, no error, no warning |
| inside an admonition, `:section-style: section` | rubrics + one actionable warning |
| top level, `:section-style: rubric` | rubrics |

Detection is structural rather than a guess, and had to account for both
parsers: reStructuredText exposes `state.parent`, while MyST substitutes a
`MockState` whose `__getattr__` *raises* for unimplemented attributes —
so `getattr(state, "parent", None)` does not help, because the default only
applies to `AttributeError`. MyST's equivalent is
`state._renderer.current_node`. An indeterminate parent degrades to rubrics,
so an unfamiliar parser produces a styled heading rather than a broken tree.
