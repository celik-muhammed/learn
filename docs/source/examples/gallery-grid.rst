YouTube videos: standalone and inside a gallery grid (reStructuredText sample)
================================================================================

This is the reStructuredText equivalent of :doc:`youtube-gallery`. It
demonstrates the ``sphinxcontrib.youtube`` ``.. youtube::`` directive used
on its own, wrapped in an admonition, and nested inside ``gallery-grid``
cards -- with the same nested content working from an ``.rst`` page as
from a ``.md`` page, no special syntax required.

Sample 1: a single video, on its own
-------------------------------------

.. youtube:: JXtISpdDPNY

Sample 2: a single video, wrapped in a dropdown admonition
-------------------------------------------------------------

In reStructuredText, nested directives are indicated by indentation, not
fence length, so this nests exactly the way any other nested RST
directive would:

.. admonition:: YouTube
    :class: dropdown admonition-youtube
    
    A Rickroll is a classic internet prank that involves tricking someone into clicking a link that leads to the music video for the song Never Gonna Give You Up by the singer Rick Astley. The joke relies on the element of surprise; the victim expects to find something relevant to what they clicked, but instead finds themselves listening to this 1987 pop hit.

    .. youtube:: dQw4w9WgXcQ

    In the context of this channel, the creator often uses this trope as a playful subversion of expectations within their skits. Since Rick Astley's song has become such a massive meme over the last two decades, it is widely recognized by internet communities globally as a lighthearted 'gotcha' moment. Even if you aren't familiar with the cultural history, it is essentially the digital version of a 'jump scare' prank, but with catchy 80s music instead of something frightening.

Sample 3: several videos grouped in one gallery grid
--------------------------------------------------------

.. gallery-grid::
   :grid-columns: 1 1 2 2

   - title: Intro talk
     content: |
       .. youtube:: 3Fp1zn5ao2M
   - title: Deep dive
     content: |
       .. youtube:: 3Fp1zn5ao2M
   - title: Lightning talk
     content: |
       .. youtube:: 3Fp1zn5ao2M

Sample 4: a gallery card with an admonition-wrapped video
---------------------------------------------------------------

.. gallery-grid::
   :grid-columns: 2

   - title: Recorded webinar
     content: |
       .. admonition:: YouTube
           :class: dropdown admonition-youtube

           .. youtube:: 3Fp1zn5ao2M
   - title: Project link
     link: https://pydata-sphinx-theme.readthedocs.io/
     link-alt: pydata-sphinx-theme docs

Sample 5: mixing video cards with ordinary link/image cards
------------------------------------------------------------------

.. gallery-grid::
   :grid-columns: 1 1 2 2

   - title: Watch the overview
     content: |
       .. youtube:: 3Fp1zn5ao2M
   - title: ArviZ
     link-alt: ArviZ Python docs
     link: https://python.arviz.org/
     img-bottom: ../_static/gallery/arviz.png
   - title: Ask a question in a dropdown
     content: |
       .. admonition:: Where do I ask questions?
           :class: dropdown

           Open a `GitHub Discussion <https://github.com/pydata/pydata-sphinx-theme/discussions>`__.

Sample 6: a card title that itself contains inline code
----------------------------------------------------------

reStructuredText was never affected by the backtick-fence issue this
sample exists to guard against on the MyST side (RST doesn't fence by
backtick count), but the same title renders correctly here too, for a
like-for-like comparison:

.. gallery-grid::
   :grid-columns: 2

   - title: Using the ``.. youtube::`` directive
     content: |
       .. youtube:: 3Fp1zn5ao2M
   - title: A plain ``code`` title, no video
     link: https://pydata-sphinx-theme.readthedocs.io/
     link-alt: pydata-sphinx-theme docs
