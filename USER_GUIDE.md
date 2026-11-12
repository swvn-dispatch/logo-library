# Logo Library user guide

Logo Library assigns catalog images to Dispatcharr channels. Use **Manual
Match** for explicit channel-to-logo mappings and **Auto Match** for configured
channel groups. Auto Match runs only when you click it; catalog refreshes do not
run matching.

> This plugin is a development preview and has not yet been validated against a
> running Dispatcharr instance. Test with a small group before wider use.

## A typical path

1. Enable Logo Library and approve its requested capabilities. Wait for the
   initial TV Logos download to finish. Use **Refresh tv-logos** when you want
   to update the catalog.
2. Reload the plugin and reopen its settings after the catalog is downloaded or
   refreshed. Catalog choices come from an index built in the background.
3. For channels that must use a particular image, add rows under **Manual
   assignment** and save. Saved manual mappings take priority over Auto Match,
   even if a mapping row is incomplete. Run **Manual Match** to apply them.
4. Under **Automatic assignment**, add a group row, choose its strategy and
   catalog path scope, and save. Start with one small group and leave
   **Replace** unchecked.
5. Run **Auto Match** and review its results. It applies matches immediately;
   it is not a preview. Channels outside enabled group rows are omitted from the
   results. Missing, ambiguous and failed matches are reported for enabled
   groups. You can add manual mappings for channels that need specific logos.
6. Once the results are satisfactory, add more group rows. Only enable
   **Replace** for a group if its existing channel logos may be overwritten.

There is no automatic rollback. Removing a manual mapping or disabling a group
does not restore or remove a previously assigned logo.

## Suggested group rows

These are starting points for group names like the ones below. Your group names
can differ. Choose the group used by your Dispatcharr channels, not a provider
group that is not in the channel list.

| Group examples | Strategy | Path scope | Replace |
|---|---|---|---|
| `LOCALS - US` | Station call sign | `countries/united-states/us-local` | Off |
| `LOCALS - CA` | Station call sign | `countries/canada` | Off |
| `ENTERTAINMENT - US`, `NEWS - US`, `SPORTS - US` | Normalized name | `countries/united-states` | Off |
| `ENTERTAINMENT - UK`, `SPORTS - UK` | Normalized name | `countries/united-kingdom` | Off |
| `ENTERTAINMENT - CA`, `NEWS - CA`, `SPORTS - CA`, `SPORTS - QC` | Normalized name | `countries/canada` | Off |

Add one row per group. Groups without an enabled row are not matched. The
directory scope is relative to the catalog root: for example, select
`countries/united-states/us-local`, not `united-states`. A scope without
indexed logos is reported as a configuration error. A broader scope can find
more logos, but can also produce more ambiguous matches.

The Canadian local scope is broader than `countries/canada/local` because some
city-specific network logos are stored outside the `local` directory. Exact
station call-sign evidence is still restricted to station-specific paths.
Quebec examples in this catalog are under Canada, not a separate Quebec root.

## How the strategy and advanced settings work

Every enabled strategy tries scoped exact name and station evidence. The
**Station call sign** choice is a reporting hint, not a restriction to names
in a particular format. **Fuzzy name** additionally allows a similarity match
after stronger evidence fails. Start with the non-fuzzy choices in the table;
enable fuzzy matching only if you are comfortable with its false-positive risk.

The collapsed **Advanced matching** section applies its settings to all
configured groups:

- **Logo variant preference:** Start with **Skip ambiguous variants**. If you
  prefer the ordinary logo when the catalog contains recognized HD or
  horizontal variants, choose **Prefer standard variant**. Unrelated ties
  are still skipped.
- **Allow generic network logos:** Off by default. When enabled, an unmatched
  channel with an explicit call sign can use a generic network logo. For
  example, a local CTV station may receive a CTV logo instead of a
  station-specific image. This is a substitution, not a verified local match.
  The action result counts generic substitutions separately.
- **Use guide IDs as a station hint:** Off by default. This can help if a
  channel name lacks a call sign and its guide ID contains one. The matcher
  requires the channel name to agree with the network, but a stale guide ID
  for another city on the same network can still select the wrong station.
  Guide IDs are not durable mapping keys and do not override manual mappings.
- **Name prefix to remove / Prefix mode:** Usually leave the prefix blank.
  The matcher handles several common separators without requiring a particular
  country prefix. If needed, enter a literal prefix or select Regex for a
  Python regular expression matched at the start of the name. Avoid patterns
  with excessive backtracking; they can stall the matching task.
- **Fuzzy threshold:** Used only by groups with the fuzzy strategy. The default
  is 90; the similarity score must be strictly greater than the threshold. It
  is not a probability of correctness, and 100 cannot match anything.

Catalog coverage varies. For example, the tested catalog snapshot did not
provide reviewed in-scope targets for all Canadian local channels. A skipped
channel is safer than an unrelated logo. Check the catalog or use a manual
mapping when a suitable image exists.

## Scope and safety

Auto Match never intentionally overrides a saved manual mapping. It skips a
channel with an existing effective logo unless **Replace** is enabled for that
group. It also rechecks the current group, channel name, logo and relevant
saved settings before assigning. Conflicting evidence and unresolved ties are
skipped rather than guessed.

The results depend on the selected scope and available catalog files. Prefix
and variant rules are heuristics, and a unique result is not proof of the
correct channel identity. Review assigned logos, particularly when using
fuzzy, generic network or guide-ID hints.
