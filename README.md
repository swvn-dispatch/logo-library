# Logo Library

Logo Library is a planned Dispatcharr plugin for mapping channel logos from
[tv-logo/tv-logos](https://github.com/tv-logo/tv-logos). The upstream project
provides the images and describes their usage terms in its README. Images are
downloaded separately and are not distributed with this repository.

## Development status

This repository is under construction and is **not yet an installable
Dispatcharr plugin**. The current code implements a staged catalog snapshot
and mapping validation core. The manifest, Dispatcharr integration, plugin
actions, user interface, and release workflows remain to be implemented.

Run the offline tests with:

```sh
python3 -m unittest discover -s tests -v
```

Catalog snapshots are currently retained after updates to avoid invalidating
readers. Snapshot cleanup and disk usage management must be addressed before a
release. No live Dispatcharr integration has been verified.
