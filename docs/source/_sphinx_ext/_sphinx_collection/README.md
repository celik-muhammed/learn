# Shared collection browser controls

`_sphinx_collection` owns the progressive browser UI for searchable/interactive
Sphinx card collections. Provider adapters must contribute metadata and options;
they must not create a second search toolbar.

## UI ownership

- `_sphinx_collection`: search/disclosure shell, local filtering, facets, sorting,
  chips/suggestions, optional saved view/additions, add/export/revert controls.
- `_sphinx_gallery_grid`: static card/grid rendering and the single
  `sk-collection` DOM root.
- `_sphinx_youtube_gallery`: typed YouTube catalog adapter that forwards the
  collection options to `gallery-grid`.
- `_sphinx_youtube_core`: provider grammar/reference primitives only; no UI.
- `_sphinxcontrib_youtube`: leaf player directives only; no collection UI.

## Compact control contract

The browser enhancement creates one inline control surface:

```text
result metadata
[ search input                    | search icon ] [ chevron ]
-------------------------------------------------------------
long-form controls when expanded
```

The result count/status is left-aligned above the primary row. The search icon
is part of the input surface. The chevron controls one in-flow panel inside the
same bordered shell; it does not open a second toolbar or popup. Typing filters
immediately, while submit/Enter remains an equivalent explicit action. IME
composition is not filtered until composition ends.

The expanded panel follows the same information hierarchy as AI Learn rather
than presenting every control at one visual level. **View** owns facets, sort,
and Reset. Domain-specific capabilities live under **Gallery tools** as compact
nested panels such as Add, Browser preferences, and Export; a tool expands
across the available width when opened and collapses back into the tool grid
when closed. **Restore original gallery** is visually separated from ordinary
view reset because it also clears local additions and saved preferences.

There is no redundant Close button or explanatory footer. Escape collapses the
outer panel and returns focus to the disclosure; the chevron remains the
primary explicit open/close control. The panel does not auto-close on arbitrary
outside pointer activity.

## Progressive-enhancement invariant

The static gallery is complete without JavaScript. Browser controls only hide,
reorder, or add local cards after page load. Provider/network lookup remains an
explicit optional capability and is not required for ordinary search/filtering.
