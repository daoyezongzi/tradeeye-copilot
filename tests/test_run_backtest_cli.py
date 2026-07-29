from pathlib import Path
import subprocess
import sys


def test_run_backtest_script_runs_from_repo_root():
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "eval/run_backtest.py"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "wrote artifacts" in result.stdout
    assert (repo_root / "artifacts" / "benchmark.json").exists()
