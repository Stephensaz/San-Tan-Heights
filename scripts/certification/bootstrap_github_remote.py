#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHA1_RE = re.compile(r'^[0-9a-f]{40}$')


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(['git', *args], cwd=ROOT, text=True, capture_output=True)
    if check and cp.returncode != 0:
        raise SystemExit(cp.stderr.strip() or cp.stdout.strip() or f"git {' '.join(args)} failed")
    return cp


def require_clean_committed_candidate() -> tuple[str, str]:
    inside = run('rev-parse', '--is-inside-work-tree').stdout.strip()
    if inside != 'true':
        raise SystemExit('repository is not an initialized Git work tree')
    revision = run('rev-parse', 'HEAD').stdout.strip()
    branch = run('branch', '--show-current').stdout.strip()
    if not revision or not branch:
        raise SystemExit('repository must have a committed HEAD on a named branch')
    dirty = [line for line in run('status', '--porcelain').stdout.splitlines() if line.strip()]
    if dirty:
        raise SystemExit('working tree must be clean before attaching a GitHub remote: ' + '; '.join(dirty[:20]))
    return revision, branch


def validate_remote_url(value: str) -> str:
    value = value.strip()
    patterns = (
        r'^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?$',
        r'^git@github\.com:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?$',
    )
    if not any(re.fullmatch(pattern, value) for pattern in patterns):
        raise SystemExit('remote must be a github.com HTTPS or SSH repository URL')
    return value


def validate_bootstrap_sha(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip().lower()
    if not SHA1_RE.fullmatch(value):
        raise SystemExit('--replace-bootstrap-sha must be a full 40-character lowercase Git SHA-1')
    return value


def remote_branch_sha(remote_name: str, branch: str) -> str | None:
    cp = run('ls-remote', '--heads', remote_name, f'refs/heads/{branch}', check=False)
    if cp.returncode != 0:
        raise SystemExit(cp.stderr.strip() or cp.stdout.strip() or 'unable to query remote branch')
    line = cp.stdout.strip()
    if not line:
        return None
    sha = line.split()[0]
    if not SHA1_RE.fullmatch(sha):
        raise SystemExit(f'unexpected remote branch SHA: {sha!r}')
    return sha


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            'Attach the frozen San Tan Heights candidate to a GitHub repository. '
            'Normal pushes are non-destructive. A one-time bootstrap replacement is permitted '
            'only when the caller pins the exact current remote SHA.'
        )
    )
    ap.add_argument('remote_url', help='Existing GitHub repository URL (HTTPS or SSH).')
    ap.add_argument('--remote-name', default='origin')
    ap.add_argument('--push', action='store_true', help='Push the existing committed candidate and set upstream tracking.')
    ap.add_argument(
        '--replace-bootstrap-sha',
        default=None,
        help='One-time remote-main replacement guarded by force-with-lease against this exact 40-character SHA.',
    )
    args = ap.parse_args()

    revision, branch = require_clean_committed_candidate()
    remote_url = validate_remote_url(args.remote_url)
    bootstrap_sha = validate_bootstrap_sha(args.replace_bootstrap_sha)

    remotes = run('remote').stdout.split()
    if args.remote_name in remotes:
        existing = run('remote', 'get-url', args.remote_name).stdout.strip()
        if existing != remote_url:
            raise SystemExit(
                f"remote {args.remote_name!r} already points to {existing!r}; refusing to rewrite it to {remote_url!r}"
            )
    else:
        run('remote', 'add', args.remote_name, remote_url)

    print(f'candidate_revision={revision}')
    print(f'branch={branch}')
    print(f'remote={args.remote_name}')
    print(f'remote_url={remote_url}')

    if args.push:
        if bootstrap_sha is None:
            run('push', '--set-upstream', args.remote_name, branch)
        else:
            observed = remote_branch_sha(args.remote_name, branch)
            if observed != bootstrap_sha:
                raise SystemExit(
                    'refusing bootstrap replacement: '
                    f'expected remote {branch} at {bootstrap_sha}, observed {observed or "<missing>"}'
                )
            lease = f'--force-with-lease=refs/heads/{branch}:{bootstrap_sha}'
            run('push', lease, '--set-upstream', args.remote_name, branch)
        print('pushed=true')
    else:
        print('pushed=false')
        if bootstrap_sha is None:
            print(f"next_command=git push --set-upstream {args.remote_name} {branch}")
        else:
            lease = f'--force-with-lease=refs/heads/{branch}:{bootstrap_sha}'
            print(f"next_command=git push {lease} --set-upstream {args.remote_name} {branch}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
