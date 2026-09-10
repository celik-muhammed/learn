YouTube gallery examples
========================

Enable ``_sphinx_ext._sphinx_youtube_gallery`` or its fully qualified
``scikitplot._externals`` equivalent. Preview over HTTP.

Standalone
----------

.. youtube:: JXtISpdDPNY

Nested in a dropdown
--------------------

.. admonition:: PCA video
   :class: dropdown

   .. youtube:: JXtISpdDPNY

Authored gallery content
------------------------

.. gallery-grid::
   :grid-columns: 1 1 2 2

   - title: PCA tutorial
     content: |
       .. youtube:: JXtISpdDPNY
   - title: PCA in a dropdown
     content: |
       .. admonition:: Watch the lesson
          :class: dropdown

          .. youtube:: JXtISpdDPNY

Catalog gallery
---------------

.. youtube-gallery::
   :searchable:
   :mode: embed
   :show-description:

   - id: JXtISpdDPNY
     title: Principal Component Analysis in Python
     description: A tutorial from Statistics Globe.

.. youtube-gallery::
   :interactive:
   :collection-id: learning-videos
   :grid-columns: 1 1 2 2

   - id: JXtISpdDPNY
     title: Principal Component Analysis in Python
     description: A tutorial from Statistics Globe.
