"""Local configuration, history, locking, and logging for SparkKeeper."""
from __future__ import annotations

import json
from copy import deepcopy
import logging
import os
import tempfile
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

APP_NAME = 'SparkKeeper'
BASE = Path(os.environ.get('SPARK_KEEPER_HOME') or (Path(os.environ.get('LOCALAPPDATA', Path.home())) / APP_NAME))
CONFIG_FILE = BASE / 'config.json'
STATE_FILE = BASE / 'state.json'
LOG_FILE = BASE / 'logs' / 'sparkkeeper.log'
PROFILE = BASE / 'edge_profile'
LOCK_FILE = BASE / 'once.lock'
DEFAULT = {'message': '今天的火花来啦', 'contacts': [], 'channel': 'msedge', 'headless': True, 'auto_send': False}


def ensure_dirs():
    BASE.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default):
    try:
        with path.open('r', encoding='utf-8') as f:
            obj = json.load(f)
        if not isinstance(obj, dict):
            raise ValueError(f'配置或状态文件格式错误：{path}')
        return obj
    except FileNotFoundError:
        return deepcopy(default)


def write_json(path: Path, data: dict):
    ensure_dirs()
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name, suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def get_config():
    data = deepcopy(DEFAULT)
    stored = read_json(CONFIG_FILE, {})
    data.update({k: v for k, v in stored.items() if k in DEFAULT})
    if not isinstance(data['contacts'], list):
        data['contacts'] = []
    return data


def validate_config(data):
    if not isinstance(data.get('message'), str) or not data['message'].strip():
        raise ValueError('消息内容不能为空')
    if len(data['message']) > 400:
        raise ValueError('消息内容不能超过 400 字')
    if data.get('channel') not in ('msedge', 'chrome', 'chromium'):
        raise ValueError('浏览器请选择 Edge / Chrome / Chromium')
    for key in ('headless', 'auto_send'):
        if not isinstance(data.get(key, False), bool):
            raise ValueError(f'{key} 必须为布尔值')
    contacts = data.get('contacts', [])
    if not isinstance(contacts, list) or len(contacts) > 60:
        raise ValueError('好友列表最多 60 人')
    names = set()
    for item in contacts:
        name = item.get('name', '') if isinstance(item, dict) else ''
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise ValueError('好友昵称无效')
        if name != name.strip():
            raise ValueError('好友昵称首尾不能包含空格')
        if not isinstance(item.get('enabled', True), bool):
            raise ValueError('好友启用状态必须为布尔值')
        if name in names:
            raise ValueError('有重复的好友昵称：' + name)
        names.add(name)


def save_config(data):
    validate_config(data)
    write_json(CONFIG_FILE, data)


def today():
    return datetime.now().astimezone().date().isoformat()


def nowstr():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def get_state():
    raw = read_json(STATE_FILE, {})
    if raw.get('date') != today():
        return {'date': today(), 'results': {}, 'last_run': None}
    if not isinstance(raw.get('results'), dict):
        raw['results'] = {}
    return raw


def record(name, status, detail=''):
    state = get_state()
    state['results'][name] = {'status': status, 'at': nowstr(), 'detail': str(detail)[:300]}
    state['last_run'] = nowstr()
    write_json(STATE_FILE, state)


def log_setup():
    ensure_dirs()
    logger = logging.getLogger('sparkkeeper')
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        handler = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding='utf-8')
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    return logger


class AlreadyRunning(Exception):
    pass


class ExecutionLock:
    """OS-owned byte lock: released on process exit, never expires under a live owner."""
    def __enter__(self):
        import msvcrt
        ensure_dirs()
        self.handle = LOCK_FILE.open('a+b')
        self.handle.seek(0, 2)
        if self.handle.tell() == 0:
            self.handle.write(b'0')
            self.handle.flush()
        self.handle.seek(0)
        try:
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            self.handle.close()
            raise AlreadyRunning('另一个任务或登录窗口仍在运行，已跳过。') from exc
        return self

    def __exit__(self, *args):
        import msvcrt
        self.handle.seek(0)
        msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        self.handle.close()


def claim_scheduled_run():
    state = get_state()
    if state.get('scheduled_at'):
        return False
    state['scheduled_at'] = nowstr()
    write_json(STATE_FILE, state)
    return True
