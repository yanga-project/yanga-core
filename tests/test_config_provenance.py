from dataclasses import dataclass, field
from pathlib import Path

import pytest
from py_app_dev.core.exceptions import UserNotificationException

from yanga_core.domain.config import BuildTargets, ComponentConfig, ConfigElement, IncludeDirectory, PlatformConfig, SourceLocation, YangaUserConfig, export, parse


@dataclass
class _Leaf(ConfigElement):
    name: str
    level: int | None = None


@dataclass
class _Doc(ConfigElement):
    leaves: list[_Leaf] = field(default_factory=list)


@dataclass
class _DocWithScalar(ConfigElement):
    # A located child list declared BEFORE a scalar that can fail. The scalar
    # belongs to this element, so a bad value must localize here, not to a child.
    leaves: list[_Leaf] = field(default_factory=list)
    level: int | None = None


def _write(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


def test_parse_locates_root_and_nested(tmp_path: Path) -> None:
    doc = parse(_Doc, _write(tmp_path / "d.yaml", "leaves:\n  - {name: a}\n  - {name: b}\n"))
    first, second = doc.leaves
    assert doc.location is not None
    assert first.location is not None
    assert second.location is not None
    assert doc.location.line == 1
    assert first.location.line == 2
    assert second.location.line == 3
    assert first.location.file == tmp_path / "d.yaml"


def test_export_is_provenance_free(tmp_path: Path) -> None:
    doc = parse(_Doc, _write(tmp_path / "d.yaml", "leaves:\n  - {name: a, level: 3}\n"))
    assert export(doc) == {"leaves": [{"name": "a", "level": 3}]}


def test_location_excluded_from_equality() -> None:
    a = _Leaf(name="a", location=SourceLocation(Path("a.yaml"), 1, 1))
    b = _Leaf(name="a", location=SourceLocation(Path("b.yaml"), 9, 9))
    assert a == b


def test_content_passthrough_stays_byte_clean(tmp_path: Path) -> None:
    """
    R1 keystone: a located fragment keeps a byte-clean ``content:`` payload.

    The ConfigFile is located, but no position is injected into the passthrough
    payload, so downstream parsers see clean bytes.
    """
    yaml_file = _write(
        tmp_path / "yanga.yaml",
        "configs:\n  - id: scoop\n    content:\n      apps:\n        - {name: git}\n",
    )
    user_config = YangaUserConfig.from_file(yaml_file)
    cfg = user_config.configs[0]
    assert cfg.location is not None
    assert cfg.content is not None
    assert cfg.location.file == yaml_file
    assert "location" not in cfg.content
    assert "location" not in cfg.content["apps"][0]


def test_kw_only_location_allows_mandatory_metadata_and_union_fields() -> None:
    """
    The kw_only ``location`` coexists with mandatory, metadata, and union fields.

    Verified by instantiating the real config classes that exercise each shape.
    """
    ComponentConfig(name="c")  # mandatory leading field
    IncludeDirectory.from_dict({"path": "inc", "scope": "public"})  # stringable-enum metadata field
    PlatformConfig(name="p", build_targets=["all"])  # union branch: list[str]
    PlatformConfig(name="p", build_targets=BuildTargets(generic=["all"]))  # union branch: dataclass


def test_parse_error_names_the_file(tmp_path: Path) -> None:
    bad = _write(tmp_path / "broken.yaml", "leaves:\n  - {name: a, level: not-an-int}\n")
    with pytest.raises(UserNotificationException) as exc:
        parse(_Doc, bad)
    assert "broken.yaml" in str(exc.value)
    assert "level" in str(exc.value)  # the field that failed is named


def test_parse_error_pinpoints_offending_list_element_not_a_sibling(tmp_path: Path) -> None:
    # line 2 is a VALID leaf; the bad one is on line 3. The error must point at
    # the actual culprit, not the innocent first element.
    bad = _write(tmp_path / "broken.yaml", "leaves:\n  - {name: ok}\n  - {name: a, level: not-an-int}\n")
    with pytest.raises(UserNotificationException) as exc:
        parse(_Doc, bad)
    message = str(exc.value)
    assert "broken.yaml:3:" in message
    assert "broken.yaml:2:" not in message


def test_parse_error_pinpoints_deeply_nested_element_in_real_config(tmp_path: Path) -> None:
    # A bad enum value buried in the second component's include_directories (line 7).
    # The walk must descend components -> include_directories to the exact line.
    bad = _write(
        tmp_path / "yanga.yaml",
        "components:\n"
        "  - name: good\n"
        "    include_directories:\n"
        "      - {path: inc, scope: public}\n"
        "  - name: bad\n"
        "    include_directories:\n"
        "      - {path: inc, scope: nonsense}\n",
    )
    with pytest.raises(UserNotificationException) as exc:
        YangaUserConfig.from_file(bad)
    message = str(exc.value)
    assert "yanga.yaml:7:" in message
    assert "yanga.yaml:2:" not in message  # not the valid first component


def test_subclass_declaring_location_is_rejected() -> None:
    # The reservation is enforced, not merely documented: redeclaring `location`
    # on a subclass fails loudly at definition time, in front of whoever edits it.
    with pytest.raises(TypeError, match="reserved"):

        @dataclass
        class _Bad(ConfigElement):
            location: str = "anywhere"  # type: ignore[assignment]  # intentionally illegal — that's what we assert


def test_user_location_yaml_key_is_ignored_not_hijacked(tmp_path: Path) -> None:
    # A user field literally named `location:` must not be routed into the provenance
    # field. The wire alias keeps it an ignored unknown key, so the element keeps its
    # real loader-derived location and parsing does not raise. (Pre-alias, mashumaro
    # tried to deserialize the string into SourceLocation and this raised.)
    doc = parse(_Doc, _write(tmp_path / "d.yaml", "leaves:\n  - {name: a, location: somewhere}\n"))
    leaf = doc.leaves[0]
    assert leaf.name == "a"
    assert leaf.location is not None
    assert leaf.location.file == tmp_path / "d.yaml"  # real provenance, not "somewhere"


def test_parse_error_points_at_parent_scalar_after_nested_child(tmp_path: Path) -> None:
    # The bad value is the PARENT's `level` (line 4), declared after two valid
    # located children. The error must localize to the parent element (line 1), not
    # to the last child that happened to parse just before the failure (line 3).
    # A single "deepest element" slot gets this wrong; the parse stack gets it right.
    bad = _write(
        tmp_path / "broken.yaml",
        "leaves:\n  - {name: a}\n  - {name: b}\nlevel: not-an-int\n",
    )
    with pytest.raises(UserNotificationException) as exc:
        parse(_DocWithScalar, bad)
    message = str(exc.value)
    assert "broken.yaml:1:" in message  # the parent element owns the bad scalar
    assert "broken.yaml:3:" not in message  # not the innocent last child


def test_malformed_yaml_names_the_file(tmp_path: Path) -> None:
    bad = _write(tmp_path / "broken.yaml", "leaves: [unterminated\n")
    with pytest.raises(UserNotificationException) as exc:
        parse(_Doc, bad)
    assert "broken.yaml" in str(exc.value)
