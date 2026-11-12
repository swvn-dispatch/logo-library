# Regional lineup fixtures

`regional_lineup.json` contains the names-only US, UK, CA and QC group snapshot.
It contains no channel IDs, guide IDs, credentials or URLs. The four other JSON
files are synthetic formatting variants of the same group members:

- `region_dash`: `US - ABC Chicago - WLS`
- `region_colon`: `US: ABC Chicago (WLS)`
- `plain_parentheses`: `ABC Chicago (WLS)`
- `no_callsign`: `ABC Chicago`

Names without call signs retain the same channel name in the last two variants.
Variants preserve order and group membership.

`catalog_paths.regional.json` is a paths-only snapshot of the Canadian, US and
UK portions of `tv-logo/tv-logos` at the revision recorded in the file. It does
not contain images or require a network connection. `regional_expected.json`
contains explicit, name-reviewed path expectations in the same order as the
original lineup. A `generic:` prefix marks an opt-in network-level substitute,
not a verified station-specific logo. `null` means no reviewed in-scope match
is currently expected, not necessarily that a logo does not exist elsewhere.
The expectations compare names and catalog paths; most logo images have not been
visually verified.

`test_regional_matrix.py` checks every channel in all five formats against
those expectations, including paths that must remain unmatched. It uses the
standard-variant preference, enables generic network fallback, and supplies
synthetic guide IDs for US local stations. A generic station substitution is
expected to be skipped in the no-call-sign format. These options are not the
plugin defaults and guide data can be stale.

The current snapshot has ten channels without a reviewed in-scope target:
Flavour Network, Home Network, NASA+, the four Rogers TV local channels, CNN in
the Canadian scope, CityNews 24/7, and Ontario Legislature. This does not prove
that no suitable image exists outside the selected scope or in another catalog.
The matrix deliberately expects a skip rather than an unverified substitution.

After updating the source fixture, regenerate the variants from the repository
root with `python3 tests/fixture_variants.py`. Update the ordered expectations
and catalog-path snapshot separately after reviewing changes. Unit tests check
that the checked-in variants match the source and the US-local examples resolve.
