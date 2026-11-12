# Logo Library user guide

Logo Library assigns catalog images to Dispatcharr channels. **Manual Match**
applies explicit channel-to-logo mappings. **Auto Match** applies matches for
configured channel groups only when you click the action. Refreshing the
catalog does not run matching.

> This plugin is a development preview. Start with a small group and review
> its results before using it more widely.

## Typical setup

1. Enable Logo Library and approve its requested capabilities. Wait for the
   initial TV Logos download. Use **Refresh tv-logos** to update it later.
2. Reload the plugin and reopen settings after downloading or refreshing the
   catalog. Path choices come from its background-built index.
3. For channels that need a particular logo, save rows under **Manual
   assignment**, then run **Manual Match**. Saved manual mappings take priority
   over Auto Match, even if a mapping row is incomplete.
4. Under **Automatic assignment**, add a row for one group. Choose a strategy
   and path scope, leave **Replace** off, and save.
5. Run **Auto Match**, inspect its result, and review the channel logos. The
   action applies matches immediately; it is not a preview. Channels outside
   enabled group rows are omitted from its results.
6. Add other groups after checking the first. Enable **Replace** for a group
   only if its existing effective logos may be overwritten.

There is no automatic rollback. Removing a mapping or disabling a group does
not restore or remove a logo already assigned to a channel.

## Suggested group settings

These are starting points for group names like the ones below. Your group names
may differ. Add one row for each group you want to match, and leave **Replace**
off until you are comfortable with the results.

| Group examples | Strategy | Path scope |
|---|---|---|
| `LOCALS - US` | Standard | `countries/united-states/us-local` |
| `LOCALS - CA` | Standard | `countries/canada` |
| `ENTERTAINMENT - US`, `NEWS - US`, `SPORTS - US` | Standard | `countries/united-states` |
| `ENTERTAINMENT - UK`, `SPORTS - UK` | Standard | `countries/united-kingdom` |
| `ENTERTAINMENT - CA`, `NEWS - CA`, `SPORTS - CA`, `SPORTS - QC` | Standard | `countries/canada` |

Scopes are relative to the catalog root. For example, select
`countries/united-states/us-local`, not `united-states`. A scope with no
indexed logos is reported as a configuration error. A broader scope can find
more logos but can also produce more ambiguous matches.

The Canadian local example uses `countries/canada` because some city-specific
logos are outside the `local` directory. Quebec sports logos are under the
Canadian catalog. These locations depend on the catalog and may change.

## Strategies

Start with **Standard**. It uses scoped exact-name, station-call-sign, and
name-part evidence without requiring a specific channel-name format. Change to
**Standard + fuzzy** only if Standard misses channels and you are willing to
review possible false matches. Fuzzy matching adds similarity-based candidates
after stronger evidence fails. Similar names can belong to different channels,
so a high score does not guarantee a correct logo.

If an existing row shows **Standard (legacy station hint)**, it uses the same
matching checks as Standard. You can change it to Standard when editing the row.

## Advanced matching

The collapsed **Advanced matching** controls apply to all configured groups.
Start with the defaults and change them deliberately:

- **Logo variant preference:** The default, **Skip ambiguous variants**, is
  conservative. **Prefer standard variant** can select an unmarked logo when
  the alternatives are recognized HD or horizontal variants of the same
  logo family. Unrelated ties are still skipped. Review the selected images.
- **Allow generic network logos:** Off by default. When enabled, an unmatched
  channel with an explicit call sign can use a generic network logo. For
  example, a local CTV station may receive a CTV logo instead of a
  station-specific image. This is a substitution, not a verified local match.
  The action counts generic substitutions separately.
- **Use guide IDs as a station hint:** Off by default. This can help when a
  channel name lacks a call sign but its guide ID contains one. The matcher
  requires the channel name to agree with the network, but a stale guide ID
  for another city on the same network can still select the wrong station.
  Guide IDs are not durable mapping keys and do not override manual mappings.
- **Name prefix to remove / Prefix mode:** Usually leave the prefix blank. The
  matcher handles common separators without requiring a particular country
  prefix. If needed, enter a literal prefix or select Regex for a Python
  regular expression matched at the start of the name. Avoid patterns with
  excessive backtracking, which can stall the matching task.
- **Fuzzy threshold:** Used only by groups set to Standard + fuzzy. The default is 90, and
  the score must be strictly greater than the threshold. A threshold of 100
  cannot produce a fuzzy match. Higher scores do not guarantee correctness.

## Safety and results

Auto Match skips saved manual mappings and, unless **Replace** is enabled,
channels with an existing effective logo. Before assigning, it rechecks the
group, channel name, effective logo, and relevant saved settings. Conflicting
evidence and unresolved ties are skipped.

The selected scope and available catalog files determine what can be matched.
Even a unique match can be wrong, especially with fuzzy matching, generic
network logos, or guide-ID hints. Review results before enabling replacement for
more groups, and use manual mappings where a specific logo matters.
