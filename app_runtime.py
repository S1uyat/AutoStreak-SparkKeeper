"""Stable application paths for source and single-file executable builds."""
import sys
from pathlib import Path


def is_frozen():
    return bool(getattr(sys, 'frozen', False))


def resource_root():
    return Path(__file__).resolve().parent


def install_root():
    return Path(sys.executable).resolve().parent if is_frozen() else resource_root()


def runner_command(dry_run=False):
    if is_frozen():
        args = [sys.executable, '--run']
    else:
        args = [sys.executable, str(resource_root() / 'runner.py')]
    return args + (['--dry-run'] if dry_run else [])


def task_command(action):
    args = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-File', str(resource_root() / 'task.ps1'), '-Action', action]
    if is_frozen():
        args += ['-ExecutablePath', sys.executable]
    return args
