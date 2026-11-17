#!/usr/bin/env python3
# Instadash AI Base — (c) Letstream Ventures Pvt Ltd. See docs/bootstrap/README.md for terms.
"""Project-local change tracking. Linux uses one sleeping inotify service, never polling."""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import sqlite3
import struct
import subprocess
import sys
import time
import uuid

SKIP = {'.git', '.venv', 'venv', 'env', 'ENV', 'node_modules', '__pycache__',
        '.pytest_cache', '.mypy_cache', '.ruff_cache', '.cache', '.tox', '.nox',
        'dist', 'build', 'coverage', 'htmlcov', 'staticfiles', '.next', '.nuxt',
        '.output', '.vite', '.dart_tool', '.gradle', 'Pods', '.instadash',
        '.agents', '.claude', '.codex', '.ssh', '.aws', '.gnupg', '.remember',
        'bootstrap.old', 'bootstrap.new', 'data'}
MUTATING_TOOLS = {'Edit', 'Write', 'MultiEdit', 'apply_patch', 'Bash', 'exec_command',
                  'write_stdin', 'functions.exec', 'functions.apply_patch',
                  'functions.exec_command', 'functions.write_stdin'}
PROTOCOL = 1


@contextmanager
def lock(path: Path):
    """Serialize startup/formatting across both native agents on Unix."""
    import fcntl
    if not path.resolve().is_relative_to(path.parents[3].resolve()) or path.is_symlink():
        raise ValueError('Tracker lock must remain inside the project')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


