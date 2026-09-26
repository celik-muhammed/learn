:html_theme.sidebar_secondary.remove:

..
  # https://devguide.python.org/documentation/markup/#substitutions

.. Welcome to Scikit-plots 101 |br| |release| - |today|

..
    substitutions don’t work in .. raw:: html
    .. raw:: html

    <div style="text-align: center"><strong>
    Welcome to Scikit-plots 101<br>|full_version| - |today|
    </strong></div>
..
    https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html#directive-centered
    .. centered:: Welcome to Scikit-plots 101 :raw-html:`<br />` |full_version| - |today|
    .. centered::
        **Scikit-plots Documentation** :raw-html:`<br />` |full_version| - |today|

..
  # https://docutils.sourceforge.io/docs/ref/rst/directives.html#custom-interpreted-text-roles

.. role:: raw-html(raw)
   :format: html

.. |br| raw:: html

   <br/>

.. _resource-external:

:raw-html:`<div style="text-align: center"><strong>` 🎓 Learning Resource External
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

.. _resource-external-index:

======================================================================
Learning Resource External
======================================================================


.. grid:: 1 1 1 1

    .. grid-item-card::
        :padding: 2
        :columns: 12 12 6 6

        **data**
        ^^^
        .. toctree::
            :maxdepth: 2

            Data Resource <./data/index.rst>

    .. grid-item-card::
        :padding: 2
        :columns: 12 12 6 6

        **doc**
        ^^^
        .. toctree::
            :maxdepth: 2

            Documentation Resource <./doc/index.rst>

    .. grid-item-card::
        :padding: 2
        :columns: 12 12 6 6

        **plot data-viz**
        ^^^
        .. toctree::
            :maxdepth: 2

            Plot Resource <./plot_dataviz/index.rst>

    .. grid-item-card::
        :padding: 2
        :columns: 12 12 6 6

        **model**
        ^^^
        .. toctree::
            :maxdepth: 2

            Model Resource <./model/index.rst>


.. grid:: 1 1 1 1

    .. grid-item-card::
        :padding: 2
        :columns: 12 12 6 6

        **guideline**
        ^^^
        .. toctree::
            :maxdepth: 2

            Guide Resource <./guide/index.rst>

    .. grid-item-card::
        :padding: 2
        :columns: 12 12 6 6

        **research**
        ^^^
        .. toctree::
            :maxdepth: 2

            Research Resource <./research/index.rst>

    .. grid-item-card::
        :padding: 2
        :columns: 12 12 6 6

        **cookbook**
        ^^^
        .. toctree::
            :maxdepth: 2

            Cookbook Resource <./cookbook/index.rst>

    .. grid-item-card::
        :padding: 2
        :columns: 12 12 6 6

        **handbook**
        ^^^
        .. toctree::
            :maxdepth: 2

            Handbook Resource <./handbook/index.rst>

    .. grid-item-card::
        :padding: 2
        :columns: 12 12 6 6

        **hands-on**
        ^^^
        .. toctree::
            :maxdepth: 2

            Hands-On Resource <./hands-on/index.rst>


.. grid:: 1 1 1 1

    .. grid-item-card::
        :padding: 2
        :columns: 12 12 6 6

        **agent**
        ^^^
        .. toctree::
            :maxdepth: 2

            Agents <./agent/index.rst>

    .. grid-item-card::
        :padding: 2
        :columns: 12 12 6 6

        **skill**
        ^^^
        .. toctree::
            :maxdepth: 2

            Skills <./skill/index.rst>
