"""
Browser-side enhancements for collection directives.

Two things a static build cannot do, added as *progressive enhancement*:
the page is complete and usable before either runs, and remains usable if
neither does.

1. **Lazy images.** Sphinx Design emits ``<img>`` with no ``loading``
   attribute, and Sphinx's HTML writer has no option to add one. On a
   thumbnail-mode gallery -- the mode chosen precisely because the
   collection is large -- that means every image in a 1000-item page is
   requested on first paint. A tiny inline script sets ``loading="lazy"``
   and ``decoding="async"`` on gallery images. Doing it in the browser is a
   deliberate trade: patching the writer would mean overriding
   ``visit_image`` globally and changing how *every* image on the site
   renders, which is a much larger blast radius than this is worth.

2. **Reader-side filtering.** Every other filter in this package runs at
   build time, which serves the *author*. A reader looking at 200 cards has
   no way to narrow them. The ``:searchable:`` flag adds a text box that
   hides non-matching cards as you type.

Why no framework, and why it degrades
-------------------------------------
Every card is rendered into the HTML and visible by default. The script
only ever *hides* things. So with JavaScript disabled, or before the script
runs, or if it throws, the reader sees the complete collection -- the
normal page. Nothing here is load-bearing.

That rules out the usual approach of rendering an empty container and
populating it from JSON: it would be faster to filter, and completely blank
without JavaScript, in a web crawler, in the ``text`` and ``epub``
builders, and in a printed PDF.

Notes
-----
**User-focused.** Add ``:searchable:`` to a gallery. The box filters on
everything visible in the card -- title and body text -- plus the values of
any fields named in ``:search-fields:``.

**Developer-focused.** The script is scoped to its own container, so
several searchable galleries on one page do not interfere. Matching is
case-insensitive substring over pre-computed text, so typing stays
responsive on large collections without an index.
"""

from __future__ import annotations

__all__ = ["ASSET_CSS", "ASSET_JS", "CONTAINER_CLASS", "SEARCHABLE_CLASS"]

#: Class marking a container the enhancements apply to.
CONTAINER_CLASS = "sk-collection"

#: Class marking a container that should get a filter box.
SEARCHABLE_CLASS = "sk-collection-searchable"

ASSET_CSS = """\
/* Collection directive enhancements. Everything here is additive: with the
   stylesheet absent the gallery renders as an ordinary Sphinx Design grid. */

.sk-collection-search {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0.75rem 0 1rem;
}

.sk-collection-search input[type="search"] {
  flex: 1 1 auto;
  min-width: 0;
  padding: 0.45rem 0.7rem;
  font: inherit;
  color: inherit;
  background: transparent;
  border: 1px solid currentColor;
  border-radius: 0.375rem;
  opacity: 0.85;
}

.sk-collection-search input[type="search"]:focus-visible {
  outline: 2px solid currentColor;
  outline-offset: 2px;
  opacity: 1;
}

.sk-collection-status {
  flex: 0 0 auto;
  font-size: 0.875em;
  opacity: 0.75;
}

/* Hidden rather than removed, so the DOM order and the reader's place on
   the page are preserved when the query is cleared. */
.sk-collection-hidden { display: none !important; }

/* Carries the filter label to the script; removed on read. Hidden here so
   it never renders, and harmless as a stray line if the stylesheet is
   missing. */
.sk-collection-label { display: none !important; }

.sk-collection-empty {
  padding: 0.75rem 0;
  font-style: italic;
  opacity: 0.75;
}

/* A section whose every card is filtered out collapses its heading too --
   an empty heading reads as a rendering bug. */
.sk-collection-section-hidden { display: none !important; }

@media print {
  /* A filter box is meaningless on paper, and the reader must get the
     whole collection regardless of what was typed before printing. */
  .sk-collection-search { display: none !important; }
  .sk-collection-hidden,
  .sk-collection-section-hidden { display: revert !important; }
}
"""

