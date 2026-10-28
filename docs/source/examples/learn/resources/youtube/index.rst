=================
YouTube Resources
=================

Video tutorials that pair well with scikit-plots.

.. important:: Before you rely on an external video

   **These links are suggestions, not endorsements.** We share third-party YouTube
   channels and videos as optional learning resources. Their inclusion does not mean
   that scikit-plots sponsors or partners with the creators, endorses their views, or
   has independently verified every claim.

   **The content belongs to its creators.** Videos may be incomplete, outdated, or
   unsuitable for your situation, and their views are not necessarily those of the
   scikit-plots project. Before using code or following technical or security advice,
   check it against current official documentation and review it for your own
   environment. External content and links may change or disappear.

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
