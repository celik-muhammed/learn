# YouTube videos: standalone and inside a gallery grid

This page collects sample usages of the `sphinxcontrib.youtube` `{youtube}`
directive, from the simplest possible embed up to grouping several videos
into one `{gallery-grid}` -- with or without other directives (like an
`{admonition}` dropdown) wrapped around the video. `{gallery-grid}` treats
each card's `content` as opaque source text for the current page's markup
language, so it accepts *any* validly-nested content the author writes,
including directives this theme doesn't otherwise know about.

## Sample 1: a single video, on its own

The simplest case -- no gallery, no admonition, just the directive:

```{youtube} 3Fp1zn5ao2M
```

## Sample 2: a single video, wrapped in a dropdown admonition

Wrapping a directive in another directive is ordinary MyST nesting: the
outer fence just needs more backticks than the inner one.

`````{admonition} YouTube
:class: dropdown admonition-youtube

```{youtube} 3Fp1zn5ao2M
```
`````

## Sample 3: several videos grouped in one gallery grid

Use `{gallery-grid}` like any other gallery, but give each card a
`content` field containing a bare `{youtube}` embed instead of an image
or a link. This groups multiple videos into the same responsive grid used
elsewhere on this page.

```{gallery-grid}
:grid-columns: "1 1 2 2"

- title: Intro talk
  content: |
    ```{youtube} 3Fp1zn5ao2M
    ```
- title: Deep dive
  content: |
    ```{youtube} 3Fp1zn5ao2M
    ```
- title: Lightning talk
  content: |
    ```{youtube} 3Fp1zn5ao2M
    ```
```

## Sample 4: a gallery card with an admonition-wrapped video

The same nesting from Sample 2 also works *inside* a gallery card. This
is the deepest common case -- `grid` > `grid-item-card` > `admonition` >
`youtube` -- four directive levels deep, handled automatically: the
directive sizes each fence to be longer than anything nested inside it,
so no manual backtick-counting is required from page authors.

```{gallery-grid}
:grid-columns: "2"

- title: Recorded webinar
  content: |
    ````{admonition} YouTube
    :class: dropdown admonition-youtube

    ```{youtube} 3Fp1zn5ao2M
    ```
    ````
- title: Project link
  link: https://pydata-sphinx-theme.readthedocs.io/
  link-alt: pydata-sphinx-theme docs
```

## Sample 5: mixing video cards with ordinary link/image cards

Because `content` is just text, a single grid can freely mix video
cards with the theme's existing link and image cards -- no separate
directive is needed for "a gallery of videos" versus "a gallery of
links"; it's the same `{gallery-grid}` either way.

```{gallery-grid}
:grid-columns: "1 1 2 2"

- title: Watch the overview
  content: |
    ```{youtube} 3Fp1zn5ao2M
    ```
- title: ArviZ
  link-alt: ArviZ Python docs
  link: https://python.arviz.org/
  img-bottom: ../_static/gallery/arviz.png
- title: Ask a question in a dropdown
  content: |
    ````{admonition} Where do I ask questions?
    :class: dropdown

    Open a [GitHub Discussion](https://github.com/pydata/pydata-sphinx-theme/discussions).
    ````
```

## Sample 6: a card title that itself contains inline code

Card titles routinely need inline code spans (a package name, a CLI
flag). This "just works" -- the title isn't treated as raw fence syntax,
so backticks inside it render as ordinary inline code rather than
interfering with the card:

```{gallery-grid}
:grid-columns: "2"

- title: "Using the `{youtube}` directive"
  content: |
    ```{youtube} 3Fp1zn5ao2M
    ```
- title: "A plain `code` title, no video"
  link: https://pydata-sphinx-theme.readthedocs.io/
  link-alt: pydata-sphinx-theme docs
```
