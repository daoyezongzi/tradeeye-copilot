import tomllib
from pathlib import Path


def test_pyproject_limits_package_discovery_to_copilot():
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    packages = data["tool"]["setuptools"]["packages"]["find"]
    assert packages["include"] == ["copilot*"]
    assert packages["exclude"] == ["web*", "eval*", "artifacts*", "docs*", "tests*"]
