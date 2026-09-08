# scikitplot/_externals/_sphinx_ext/_sphinxcontrib_youtube/utils.py
#
# fmt: off
# ruff: noqa
# ruff: noqa: PGH004
# flake8: noqa
# pylint: skip-file
# mypy: ignore-errors
# type: ignore
#
# Authors: Dr David Ham, Chris Pickel and others
# SPDX-License-Identifier: BSD-3-Clause

"""Skeleton of the video directive ready to be extended for specific providers."""

import re
from pathlib import Path
from typing import ClassVar

import requests
from docutils import nodes
from docutils.parsers.rst import Directive, directives
from sphinx.util import logging
from sphinx.util.display import status_iterator

logger = logging.getLogger(__name__)

CONTROL_HEIGHT = 30

THUMBNAIL_DIR = "_video_thumbnail"

#: scikit-plots local patch: connect+read timeout, in seconds, for the latex
#: thumbnail fetch. Bounded so a slow host cannot stall a docs build.
DOWNLOAD_TIMEOUT = (5, 30)

#: scikit-plots local patch: ceiling on thumbnails fetched in one build.
#:
#: The latex and texinfo builders fetch a thumbnail per video, because a PDF
#: cannot embed a player. Per-request timeouts bound each call but *not* the
#: aggregate: a 1200-video catalog is 1200 requests, and at the worst-case
#: read timeout that is over eleven hours before the build gives up -- a job
#: that looks hung rather than failed, which is the broken-pipe failure this
#: whole design exists to avoid.
#:
#: Beyond this ceiling, remaining thumbnails are skipped with one warning
#: naming the count and this setting. A PDF missing some video stills is a
#: far better outcome than a CI job that never returns.
DEFAULT_DOWNLOAD_LIMIT = 200

# -- helper methods ------------------------------------------------------------


# -- scikit-plots local patch: video reference normalisation -------------------
# Upstream takes ``self.arguments[0]`` as an opaque video id and interpolates it
# straight into the embed URL, so a pasted watch URL produced
# ``.../embed/https://www.youtube.com/watch?v=ID`` -- a dead iframe, emitted with
# no warning and a successful build.
#
# The URL grammar lives in one place (``youtube_catalog.reference``) rather than
# being duplicated here, so the directive, the catalog and the sync tool can
# never disagree about what a given URL means. The fallback keeps this vendored
# extension usable standalone, at reduced capability, if that module is absent.

from ..youtube_catalog.reference import (
    ReferenceError as _ReferenceError,
    parse_video_reference as _parse_video_reference,
)


def parse_youtube_id(value):
    """
    Normalise any single-video reference to its canonical id.

    Parameters
    ----------
    value : str
        A bare id or any YouTube URL naming one video.

    Returns
    -------
    str
        The canonical 11-character video id.

    Raises
    ------
    ValueError
        If the value names no single video.
    """
    return _parse_video_reference(value).video_id



def get_size(d, key):
    """Return a valid css size and unit."""
    if key not in d:
        return None
    m = re.match(r"(\d+)(|%|px)$", d[key])
    if not m:
        raise ValueError("invalid size %r" % d[key])
    return int(m.group(1)), m.group(2) or "px"


def css(d):
    """Return a valid css style string."""
    return "; ".join(sorted("%s: %s" % kv for kv in d.items()))


# -- node and directive definition ---------------------------------------------


def _merge_url_parameters(url_parameters, start_at):
    """
    Fold a start offset into an embed's query string.

    Parameters
    ----------
    url_parameters : str
        The author's explicit ``:url_parameters:`` value, e.g. ``"?rel=0"``.
    start_at : int or None
        Start offset in seconds, recovered from the pasted URL.

    Returns
    -------
    str
        The query string to append to the embed URL. An explicit
        ``start``/``t`` written by the author always wins: the directive
        option is a deliberate instruction, while the offset in a pasted URL
        is incidental.
    """
    if start_at is None:
        return url_parameters
    if re.search(r"[?&](?:start|t)=", url_parameters):
        return url_parameters
    separator = "&" if url_parameters.startswith("?") else "?"
    return f"{url_parameters}{separator}start={start_at}"


