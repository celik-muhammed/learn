"""Application-local validation for the two supported installation layouts."""
from sphinx.errors import ExtensionError


def check_namespace(app, root):
    """Reject mixed import roots before registering this extension's objects."""
    names = list(app.config.extensions) + list(app.extensions)
    roots = {root}
    for name in names:
        if "_sphinx_ext." in name:
            roots.add(name.split("_sphinx_ext.", 1)[0] + "_sphinx_ext")
    previous = getattr(app, "_scikitplot_sphinx_extension_root", None)
    if previous:
        roots.add(previous)
    if len(roots) != 1:
        raise ExtensionError(
            "Mixed scikit-plots extension namespaces: " + ", ".join(sorted(roots))
            + ". Use one namespace consistently in extensions and setup_extension()."
        )
    app._scikitplot_sphinx_extension_root = root
