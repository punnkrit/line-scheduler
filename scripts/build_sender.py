"""Build the separately maintained LINE sender at an exact reviewed commit."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def command(args, cwd=None, env=None):
    return subprocess.check_output(args, cwd=cwd, env=env, text=True).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, help="Reuse a clean checkout at the pinned commit")
    args = parser.parse_args()
    lock = json.loads((ROOT / "client.lock.json").read_text())
    if lock["repository"] != "https://github.com/punnkrit/line-scheduler-client.git" or not re.fullmatch(r"[a-f0-9]{40}", lock["commit"]):
        raise SystemExit("Invalid client lock")
    if command(["go", "env", "GOVERSION"]) != "go" + lock["go_version"]:
        raise SystemExit("Use Go " + lock["go_version"] + " to build the reviewed sender")
    source = args.source.resolve() if args.source else ROOT / ".build" / "client"
    if not args.source:
        if not source.exists():
            source.mkdir(parents=True)
            command(["git", "init"], cwd=source)
        if command(["git", "status", "--porcelain"], cwd=source):
            raise SystemExit("Build checkout has changes; refusing to replace them")
        command(["git", "fetch", "--depth=1", lock["repository"], lock["commit"]], cwd=source)
        command(["git", "checkout", "--detach", lock["commit"]], cwd=source)
    if command(["git", "rev-parse", "HEAD"], cwd=source) != lock["commit"]:
        raise SystemExit("Client checkout does not match client.lock.json")
    if command(["git", "status", "--porcelain", "--untracked-files=no"], cwd=source):
        raise SystemExit("Client checkout has tracked changes")
    command(["go", "mod", "verify"], cwd=source)
    output = ROOT / "deploy" / "aws" / ".local"
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    for target, arch, name, package in [
        ("linux", "arm64", "cloudline", "./cmd/cloudline"),
        ("windows", "amd64", "cloudline.exe", "./cmd/cloudline"),
        ("windows", "amd64", "line.exe", "./cmd/line"),
    ]:
        env = dict(os.environ, CGO_ENABLED="0", GOOS=target, GOARCH=arch)
        command(["go", "build", "-trimpath", "-o", str(output / name), package], cwd=source, env=env)
    print("Built the pinned sender and Windows QR-login CLI in deploy/aws/.local")


if __name__ == "__main__":
    main()
