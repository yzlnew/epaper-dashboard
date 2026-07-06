#!/usr/bin/env python3
"""Push a rendered PNG to HA's /config/www/eink/ (served at /local/eink/...).

The ESPHome panels poll a fixed URL, so deploying = overwriting one file:
  bw → dashboard.png     e6 → dashboard_e6.png

Transport: `sshpass` when installed, else pure-python paramiko. The HA SSH
add-on has no SFTP subsystem, so paramiko streams bytes through `cat > file`;
the target dir is created once with passwordless sudo (hassio is in wheel).

  .venv/bin/python -m renderer.deploy --panel e6 [--file PATH]
"""

from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from . import config
from .panels import PANELS


def _env(name: str, value: str) -> str:
    if not value:
        print(f"[deploy] missing env {name}; run: set -a && source .env && set +a", file=sys.stderr)
        raise SystemExit(2)
    return value


def _sshpass_run(cmd: str) -> tuple[int, str, str]:
    base = ["sshpass", "-p", _env("HA_SSH_PASSWORD", config.SSH_PASSWORD),
            "ssh", "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR",
            f"{config.SSH_USER}@{_env('HA_SSH_HOST', config.SSH_HOST)}", cmd]
    r = subprocess.run(base, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def _sshpass_put(local: Path, remote: str) -> None:
    subprocess.run(
        ["sshpass", "-p", config.SSH_PASSWORD,
         "scp", "-O", "-q", "-o", "StrictHostKeyChecking=no",
         "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR",
         str(local), f"{config.SSH_USER}@{config.SSH_HOST}:{remote}"],
        check=True)


def _paramiko_put(local: Path, remote: str, mkdir: str) -> None:
    import paramiko  # type: ignore

    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(_env("HA_SSH_HOST", config.SSH_HOST), username=config.SSH_USER,
                password=_env("HA_SSH_PASSWORD", config.SSH_PASSWORD),
                timeout=12, allow_agent=False, look_for_keys=False)
    try:
        _in, out, err = cli.exec_command(mkdir, timeout=20)
        rc = out.channel.recv_exit_status()
        if rc != 0 or "OK" not in out.read().decode():
            raise RuntimeError(f"mkdir failed rc={rc}: {err.read().decode()[:200]}")
        chan = cli.get_transport().open_session()
        chan.exec_command(f"cat > {shlex.quote(remote)}")
        chan.sendall(local.read_bytes())
        chan.shutdown_write()
        rc = chan.recv_exit_status()
        if rc != 0:
            raise RuntimeError(f"upload failed rc={rc}")
    finally:
        cli.close()


def deploy(panel_name: str, local: Path | None = None) -> None:
    remote_png = PANELS[panel_name].remote_png
    local = local or config.OUT_DIR / f"{panel_name}_current.png"
    if not local.exists():
        print(f"[deploy] {local} missing — render first", file=sys.stderr)
        raise SystemExit(2)

    remote = f"{config.REMOTE_DIR}/{remote_png}"
    mkdir = (f"sudo -n mkdir -p {shlex.quote(config.REMOTE_DIR)} && "
             f"sudo -n chown {config.SSH_USER}:{config.SSH_USER} "
             f"{shlex.quote(config.REMOTE_DIR)} && echo OK")

    if shutil.which("sshpass"):
        rc, out, err = _sshpass_run(mkdir)
        if rc != 0 or "OK" not in out:
            raise RuntimeError(f"mkdir failed: rc={rc} out={out!r} err={err!r}")
        _sshpass_put(local, remote)
        via = "sshpass"
    else:
        _paramiko_put(local, remote, mkdir)
        via = "paramiko"
    print(f"[deploy] {local.name} ({local.stat().st_size}B) → {remote} via {via}")
    print(f"[deploy] panel URL: http://{config.SSH_HOST}:8123/local/eink/{remote_png}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", choices=list(PANELS), required=True)
    ap.add_argument("--file", type=Path, default=None)
    args = ap.parse_args()
    deploy(args.panel, args.file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
