---
orphan: true
---

# Start here: galleries and video pages

Everything on this page is a working example. Copy a block, change the
words, rebuild. You do not need to read any of the other documentation
first.

There are two directives, and they are independent:

| You want | Use | Needs |
| --- | --- | --- |
| a grid of anything (links, images, tutorials, projects) | `gallery-grid` | nothing else |
| a page of YouTube videos | `youtube-gallery` | enable it and it loads the rest itself |

Both work in `.md` (MyST) and `.rst` pages, with the same options. Every
example below is shown in both.

---

## 1. Your first gallery, in six lines

Write the items directly inside the directive:

In a Markdown (`.md`) page:

~~~markdown
```{gallery-grid}
- title: Getting started
  link: https://scikit-plots.github.io/
- title: API reference
  link: https://scikit-plots.github.io/
```
~~~

The same thing in a reStructuredText (`.rst`) page:

~~~rst
.. gallery-grid::

   - title: Getting started
     link: https://scikit-plots.github.io/
   - title: API reference
     link: https://scikit-plots.github.io/
~~~

That is the whole minimum. `title` is the only key you must supply.

```{gallery-grid}
- title: Getting started
  link: https://scikit-plots.github.io/
- title: API reference
  link: https://scikit-plots.github.io/
```

---

## 2. Move the items into a data file

Once you have more than a handful, put them in a YAML file next to your
page and pass its path:

```{gallery-grid} ./_data/starter.yaml
:limit: 2
:show-count:
```

~~~markdown
```{gallery-grid} ./_data/starter.yaml
:limit: 2
:show-count:
~~~
```

Open `_data/starter.yaml` and read the comments at the top — it explains
every key in five lines.

:::{admonition} The one rule worth knowing
:class: tip

Four keys are **rendered**: `title`, `link`, `content`, `img-top`.

Everything else is **data** — invisible on the card, but available to
`:filter:`, `:sort:` and `:group-by:`. So `level: beginner` will not show
up on the card, and that is exactly what makes `:filter: level=beginner`
possible.
:::

---

## 3. Show only some items — `:filter:`

Terms are separated by commas. **All** of them must hold.

```{gallery-grid} ./_data/starter.yaml
:filter: level=beginner
```

~~~markdown
:filter: level=beginner
~~~

The operators, in full. There are no others, and there is no expression
language — a filter is parsed, never executed.

| Write | Means | Example |
| --- | --- | --- |
| `field` | the field has a value | `link` |
| `!field` | the field is missing or empty | `!deprecated` |
| `field=x` | equals `x` (ignoring case) | `level=beginner` |
| `field!=x` | does not equal `x` | `level!=advanced` |
| `field~x` | contains the text `x` | `title~curve` |
| `field!~x` | does not contain `x` | `title!~draft` |
| `field^x` | starts with `x` | `title^Plotting` |
| `field$x` | ends with `x` | `title$plots` |
| `field:a\|b` | is any of `a`, `b` | `topic:metrics\|clustering` |
| `field>x` `field>=x` `field<x` `field<=x` | ordered comparison | `minutes<15`, `added>=2025-01-01` |

Numbers compare as numbers and ISO dates as dates, so `minutes<15` does
not accidentally compare `"9"` against `"12"` as text.

Two together — short beginner material:

```{gallery-grid} ./_data/starter.yaml
:filter: level=beginner, minutes<15
```

A value containing a comma goes in quotes: `:filter: title~"curves, plots"`.

---

## 4. Put them in order — `:sort:`

Give a field name. Add a `-` in front for descending.

```{gallery-grid} ./_data/starter.yaml
:sort: -added
```

~~~markdown
:sort: -added        # newest first
:sort: minutes       # shortest first
:sort: level,minutes # by level, then by length within each level
~~~

Items missing the sort field always come last, whichever direction you
choose — an unknown value does not belong at either end of a ranking.

---

## 5. Break it into sections — `:group-by:`

```{gallery-grid} ./_data/starter.yaml
:group-by: level
:sort: minutes
```

~~~markdown
:group-by: level
:sort: minutes
~~~

Sections appear in the order their first item appears, so `:sort:`
controls the section order too. Items with no value land in a final
**Ungrouped** section rather than disappearing.

If the field holds a *list*, the item appears once per entry. Grouping the
same file by `topic` puts the classification tutorials under three
headings:

```{gallery-grid} ./_data/starter.yaml
:group-by: topic
:sort: title
```

---

## 6. Long collections — `:limit:`, `:offset:`, `:show-count:`

```{gallery-grid} ./_data/starter.yaml
:sort: -added
:limit: 3
:show-count:
```

`:show-count:` prints an honest "Showing 3 of 5 items" so a truncated
gallery never pretends to be complete. `:offset:` skips from the front, so
`:offset: 3` `:limit: 3` is page two.

