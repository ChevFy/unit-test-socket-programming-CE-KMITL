#!/usr/bin/env python3
"""
Cross-platform cleanup script
Works on Windows, Linux, and Mac
"""

import subprocess
from pathlib import Path


def main():
    print("Cleaning up Docker environment...")

    script_dir = Path(__file__).parent.parent
    compose_file = script_dir / "docker-compose.yml"

    print("Stopping Docker containers...")
    subprocess.run(["docker-compose", "-f", str(compose_file), "down", "-v"], capture_output=True)

    test_dir = script_dir / "test"
    recived_dir = script_dir / "recived"

    print("Cleaning test files...")
    if test_dir.exists():
        for item in test_dir.iterdir():
            if item.is_file():
                item.unlink()
                print(f"  Removed: {item.name}")

    print("Cleaning received files...")
    if recived_dir.exists():
        for item in recived_dir.iterdir():
            if item.is_file():
                item.unlink()
                print(f"  Removed: {item.name}")

    print("\nCleanup complete!")


if __name__ == "__main__":
    main()
