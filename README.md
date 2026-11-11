# Logo Library

A [Dispatcharr](https://github.com/Dispatcharr/Dispatcharr) plugin for mapping
channel logos from logo catalogs. Choose a channel and a catalog logo in
the plugin settings, then apply your saved mappings to Dispatcharr.

> **Development preview:** Logo Library has not yet been validated against a
> running Dispatcharr instance. The minimum Dispatcharr version and release
> workflows are also unverified. Do not use it in production yet.

## Support

This project is maintained in my spare time. If it's saved you some headaches, a tip is always appreciated.

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/sethwv)

---

## How it works

Logo catalogs manage their own storage and actions. Selected images are copied
into Dispatcharr's local logo directory when mappings are applied, so assigned
logos do not depend on the plugin being enabled or on a catalog being reachable.

- Map multiple channels to the same logo.
- Replace existing channel logos, including logos on automatically created channels.
- Keep mappings in the settings table after applying them.
- Select logos from multiple catalogs in the same mapping table.
- Update a logo catalog using its action.
- Use **Apply changes** to refresh assigned copies after catalog updates.

Automatic assignment is planned but is not implemented.

## Catalog filters

Use the collapsed **Catalog filters** section to narrow the logo choices in the
mapping table. Filters currently apply to TV Logos. Each row selects an include
or exclude mode and text to match against the full catalog-relative path.
Contains, starts with, exact, and regex modes are case-insensitive. For example,
an **Include contains** row with `canada` shows matching paths.

When there are include rows, a path must match at least one of them. Any matching
exclude row removes it from the choices. Without include rows, all paths are
included before exclusions. Existing mapped logos remain selectable even when
filtered out. Save the settings, reload the plugin, and reopen its settings to
refresh the choices.

Regex uses Python's regular expression syntax. Invalid or incomplete rows are
ignored and reported in the filter section after reload. Avoid expressions that
cause excessive backtracking, as they can stall the settings page.

## Manual assignment

1. Enable Logo Library and approve its requested capabilities. The initial
   catalog download runs in the background.
2. Once the initial catalog download completes, click **Reload plugin** and reopen its settings.
3. Under **Manual assignment**, add a row and select a channel and logo path.
   The dropdown identifies each logo by catalog and catalog-relative path.
4. Save the plugin settings, then run **Apply changes**. Review the action
   result for skipped rows and errors.

An explicit mapping replaces the channel's existing logo. Duplicate channel
rows are skipped, as are missing channels or logo files; other valid mappings
can still be applied. Removing a row stops managing that channel but does not
remove or restore its previously assigned logo. Disabling or uninstalling the
plugin does not remove assigned copies.

After updating a catalog, reload the plugin and reopen its settings
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
| Outbound network | Download logo catalogs. |
| Filesystem write | Copy selected logos into `/data/logos` for Dispatcharr to serve. |

Logo catalogs may need persistent and temporary disk space.

## Logo catalog credits

### TV Logos

The TV Logos catalog accesses images maintained by
[tv-logo/tv-logos](https://github.com/tv-logo/tv-logos). Logo Library does not
bundle or distribute its images. It provides tools to access the catalog and
map its logos to channels within Dispatcharr. Refer to the upstream project's
README for attribution and usage terms.

The catalog is downloaded locally when the plugin is enabled. Use
**Refresh TV Logos library** to refresh it. The current and previous snapshots are
retained, and updates need temporary space for the archive and extracted images.
Logo choices come from a cached index rather than a filesystem scan at worker
startup. Existing installations build a missing index in the background. Reload
the plugin and reopen its settings once indexing completes.