ASSET_JS = """\
/* Collection directive enhancements -- progressive, never load-bearing.
   Every card is already in the HTML and visible; this only hides things. */
(function () {
  "use strict";

  function lazyImages(root) {
    // Sphinx Design emits <img> without `loading`, and Sphinx's HTML writer
    // has no option to add one. On a large thumbnail gallery that is one
    // eager request per card on first paint.
    var images = root.querySelectorAll("img:not([loading])");
    for (var i = 0; i < images.length; i++) {
      images[i].setAttribute("loading", "lazy");
      images[i].setAttribute("decoding", "async");
    }
  }

  function ownerOf(root, item) {
    // Which heading does this card sit under? Computed once per card, at
    // setup, rather than re-derived while typing.
    //
    // Two structures, because `:section-style:` produces either. With a real
    // section the card is a descendant of a <section> whose first child is
    // the heading. With a rubric the heading is a *previous sibling* of the
    // card's top-level block. An earlier version searched for a visible
    // `.sd-card` inside each section instead -- which never matched, because
    // the class that hides a card goes on its column wrapper, not on the
    // card itself, so every heading stayed visible however few cards did.
    var section = item.closest("section");
    if (section && root.contains(section) && section !== root) return section;

    var block = item;
    while (block.parentElement && block.parentElement !== root) {
      block = block.parentElement;
    }
    var previous = block.previousElementSibling;
    while (previous && !previous.matches("p.rubric")) {
      previous = previous.previousElementSibling;
    }
    return previous || null;
  }

  function cardsIn(root) {
    var cards = root.querySelectorAll(".sd-card");
    var out = [];
    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];
      // A card nested inside another card belongs to its parent; filtering
      // it independently would hide content from a still-visible card.
      if (card.parentElement && card.parentElement.closest(".sd-card")) continue;
      var item = card.closest(".sd-col, .sd-row > *") || card;
      var extra = card.getAttribute("data-search") || "";
      out.push({
        node: item,
        owner: ownerOf(root, item),
        text: ((card.textContent || "") + " " + extra).toLowerCase()
      });
    }
    return out;
  }

  function enhance(root) {
    lazyImages(root);
    if (!root.classList.contains("sk-collection-searchable")) return;

    var cards = cardsIn(root);
    if (!cards.length) return;

    // The label travels in a hidden element rather than a `data-` attribute:
    // docutils' HTML writer emits only known attributes on a container, so a
    // `data-*` set on the node is silently dropped. The element is removed
    // once read, so it never reaches the accessibility tree twice.
    var carrier = root.querySelector(".sk-collection-label");
    var label = "Filter this list";
    if (carrier) {
      label = (carrier.textContent || "").trim() || label;
      carrier.parentNode.removeChild(carrier);
    }
    var wrap = document.createElement("div");
    wrap.className = "sk-collection-search";

    var input = document.createElement("input");
    input.type = "search";
    input.placeholder = label;
    // The box is generated, so it has no <label> to point at; an
    // aria-label is what gives it an accessible name.
    input.setAttribute("aria-label", label);

    var status = document.createElement("span");
    status.className = "sk-collection-status";
    // Announce counts to screen readers as they change, politely so it does
    // not interrupt whatever the reader is doing.
    status.setAttribute("aria-live", "polite");
    status.setAttribute("role", "status");

    var empty = document.createElement("p");
    empty.className = "sk-collection-empty sk-collection-hidden";
    empty.textContent = "Nothing matches that filter.";

    wrap.appendChild(input);
    wrap.appendChild(status);
    root.insertBefore(wrap, root.firstChild);
    root.appendChild(empty);

    function apply() {
      var query = input.value.trim().toLowerCase();
      var shown = 0;
      for (var i = 0; i < cards.length; i++) {
        var hit = !query || cards[i].text.indexOf(query) !== -1;
        cards[i].node.classList.toggle("sk-collection-hidden", !hit);
        if (hit) shown++;
      }
      // Collapse a heading once nothing beneath it survives the filter: a
      // heading with no content reads as a rendering bug.
      var alive = new Map();
      for (var c = 0; c < cards.length; c++) {
        if (!cards[c].owner) continue;
        var live = !cards[c].node.classList.contains("sk-collection-hidden");
        alive.set(cards[c].owner, (alive.get(cards[c].owner) || false) || live);
      }
      alive.forEach(function (live, owner) {
        owner.classList.toggle("sk-collection-section-hidden", Boolean(query) && !live);
      });
      empty.classList.toggle("sk-collection-hidden", shown !== 0);
      status.textContent = query
        ? shown + " of " + cards.length
        : cards.length + " items";
    }

    input.addEventListener("input", apply);
    input.addEventListener("keydown", function (event) {
      // Escape clearing the box is the convention for a search field, and
      // it is the fastest way back to the full collection.
      if (event.key === "Escape") {
        input.value = "";
        apply();
      }
    });
    apply();
  }

  function run() {
    var roots = document.querySelectorAll(".sk-collection");
    for (var i = 0; i < roots.length; i++) {
      try {
        enhance(roots[i]);
      } catch (error) {
        // One malformed collection must not stop the others, and must never
        // leave the page worse than the plain HTML it started as.
        if (window.console) console.warn("sk-collection:", error);
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
"""
