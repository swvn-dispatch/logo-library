# Guide IDs as logo matching signals

## Recommendation

Do not use guide IDs for automatic assignment yet. They are optional,
source-dependent metadata, not stable channel identities. The preliminary
candidate counts below do not establish correctness, and additional matches
have not been manually verified. A changed or missing guide ID must never
invalidate a saved manual mapping.

## Candidate parsing and risks

A conservative experiment decoded HTML entities, stripped a trailing
two-letter country suffix after a dot for name matching, and otherwise matched
the resulting string with the existing normalized-name matcher. The local
station experiment extracted uppercase US-style call-sign tokens from decoded
IDs using the existing call-sign matcher. Examples such as `ABC&amp;News.us`,
`WXYZ.example`, and `Network.us (Alias)` are illustrative, not production
values. The first decodes to `ABC&News.us`; the second may contain a call-sign
token; the third shows why a suffix cannot safely be removed without knowing
the ID format.

Parsing may collide across countries, providers, aliases, and channels. A
call-sign-shaped token can be an ordinary word or refer to a different station.
Guide IDs can be stale, recycled, HTML-encoded, missing, or changed by a source.
Any future use should be supplemental, respect the configured catalog scope,
reject conflicting signals and ambiguous candidates, and never supersede a
manual mapping. The current matcher does not consume guide IDs.

## Preliminary read-only query results

On the sampled lineup, 365 of 815 channels had a nonempty effective guide ID.
Among those IDs, 343 contained a dot, 132 contained parentheses, four
contained an HTML entity, and 13 contained an uppercase US-style call-sign
token. Counts reflect the sampled instance at one point in time, not a general
estimate across providers.

The following is a counterfactual comparison across **all** sampled channels
against each listed catalog scope. It does not use actual group assignments,
and candidates are not verified assignments. For each scope, the baseline is
the current channel-name strategy. Additional candidates are guide-ID matches
for which that baseline found no unique path.

| Scope and strategy | Baseline unique | Guide-ID unique | Additional candidates | Both agree | Both disagree | Guide-ID ambiguous |
|---|---:|---:|---:|---:|---:|---:|
| US catalog, normalized name | 4 | 2 | 2 | 0 | 0 | 2 |
| UK catalog, normalized name | 4 | 2 | 2 | 0 | 0 | 12 |
| US local catalog, call sign | 12 | 12 | 0 | 12 | 0 | 0 |

The two additional candidates in each name scope may overlap between scopes.
The absence of disagreements among unique matches is not a false-positive
rate: no independent ground truth was checked, and the experiment excludes
nonmatching IDs and uses hypothetical scopes. Actual incremental coverage and
false-positive rates require a representative, group-scoped sample with
independently verified expected logos across multiple providers and ID formats.
