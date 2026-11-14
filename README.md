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
2. Wait for the catalog download to complete. Logo and folder choices update
   automatically.
3. Under **Automatic assignment**, add a row for each channel group to match.
   Choose a strategy and catalog folder, then save your settings.
4. Run **Auto Match** and review the results for skipped and failed channels.
5. For specific logos, add rows under **Manual assignment**, save, and run
   **Manual Match**.

## Automatic assignment

Auto Match runs when requested or scheduled, for groups with a valid enabled row. Start
with **Standard**, which uses channel names and station information. **Standard
+ fuzzy** also considers similar names when stronger matches are unavailable.
Review assignments, especially when using fuzzy matching.

Channel names that differ from catalog filenames may need a manual mapping.
Auto Match can match a name and number in either order and can infer an omitted
1 when there is no exact unnumbered match. Other differences, such as
E! for E Entertainment, may require a manual mapping.

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
skipped and failed channels**. The action needs an available task result.

Complete manual mappings and ignored channels are reported as preserved or
ignored rather than skipped. A preserved mapping has not necessarily been
applied or verified. Review skipped channels and failures in the action result.
The downloadable Auto Match result groups `channels` into `success`, `skipped`
and `failed` arrays, sorted by channel number. Successful entries distinguish
applied logos, preserved manual mappings and ignored channels. Ambiguous and
below-threshold results can include up to ten candidate catalog paths considered
within the configured scope and filters. `candidates_truncated` is the number
omitted. Fuzzy candidates include a `similarity` percentage; it measures name
similarity, not the probability that a logo is correct. Only the best-scoring
fuzzy candidates are shown, including ties. Candidate details do not change
the matching decision. The grouped object replaces the previous `channels` list
in newly generated reports; existing reports remain readable by the Ignore action.

### Advanced settings

The collapsed **Automatic assignment - Advanced** section includes options for
channel name cleanup, fuzzy threshold and logo variants. Add cleanup rules to
remove text at the start or end of a name, or a Python regex match anywhere.
The first matching rule removes one occurrence before matching. Existing
group-specific prefix rules still override the shared table. Avoid
regex patterns with excessive backtracking, which can stall
the matching task. The fuzzy threshold defaults to 90 percent; a match must
score above it. Similarity is not a probability that a logo is correct.

**Channel catalog hints** match the original channel name using contains, starts
with, or regex, optionally case-sensitive. Each matching row contributes a
case-insensitive include rule for the full catalog-relative path. For example,
a channel starting with `CA |` can prefer paths containing `canada`. Auto Match
tries the combined preferred paths first, then falls back to the normal pool
if no usable match is found, including ambiguous or low-scoring matches. The
fallback can therefore select a logo outside the hinted paths. Group scopes
and global catalog filters always apply. Hints do not remove name prefixes; use
the separate channel name cleanup setting if needed.

**Channel patterns to ignore** uses the same channel matching modes and optional
case sensitivity. A matching channel is ignored by Auto Match, including when
it has a manual mapping. Explicit Manual Match remains available. Invalid
pattern rules stop Auto Match until corrected.

Logo variant preference defaults to Prefer standard and can instead prefer an HD
logo within a recognized variant family. Prefer HD chooses the HD logo with the
fewest additional recognized variant attributes, or a standard logo when no HD
variant is available. Remaining ties are skipped.

**Use channel TVG ID as a station hint** is off by default. The station hint reads
the channel's TVG ID, using its override when set, not the matched EPG entry.
TVG IDs may be stale and cannot verify a station's city.

**Allow generic network logos** is on by default. It allows a generic network
logo to substitute for an unmatched station, not a confirmed station-specific
logo. Disable it to avoid these substitutions.

## Manual assignment

Add a channel and logo path to the mapping table, save, and run **Manual Match**.
An explicit mapping replaces the channel's existing logo. Duplicate rows,
missing channels and unavailable logo files are skipped; other valid mappings
can still be applied. Removing a mapping does not remove or restore its assigned
logo.

To prepare manual mappings for skipped and failed channels from the latest Auto
Match, run **Create manual mappings for skipped and failed channels**. The
action adds blank rows without
duplicating existing channels or choosing logos. Select a logo for each row,
save, and run Manual Match. Until completed or removed, blank mappings prevent
Auto Match from matching those channels. The action requires an available task
result and its stored channel identities.

The Manual Match result includes the saved manual mapping definitions. The
Auto Match result includes its group settings, ignored channels and advanced
settings, including channel hints and ignore patterns. Both results include
saved catalog filters. Filters do not prevent saved manual mappings from being
applied.
All action results include the plugin and Dispatcharr versions. Development
versions include the Dispatcharr build timestamp when available; an unavailable
Dispatcharr version is reported as `unknown`.

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

Use **Refresh tv-logos downloaded catalog** to download the latest catalog and
update the available choices. Catalog updates do not automatically assign
logos. After changing filters, save settings and reload the plugin to rebuild
the filtered logo and folder choices. Auto Match uses saved filters even before
the choices are rebuilt.

The actions that add ignored channels or manual mappings refresh saved settings
in the UI. Unsaved edits to the same settings take precedence over the refreshed
values. If channel choices are stale, reload the plugin to rebuild them.

## Scheduled Tasks

The collapsed **Scheduled Tasks** section below Catalog filters controls Auto
Match and catalog refresh independently. Both are disabled by default. Select
**Interval** and enter a whole number of hours from 1 to 87600, or select
**Cron** and enter five fields: minute, hour, day of month, month and weekday.
For example, `0 3 * * 0` runs at 03:00 on Sundays. Cron uses **UTC**, not the
container timezone. Numeric fields, lists, ranges and steps are supported;
weekday 0 or 7 is Sunday. When both day fields are restricted, either can
match. Invalid schedules do not run and are reported in settings and logs.

Save settings to apply a schedule. A new or changed interval starts counting
from when the scheduler sees it; a new cron schedule waits for a later minute.
Cron runs missed while the service is down are not replayed. An overdue interval
runs once after the service resumes, then counts from that dispatch. Task
history shows scheduled outcomes. Auto Match uses current saved settings and
can replace logos where Replace is enabled. Catalog refresh does not run Auto
Match or update copied logos, and choices still require a plugin reload.

The scheduler stops when the plugin loses leadership or is disabled. A task
already running is not stopped. Overlapping runs of the same action, including
manual runs, are rejected. A claimed slot can be lost if the leader crashes
between recording the claim and dispatching it; this avoids replaying the same
slot after a handoff. Dispatch failures are logged and retried while due.

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
**Refresh tv-logos downloaded catalog** to refresh it. The current and previous snapshots are
retained, and updates need temporary space for the archive and extracted images.
Logo choices come from a cached index rather than a filesystem scan at worker
startup. Existing installations build a missing index in the background and
refresh the available choices when indexing completes.
