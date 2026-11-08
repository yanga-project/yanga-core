"""
What one run publishes and where readers find it.

A manifest on disk is the hand-off between separate runs (variant builds, the SPL documentation
report) and the SPL overview, which reads only manifests.
"""

from dataclasses import dataclass, field
from enum import auto
from pathlib import Path
from typing import Any

from py_app_dev.core.config import BaseConfigJSONMixin

from .config import StringableEnum, stringable_enum_field_metadata
from .reports import ReportScope

PUBLISH_MANIFEST_FILE_NAME = "publish_manifest.json"


class PublishKind(StringableEnum):
    REPORT = auto()
    ARTIFACT = auto()


@dataclass
class PublishedFile:
    """Registered by a step for a file it publishes; WritePublishManifest turns it into a manifest entry."""

    kind: PublishKind
    name: str
    #: Absolute path of the file; WritePublishManifest turns it into a link relative to the site root.
    path: Path


@dataclass
class ManifestEntry(BaseConfigJSONMixin):
    kind: PublishKind = field(metadata=stringable_enum_field_metadata(PublishKind))
    name: str
    #: Relative to the site root, or an absolute URL when the output is published elsewhere.
    link: str


@dataclass
class PublishManifest(BaseConfigJSONMixin):
    scope: ReportScope = field(metadata=stringable_enum_field_metadata(ReportScope))
    build_time: str
    variant: str | None = None
    platform: str | None = None
    build_type: str | None = None
    commit: str | None = None
    description: str | None = None
    #: Selected features and their values, as the feature model generator wrote them.
    features: dict[str, Any] = field(default_factory=dict)
    entries: list[ManifestEntry] = field(default_factory=list)
