import importlib
import json
import os
import sys

import yaml
from fastapi.openapi.utils import get_openapi

# Appends current running folder to the Python path.
workspace = os.environ.get("/Users/palmee/Documents/firecrest-v2-cscs/firecrest-v2/")
sys.path.append("/Users/palmee/Documents/firecrest-v2-cscs/firecrest-v2/src")

# Sets-up the ENV variables.
install = None  # os.environ.get(f"INPUT_{'installDependencies'.upper()}")
directory = "src"
pyfile = "firecrest.main"
obj = "app"
version = None
output_name = "test"
output_extension = "json"

# Ensures pyfile was passed and that it does not have a .py extension.
if not pyfile:
    raise Exception("'fileName' is a required key that was not given for the action.")
elif ".py" in pyfile:
    pyfile = pyfile.replace(".py", "")

# Install package dependencies.
if install:
    os.system(install)

# Imports the module in which the FastAPI app lives in.
try:
    mod = importlib.import_module(f"{directory}.{pyfile}")
except Exception as e:
    raise ModuleNotFoundError(
        f"Error importing {directory}/{pyfile}.py file. "
        "Are you sure both variables were set correctly in your action file? "
        f"Complete error: {e}"
    )

# Imports the FastAPI application.
app = getattr(mod, obj)

# Iterates through all of the routes and finds the correct version.
if version:
    for route in app.router.routes:
        if version in route.path:
            app = route.app
            break

# Gets the OpenAPI specs.
specs = get_openapi(
    title=app.title if app.title else None,
    version=app.version if app.version else None,
    openapi_version=app.openapi_version if app.openapi_version else None,
    description=app.description if app.description else None,
    routes=app.routes if app.routes else None,
)

with open(f"{output_name}.{output_extension}", "w") as f:
    if "json" in output_extension:
        json.dump(specs, f)
    elif "yaml" in output_extension:
        yaml.dump(specs, f)
    else:
        raise Exception(
            "The 'outputExtension' is invalid.",
            "May either be 'yaml' or 'json'.",
        )