class video(nodes.General, nodes.Element):
    """Video node."""

    pass


class Video(Directive):
    """Abstract Video directive."""

    _node = None
    "Subclasses should replace with node class."

    _thumbnail_url = "{}"
    "url to retrieve thumbnail images"

    _platform = ""
    "name of the platform"

    _platform_url = ""
    "url of the platform video provider"

    _platform_url_privacy = ""
    "the aleternative url to provide the video privately"

    has_content = True
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False
    option_spec: ClassVar = {
        "width": directives.unchanged,
        "height": directives.unchanged,
        "aspect": directives.unchanged,
        "align": directives.unchanged,
        "url_parameters": directives.unchanged,
        "privacy_mode": directives.unchanged,
        # scikit-plots local patch: accessible name for the <iframe>.
        "title": directives.unchanged,
    }

    def run(self):
        """Run the directive."""
        env = self.state.document.settings.env
        # scikit-plots local patch: accept watch/short/embed URLs, not just
        # bare ids, and fail with a located error instead of a dead embed.
        start_at = None
        if self._platform == "youtube":
            try:
                reference = _parse_video_reference(self.arguments[0])
            except (_ReferenceError, ValueError) as exc:
                return [
                    self.state_machine.reporter.error(
                        f"youtube: {exc}", line=self.lineno
                    )
                ]
            video_id = reference.video_id
            # A `t=`/`start=` offset in the pasted URL is intent, not noise:
            # carry it into the player instead of discarding it.
            start_at = getattr(reference, "start", None)
        else:
            video_id = self.arguments[0]
        url = self._thumbnail_url.format(video_id)
        env.video_remote_images[url] = Path(THUMBNAIL_DIR, f"{video_id}.jpg")
        env.images.add_file("", env.video_remote_images[url])

        if "aspect" in self.options:
            aspect = self.options.get("aspect")
            m = re.match(r"(\d+):(\d+)", aspect)
            if m is None:
                # scikit-plots local patch: located error, not a traceback.
                return [
                    self.state_machine.reporter.error(
                        f"invalid aspect ratio {aspect!r}, expected e.g. '16:9'",
                        line=self.lineno,
                    )
                ]
            aspect = tuple(int(x) for x in m.groups())
        else:
            aspect = None

        alignment = ["left", "center", "right"]
        if "align" in self.options:
            align = self.options.get("align")
            if align not in alignment:
                # scikit-plots local patch: located error, not a traceback.
                return [
                    self.state_machine.reporter.error(
                        f"invalid alignment {align!r}, choices are: {alignment}",
                        line=self.lineno,
                    )
                ]
        else:
            align = None

        # custom platform url for peertube
        instance = self._platform_url
        if "instance" in self.options:
            instance = self.options.get("instance")

        return [
            self._node(
                id=video_id,
                title=self.options.get("title"),
                aspect=aspect,
                width=get_size(self.options, "width"),
                height=get_size(self.options, "height"),
                align=align,
                url_parameters=_merge_url_parameters(
                    self.options.get("url_parameters", ""), start_at
                ),
                privacy_mode=self.options.get("privacy_mode"),
                platform=self._platform,
                platform_url=self._platform_url,
                platform_url_privacy=self._platform_url_privacy,
                instance=instance,
            )
        ]


# -- builder specific methods --------------------------------------------------


