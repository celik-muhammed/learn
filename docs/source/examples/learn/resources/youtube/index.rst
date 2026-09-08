=================
YouTube Resources
=================

Video tutorials that pair well with scikit-plots.

Videos
------

.. youtube:: 3Fp1zn5ao2M

.. youtube-gallery:: ./_data/youtube.yaml
   :group-by: channel
   :sort: -published
   :show-description:

Channels
--------

.. gallery-grid::
  :grid-columns: 1 2 2 3
  :class-card: downstream-project-links
  :sort: title
  
  - title: Statistics Globe
    link-alt: Statistics Globe Channel
    link: https://www.youtube.com/@StatisticsGlobe
  - title: Statistics Globe
    link-alt: Statistics Globe Channel
    link: https://www.youtube.com/@StatisticsGlobe
  - title: Statistics Globe
    link-alt: Statistics Globe Channel
    link: https://www.youtube.com/@StatisticsGlobe
  - title: Statistics Globe
    link-alt: Statistics Globe Channel
    link: https://www.youtube.com/@StatisticsGlobe
  - title: Statistics Globe
    link-alt: Statistics Globe Channel
    link: https://www.youtube.com/@StatisticsGlobe
  - title: Statistics Globe
    link-alt: Statistics Globe Channel
    link: https://www.youtube.com/@StatisticsGlobe


Adding a video
--------------

Paste the URL from your address bar into ``_data/youtube.yaml``:

.. code-block:: yaml

   - id: https://www.youtube.com/watch?v=SOME_ID&list=PLxxx&index=4
     title: What the video is about
     channel: Who made it
     tags: [topic]

Watch URLs, ``youtu.be`` links, Shorts and bare ids all work -- the
``&list=`` and ``&index=`` parts are ignored for a single video, so there is
nothing to clean up by hand.
