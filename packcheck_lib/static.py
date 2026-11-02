"""The checks packcheck makes without running Archon."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import yaml

from packcheck_lib.failure import Failure
from packcheck_lib.layout import Parsed, fixtures, yaml_files

TIERS = {"small", "medium", "large"}
FENCE_KEYS = {"allowRead", "denyRead", "allowWrite", "denyWrite"}


def pairs(node: yaml.Node | None) -> Iterator[tuple[yaml.ScalarNode, yaml.Node]]:
    """Every (key, value) pair of every mapping in the tree, at any depth."""
    if isinstance(node, yaml.MappingNode):
        for key, value in node.value:
            if isinstance(key, yaml.ScalarNode):
                yield key, value
            yield from pairs(key)
            yield from pairs(value)
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            yield from pairs(item)


def scalars(node: yaml.Node) -> list[yaml.ScalarNode]:
    """A scalar, or the scalars of a sequence."""
    if isinstance(node, yaml.ScalarNode):
        return [node]
    if isinstance(node, yaml.SequenceNode):
        return [i for i in node.value if isinstance(i, yaml.ScalarNode)]
    return []


def line(node: yaml.Node) -> int:
    return node.start_mark.line + 1


def models(root: yaml.Node | None) -> Iterator[yaml.ScalarNode]:
    """Every scalar given to a `model` key, workflow or node level."""
    for key, value in pairs(root):
        if key.value == "model":
            yield from scalars(value)


def fence_paths(root: yaml.Node | None) -> Iterator[yaml.ScalarNode]:
    """Every path listed under a sandbox `filesystem` fence key."""
    for key, value in pairs(root):
        if key.value != "filesystem" or not isinstance(value, yaml.MappingNode):
            continue
        for fkey, paths in value.value:
            if isinstance(fkey, yaml.ScalarNode) and fkey.value in FENCE_KEYS:
                yield from scalars(paths)


def workflow_failures(label: str, path: Path, root: yaml.Node | None) -> list[Failure]:
    """Tier or alias models and relative sandbox paths in one workflow YAML."""
    out = [
        Failure(
            label,
            "tier-model",
            f"{path.name}:{line(item)}: model {item.value!r} is a tier or alias",
        )
        for item in models(root)
        if item.value in TIERS or item.value.startswith("@")
    ]
    out += [
        Failure(
            label,
            "relative-fence",
            f"{path.name}:{line(item)}: sandbox path {item.value!r} is not absolute",
        )
        for item in fence_paths(root)
        if not item.value.startswith("/")
    ]
    return out


def fixture_failures(label: str, path: Path, root: yaml.Node | None) -> list[Failure]:
    """exec-code at any depth whose YAML value is anything but false or null."""
    out: list[Failure] = []
    loader = yaml.SafeLoader("")
    for key, value in pairs(root):
        if key.value != "exec-code":
            continue
        try:
            v = loader.construct_object(value, deep=True)
        except yaml.YAMLError:
            v = value
        if v is not False and v is not None:
            out.append(
                Failure(
                    label, "exec-code", f"{path.name}:{line(key)}: exec-code: {v!r}"
                )
            )
    return out


def _file_failures(
    label: str, path: Path, parsed: Parsed, fixture: bool
) -> list[Failure]:
    """One file's failures. An unparseable workflow fails validate; an unparseable
    fixture fails as exec-code, since it cannot be shown safe."""
    if path in parsed.errors:
        check = "exec-code" if fixture else "validate"
        error = parsed.errors[path]
        return [Failure(label, check, f"{path.name}: unparseable YAML: {error}")]
    judge = fixture_failures if fixture else workflow_failures
    return judge(label, path, parsed.docs.get(path))


def static_failures(pack: Path, folders: list[Path], parsed: Parsed) -> list[Failure]:
    out: list[Failure] = []
    for folder in folders:
        label = f"{pack.name}/{folder.name}"
        found = fixtures(folder)
        if not found:
            out.append(Failure(label, "no-fixture", "no fixtures/*.stubs.yaml"))
        for fx in found:
            out.extend(_file_failures(label, fx, parsed, fixture=True))
        for y in yaml_files(folder):
            out.extend(_file_failures(label, y, parsed, fixture=False))
    # A YAML directly in the pack is a one-level grouped workflow to Archon.
    for y in yaml_files(pack):
        out.extend(_file_failures(f"{pack.name}/{y.stem}", y, parsed, fixture=False))
    return out
