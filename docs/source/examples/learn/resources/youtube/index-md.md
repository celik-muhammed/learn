# YouTube Resources

Video tutorials that pair well with scikit-plots.

## Videos

```{youtube-gallery} ./_data/youtube.yaml
:group-by: channel
:sort: -published
:show-description:
```

## Channels

```{gallery-grid}
:sort: title

- title: Statistics Globe
  link: https://www.youtube.com/@StatisticsGlobe
  content: |
    By Joachim Schork. Also publishes written tutorials at
    [statisticsglobe.com/tutorials](https://statisticsglobe.com/tutorials).
  language: [python, r]
```

## Adding a video

Paste the URL from your address bar into `_data/youtube.yaml`:

```yaml
- id: https://www.youtube.com/watch?v=SOME_ID&list=PLxxx&index=4
  title: What the video is about
  channel: Who made it
  tags: [topic]
```

Watch URLs, `youtu.be` links, Shorts and bare ids all work — the `&list=`
and `&index=` parts are ignored for a single video, so there is nothing to
clean up by hand.

To pull a whole channel or playlist in at once:

```bash
python -m scikitplot._sphinx_ext.youtube_catalog.sync \
    --source https://www.youtube.com/@StatisticsGlobe \
    --output learn/resources/youtube/_data/youtube.yaml
```

Review the diff, commit it. The documentation build itself never contacts
YouTube, so this page renders identically offline and on every rebuild.

See `examples/start-here.md` for the full set of sorting, filtering and
grouping options.
