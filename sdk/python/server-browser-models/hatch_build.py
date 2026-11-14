"""Bundle the authoritative contract without tracking generated copies."""
import json
from pathlib import Path

import yaml
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        root = Path(self.root)
        # Sdists carry their own build input; workspace builds use the OAS source.
        source = root / "assets/chiv2-server-browser-api.yaml"
        if not source.is_file():
            source = root.parents[2] / "assets/chiv2-server-browser-api.yaml"
        if self.target_name == "sdist":
            build_data["force_include"][str(source)] = "assets/chiv2-server-browser-api.yaml"
            return
        target = root / "src/server_browser_models"
        text = source.read_text()
        resources = {
            "openapi.yaml": text,
            "contract.json": json.dumps(yaml.safe_load(text), indent=2, sort_keys=True) + "\n",
        }
        for name, content in resources.items():
            path = target / name
            path.write_text(content)
            build_data["force_include"][str(path)] = f"server_browser_models/{name}"
