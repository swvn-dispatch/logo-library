# Regional lineup fixtures

`regional_lineup.json` contains the names-only US, UK, CA and QC group snapshot.
It contains no channel IDs, guide IDs, credentials or URLs. The four other JSON
files are synthetic formatting variants of the same group members:

- `region_dash`: `US - ABC Chicago - WLS`
- `region_colon`: `US: ABC Chicago (WLS)`
- `plain_parentheses`: `ABC Chicago (WLS)`
- `no_callsign`: `ABC Chicago`

Names without call signs retain the same channel name in the last two variants.
Variants preserve order and group membership. They do not contain verified logo
assignments and should not be treated as evidence that a match is correct.

After updating the source fixture, regenerate the variants from the repository
root with `python3 tests/fixture_variants.py`. Unit tests check that the checked-in
files match the generated variants and that the US-local station examples still
resolve. The call-sign-free regression uses synthetic guide IDs and requires the
optional guide-ID hint.