---

## 7. YouTube: one video

~~~markdown
```{youtube} https://www.youtube.com/watch?v=JXtISpdDPNY&list=PLabc&index=2
~~~
```

Paste whatever your address bar gave you. Watch URLs, `youtu.be` links,
Shorts, `/live/`, `/embed/`, links copied out of a sentence, and bare
video ids all work. A `?t=90` in the link starts the player there.

If you paste something that is *not* a single video — a channel, a
playlist, a clip — you get a message telling you what it was and which
directive to use instead. You will not get a blank player.

---

## 8. YouTube: many videos

`youtube-gallery` reads a catalog file and renders a slice of it. It takes
the same `:sort:`, `:group-by:`, `:limit:` and `:offset:` as
`gallery-grid`, plus a few video-specific ones.

~~~markdown
```{youtube-gallery} ./_data/youtube.yaml
:playlist: Intro to PCA
:sort: position
:limit: 6
~~~
```

| Option | Does |
| --- | --- |
| `:channel:` `:playlist:` | restrict to one — by name, by id, or by pasting a URL |
| `:since:` `:until:` | a publication date range |
| `:match:` | text search over title and description |
| `:tags:` | comma-separated, all must be present |
| `:group-by:` | `playlist`, `channel`, `year` |
| `:sort:` | `position`, `published`, `title`, `duration` (with `-`) |
| `:mode:` | `auto`, `embed`, `thumbnail`, `list` |

For a handful of videos you can skip the catalog entirely and list them
inline:

~~~markdown
```{youtube-gallery}
- id: https://www.youtube.com/watch?v=JXtISpdDPNY
  title: Principal Component Analysis in Python
- https://youtu.be/dQw4w9WgXcQ
~~~
```

### About `:mode:`

`auto` embeds a real player up to 24 videos and switches to clickable
thumbnails beyond that. This is not a stylistic default. Each embed is a
third-party iframe; a page of several hundred is slow to load and painful
to navigate with a screen reader. `list` renders plain links and stays
usable at four figures.

You can always force `:mode: embed` — you will get a build warning telling
you the cost, not a refusal.

---

## 9. Filling the catalog from YouTube

The build never talks to YouTube. You refresh the catalog yourself, look
at the diff, and commit it:

```bash
python -m scikitplot._sphinx_ext.youtube_catalog.sync \
    --source https://www.youtube.com/@cs50/playlists \
    --output docs/_data/youtube.yaml
```

`--source` takes any YouTube URL — a video, a playlist, a channel, a
handle, a channel tab. Repeat it for several.

Set `YOUTUBE_API_KEY` for the full history; without it the public RSS
feeds are used and you get roughly the most recent 15 items.

:::{admonition} Why not fetch during the build?
:class: note

Because then your documentation would stop building on the day YouTube
rate-limits your CI, and two builds of the same commit could produce
different pages. A committed catalog means a rebuild is reproducible and
a reviewer can see in the pull request exactly which videos were added.

Re-running the sync when nothing changed rewrites nothing and leaves an
empty `git diff`.
:::

---

## 10. When something goes wrong

Every error names the file and line, and the build continues so you can
fix several at once.

| Message | Fix |
| --- | --- |
| `expected a YAML list of items, got dict` | your items need a leading `- ` |
| `no items matched the filter (5 in source)` | a filter typo — check the field name against your YAML |
| `cannot parse filter term …` | the message lists every valid operator |
| `unknown sort key 'titel'` | the message lists every valid key |
| `no grid data found at …` | wrong path; it is relative to the page, not the project root |
| `… is outside the documentation source directory` | data files must live inside the docs tree |
| `'…' names the channel @x, not a single video` | use `youtube-gallery`, not `youtube` |

:::{admonition} A gallery that renders empty
:class: warning

Nine times out of ten this is a filter matching nothing, and the build log
will say so. Delete the `:filter:` line, rebuild, and add the terms back
one at a time.
:::

---

## 11. Let readers filter it themselves

Everything above filters at build time — you decide what appears. Add
`:searchable:` and the reader gets a box that narrows the cards as they
type:

~~~markdown
```{gallery-grid} ./_data/starter.yaml
:group-by: level
:searchable:
:search-label: Filter tutorials
```
~~~

```{gallery-grid} ./_data/starter.yaml
:group-by: level
:searchable:
:search-label: Filter tutorials
```

Try it: type `cluster`. Sections with nothing left in them collapse, and the
count updates. `Escape` clears the box.

Nothing here is required for the page to work — every card is in the HTML
and visible before any script runs, so the gallery is complete with
JavaScript off, in a printed PDF, and in the epub build.

## Where to go next

- `_data/starter.yaml` — the dataset every example above reads
- `youtube-gallery.md` — the six video scenarios, worked through
- `README.md` — the design rationale and the full option reference
