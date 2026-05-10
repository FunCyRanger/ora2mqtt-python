"""Tests for manifest.json validation."""

import json
from pathlib import Path


def get_manifest_path():
    """Get manifest path relative to tests directory."""
    # From tests/integration -> project root -> custom_components/ora
    tests_dir = Path(__file__).parent
    project_root = tests_dir.parent.parent
    return project_root / "custom_components" / "ora" / "manifest.json"


class TestManifestJson:
    """Test manifest.json is valid."""

    def test_manifest_is_valid_json(self):
        """Test manifest.json is valid JSON."""
        manifest_path = get_manifest_path()
        content = manifest_path.read_text()

        # This will raise json.JSONDecodeError if invalid
        data = json.loads(content)
        assert data is not None

    def test_manifest_has_required_fields(self):
        """Test manifest has required fields."""
        manifest_path = get_manifest_path()
        content = manifest_path.read_text()
        data = json.loads(content)

        assert "domain" in data
        assert "version" in data
        assert "config_flow" in data

    def test_manifest_version_is_valid(self):
        """Test version is valid semver."""
        manifest_path = get_manifest_path()
        content = manifest_path.read_text()
        data = json.loads(content)

        version = data.get("version", "")
        # Must be like "0.2.1" or "1.0.0"
        parts = version.split(".")
        assert len(parts) == 3, f"Invalid version format: {version}"
