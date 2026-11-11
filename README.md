# Logo Library

A [Dispatcharr](https://github.com/Dispatcharr/Dispatcharr) plugin for mapping
channel logos from the [tv-logo/tv-logos](https://github.com/tv-logo/tv-logos)
catalog. Choose a channel and a logo path in the plugin settings, then apply
your saved mappings to Dispatcharr.

> **Development preview:** Logo Library has not yet been validated against a
> running Dispatcharr instance. The minimum Dispatcharr version and release
> workflows are also unverified. Do not use it in production yet.

## Support

This project is maintained in my spare time. If it's saved you some headaches, a tip is always appreciated.

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/sethwv)

---

## How it works

When enabled, Logo Library queues a download of the tv-logos catalog into its
persistent plugin storage. Selected images are copied into Dispatcharr's local
logo directory when mappings are applied, so assigned logos do not depend on
the plugin being enabled or on the upstream repository being reachable.

- Map multiple channels to the same logo.
- Replace existing channel logos, including logos on automatically created channels.
- Keep mappings in the settings table after applying them.
- Update the local catalog manually with the **Update catalog** action.
- Use **Apply changes** to refresh assigned copies after a catalog update.

Automatic assignment is planned but is not implemented.

## Manual assignment

1. Enable Logo Library and approve its requested capabilities. The initial
   catalog download runs in the background.
2. Once the download completes, click **Reload plugin** and reopen its settings.
3. Under **Manual assignment**, add a row and select a channel and logo path.
   Logo paths are relative to the tv-logos repository, including nested folders.
4. Save the plugin settings, then run **Apply changes**. Review the action
   result for skipped rows and errors.

An explicit mapping replaces the channel's existing logo. Duplicate channel
rows are skipped, as are missing channels or logo files; other valid mappings
can still be applied. Removing a row stops managing that channel but does not
remove or restore its previously assigned logo. Disabling or uninstalling the
plugin does not remove assigned copies.

After running **Update catalog**, reload the plugin and reopen its settings
before editing mappings. Catalog updates do not change assigned logos until you
run **Apply changes** again. Image caches may delay visible changes.

### Current limitations

Dispatcharr's native table dropdowns are not searchable. Its plugin field
options are also cached per process, so a settings save can still encounter
stale options after a reload. Confirm that saving succeeded before applying
changes. A future upstream fix is needed for reliable field refresh across
processes.

## Dispatcharr requirements

The manifest targets Dispatcharr `v0.34.0` or newer and uses manifest version 2.
This minimum is provisional until tested. Enabling the plugin requests these
capabilities:

| Capability | Purpose |
|---|---|
| Background tasks | Download the catalog and apply mappings without blocking the UI. |
| Persistent service | Use Dispatcharr's leader lifecycle to queue the initial download. |
| Outbound network | Download the tv-logos catalog. |
| Filesystem write | Copy selected logos into `/data/logos` for Dispatcharr to serve. |

The current and previous catalog snapshots are retained. An update also needs
temporary disk space for the archive and extracted images.

## Logo attribution

The logo catalog is maintained by [tv-logo/tv-logos](https://github.com/tv-logo/tv-logos).
Images are downloaded separately and are not bundled in this plugin. Refer to
the upstream README for attribution and usage terms.

## Development

Run the offline tests with:

```sh
python3 -m unittest discover -s tests -v
```

Build a local archive with `./package.sh`. To package a specific version
without changing the source manifest, use `./package.sh --version 0.1.0`.

Pushes to `dev` trigger tests and a versioned GitHub prerelease. The prerelease
version uses the latest stable version and the source commit's short SHA. Its
ZIP contains the plugin under `logo_library`. The release workflow notifies the
plugin registry when the aggregator token is available. Dev builds are for
testing and may change without notice.

The dev rebase workflow updates the remote `dev` branch on pushes to `main` and
stops on conflicts rather than resolving them automatically.