class Scope:
    """Prune exclusions and let Git implement nested .gitignore / negation semantics."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.state = self.root / '.instadash/state/tracker'
        if not self.state.resolve().is_relative_to(self.root):
            raise ValueError('Tracker state must remain inside the project')
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        for name in ('ignore.git', 'changes.sqlite3', 'changes.sqlite3-wal', 'changes.sqlite3-shm'):
            if (self.state / name).is_symlink():
                raise ValueError('Tracker storage must not be a symlink')
        self.configure()
        self.proc = None
        self.cache: dict[str, bool] = {}
        # An isolated Git metadata directory makes matching work outside repositories too.
        self.gitdir = self.state / 'ignore.git'
        self.env = dict(os.environ, GIT_DIR=str(self.gitdir), GIT_WORK_TREE=str(self.root),
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1', GIT_FLUSH='1')
        # Do not inherit Git context from a hook launched by an unrelated Git command.
        for key in list(self.env):
            if key.startswith('GIT_') and key not in {
                'GIT_DIR', 'GIT_WORK_TREE', 'GIT_CONFIG_GLOBAL', 'GIT_CONFIG_NOSYSTEM', 'GIT_FLUSH'
            }:
                del self.env[key]
        if not (self.gitdir / 'config').is_file():
            init_env = {key: value for key, value in self.env.items()
                        if key not in {'GIT_DIR', 'GIT_WORK_TREE'}}
            subprocess.run(['git', 'init', '--bare', '-q', str(self.gitdir)], env=init_env,
                           check=True, capture_output=True, timeout=5)
        self.reset()

    def configure(self) -> None:
        manifest = json.loads((self.root / '.instadash.json').read_text())
        directories = manifest.get('watch_exclude_dirs', [])
        paths = manifest.get('watch_exclude_paths', [])
        if not isinstance(directories, list) or not isinstance(paths, list):
            raise ValueError('Watch exclusions must be arrays')
        if any(not isinstance(name, str) or not name or '/' in name or name in {'.', '..'}
               for name in directories):
            raise ValueError('watch_exclude_dirs accepts directory names only')
        if any(not isinstance(name, str) or not name or Path(name).is_absolute()
               or '..' in Path(name).parts or name == '.' for name in paths):
            raise ValueError('watch_exclude_paths accepts project-relative paths only')
        self.skip = SKIP | set(directories)
        self.excluded_paths = {Path(name).as_posix().rstrip('/') for name in paths}

    def reset(self) -> None:
        self.close()
        self.cache.clear()
        self.proc = subprocess.Popen(
            ['git', '-c', 'core.bare=false', '-c', 'core.excludesFile=' + os.devnull,
             'check-ignore', '--no-index', '--stdin', '-z', '-v', '-n'],
            cwd=self.root, env=self.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=0)

    def close(self) -> None:
        if self.proc is not None:
            if self.proc.poll() is None:
                self.proc.terminate()
            self.proc.wait(timeout=3)
            self.proc.stdin.close()
            self.proc.stdout.close()
            self.proc = None

    def allowed(self, name: str, directory: bool = False) -> bool:
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or any(p in self.skip for p in path.parts):
            return False
        if any(prefix.as_posix() in self.excluded_paths for prefix in (path, *path.parents)):
            return False
        if (path.name == '.env' or path.name.startswith('.env.') and path.name != '.env.example'
                or path.suffix in {'.pem', '.key', '.p12', '.jks'}
                or path.name.endswith(('.log', '.pid', '.pyc')) or path.name.startswith('.coverage')):
            return False
        # lstat each ancestor: neither watches nor explicit edit paths may traverse symlinks.
        current = self.root
        for part in path.parts:
            current = current / part
            if current.is_symlink():
                return False
        query = path.as_posix() + ('/' if directory else '')
        # Ignore files themselves must remain visible so changes invalidate cached rules.
        if path.name == '.gitignore':
            return True
        if query not in self.cache:
            if len(self.cache) >= 16384:
                self.cache.clear()
            self.proc.stdin.write(os.fsencode(query) + b'\0')
            self.proc.stdin.flush()
            fields = bytearray()
            deadline = time.monotonic() + 5
            while fields.count(0) < 4:
                wait = deadline - time.monotonic()
                if wait <= 0 or not select.select([self.proc.stdout], [], [], wait)[0]:
                    raise TimeoutError('Git ignore matcher did not respond')
                chunk = os.read(self.proc.stdout.fileno(), 65536)
                if not chunk:
                    raise OSError('Git ignore matcher exited')
                fields.extend(chunk)
            pattern = fields.split(b'\0')[2]
            self.cache[query] = bool(pattern and not pattern.startswith(b'!'))
        return not self.cache[query]

    def scan(self, watch=None, start: Path | None = None) -> dict[str, int]:
        """Walk once at startup/recovery, pruning before descending or adding a watch."""
        found = {}
        for base, dirs, files in os.walk(start or self.root, followlinks=False):
            relative = Path(base).relative_to(self.root).as_posix()
            if relative != '.' and not self.allowed(relative, True):
                dirs.clear()
                continue
            if watch:
                watch(Path(base))
            dirs[:] = [d for d in dirs if self.allowed(
                (Path(base) / d).relative_to(self.root).as_posix(), True)]
            for name in files:
                rel = (Path(base) / name).relative_to(self.root).as_posix()
                if self.allowed(rel):
                    try:
                        found[rel] = (self.root / rel).stat().st_mtime_ns
                    except FileNotFoundError:
                        pass
        return found


class Journal:
    """One durable latest-change row per path; indexed cursors avoid full snapshot transfers."""

    def __init__(self, state: Path):
        self.db = sqlite3.connect(state / 'changes.sqlite3')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=NORMAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS files '
                        '(path TEXT PRIMARY KEY, stamp INTEGER, rev INTEGER, '
                        'origin INTEGER, formatted INTEGER)')
        self.db.execute('CREATE INDEX IF NOT EXISTS revision ON files(rev)')
        self.db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)')
        self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('epoch', ?)", (uuid.uuid4().hex,))
        self.epoch = self.db.execute("SELECT value FROM metadata WHERE key='epoch'").fetchone()[0]
        self.rev = self.db.execute('SELECT COALESCE(MAX(rev), 0) FROM files').fetchone()[0]
        self.db.commit()

    def record(self, name: str, stamp: int | None, origin: int | None = None) -> None:
        old = self.db.execute('SELECT stamp FROM files WHERE path=?', (name,)).fetchone()
        if old and old[0] == stamp:
            return
        self.rev += 1
        self.db.execute('INSERT OR REPLACE INTO files VALUES (?, ?, ?, ?, NULL)',
                        (name, stamp, self.rev, origin if origin is not None else stamp))

    def reconcile(self, found: dict[str, int]) -> None:
        for name, in self.db.execute('SELECT path FROM files WHERE stamp IS NOT NULL').fetchall():
            if name not in found:
                self.record(name, None)
        for name, stamp in found.items():
            self.record(name, stamp)
        self.db.commit()

    def changes(self, cursor: dict) -> dict:
        # A replaced/corrupt journal cannot silently satisfy a pre-existing handoff gate.
        if cursor and cursor.get('epoch') != self.epoch:
            raise ValueError('Tracker history changed; restart the session to establish a baseline')
        rows = self.db.execute('SELECT path, stamp, origin, formatted FROM files WHERE rev>?',
                               (cursor.get('rev', self.rev),)).fetchall()
        return {'cursor': {'epoch': self.epoch, 'rev': self.rev},
                'changes': {name: {'stamp': stamp, 'origin': origin,
                                   'formatted': stamp is not None and stamp == formatted}
                            for name, stamp, origin, formatted in rows}}


class Inotify:
    """Watch content mutations only. Reads/access events never wake this process."""

    MASK = 0x8 | 0x4 | 0x40 | 0x80 | 0x100 | 0x200 | 0x400 | 0x800
    OVERFLOW = 0x4000
    DIRECTORY = 0x40000000

    def __init__(self):
        self.lib = ctypes.CDLL(None, use_errno=True)
        self.fd = self.lib.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if self.fd < 0:
            raise OSError(ctypes.get_errno(), 'inotify_init1')
        self.paths: dict[int, Path] = {}

    def add(self, path: Path) -> None:
        wd = self.lib.inotify_add_watch(self.fd, os.fsencode(path), self.MASK | 0x02000000)
        if wd < 0:
            raise OSError(ctypes.get_errno(), 'inotify_add_watch', str(path))
        self.paths[wd] = path

    def close(self) -> None:
        os.close(self.fd)

    def events(self) -> list[tuple[Path, int]]:
        result = []
        for _ in range(16):  # Bound a burst so incoming hook clients cannot starve.
            try:
                data = os.read(self.fd, 262144)
            except BlockingIOError:
                break
            offset = 0
            while offset < len(data):
                wd, mask, _, size = struct.unpack_from('iIII', data, offset)
                raw = data[offset + 16:offset + 16 + size].split(b'\0')[0]
                offset += 16 + size
                if mask & self.OVERFLOW:
                    result.append((Path('.'), mask))
                elif wd in self.paths:
                    path = self.paths[wd] / os.fsdecode(raw) if raw else self.paths[wd]
                    result.append((path, mask))
                    if mask & 0x8000:  # IN_IGNORED
                        self.paths.pop(wd, None)
        return result


class Service:
    def __init__(self, root: Path):
        self.scope = Scope(root)
        self.root = self.scope.root
        self.journal = Journal(self.scope.state)
        self.watcher = Inotify()
        self.rescans = 0
        self.rebuild()

    def rebuild(self) -> None:
        self.watcher.close()
        self.watcher = Inotify()
        self.scope.configure()
        self.scope.reset()
        found = self.scope.scan(self.watcher.add)
        self.journal.reconcile(found)
        self.rescans += 1

    def drain(self) -> None:
        events = self.watcher.events()
        if any(mask & Inotify.OVERFLOW for _, mask in events):
            self.rebuild()
            return
        selected = {}
        for path, mask in events:
            try:
                name = path.relative_to(self.root).as_posix()
            except ValueError:
                continue
            if not self.scope.allowed(name, bool(mask & Inotify.DIRECTORY)):
                continue
            if path.name == '.gitignore' or name == '.instadash.json':
                self.rebuild()
                return
            selected[path] = selected.get(path, 0) | mask
        for path, mask in selected.items():
            name = path.relative_to(self.root).as_posix()
            if mask & Inotify.DIRECTORY or mask & (0x400 | 0x800):
                # Moves invalidate descendant watch paths. Re-register this subtree only.
                for wd, watched in list(self.watcher.paths.items()):
                    if watched == path or path in watched.parents:
                        self.watcher.lib.inotify_rm_watch(self.watcher.fd, wd)
                        self.watcher.paths.pop(wd, None)
                prefix = name + '/'
                for old, in self.journal.db.execute(
                        'SELECT path FROM files WHERE stamp IS NOT NULL AND substr(path,1,?)=?',
                        (len(prefix), prefix)).fetchall():
                    self.journal.record(old, None)
                if path.is_dir() and not path.is_symlink():
                    for child, stamp in self.scope.scan(self.watcher.add, path).items():
                        self.journal.record(child, stamp)
            else:
                stamp = path.stat().st_mtime_ns if path.is_file() else None
                self.journal.record(name, stamp)
        self.journal.db.commit()

    def request(self, message: dict) -> dict:
        self.drain()
        operation = message.get('op')
        if operation == 'ack':
            for name, origin in message.get('files', {}).items():
                if not self.scope.allowed(name):
                    continue
                path = self.root / name
                if path.is_file():
                    stamp = path.stat().st_mtime_ns
                    self.journal.record(name, stamp, origin)
                    self.journal.db.execute('UPDATE files SET formatted=?, origin=? WHERE path=?',
                                            (stamp, origin, name))
            self.journal.db.commit()
            return {}
        for name in message.get('paths', []):
            if self.scope.allowed(name):
                path = self.root / name
                self.journal.record(name, path.stat().st_mtime_ns if path.is_file() else None)
        self.journal.db.commit()
        result = self.journal.changes(message.get('cursor', {}))
        for name in message.get('paths', []):
            if self.scope.allowed(name):
                row = self.journal.db.execute(
                    'SELECT stamp, origin, formatted FROM files WHERE path=?', (name,)).fetchone()
                if row:
                    stamp, origin, formatted = row
                    result['changes'][name] = {'stamp': stamp, 'origin': origin,
                                              'formatted': stamp is not None and stamp == formatted}
        result['changes'] = {name: change for name, change in result['changes'].items()
                             if self.scope.allowed(name)}
        if message.get('all'):
            result['snapshot'] = dict(self.journal.db.execute(
                'SELECT path, stamp FROM files WHERE stamp IS NOT NULL'))
        result.update(pid=os.getpid(), rescans=self.rescans, watches=len(self.watcher.paths),
                      protocol=PROTOCOL)
        return result

    def close(self) -> None:
        self.scope.close()
        self.watcher.close()
        self.journal.db.close()


def address(root: Path) -> str:
    key = hashlib.sha256(os.fsencode(root.resolve())).hexdigest()[:40]
    return '\0instadash-' + str(os.getuid()) + '-' + key


def rpc(root: Path, message: dict) -> dict:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(8)
        client.connect(address(root))
        client.sendall(json.dumps(message).encode() + b'\n')
        chunks = bytearray()
        while not chunks.endswith(b'\n'):
            chunk = client.recv(65536)
            if not chunk:
                raise OSError('Tracker closed its connection')
            chunks.extend(chunk)
        result = json.loads(chunks)
        if 'error' in result:
            raise RuntimeError(result['error'])
        return result


def connect(root: Path, message: dict) -> dict:
    """Lazy startup with one shared instance, safe across concurrent hook processes."""
    try:
        return rpc(root, message)
    except (ConnectionRefusedError, ConnectionResetError, BrokenPipeError, FileNotFoundError):
        pass
    state = root / '.instadash/state/tracker'
    with lock(state / 'startup.lock'):
        try:
            return rpc(root, message)
        except (ConnectionRefusedError, ConnectionResetError, BrokenPipeError, FileNotFoundError):
            pass
        if (state / 'service.log').is_symlink():
            raise ValueError('Tracker log must not be a symlink')
        with (state / 'service.log').open('ab') as log:
            subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--serve', str(root)],
                             stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                             start_new_session=True, close_fds=True)
        deadline = time.monotonic() + 7
        while time.monotonic() < deadline:
            try:
                return rpc(root, message)
            except (ConnectionRefusedError, ConnectionResetError, BrokenPipeError, FileNotFoundError):
                time.sleep(0.025)  # Startup handshake only, never a filesystem polling loop.
        raise TimeoutError('Project watcher startup timed out; inspect .instadash/state/tracker/service.log')


def serve(root: Path) -> None:
    os.umask(0o077)
    os.nice(10)
    # Bind before scanning so parallel clients wait for the same initialization.
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(address(root))
        server.listen(16)
        service = Service(root)
        try:
            while root.is_dir():
                ready, _, _ = select.select([server, service.watcher.fd], [], [], 900)
                if not ready:  # Exit after 15 minutes with no events/clients; journal persists.
                    break
                if service.watcher.fd in ready:
                    service.drain()
                if server in ready:
                    with server.accept()[0] as client:
                        client.settimeout(5)
                        _, uid, _ = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                        if uid != os.getuid():
                            continue
                        raw = bytearray()
                        while not raw.endswith(b'\n') and len(raw) <= 1048576:
                            chunk = client.recv(65536)
                            if not chunk:
                                break
                            raw.extend(chunk)
                        try:
                            message = json.loads(raw)
                            if message.get('op') == 'shutdown':
                                client.sendall(b'{}\n')
                                break
                            result = service.request(message)
                        except (OSError, ValueError, RuntimeError) as exc:
                            result = {'error': str(exc)}
                        try:
                            client.sendall(json.dumps(result).encode() + b'\n')
                        except OSError:
                            pass  # A timed-out/killed hook must not take down shared tracking.
        finally:
            service.close()


class Tracking:
    """Per-hook adapter: tiny journal cursor on Linux, single-scan fallback elsewhere."""

    def __init__(self, root: Path, baseline: dict, paths: list[str], direct: bool = False):
        self.root = root
        self.scope = None
        self.direct = direct
        self.baseline = baseline
        self.mode = 'watch' if sys.platform.startswith('linux') else 'scan'
        if os.environ.get('INSTADASH_TRACKER_MODE') == 'scan' or baseline.get('_mode') == 'scan':
            self.mode = 'scan'
        if self.mode == 'watch':
            try:
                cursor = baseline.get('cursor', {})
                self.result = connect(root, {'cursor': cursor, 'paths': paths,
                                             'all': bool(baseline and not cursor)})
                if baseline and not cursor:
                    # Upgrade from the old timestamp map / portable scan mode once.
                    before = baseline.get('snapshot', {k: v for k, v in baseline.items() if k not in {'seen_ns', '_mode'}})
                    found = self.result.pop('snapshot')
                    if 'snapshot' not in baseline:
                        # 1.2 watched only these roots. Existing newly-covered project files
                        # are a baseline, not thousands of new edits to format on upgrade.
                        roots = {'backend', 'frontend', 'mobile', 'infra', 'scripts'}
                        found = {name: stamp for name, stamp in found.items()
                                 if name.split('/', 1)[0] in roots}
                    changed = list(self.diff(before, found))
                    # Reapply current exclusions to deleted/previously ignored legacy paths.
                    self.result = connect(root, {'cursor': self.result['cursor'], 'paths': changed})
                return
            except (OSError, TimeoutError) as exc:
                print(f'Instadash watcher unavailable ({type(exc).__name__}); using single-scan fallback.',
                      file=sys.stderr)
                # Cursor-only state has no timestamp baseline for safe fallback. Fail closed.
                if 'cursor' in baseline:
                    raise RuntimeError('Watcher unavailable; restore it before completing the session') from exc
                self.mode = 'scan'
        if 'cursor' in baseline:
            raise RuntimeError('Watcher cursor cannot be used in scan mode; start a new session')
        self.scope = Scope(root)
        before = baseline.get('snapshot', {k: v for k, v in baseline.items() if k not in {'seen_ns', '_mode'}})
        self.found = dict(before) if direct and baseline else self.scope.scan()
        if direct and baseline:
            for name in paths:
                if self.scope.allowed(name):
                    path = root / name
                    if path.is_file():
                        self.found[name] = path.stat().st_mtime_ns
                    else:
                        self.found.pop(name, None)
        self.result = {'changes': self.diff(before, self.found) if baseline else {}}

    @staticmethod
    def diff(before: dict, found: dict) -> dict:
        return {name: {'stamp': found.get(name), 'origin': found.get(name), 'formatted': False}
                for name in before.keys() | found.keys() if before.get(name) != found.get(name)}

    def acknowledge(self, files: dict[str, int]) -> None:
        if not files:
            return
        if self.mode == 'watch':
            connect(self.root, {'op': 'ack', 'files': files})
        else:
            for name in files:
                path = self.root / name
                if path.is_file():
                    self.found[name] = path.stat().st_mtime_ns
                else:
                    self.found.pop(name, None)

    def checkpoint(self) -> dict:
        if self.mode == 'watch':
            return {'cursor': self.result['cursor'], 'seen_ns': time.time_ns()}
        return {'snapshot': self.found, 'seen_ns': time.time_ns(), '_mode': 'scan'}

    def close(self) -> None:
        if self.scope:
            self.scope.close()


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--serve':
        serve(Path(sys.argv[2]).resolve())
    elif len(sys.argv) == 3 and sys.argv[1] == '--shutdown':
        try:
            rpc(Path(sys.argv[2]).resolve(), {'op': 'shutdown'})
        except (ConnectionRefusedError, ConnectionResetError, BrokenPipeError, FileNotFoundError):
            pass
