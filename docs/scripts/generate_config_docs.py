# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import inspect
import sys
import types

from enum import Enum
from importlib import import_module
from pathlib import Path
from pydantic import BaseModel
from typing import Dict, get_args, get_origin, List, Set, Type, Union

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

# === CONFIG ===
MODEL_PATH = "firecrest.config.Settings"
OUTPUT_FILE = "docs/setup/conf/README.md"
EXAMPLE_FILE = "f7t-api-config.local-env.yaml"
# ==============


def unwrap_type(field_type):
    """
    Recursively unwraps typing constructs like Optional, List, Dict,
    and returns a flat list of inner types.
    """
    origin = get_origin(field_type)
    args = get_args(field_type)

    if origin is Union or origin is types.UnionType:
        return [t for arg in args for t in unwrap_type(arg)]

    elif origin in (list, List, tuple, set):
        if args:
            return unwrap_type(args[0])
        return []

    elif origin in (dict, Dict):
        if len(args) == 2:
            return unwrap_type(args[1])
        return []

    return [field_type]


def format_type(annotation):
    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is Union:
        return " | ".join(format_type(a) for a in args)

    elif origin in (list, List):
        if args:
            return f"List[{format_type(args[0])}]"
        return "List"

    elif origin in (dict, Dict):
        if len(args) == 2:
            return f"Dict[{format_type(args[0])}, {format_type(args[1])}]"
        return "Dict"

    elif hasattr(annotation, "__name__"):
        if annotation.__name__ == "NoneType":
            return "None"
        if inspect.isclass(annotation) and issubclass(annotation, Enum):
            return f"{annotation.__name__} (enum)"
        return annotation.__name__

    return str(annotation)


def document_model(model: Type[BaseModel], seen: Set[Type] = None, title=None) -> str:
    if seen is None:
        seen = set()

    if model in seen:
        return ""

    seen.add(model)

    model_title = f"### `{model.__name__}`" if not title else f"## {title}\n"
    lines = []
    lines.append(model_title)
    if model.__doc__:
        lines.append(model.__doc__.strip())

    lines.append("")

    lines.append("| Field | Type | Description | Default |")
    lines.append("|-------|------|-------------|---------|")

    for field_name in sorted(model.model_fields):
        field = model.model_fields[field_name]
        field_type = format_type(field.annotation)
        desc = field.description or "—"
        default = "—"

        if field.is_required():
            default = "`(required)`"
        elif field.default_factory is not None:
            try:
                factory_name = field.default_factory.__name__
                if factory_name == "dict":
                    default = "`{}`"
                elif factory_name == "list":
                    default = "`[]`"
                else:
                    default = f"`<generated by {factory_name}()>`"
            except AttributeError:
                default = "`<dynamic default>`"
        elif field.default is not ...:
            default = f"`{repr(field.default)}`"

        lines.append(f"| `{field_name}` | `{field_type}` | {desc} | {default} |")

    lines.append("")

    # Document nested models
    for field_name, field in model.model_fields.items():
        internal_types = unwrap_type(field.annotation)
        for t in internal_types:
            if inspect.isclass(t) and issubclass(t, BaseModel):
                lines.append(f'??? note "Details of `{field_name}` ({t.__name__})"')
                nested_md = document_model(t, seen)
                nested_block = "\n".join(
                    "    " + line for line in nested_md.splitlines()
                )
                lines.append(nested_block)
                lines.append("")

            if inspect.isclass(t) and issubclass(t, Enum):
                lines.append("")
                lines.append(
                    f'??? note "Enum values for `{field_name}` ({t.__name__})"'
                )
                if t.__doc__:
                    lines.append(f"    {t.__doc__.strip()}\n")
                for member in t:
                    lines.append(f"    - `{member.value}`")

    return "\n".join(lines)


def import_model(path: str) -> Type[BaseModel]:
    """Dynamically import the model class."""
    module_path, class_name = path.rsplit(".", 1)
    module = import_module(module_path)
    model = getattr(module, class_name)
    if not issubclass(model, BaseModel):
        raise TypeError(f"{model} is not a subclass of BaseModel")
    return model


def main():
    model = import_model(MODEL_PATH)
    print(f"Generating configuration markdown for `{model.__name__}`...")

    markdown = (
        "# Configuration Reference\n\n"
        "<!--- ⚠️ DO NOT EDIT. Generated by docs/scripts/generate_config_docs.py "
        "-->\n\n"
    )
    with open(EXAMPLE_FILE) as f:
        example = f.read()

    markdown += (
        "This page documents all available configuration options for FirecREST.\n\n"
        "Below is an example configuration file showing how values can be structured:\n"
        '??? example "Click to view a sample configuration file"\n'
        "    ```yaml\n"
    )

    for line in example.splitlines():
        markdown += f"    {line}\n"
    markdown += "    ```\n\n"

    markdown += "In the following tables, you can find all the "
    markdown += "supported configuration options, along with their types, "
    markdown += "descriptions, and default values.:\n\n"
    markdown += document_model(model)

    output_path = Path(OUTPUT_FILE)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown)
    print(f"Configuration markdown generated: {output_path.resolve()}")


if __name__ == "__main__":
    main()
