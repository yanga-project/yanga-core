import json
from pathlib import Path

from poks.domain import PoksApp, PoksBucket, PoksConfig

from yanga_core.domain.config import ConfigFile, PlatformConfig, VariantConfig, YangaUserConfig
from yanga_core.domain.execution_context import ExecutionContext, UserVariantRequest
from yanga_core.steps.poks_install import PoksInstall


def test_poks_install_honors_root_poks_json(tmp_path: Path) -> None:
    # The base now contributes the project-root poks.json; a scoped platform fragment merges on top.
    (tmp_path / "poks.json").write_text(
        json.dumps(
            {
                "buckets": [{"name": "main", "url": "https://github.com/example/main"}],
                "apps": [{"name": "root_app", "version": "1.0", "bucket": "main"}],
            }
        )
    )
    platform = PlatformConfig(
        name="test_platform",
        configs=[ConfigFile(id="poks", content=PoksConfig(buckets=[], apps=[PoksApp(name="platform_app", version="2.0", bucket="main")]).to_dict())],
    )
    exec_context = ExecutionContext(project_root_dir=tmp_path, variant_name="v", user_request=UserVariantRequest("v"), platform=platform)

    collected = PoksInstall(exec_context, "install")._merge_manifests()

    assert {app.name for app in collected.apps} == {"root_app", "platform_app"}


def test_poks_get_inputs_includes_scoped_fragment_file(tmp_path: Path) -> None:
    yaml_file = tmp_path / "yanga.yaml"
    yaml_file.write_text('platforms:\n  - name: p\n    configs:\n      - id: poks\n        content: {apps: [{name: cmake, version: "3.28", bucket: main}]}\n')
    user_config = YangaUserConfig.from_file(yaml_file)
    context = ExecutionContext(project_root_dir=tmp_path, variant_name="v", user_request=UserVariantRequest("v"), platform=user_config.platforms[0])

    step = PoksInstall(context, "install")

    assert yaml_file in step.get_inputs()


def test_poks_install_with_platform_dependencies(tmp_path: Path) -> None:
    platform = PlatformConfig(
        name="test_platform",
        configs=[
            ConfigFile(
                id="poks",
                content=PoksConfig(
                    buckets=[PoksBucket(name="main", url="https://github.com/example/main")],
                    apps=[PoksApp(name="cmake", version="3.28.1", bucket="main")],
                ).to_dict(),
            )
        ],
    )

    exec_context = ExecutionContext(
        project_root_dir=tmp_path,
        variant_name="test_variant",
        user_request=UserVariantRequest("test_variant"),
        platform=platform,
    )

    poks_install = PoksInstall(exec_context, "install")
    collected = poks_install._merge_manifests()

    assert len(collected.buckets) == 1
    assert collected.buckets[0].name == "main"
    assert collected.buckets[0].url == "https://github.com/example/main"

    assert len(collected.apps) == 1
    assert collected.apps[0].name == "cmake"
    assert collected.apps[0].version == "3.28.1"
    assert collected.apps[0].bucket == "main"


def test_poks_install_with_variant_dependencies(tmp_path: Path) -> None:
    variant = VariantConfig(
        name="test_variant",
        configs=[
            ConfigFile(
                id="poks",
                content=PoksConfig(
                    buckets=[PoksBucket(name="extras", url="https://github.com/example/extras")],
                    apps=[PoksApp(name="ninja", version="1.11.1", bucket="extras")],
                ).to_dict(),
            )
        ],
    )

    exec_context = ExecutionContext(
        project_root_dir=tmp_path,
        variant_name="test_variant",
        user_request=UserVariantRequest("test_variant"),
        variant=variant,
    )

    poks_install = PoksInstall(exec_context, "install")
    collected = poks_install._merge_manifests()

    assert len(collected.buckets) == 1
    assert collected.buckets[0].name == "extras"

    assert len(collected.apps) == 1
    assert collected.apps[0].name == "ninja"
    assert collected.apps[0].version == "1.11.1"


def test_poks_install_merges_platform_and_variant_dependencies(tmp_path: Path) -> None:
    platform = PlatformConfig(
        name="test_platform",
        configs=[
            ConfigFile(
                id="poks",
                content=PoksConfig(
                    buckets=[PoksBucket(name="main", url="https://github.com/example/main")],
                    apps=[PoksApp(name="cmake", version="3.28.1", bucket="main")],
                ).to_dict(),
            )
        ],
    )

    variant = VariantConfig(
        name="test_variant",
        configs=[
            ConfigFile(
                id="poks",
                content=PoksConfig(
                    buckets=[PoksBucket(name="extras", url="https://github.com/example/extras")],
                    apps=[PoksApp(name="ninja", version="1.11.1", bucket="extras")],
                ).to_dict(),
            )
        ],
    )

    exec_context = ExecutionContext(
        project_root_dir=tmp_path,
        variant_name="test_variant",
        user_request=UserVariantRequest("test_variant"),
        platform=platform,
        variant=variant,
    )

    poks_install = PoksInstall(exec_context, "install")
    collected = poks_install._merge_manifests()

    assert len(collected.buckets) == 2
    assert {b.name for b in collected.buckets} == {"main", "extras"}

    assert len(collected.apps) == 2
    assert {a.name for a in collected.apps} == {"cmake", "ninja"}


