# Changelog

## [v1.2.0] - 2026-05-06
### Added
- Real chapter counts fetched from uuread individual novel pages
- Parallel fetching with 10 threads for speed
- Multi-pattern HTML scraper with in-memory caching
- Live DOM updates that preserve counts across poll cycles
- Minimum chapter filter applied after counts load

## [v1.1.0] - 2026-05-06
### Added
- WTR smart matching using CN character overlap
- Probable/Duplicate/New tabs for result categorisation
- WTR search button on each result card
- Tags & keywords filter system
- CSV export for submission

### Fixed
- Relative API URL for ngrok compatibility

## [v1.0.0] - 2026-05-06
### Added
- Initial release
- uuread.tw scraper (300+ novels per search, ongoing + completed)
- Flask backend with job-based async search
- Beautiful dark parchment UI
