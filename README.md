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
- Use **Manual Match** to refresh assigned copies after catalog updates.

Automatic assignment runs only when explicitly requested. Under **Automatic
assignment**, add and save a row for each group to enable, select a strategy
and optional directory scope, then run **Auto Match**. Only groups
used by channels are selectable, using their effective group assignments. The
sole registered catalog is selected automatically; matching is disabled if
multiple catalogs are registered until catalog selection is available.
Groups without a valid enabled row are skipped. Saved manual mappings always
take precedence, including incomplete mappings with a channel selected. By
default, channels with an effective logo are skipped; select **Replace** for a
group to allow replacement. Review the action result for skipped
channels and failures. Channels outside enabled group configurations are
omitted from the results and skip counts. Invalid group configurations are
still reported. Catalog updates do not trigger matching.

The directory selector lists paths from the catalog index. A saved path that is
no longer available remains visible, but an empty scope produces a configuration
error rather than a series of misleading `no_match` results. Leave the scope
blank to search the entire catalog.

The default name prefix and fuzzy threshold are shared settings below the group
table. Add a group-specific prefix rule to override the default for a group.
Rules may be literal or Python regex; regex is matched only at the beginning of
the channel name. Avoid expressions with excessive backtracking, which can stall
the matching task. Invalid regex and duplicate group rules disable that group.
Older prefix and threshold values in the main group table are ignored. The
default fuzzy threshold is 90 percent.

The normalized-name matcher uses Unicode normalization,
case folding, punctuation removal, `&` to `and`, and `+` to `plus`.
It preserves digits and does not transliterate or equate spelled-out numbers
with digits. An optional literal or regex channel-name prefix is removed first. For TV
Logos, recognized country suffixes are stripped only in their corresponding
country directories; `hd`, `hz`, and `horizontal` filename suffixes are treated
as variants. Multiple matching paths are ambiguous by default. The optional
**Prefer standard variant** setting selects a single unmarked path only if all
candidates share a recognized HD or horizontal variant family. Other
country suffixes remain part of the name until explicitly supported.

The call-sign matcher only considers uppercase US-style `K` or
`W` call signs in channel names and station-specific TV Logos paths under
`countries/united-states/us-local`. The configured directory scope narrows those
paths further. Multiple call signs or unresolved logo variants are skipped. This
heuristic does not verify station identity and does not support Canadian call
signs or guide metadata yet.

The fuzzy matcher scores normalized names with Python's
`SequenceMatcher` ratio, expressed as a percentage. A match must score strictly
above the configured threshold, so a threshold of 100 cannot match anything.
Digit sequences and the presence of `plus` must agree. Exact top-score ties
are skipped unless the standard-variant preference resolves a recognized variant
family; a close second score does not prevent a unique winner. The score
is a similarity measure, not a probability that an assignment is correct.

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
4. Save the plugin settings, then run **Manual Match**. Review the action
   result for skipped rows and errors.

An explicit mapping replaces the channel's existing logo. Duplicate channel
rows are skipped, as are missing channels or logo files; other valid mappings
can still be applied. Removing a row stops managing that channel but does not
remove or restore its previously assigned logo. Disabling or uninstalling the
plugin does not remove assigned copies.

After updating a catalog, reload the plugin and reopen its settings
before editing mappings. Catalog updates do not change assigned logos until you
run **Manual Match** again. Image caches may delay visible changes.

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
**Refresh tv-logos** to refresh it. The current and previous snapshots are
retained, and updates need temporary space for the archive and extracted images.
Logo choices come from a cached index rather than a filesystem scan at worker
startup. Existing installations build a missing index in the background. Reload
the plugin and reopen its settings once indexing completes.
