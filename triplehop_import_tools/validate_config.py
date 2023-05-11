import json
import os
import pathlib

import jsonschema


def validate() -> None:
    resolver = jsonschema.validators.RefResolver(
        base_uri=f"{pathlib.Path('triplehop_import_tools/triplehop_import_tools/schemas').resolve().as_uri()}/",
        referrer=True,
    )

    with open(
        "triplehop_import_tools/triplehop_import_tools/schemas/entity.schema.json"
    ) as f:
        entity_schema = json.load(f)
    for fn in os.listdir("human_readable_config/entity"):
        with open(f"human_readable_config/entity/{fn}") as f:
            try:
                jsonschema.validate(
                    instance=json.load(f),
                    schema=entity_schema,
                    resolver=resolver,
                )
            except (
                jsonschema.exceptions.SchemaError,
                jsonschema.exceptions.ValidationError,
            ) as e:
                print(f"Validation error in human_readable_config/entity/{fn}")
                print(e.message)

    with open(
        "triplehop_import_tools/triplehop_import_tools/schemas/relation.schema.json"
    ) as f:
        relation_schema = json.load(f)
    for fn in os.listdir("human_readable_config/relation"):
        with open(f"human_readable_config/relation/{fn}") as f:
            try:
                jsonschema.validate(
                    instance=json.load(f),
                    schema=relation_schema,
                    resolver=resolver,
                )
            except (
                jsonschema.exceptions.SchemaError,
                jsonschema.exceptions.ValidationError,
            ) as e:
                print(f"Validation error in human_readable_config/relation/{fn}")
                print(e.message)


if __name__ == "__main__":
    validate()
