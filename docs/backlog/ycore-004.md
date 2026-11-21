---
status: Done (2026-11-21)
priority: Medium
related: [YCORE-001]
---

# [YCORE-004] Component path, containers and repository URL for the reports

## Summary

As the owner of a product line report, I want the report data to carry each component's path relative to the project root and to tell containers apart with their subcomponents, and the publish manifest to carry the repository URL next to the commit, so that a report can show the components as a folder tree, list the containers on their own, and link sources and commits to the code host without any configuration.

## Description

The variant report lists all components in one flat list, so a reader cannot see where a component lives. The report data of a component carries only its name, files and build directory, although the resolved component knows its path. A container (a component with subcomponents and no sources of its own) gets an entry like any other component; without documentation it shows as an empty chapter (`light_application` in the SPLedY Disco gtest report).

The publish manifest records the commit of a run, but not where that commit can be seen. The SPL overview therefore shows the commit as a plain hash, and the source links in the reports cannot point at the code host on CI. Nothing in a project holds the repository URL today, and the owner wants to configure it in one place at most; detecting it from the checkout needs no configuration at all.

## Scope decisions

- **The path replaces a component kind.** Grouping by variant, platform and external was dropped: a container whose subcomponents come from several of them has no single kind, and the folder tree helps a reader find a component without extra rules.
- **The path is relative to the project root**, with `/` as the separator. An external component lies under its external project, so its path is wherever that project is, which may be inside the build tree.
- **A container carries the names of its subcomponents** in the report data, so a template lists it with them; a subcomponent keeps its own entry and path.
- **The repository URL is detected, not configured**: from the `origin` remote of the project checkout, an SSH form (`git@host:org/repo.git`) turned into the HTTPS form (`https://host/org/repo`). One function next to the commit detection, used by the publish manifest and by build backends (yanga's source links). No URL when there is no git, no remote, or a form it cannot turn into HTTPS.
- Out of scope: the report templates (SPLED-004), link formats of a code host (the function returns the base URL only), a configuration override for the URL.

## Acceptance criteria

- [x] The component report data of every component carries its path relative to the project root
- [x] The component report data of a container names its subcomponents; it is empty for any other component
- [x] The repository URL function returns the HTTPS URL for an HTTPS and for an SSH `origin`, and nothing without git or without a remote
- [x] The publish manifest records the repository URL when one is detected
- [x] The domain reference describes the new report data fields and the repository URL
- [x] `pypeline run` is green