def test_poks_install_with_root_and_platform_configs(tmp_path: Path) -> None:
    root_cfg = ConfigFile(
        id="poks",
        content={
            "buckets": [{"name": "global_bucket", "url": "https://github.com/global/bucket"}],
            "apps": [{"name": "global_app", "version": "1.0.0", "bucket": "global_bucket"}],
        },
    )
    platform_cfg = ConfigFile(
        id="poks",
        content={
            "buckets": [{"name": "global_bucket", "url": "https://github.com/global/bucket"}],
            "apps": [{"name": "platform_app", "version": "0.0.1", "bucket": "global_bucket"}],
        },
    )

    exec_context = ExecutionContext(
        project_root_dir=tmp_path,
        variant_name="test_variant",
        user_request=UserVariantRequest("test_variant"),
        project_configs=[root_cfg],
        platform=PlatformConfig(name="test_platform", configs=[platform_cfg]),
    )

    collected = PoksInstall(exec_context, "install")._merge_manifests()

    assert {b.name for b in collected.buckets} == {"global_bucket"}
    assert {a.name for a in collected.apps} == {"global_app", "platform_app"}


def test_poks_install_merges_buckets_with_conflicts(tmp_path: Path) -> None:
    platform = PlatformConfig(
        name="test_platform",
        configs=[
            ConfigFile(
                id="poks",
                content=PoksConfig(
                    buckets=[PoksBucket(name="main", url="https://github.com/example/main")],
                    apps=[],
                ).to_dict(),
            )
        ],
    )

    variant = VariantConfig(
        name="test_variant",
        configs=[
            ConfigFile(
                id="poks",
                content=PoksConfig(
                    buckets=[PoksBucket(name="main", url="https://github.com/example/main")],
                    apps=[],
                ).to_dict(),
            )
        ],
    )

    exec_context = ExecutionContext(
        project_root_dir=tmp_path,
        variant_name="test_variant",
        user_request=UserVariantRequest("test_variant"),
        platform=platform,
        variant=variant,
    )

    poks_install = PoksInstall(exec_context, "install")
    collected = poks_install._merge_manifests()

    # Last definition wins (platform is collected after variant)
    assert len(collected.buckets) == 1
    assert collected.buckets[0].name == "main"
    assert collected.buckets[0].url == "https://github.com/example/main"


def test_poks_install_generates_config(tmp_path: Path) -> None:
    platform = PlatformConfig(
        name="test_platform",
        configs=[
            ConfigFile(
                id="poks",
                content=PoksConfig(
                    buckets=[PoksBucket(name="main", url="https://github.com/example/main")],
                    apps=[PoksApp(name="cmake", version="3.28.1", bucket="main")],
                ).to_dict(),
            )
        ],
    )

    exec_context = ExecutionContext(
        project_root_dir=tmp_path,
        variant_name="test_variant",
        user_request=UserVariantRequest("test_variant"),
        platform=platform,
    )

    poks_install = PoksInstall(exec_context, "install")
    config = poks_install._merge_manifests()
    poks_install._generate_poks_config(config)

    assert poks_install._output_config_file.exists()

    content = json.loads(poks_install._output_config_file.read_text())

    assert "buckets" in content
    assert "apps" in content
    assert len(content["buckets"]) == 1
    assert content["buckets"][0]["name"] == "main"
    assert len(content["apps"]) == 1
    assert content["apps"][0]["name"] == "cmake"
    assert content["apps"][0]["version"] == "3.28.1"


def test_poks_install_variant_specific_directories(tmp_path: Path) -> None:
    platform = PlatformConfig(
        name="test_platform",
        configs=[
            ConfigFile(
                id="poks",
                content=PoksConfig(
                    buckets=[PoksBucket(name="main", url="https://github.com/example/main")],
                    apps=[PoksApp(name="cmake", version="3.28.1", bucket="main")],
                ).to_dict(),
            )
        ],
    )

    for variant_name in ["variant_a", "variant_b"]:
        exec_context = ExecutionContext(
            project_root_dir=tmp_path,
            variant_name=variant_name,
            user_request=UserVariantRequest(variant_name),
            platform=platform,
        )

        poks_install = PoksInstall(exec_context, "install")
        config = poks_install._merge_manifests()
        poks_install._generate_poks_config(config)

        expected_file = tmp_path / ".yanga" / "build" / variant_name / "test_platform" / "poks.json"
        assert expected_file.exists()
        assert poks_install._output_config_file == expected_file