def visit_video_node_html(self, node, platform_url_privacy=None, additional_attr={}):
    """Visit html video node."""
    aspect = node["aspect"]
    width = node["width"]
    height = node["height"]
    url_parameters = node["url_parameters"]
    platform_url = node["platform_url"]
    platform_url_privacy = node["platform_url_privacy"]
    if node.get("privacy_mode") and platform_url_privacy:
        platform_url = platform_url_privacy

    if aspect is None:
        aspect = 16, 9

    div_style = {}
    if (height is None) and (width is not None) and (width[1] == "%"):
        div_style = {
            "padding-top": "%dpx" % CONTROL_HEIGHT,
            "padding-bottom": "%f%%" % (width[0] * aspect[1] / aspect[0]),
            "width": "%d%s" % width,
            "position": "relative",
        }
        style = {
            "position": "absolute",
            "top": "0",
            "left": "0",
            "width": "100%",
            "height": "100%",
            "border": "0",
        }
        attrs = {
            "src": "{}{}{}".format(platform_url, node["id"], url_parameters),
            "style": css(style),
            **additional_attr,
        }
    else:
        if width is None:
            if height is None:
                width = 560, "px"
            else:
                width = height[0] * aspect[0] / aspect[1], "px"
        if height is None:
            height = width[0] * aspect[1] / aspect[0], "px"
        style = {
            "width": "%d%s" % width,
            "height": "%d%s" % (height[0] + CONTROL_HEIGHT, height[1]),
            "border": "0",
        }
        attrs = {
            "src": "{}{}{}".format(platform_url, node["id"], url_parameters),
            "style": css(style),
            **additional_attr,
        }
    if node["align"] is not None:
        div_style["text-align"] = node["align"]
    attrs["allowfullscreen"] = "true"
    # -- scikit-plots local patch: accessibility + gallery performance -------
    # `title` gives the frame an accessible name (WCAG 2.1 SC 4.1.2); without
    # it a page of embeds is an unnavigable list of unnamed frames.
    # `loading="lazy"` matters at gallery scale: a 100- or 1000-video page
    # otherwise opens that many YouTube connections on first paint.
    # `max-width` keeps the fixed-px default from overflowing a narrow
    # `grid-item-card` on mobile without changing the desktop rendering.
    attrs["title"] = node.get("title") or "{} video player".format(
        node["platform"] or "embedded"
    )
    attrs["loading"] = "lazy"
    if "max-width" not in attrs["style"]:
        attrs["style"] = attrs["style"] + "; max-width: 100%"
    # -- end scikit-plots local patch ----------------------------------------
    div_attrs = {
        "CLASS": "video_wrapper",
        "style": css(div_style),
    }
    if node["align"] is not None:
        div_attrs["CLASS"] += " align-%s" % node["align"]
    self.body.append(self.starttag(node, "div", **div_attrs))
    self.body.append(self.starttag(node, "iframe", **attrs))
    self.body.append("</iframe></div>")


def visit_video_node_epub(self, node):
    """Visit epub video node."""
    url_parameters = node["url_parameters"]
    link_url = "{}{}{}".format(node["platform_url"], node["id"], url_parameters)

    self.body.append(self.starttag(node, "a", CLASS="video_link_url", href=link_url))
    self.body.append(link_url)
    self.body.append("</a>")


def visit_video_node_latex(self, node):
    """Visit latex video node."""
    folder = r"\graphicspath{ {./%s/}{./} }" % THUMBNAIL_DIR
    if folder not in self.elements["preamble"]:
        self.elements["preamble"] += folder + "\n"

    macro = f"\\sphinxcontrib{node['platform']}"
    if macro not in self.elements["preamble"]:
        cmd = (
            r"\newcommand{%s}[3]{\begin{quote}\begin{center}\fbox{\url{#1#2#3}}\end{center}\end{quote}}"
            % macro
        )
        self.elements["preamble"] += cmd + "\n"

    self.body.append(
        "{}{{{}}}{{{}}}{{{}}}\n".format(
            macro, node["platform_url"], node["id"], node["url_parameters"]
        )
    )


def visit_video_node_unsupported(self, node):
    """Visit unsupported video node."""
    logger.warning(f"{node['platform']}: unsupported output format (node skipped)")
    raise nodes.SkipNode


def depart_video_node(self, node):
    """Depart any video node."""
    pass


