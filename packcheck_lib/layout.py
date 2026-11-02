"""Where a pack's workflows and fixtures sit, and their YAML parsed once."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_STR_TAG = "tag:yaml.org,2002:str"


def yaml_files(folder: Path) -> list[Path]:
    return sorted(
        p for p in folder.iterdir() if p.suffix in (".yaml", ".yml") and p.is_file()
    )


def workflow_folders(pack: Path) -> list[Path]:
    """Direct subfolders (dot-folders such as .shared skipped) holding a YAML file."""
    return sorted(
        d
        for d in pack.iterdir()
        if d.is_dir() and not d.name.startswith(".") and yaml_files(d)
    )


def fixtures(folder: Path) -> list[Path]:
    """The folder's fixtures/*.stubs.yaml, sorted."""
    where = folder / "fixtures"
    return sorted(where.glob("*.stubs.yaml")) if where.is_dir() else []


@dataclass
class Parsed:
    """Each file's YAML document as a node tree (marks give line numbers), or the
    error that kept it from parsing. A file sits in exactly one of the two."""

    docs: dict[Path, yaml.Node | None] = field(default_factory=dict)
    errors: dict[Path, yaml.YAMLError] = field(default_factory=dict)


def parse(paths: Iterable[Path]) -> Parsed:
    parsed = Parsed()
    for path in paths:
        try:
            parsed.docs[path] = yaml.compose(path.read_text(), Loader=yaml.SafeLoader)
        except yaml.YAMLError as e:
            parsed.errors[path] = e
    return parsed


def pack_paths(pack: Path, folders: list[Path]) -> list[Path]:
    """Every YAML file packcheck reads: workflow files, fixtures, pack-level files."""
    paths = [p for f in folders for p in (*yaml_files(f), *fixtures(f))]
    return paths + yaml_files(pack)


def doc_name(root: yaml.Node | None) -> str:
    """The document's top-level string `name`, or "" when it has none."""
    name = ""
    if isinstance(root, yaml.MappingNode):
        for key, value in root.value:
            if (
                isinstance(key, yaml.ScalarNode)
                and key.value == "name"
                and isinstance(value, yaml.ScalarNode)
                and value.tag == _STR_TAG
            ):
                name = value.value
    return name


def labels_by_name(
    pack: Path, folders: list[Path], parsed: Parsed
) -> dict[str, list[str]]:
    """Each workflow name Archon will see, with the "<pack>/<workflow>" labels
    declaring it. A folder's name is its first YAML's `name`, else the folder name;
    a pack-level YAML (a one-level grouped workflow) is named by its `name`, else
    its stem. An unparseable file has no `name`."""
    labels: dict[str, list[str]] = {}
    for f in folders:
        names = [doc_name(parsed.docs.get(y)) for y in yaml_files(f)]
        name = next((n for n in names if n), f.name)
        labels.setdefault(name, []).append(f"{pack.name}/{f.name}")
    for y in yaml_files(pack):
        name = doc_name(parsed.docs.get(y)) or y.stem
        labels.setdefault(name, []).append(f"{pack.name}/{y.stem}")
    return labels
