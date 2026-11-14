# Changelog

All notable changes to this project are documented in this file.

## [v0.1.1](https://github.com/swvn-dispatch/logo-library/releases/tag/v0.1.1) - 2026-11-13

### Added

- Schedule Auto Match and catalog refresh independently using hourly intervals or UTC cron expressions. Both schedules are disabled by default.
- Choose a preference for HD logo variants when matching.
- Show candidate logos for ambiguous and below-threshold Auto Match results, including similarity scores for fuzzy matches.

### Changed

- Prefer standard logo variants and allow generic network logos for unmatched stations by default. Both settings can be changed in advanced options.
- Group downloadable Auto Match results into successful, skipped, and failed channels, sorted by channel number. This changes the `channels` field from a list to an object in new reports.

### Fixed

- Prefer HD logos with fewer additional variant attributes when multiple HD variants are available.
- Display automatic assignment group guidance as separate, readable lines.

## [v0.1.0](https://github.com/swvn-dispatch/logo-library/releases/tag/v0.1.0) - 2026-11-12

### Added

- Assign Dispatcharr channel logos from the tv-logos catalog using manual mappings or on-demand automatic matching by channel group.
- Choose a catalog folder and matching strategy for each group, with optional fuzzy matching and controls for replacing existing logos.
- Filter catalog paths to narrow logo choices and automatic matching candidates.
- Exclude individual channels from automatic matching or add skipped and failed channels to the ignore list.
- Configure name prefixes, logo variant preferences, station hints, and fuzzy matching thresholds.
- Review matching results, including skipped and failed channels, and refresh the catalog when new logos are available.
