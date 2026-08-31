..
  # https://www.sphinx-doc.org/en/master/usage/restructuredtext/field-lists.html#file-wide-metadata
  # https://pydata-sphinx-theme.readthedocs.io/en/latest/user_guide/layout.html#remove-the-primary-sidebar-from-pages
  # https://pydata-sphinx-theme.readthedocs.io/en/latest/user_guide/page-toc.html#remove-the-table-of-contents

:html_theme.sidebar_secondary.remove:

..
  # https://devguide.python.org/documentation/markup/#substitutions

.. Welcome to Scikit-plots 101 |br| |release| - |today|

..
    ✨ substitutions don’t work in .. raw:: html
    .. raw:: html

    <div style="text-align: center"><strong>
    Welcome to Scikit-plots 101<br>|full_version| - |today|
    </strong></div>

..
    # https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html#directive-centered
    .. centered:: Welcome to Scikit-plots 101 :raw-html:`<br />` |full_version| - |today|
    .. centered::
        **Scikit-plots Documentation** :raw-html:`<br />` |full_version| - |today|

..
  # https://docutils.sourceforge.io/docs/ref/rst/directives.html#custom-interpreted-text-roles

.. role:: raw-html(raw)
   :format: html

.. |br| raw:: html

   <br/>

.. _scikit-plots-learning:

:raw-html:`<div style="text-align: center"><strong>` 🤗 Scikit-plots Learning
|br| |full_version| - |today|
:raw-html:`</strong></div>`

..
  https://devguide.python.org/documentation/markup/#sections
  https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html#sections
  # with overline, for parts    : ######################################################################
  * with overline, for chapters : **********************************************************************
  = for sections                : ======================================================================
  - for subsections             : ----------------------------------------------------------------------
  ^ for subsubsections          : ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  " for paragraphs              : """"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

..
  # https://rsted.info.ucl.ac.be/
  # https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html#paragraph-level-markup
  # https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html#footnotes
  # https://documatt.com/restructuredtext-reference/element/admonition.html
  # attention, caution, danger, error, hint, important, note, tip, warning, admonition, seealso
  # versionadded, versionchanged, deprecated, versionremoved, rubric, centered, hlist

.. _learning-index:

..
  • ☀️ 🌕 🌙 ✨

======================================================================
🌕 Learning Hub • AI-Powered ✨
======================================================================

.. toctree::
	:maxdepth: 1
	:caption: Project
	:hidden:

	scikit-plots <https://scikit-plots.github.io/dev/index.html>
	Learn <learn/index.rst>
	Tags <_tags/tagsindex.rst>

	Code of Conduct <https://scikit-plots.github.io/dev/project/code_of_conduct.html>
	Community <https://scikit-plots.github.io/dev/project/community.html>
	Developer's Guide <https://scikit-plots.github.io/dev/devel/index.html>
	Governance Process <https://scikit-plots.github.io/dev/project/governance.html>
	About Us | Project <https://scikit-plots.github.io/dev/project/index.html>


.. seealso::

  .. rubric:: 🚀 Try Scikit-Plots in Your Browser with Notebooks

  No installation required. Launch one of the interactive environments below.

  ..
    * Lab   : https://scikit-plots.github.io/dev/lite/lab/index.html
    * Retro : https://scikit-plots.github.io/dev/lite/tree/index.html
    * Repl  : https://scikit-plots.github.io/dev/lite/repl/index.html?kernel=python&code=import%20this

    * - `Open Lab <https://scikit-plots.github.io/dev/lite/lab/index.html>`__
    * - `Open Retro <https://scikit-plots.github.io/dev/lite/tree/index.html>`__
    * - `Open REPL <https://scikit-plots.github.io/dev/lite/repl/index.html?kernel=python&code=import%20this>`__

    +----------+----------------------------------------------------------------------+
    | Interface| URL                                                                  |
    +==========+======================================================================+
    | Lab      | https://scikit-plots.github.io/dev/lite/lab/index.html               |
    +----------+----------------------------------------------------------------------+
    | Retro    | https://scikit-plots.github.io/dev/lite/tree/index.html              |
    +----------+----------------------------------------------------------------------+
    | REPL     | https://scikit-plots.github.io/dev/lite/repl/index.html?kernel=python|
    |          | &code=import%20this                                                  |
    +----------+----------------------------------------------------------------------+

  .. list-table:: 🚀 Launch Interactive Environments
    :header-rows: 1
    :widths: 20 80

    * - Interface
      - URL
    * - Lab
      - https://scikit-plots.github.io/dev/lite/lab/index.html
    * - Retro
      - https://scikit-plots.github.io/dev/lite/tree/index.html
    * - REPL
      - https://scikit-plots.github.io/dev/lite/repl/index.html?kernel=python&code=import%20this


.. admonition:: jupyterlite (pyodide, xeus-python, c, c++)
  :collapsible: closed

  .. rubric:: jupyterlite lab pyodide:

  * https://jupyterlite-pyodide-kernel.readthedocs.io/en/latest/_static/lab/index.html

  .. rubric:: jupyterlite lab all-in-one-pyodide[pyodide, xpython, r, c, cpp, sqlite, js, p5]:

  * https://jupyter.org/try-jupyter/lab/index.html
  * https://jupyterlite.github.io/demo/lab/index.html
  * https://jupyterlite.readthedocs.io/en/stable/_static/lab/index.html

  .. rubric:: jupyterlite lab all-in-one-xeus[xpython, r, c, cpp, js]:

  * https://jupyterlite-xeus.readthedocs.io/en/stable/lite/lab/index.html
  * https://jupyterlite.github.io/xeus-lite-demo/lab/index.html

  .. rubric:: jupyterlite lab terminal[pyodide]:

  * https://jupyterlite.github.io/terminal/lab/index.html
  * https://jupyterlite.github.io/cockle/

  .. rubric:: jupyterlite lab misc:

  * https://jupyterlite.github.io/javascript-kernel/lab/index.html
  * https://jupyterlite.github.io/p5-kernel/lab/index.html
  * https://jupyterlite.github.io/echo-kernel/lab/index.html

.. raw:: html

  <div>
    <!-- Interactive Shell -->
    <!-- src="https://jupyterlite.github.io/demo/repl/?toolbar=1&kernel=python&code=import%20numpy%20as%20np" -->
    <!-- src="https://jupyterlite.github.io/demo/repl/#toolbar=1&kernel=python&execute=0&code=import+numpy+as+np" -->
    <iframe
      src="https://jupyterlite.github.io/demo/repl/#toolbar=1&kernel=python&execute=0&code=import+numpy+as+np"
      width="100%" height="71vh"
      style="height: 71vh; display: block;"
    >Try the REPL!
    </iframe>
  </div>
