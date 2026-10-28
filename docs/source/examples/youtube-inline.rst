:orphan:

Inline YouTube gallery
======================

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

.. youtube-gallery::
   :grid-columns: 1 1 2 2
   :interactive:
   :grid-gutter: 3
   :card-shadow: sm
   :video-width: 100%
   :video-aspect: 16:9
   :filter-fields: channel,tags
   :sort-fields: title,published,duration
   :show-description:

   videos:
     - id: JXtISpdDPNY
       title: Principal Component Analysis in Python
       channel: Statistics Globe
       tags: [pca, dimensionality-reduction]
     - id: UNzCG3lw6O0
       title: Building Great Agent Skills
       tags: [agents, skills]

File-backed YouTube gallery
---------------------------

.. youtube-gallery:: youtube.yaml
   :grid-columns: 1 1 2 2
   :group-by: channel
   :sort: -published
   :interactive:
   :grid-gutter: 3
   :card-shadow: sm
   :video-width: 100%
   :video-aspect: 16:9
   :filter-fields: channel,tags
   :show-description:
