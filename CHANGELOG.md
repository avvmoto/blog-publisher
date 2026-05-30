# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [0.1.0] - 2026-05-31

### Added
- `publish()` factory API with `PublishParams` validation
- `BaseBlogPlatform` ABC for platform implementations
- chichi-pui platform: image upload, title, caption, tags, age limit, taste, thumbnail (cover image)
- `tools/save_auth.py`: Chrome CDP-based session saver for Google OAuth sites
- Cloudflare detection bypass via `playwright-stealth`
- Pure-function test suite (17 tests, no mocks, no I/O)
