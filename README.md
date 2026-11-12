# Logo Library

A [Dispatcharr](https://github.com/Dispatcharr/Dispatcharr) plugin for mapping
channel logos from logo catalogs. Choose a channel and a catalog logo in
the plugin settings, then apply your saved mappings to Dispatcharr.

See the [user guide](USER_GUIDE.md) for a typical setup and recommended group
settings.

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
assignment**, add a row for each group to enable, choose its strategy, catalog
scope and replacement policy, then save and run **Auto Match**. Only groups
used by channels are selectable, using their effective group assignments. The
sole registered catalog is selected automatically; matching is disabled if
multiple catalogs are registered until catalog selection is available.
Groups without a valid enabled configuration are skipped. Saved manual mappings always
take precedence, including incomplete mappings with a channel selected. By
default, channels with an effective logo are skipped; select **Replace** in a
group row to allow it. Review
the action result for skipped channels and failures. Channels outside enabled group configurations are
omitted from the results and skip counts. Invalid group configurations are
still reported. Catalog updates do not trigger matching.

The directory selector lists paths from the catalog index. A saved path that is
no longer available remains visible, but an empty scope produces a configuration
error rather than a series of misleading `no_match` results. Select **Entire
catalog**, or leave an override scope blank, to search the entire catalog.

The collapsed **Advanced matching** section contains optional prefix, fuzzy
threshold and variant controls. The shared prefix may be literal or Python
regex; regex is matched only at the beginning of the channel name. Avoid
expressions with excessive backtracking, which can stall the matching task.
Previously saved group-specific prefix rules remain available in this section
until removed and take precedence over the shared prefix. Invalid regex and
duplicate group rules disable that group. Older prefix and threshold values in
the main group table are ignored. The default fuzzy threshold is 90 percent.

Enabled groups use a layered matcher. It looks for exact normalized names,
station-specific call signs, and exact name components separated by a pipe or
spaced dash, regardless of any country prefix. Distinct strong candidates are
reported as conflicts. The strategy choice controls fuzzy fallback: selecting
**Standard + fuzzy** enables it after the stronger evidence fails; Standard
uses only stronger evidence. The result records the method used.

The normalized-name matcher uses Unicode normalization,
case folding, punctuation removal, `&` to `and`, and `+` to `plus`.
It preserves digits and does not transliterate or equate spelled-out numbers
with digits. It considers common descriptive suffixes such as `channel`,
`network` and `television` only when an exact name does not match. A small set
of country-scoped TV Logos aliases handles known alternate branding. An optional
literal or regex channel-name prefix is removed first. For TV
Logos, recognized country suffixes are stripped only in their corresponding
country directories; `hd`, `hz`, and `horizontal` filename suffixes are treated
as variants. Multiple matching paths are ambiguous by default. The optional
**Prefer standard variant** setting selects a single unmarked path only if all
candidates share a recognized HD or horizontal variant family. Other
country suffixes remain part of the name until explicitly supported.

The call-sign matcher considers uppercase US-style `K` or `W` call signs and
Canadian `C` call signs in channel names. It only uses station-specific TV
Logos directories `countries/united-states/us-local` and
`countries/canada/local`, narrowed by the configured scope. A generic filename
containing a call-sign-shaped word is not treated as station evidence. Multiple
call signs or unresolved variants are skipped. This heuristic does not verify
station identity.

**Use guide IDs as a station hint** is off by default. When enabled, a guide
ID may supply a call sign missing from the channel name, but only when it
resolves to a station-specific catalog file and the channel name agrees with
the network in that filename. The guide ID is checked again before assignment.
Guide IDs can change or become stale: network agreement cannot distinguish two
stations on the same network, so this option can still assign the wrong city.
It never changes the saved manual mapping or uses guide IDs as a durable key.

**Allow generic network logos** is off by default. When enabled, an unmatched
channel with an explicit station call sign may use an exact generic network
logo as a substitute for that local station. It requires a whole network-name
prefix and preserves numbered variants, such as CTV and CTV 2. The match is
reported as `network_fallback` and the action reports the number applied. This
is a network-level substitute, not a verified station-specific logo. Manual
mappings still take priority.

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