_NODE_VISITORS = {
    "html": (visit_video_node_html, depart_video_node),
    "epub": (visit_video_node_epub, depart_video_node),
    "latex": (visit_video_node_latex, depart_video_node),
    "man": (visit_video_node_unsupported, depart_video_node),
    "texinfo": (visit_video_node_unsupported, depart_video_node),
    "text": (visit_video_node_unsupported, depart_video_node),
}

# -- manage downloaded images ---------------------------------------------------


def merge_download_images(app, env, docnames, other):
    """Merge remote images, when using parallel processing."""
    env.video_remote_images.update(other.video_remote_images)


def download_images(app, env):
    """
    Download thumbnails for the latex build.

    Parameters
    ----------
    app : sphinx.application.Sphinx
        The Sphinx application.
    env : sphinx.environment.BuildEnvironment
        The build environment carrying ``video_remote_images``.

    Notes
    -----
    This is the only place a *documentation build* reaches the network, and
    it runs for latex-family builders only. The number of requests is capped
    (see :data:`DEFAULT_DOWNLOAD_LIMIT`) so the aggregate cost is bounded,
    not just each individual call.
    """
    # images should only be downloaded if the builder is Latex related
    if "latex" not in app.builder.name:
        return

    iterator = (
        app.builder.status_iterator
        if hasattr(app.builder, "status_iterator")
        else status_iterator
    )
    msg = "Downloading remote images..."
    nb_images = len(env.video_remote_images)
    # scikit-plots local patch: aggregate download budget. Mutable
    # single-element lists rather than plain ints so the counters survive
    # the `continue` branches below without a nonlocal declaration.
    _limit = getattr(
        app.config, "video_download_limit", DEFAULT_DOWNLOAD_LIMIT
    )
    _downloaded = [0]
    _skipped = [0]
    for src in iterator(env.video_remote_images, msg, "brown", nb_images):

        # scikit-plots local patch: bound the aggregate, not just each call.
        if _downloaded[0] >= _limit:
            _skipped[0] += 1
            continue
        dst = Path(app.outdir) / env.video_remote_images[src]
        if not dst.is_file():
            _downloaded[0] += 1
            logger.info(f"{src} -> {dst} (downloading)")
            dst.parent.mkdir(parents=True, exist_ok=True)
            # -- scikit-plots local patch: bounded, fully-handled fetch ----
            # Upstream calls `requests.get` with no timeout and catches only
            # `ConnectionError`, so a hung or slow thumbnail host stalls the
            # build indefinitely, and a read timeout / HTTP error / broken
            # pipe propagates as an unhandled exception. It also wrote the
            # response body unconditionally, so a 404 page was saved as a
            # `.jpg`. Fetch first, validate, then write only on success.
            try:
                response = requests.get(src, timeout=DOWNLOAD_TIMEOUT)
                response.raise_for_status()
                payload = response.content
            except (requests.RequestException, OSError) as exc:
                logger.warning(f'Cannot download thumbnail "{src}": {exc}')
                continue
            try:
                dst.write_bytes(payload)
            except OSError as exc:
                logger.warning(f'Cannot write thumbnail "{dst}": {exc}')
            # -- end scikit-plots local patch ------------------------------
        else:
            logger.info(f"{src} -> {dst} (already in cache)")

    # scikit-plots local patch: report the budget rather than truncating in
    # silence -- a PDF quietly missing 1000 stills would look like a bug in
    # the document, not a deliberate limit.
    if _skipped[0]:
        logger.warning(
            f"video: fetched {_downloaded[0]} thumbnails and skipped "
            f"{_skipped[0]} after reaching the download limit of {_limit}. "
            f"Raise 'video_download_limit' in conf.py if the PDF needs them."
        )


def configure_image_download(app):
    """Configure Sphinx to download video thumbnails."""
    app.env.video_remote_images = {}

    output_dir = Path(app.outdir) / THUMBNAIL_DIR
    # scikit-plots local patch: `parents=True` -- `outdir` need not exist yet
    # when `builder-inited` fires, which made this raise FileNotFoundError.
    output_dir.mkdir(parents=True, exist_ok=True)
    app.config.html_static_path.append(str(output_dir))
