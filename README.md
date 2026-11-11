# Logo Library

Logo Library is a planned Dispatcharr plugin for mapping channel logos from
[tv-logo/tv-logos](https://github.com/tv-logo/tv-logos). The upstream project
provides the images and describes their usage terms in its README. Images are
downloaded separately and are not distributed with this repository.

## Development status

This repository is under construction. The manifest and initial Dispatcharr
integration are present, but packaging, release workflows, and live integration
validation remain outstanding. Do not use it in production yet.

The plugin begins downloading the catalog when enabled. After the download or
an Update catalog action, click **Reload plugin** and reopen its settings.
Save the mappings before clicking **Apply changes**. Deleting a row does not
undo a previously assigned logo. Updating the catalog does not update channel
logos until Apply changes runs again.

The native dropdowns are not searchable, and Dispatcharr can validate against
stale per-process field options even after a reload. This is a known upstream
limitation. A failed settings save must be resolved before applying changes.
The plugin requires background tasks, a leader service, outbound network access,
and permission to write copies into `/data/logos`.

Run the offline tests with:

```sh
python3 -m unittest discover -s tests -v
```

Catalog snapshots are currently retained after updates to avoid invalidating
readers. Snapshot cleanup and disk usage management must be addressed before a
release. No live Dispatcharr integration or minimum supported version has been verified.
