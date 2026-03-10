import pytest

from yanga_core.domain.config import IncludeDirectoryScope, StringableEnum


class Color(StringableEnum):
    RED = 1
    GREEN = 2
    BLUE = 3


def test_from_string_returns_correct_subclass_instance() -> None:
    result = Color.from_string("red")
    assert result is Color.RED
    assert isinstance(result, Color)


def test_from_string_is_case_insensitive() -> None:
    assert Color.from_string("red") is Color.RED
    assert Color.from_string("RED") is Color.RED
    assert Color.from_string("Red") is Color.RED


def test_from_string_returns_correct_subclass_type() -> None:
    result = IncludeDirectoryScope.from_string("public")
    assert result is IncludeDirectoryScope.PUBLIC
    assert isinstance(result, IncludeDirectoryScope)


def test_to_string_returns_name() -> None:
    assert Color.RED.to_string() == "RED"
    assert Color.GREEN.to_string() == "GREEN"


def test_str_returns_name() -> None:
    assert str(Color.RED) == "RED"
    assert str(Color.BLUE) == "BLUE"


def test_round_trip() -> None:
    for member in Color:
        assert Color.from_string(member.to_string()) is member


def test_from_string_invalid_name_raises() -> None:
    with pytest.raises(AttributeError):
        Color.from_string("YELLOW")
