---
status: Done (2026-11-21)
priority: Medium
related: [YCORE-004]
---

# [YCORE-005] Tagged report entries

## Summary

As the owner of a product line report, I want every report entry to carry free tags and the report data to select entries by tag, so that my report template decides the structure of the report and a new grouping needs no change in yanga-core.

## Description

A variant report lists the generated entries in the order the generators registered them. Results exist at several levels (one component, one container, all components merged, all containers merged, the variant test, everything merged) and of several kinds (tests, coverage, static analysis). A project cannot place them by level or kind, and a closed list of levels in yanga-core would grow with every new grouping (platform components, external components).

## Scope decisions

- **Free tags on every entry**: `ReportRelevantFiles` gets `tags: list[str]`, empty by default. The `file_type` stays: it tells the renderer how to include a file, not where.
- **Two selections on the report data**: `files(*tags)` returns the entries that carry all given tags, in registration order; `untagged()` returns the entries without tags.
- **A documented vocabulary, no enum**: level `component`, `container`, `variant`, `overall`, plus `merged`; kind `docs`, `sources`, `test`, `coverage`, `static-analysis`, `configuration`; the component name on its own entries. yanga-core documents it; generators in yanga set it.
- **The decision is recorded as the section "Tagged Report Entries"** of the design decisions, with the wording agreed in the planning note.
- **Domain selection and template view** (decided in the epic run, 2026-11-21): the domain `ReportData.entries(*tags)` and `ReportData.untagged_entries()` return the entries (`list[ReportRelevantFiles]`); the template-facing `SphinxReportConfig.files(*tags)` and `SphinxReportConfig.untagged()` return the toctree lines of those entries, built as `get_component_files_list` builds them. Different names, because a subclass method cannot change the return type. Order: registration order within each component and within the variant entries; components in report order, then the variant entries. The ADR's "The shape" uses these four names.
- **yanga-core tags its own registrations** (decided in the epic run, 2026-11-21): yanga cannot tag an entry yanga-core registers, so yanga-core sets the tags itself. The only one is the feature documentation of `KConfigGen`: `variant`, `configuration`.
- Out of scope: setting tags in yanga's generators (YANGA-011), the project templates (SPLED-006), a check for unknown tags in a template.

## Acceptance criteria

- [x] A report entry carries the tags it was registered with, and they survive the write and read of `report_config.json`
- [x] `files(*tags)` returns exactly the entries that carry all given tags, in registration order, and nothing when no entry matches
- [x] `untagged()` returns exactly the entries without tags
- [x] The design decisions have the section "Tagged Report Entries", and the domain reference describes the tags, the two selections and the vocabulary
- [x] `pypeline run` is green
