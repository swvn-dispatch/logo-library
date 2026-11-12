# Logo Library

A [Dispatcharr](https://github.com/Dispatcharr/Dispatcharr) plugin for assigning
channel logos from the [tv-logos catalog](https://github.com/tv-logo/tv-logos).
Use automatic matching by channel group or choose individual logos manually.

## Support

This project is maintained in my spare time. If it's saved you some headaches, a tip is always appreciated.

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/sethwv)

---

## Getting started

1. Enable Logo Library and approve its requested capabilities. The initial
   catalog download runs in the background.
2. When the download completes, click **Reload plugin** and reopen its settings.
3. Under **Automatic assignment**, add a row for each channel group to match.
   Choose a strategy and catalog folder, then save your settings.
4. Run **Auto Match** and review the results for skipped and failed channels.
5. For specific logos, add rows under **Manual assignment**, save, and run
   **Manual Match**.

## Automatic assignment

Auto Match runs only when requested, for groups with a valid enabled row. Start
with **Standard**, which uses channel names and station information. **Standard
+ fuzzy** also considers similar names when stronger matches are unavailable.
Review assignments, especially when using fuzzy matching.

Choose a catalog folder to limit the search, including its subfolders. A country
folder is a useful starting point unless a group spans multiple countries.
Choose **Entire catalog** to search all available paths. Catalog filters still
apply. A saved folder with no available logos produces a configuration error.

By default, Auto Match leaves existing channel logos alone. Check **Replace**
to allow overwriting them for a group. Saved manual mappings take priority,
including incomplete mappings with a channel selected. Channels outside enabled
groups are omitted from results; configuration errors are reported.

Use **Channels to ignore** below the group table to exclude individual channels
from Auto Match. This does not prevent an explicit Manual Match. To add all
skipped and failed channels from the latest Auto Match result, run **Ignore
skipped and failed channels**, then reload the plugin and reopen its settings.
The action needs an available task result.

Complete manual mappings and ignored channels are reported as preserved or
ignored rather than skipped. A preserved mapping has not necessarily been
applied or verified. Review skipped channels and failures in the action result.

### Advanced settings

The collapsed **Automatic assignment - Advanced** section includes options for
name prefixes, fuzzy threshold and logo variants. Prefixes can be literal or
Python regex. Avoid regex patterns with excessive backtracking, which can stall
the matching task. The fuzzy threshold defaults to 90 percent; a match must
score above it. Similarity is not a probability that a logo is correct.

**Use guide IDs as a station hint** and **Allow generic network logos** are off
by default. Guide IDs may be stale and cannot verify a station's city. A generic
network logo is a substitute, not a confirmed station-specific logo.

## Manual assignment

Add a channel and logo path to the mapping table, save, and run **Manual Match**.
An explicit mapping replaces the channel's existing logo. Duplicate rows,
missing channels and unavailable logo files are skipped; other valid mappings
can still be applied. Removing a mapping does not remove or restore its assigned
logo.

Selected images are copied into Dispatcharr's local logo directory. Assigned
logos remain available if the plugin is disabled or the catalog is unreachable.
After a catalog update, run Manual Match again to refresh assigned copies.
Image caches may delay visible changes.

## Catalog filters and updates

Use **Catalog filters** to narrow manual logo choices, automatic scope choices
and Auto Match candidates. Include and exclude rules match full catalog-relative
paths using case-insensitive contains, starts with, exact or regex matching.
Includes are combined; any matching exclusion removes a path. Saved manual
mappings remain available even if filtered out. Invalid filter settings stop
Auto Match until corrected.

Use **Refresh tv-logos** to download the latest catalog. Save settings, reload
the plugin and reopen its settings to refresh choices after changing filters or
updating the catalog. Catalog updates do not automatically assign logos.
Dispatcharr caches field options per process, so confirm that settings saved
successfully after a reload.

## Requirements

The manifest targets Dispatcharr `v0.34.0` or newer; this minimum is
provisional. The plugin requests background tasks, persistent service, outbound
network and filesystem write capabilities to manage the catalog and logos.
Catalog updates require disk space for snapshots and temporary files.

## Logo catalog credits

### TV Logos

The TV Logos catalog accesses images maintained by
[tv-logo/tv-logos](https://github.com/tv-logo/tv-logos). Logo Library does not
bundle or distribute its images. It provides tools to access the catalog and
map its logos to channels within Dispatcharr. Refer to the upstream project's
README for attribution and usage terms.

The catalog is downloaded locally when the plugin is enabled. Use
**Refresh tv-logos** to refresh it. The current and previous snapshots are
retained, and updates need temporary space for the archive and extracted images.
Logo choices come from a cached index rather than a filesystem scan at worker
startup. Existing installations build a missing index in the background. Reload
the plugin and reopen its settings once indexing completes.
