# Logo Library

Logo Library is a planned Dispatcharr plugin for mapping channel logos from
[tv-logo/tv-logos](https://github.com/tv-logo/tv-logos). The upstream project
provides the images and describes their usage terms in its README. Images are
downloaded separately and are not distributed with this repository.

## Development status

This repository is under construction. The manifest, initial Dispatcharr
integration, packaging, and release workflows are present, but live integration
validation and registry publishing remain outstanding. Do not use it in
production yet.

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

Build a local archive with `./package.sh`. To package a specific version
without changing the source manifest, use `./package.sh --version 0.1.0`.
Release workflows require a GitHub repository and an aggregator dispatch token.
The dev rebase workflow updates the remote `dev` branch on pushes to `main` and
stops on conflicts rather than resolving them automatically.

The current and previous catalog snapshots are retained; a new update also
requires temporary space for its archive and extracted files. No live
Dispatcharr integration or minimum supported version has been verified.
