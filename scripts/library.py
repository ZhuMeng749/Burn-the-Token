#!/usr/bin/env python3
"""Local reference-shot catalogue. Registration is not perceptual video analysis."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.webm', '.m4v', '.avi'}
CARD_KEYS = {'title', 'purpose', 'tags', 'recipe', 'observations', 'notes', 'status'}
OBSERVATION_KEYS = {'static', 'motion', 'audio'}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def positive_time(value):
    if isinstance(value, bool):
        raise ValueError('Time must be a finite number.')
    try:
        value = float(value)
    except (ValueError, TypeError) as error:
        raise ValueError('Time must be a finite number.') from error
    if not math.isfinite(value) or value < 0:
        raise ValueError('Time must be finite and non-negative.')
    return round(value, 6)


def tool(name, explicit=None):
    executable = explicit or shutil.which(name)
    if not executable:
        raise ValueError(f'{name} not found. Install FFmpeg or pass --{name} PATH.')
    return executable


def probe(path, executable=None):
    result = subprocess.run([tool('ffprobe', executable), '-v', 'error', '-show_streams',
                             '-show_format', '-of', 'json', str(path)],
                            capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    video = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
    if video is None:
        raise ValueError('No video stream found.')
    duration = positive_time(video.get('duration') or data.get('format', {}).get('duration'))
    if duration <= 0:
        raise ValueError('Video has no measurable duration.')
    return {'duration_seconds': duration, 'width': video.get('width'),
            'height': video.get('height'), 'fps': video.get('avg_frame_rate'),
            'rotation': video.get('tags', {}).get('rotate'),
            'side_data_list': video.get('side_data_list', []),
            'audio_streams': sum(s.get('codec_type') == 'audio' for s in data['streams'])}


def validate_card(card):
    if not isinstance(card, dict) or set(card) - CARD_KEYS:
        raise ValueError('Shot card must be an object with documented fields only.')
    for key in ('title', 'purpose', 'notes'):
        if key in card and not isinstance(card[key], str):
            raise ValueError(f'{key} must be text.')
    if 'tags' in card and (not isinstance(card['tags'], list) or
                           any(not isinstance(t, str) or not t.strip() for t in card['tags'])):
        raise ValueError('tags must be an array of non-empty strings.')
    if card.get('status', 'active') not in ('active', 'archived'):
        raise ValueError('status must be active or archived.')
    if 'recipe' in card and not isinstance(card['recipe'], dict):
        raise ValueError('recipe must be an object.')
    if 'observations' in card:
        observations = card['observations']
        if not isinstance(observations, dict) or set(observations) - OBSERVATION_KEYS:
            raise ValueError('observations may contain static, motion and audio only.')
        for item in observations.values():
            if not isinstance(item, dict) or item.get('status') not in ('not_run', 'observed', 'inferred'):
                raise ValueError('Observation status must be not_run, observed or inferred.')
            if not isinstance(item.get('evidence', []), list) or any(
                    not isinstance(v, str) or not v.strip() for v in item.get('evidence', [])):
                raise ValueError('Observation evidence must be an array of text paths or notes.')
            if item['status'] == 'observed' and not item.get('evidence'):
                raise ValueError('Observed entries require evidence; registration alone is not observation.')
    # Reject non-finite values anywhere in a JSON card.
    json.dumps(card, allow_nan=False)


def empty_card():
    return {'title': '', 'purpose': '', 'tags': [], 'recipe': {}, 'notes': '',
            'status': 'active', 'observations': {
                key: {'status': 'not_run', 'evidence': []} for key in sorted(OBSERVATION_KEYS)}}


class Library:
    def __init__(self, root, create=False):
        self.root = Path(root).expanduser().resolve()
        path = self.root / 'library.sqlite3'
        if not create and not path.is_file():
            raise ValueError(f'Library not found: {path}; run init first.')
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=15)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        schema = self.db.execute('PRAGMA user_version').fetchone()[0]
        if schema not in (0, 1):
            self.db.close()
            raise ValueError(f'Unsupported library schema {schema}; do not overwrite it.')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS videos (
                id TEXT PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE,
                metadata TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sources (
                video_id TEXT REFERENCES videos(id), path TEXT NOT NULL,
                last_seen TEXT NOT NULL, PRIMARY KEY(video_id, path));
            CREATE TABLE IF NOT EXISTS shots (
                id TEXT PRIMARY KEY, video_id TEXT REFERENCES videos(id),
                start REAL NOT NULL, end REAL NOT NULL, card TEXT NOT NULL,
                revision INTEGER NOT NULL, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, UNIQUE(video_id, start, end));
            CREATE TABLE IF NOT EXISTS revisions (
                shot_id TEXT REFERENCES shots(id), revision INTEGER NOT NULL,
                card TEXT NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(shot_id, revision));
            CREATE TABLE IF NOT EXISTS usage (
                id INTEGER PRIMARY KEY, shot_id TEXT REFERENCES shots(id),
                revision INTEGER NOT NULL, project TEXT NOT NULL,
                target_shot TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL);
            PRAGMA user_version=1;
        ''')

    def close(self):
        self.db.close()

    def ingest(self, path, ffprobe=None):
        path = Path(path).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f'Not a file: {path}')
        before = path.stat()
        sha = digest(path)
        row = self.db.execute('SELECT * FROM videos WHERE sha256=?', (sha,)).fetchone()
        metadata = json.loads(row['metadata']) if row else probe(path, ffprobe)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('Source changed while being registered; retry once the file is stable.')
        video_id = row['id'] if row else 'v_' + sha[:20]
        with self.db:
            if row is None:
                self.db.execute('INSERT INTO videos VALUES (?,?,?,?)',
                                (video_id, sha, json.dumps(metadata), now()))
            self.db.execute('INSERT OR REPLACE INTO sources VALUES (?,?,?)',
                            (video_id, str(path), now()))
        return {'video_id': video_id, 'duplicate': row is not None, 'sha256': sha, **metadata}

    def video(self, video_id):
        row = self.db.execute('SELECT * FROM videos WHERE id=?', (video_id,)).fetchone()
        if row is None:
            raise ValueError(f'Unknown video: {video_id}')
        return {**dict(row), 'metadata': json.loads(row['metadata']), 'paths': [
            r[0] for r in self.db.execute('SELECT path FROM sources WHERE video_id=?', (video_id,))]}

    def source(self, video_id):
        video = self.video(video_id)
        for path in video['paths']:
            try:
                if Path(path).is_file() and digest(path) == video['sha256']:
                    return Path(path)
            except OSError:
                continue
        raise ValueError(f'Source missing or content changed for {video_id}; re-register the original file.')

    def get(self, shot_id):
        row = self.db.execute('SELECT * FROM shots WHERE id=?', (shot_id,)).fetchone()
        if row is None:
            raise ValueError(f'Unknown shot: {shot_id}')
        return {**dict(row), 'card': json.loads(row['card'])}

    def record(self, video_id, start, end, card):
        validate_card(card)
        start, end = positive_time(start), positive_time(end)
        video = self.video(video_id)
        if start >= end or end > video['metadata']['duration_seconds']:
            raise ValueError('Shot must satisfy 0 <= start < end <= video duration.')
        key = f'{video_id}:{start:.6f}:{end:.6f}'
        shot_id = 's_' + hashlib.sha256(key.encode()).hexdigest()[:20]
        existing = self.db.execute('SELECT id FROM shots WHERE id=?', (shot_id,)).fetchone()
        if existing:
            return self.update(shot_id, card)
        result = empty_card()
        result.update(card)
        result['observations'] = {**empty_card()['observations'], **card.get('observations', {})}
        timestamp = now()
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False)
        with self.db:
            self.db.execute('INSERT INTO shots VALUES (?,?,?,?,?,?,?,?)',
                            (shot_id, video_id, start, end, encoded, 1, timestamp, timestamp))
            self.db.execute('INSERT INTO revisions VALUES (?,?,?,?)',
                            (shot_id, 1, encoded, timestamp))
        return self.get(shot_id)

    def update(self, shot_id, changes):
        validate_card(changes)
        current = self.get(shot_id)
        card = current['card']
        for key, value in changes.items():
            card[key] = {**card.get(key, {}), **value} if key in ('recipe', 'observations') else value
        validate_card(card)
        encoded = json.dumps(card, ensure_ascii=False, allow_nan=False)
        with self.db:
            # Guard against concurrent writers changing the same shot after our read.
            cursor = self.db.execute('UPDATE shots SET card=?, revision=revision+1, updated_at=? '
                                     'WHERE id=? AND revision=?',
                                     (encoded, now(), shot_id, current['revision']))
            if cursor.rowcount != 1:
                raise ValueError('Shot changed concurrently; reload it before updating.')
            self.db.execute('INSERT INTO revisions VALUES (?,?,?,?)',
                            (shot_id, current['revision'] + 1, encoded, now()))
        return self.get(shot_id)

    def search(self, query='', tags=(), purpose='', video_id=None, include_archived=False, project=None):
        results = []
        for row in self.db.execute('SELECT id FROM shots ORDER BY video_id,start'):
            shot = self.get(row['id'])
            card = shot['card']
            if card['status'] == 'archived' and not include_archived:
                continue
            haystack = json.dumps(card, ensure_ascii=False).casefold()
            if any(term.casefold() not in haystack for term in query.split()):
                continue
            if not set(t.casefold() for t in tags).issubset(t.casefold() for t in card['tags']):
                continue
            if purpose.casefold() not in card['purpose'].casefold() or (video_id and video_id != shot['video_id']):
                continue
            shot['source_paths'] = self.video(shot['video_id'])['paths']
            shot['source_exists_unverified'] = any(Path(p).is_file() for p in shot['source_paths'])
            if project is not None:
                shot['project_usage'] = [dict(r) for r in self.db.execute(
                    'SELECT * FROM usage WHERE shot_id=? AND project=? ORDER BY id', (shot['id'], project))]
            results.append(shot)
        return results

    def use(self, shot_id, project, target_shot, note=''):
        shot = self.get(shot_id)
        if shot['card']['status'] == 'archived':
            raise ValueError('Restore an archived shot before using it.')
        with self.db:
            cursor = self.db.execute('INSERT INTO usage (shot_id,revision,project,target_shot,note,created_at) '
                                     'VALUES (?,?,?,?,?,?)',
                                     (shot_id, shot['revision'], project, target_shot, note, now()))
        return {'usage_id': cursor.lastrowid, 'shot_id': shot_id, 'revision': shot['revision']}

    def check(self):
        results = []
        for row in self.db.execute('SELECT id FROM videos ORDER BY id'):
            video = self.video(row['id'])
            paths = []
            for path in video['paths']:
                state = 'missing'
                if Path(path).is_file():
                    try:
                        state = 'valid' if digest(path) == video['sha256'] else 'content_changed'
                    except OSError:
                        state = 'unreadable'
                paths.append({'path': path, 'state': state})
            results.append({'video_id': video['id'], 'usable': any(p['state'] == 'valid' for p in paths),
                            'sources': paths})
        return results

    def extract(self, shot_id, count=5, ffmpeg=None):
        if not 1 <= count <= 12:
            raise ValueError('Frame count must be between 1 and 12.')
        executable = tool('ffmpeg', ffmpeg)
        shot = self.get(shot_id)
        path = self.source(shot['video_id'])
        out = self.root / 'evidence' / shot_id
        out.mkdir(parents=True, exist_ok=True)
        images = []
        for index in range(count):
            at = shot['start'] + (shot['end'] - shot['start']) * (index + 0.5) / count
            target = out / f'{at:.6f}.jpg'
            subprocess.run([executable, '-v', 'error', '-y', '-ss', str(at), '-i', str(path),
                            '-frames:v', '1', '-vf', 'scale=640:-2', str(target)],
                           capture_output=True, text=True, check=True)
            if not target.is_file() or not target.stat().st_size:
                raise ValueError(f'No frame decoded at {at:.6f}s.')
            images.append({'seconds': at, 'path': str(target)})
        # Never mark observations as reviewed based on extraction.
        return {'shot_id': shot_id, 'frames': images, 'observation_status_changed': False}

    def export(self):
        return {'schema_version': 1, 'videos': [self.video(r[0]) for r in self.db.execute('SELECT id FROM videos')],
                'shots': self.search(include_archived=True),
                'revisions': [{**dict(r), 'card': json.loads(r['card'])} for r in self.db.execute('SELECT * FROM revisions')],
                'usage': [dict(r) for r in self.db.execute('SELECT * FROM usage')]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', default=os.environ.get('BURN_THE_TOKEN_LIBRARY',
                        'reference-library/burn-the-token'))
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('init')
    ingest = commands.add_parser('ingest')
    ingest.add_argument('paths', nargs='+')
    ingest.add_argument('--ffprobe')
    ingest.add_argument('--recursive', action='store_true')
    record = commands.add_parser('record-shot')
    record.add_argument('--video', required=True)
    record.add_argument('--start', type=float, required=True)
    record.add_argument('--end', type=float, required=True)
    record.add_argument('--data', type=Path, required=True)
    update = commands.add_parser('update-shot')
    update.add_argument('--shot', required=True)
    update.add_argument('--data', type=Path, required=True)
    show = commands.add_parser('show')
    show.add_argument('--shot', required=True)
    search = commands.add_parser('search')
    search.add_argument('--query', default='')
    search.add_argument('--tag', action='append', default=[])
    search.add_argument('--purpose', default='')
    search.add_argument('--video')
    search.add_argument('--project')
    search.add_argument('--include-archived', action='store_true')
    use = commands.add_parser('use')
    use.add_argument('--shot', required=True)
    use.add_argument('--project', required=True)
    use.add_argument('--target-shot', required=True)
    use.add_argument('--note', default='')
    commands.add_parser('check')
    commands.add_parser('export')
    extract = commands.add_parser('extract')
    extract.add_argument('--shot', required=True)
    extract.add_argument('--count', type=int, default=5)
    extract.add_argument('--ffmpeg')
    args = parser.parse_args(argv)
    library = None
    try:
        library = Library(args.library, create=args.command == 'init')
        if args.command == 'init':
            result = {'library': str(library.root), 'schema_version': 1}
        elif args.command == 'ingest':
            files = []
            for value in args.paths:
                path = Path(value).expanduser()
                files.extend(sorted(p for p in (path.rglob('*') if args.recursive else path.glob('*'))
                                    if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS)
                             if path.is_dir() else [path])
            if not files:
                raise ValueError('No video files found.')
            result = {'registered': [], 'errors': []}
            for path in files:
                try:
                    result['registered'].append(library.ingest(path, args.ffprobe))
                except (OSError, ValueError, subprocess.CalledProcessError) as error:
                    result['errors'].append({'path': str(path), 'error': str(error)})
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1 if result['errors'] else 0
        elif args.command in ('record-shot', 'update-shot'):
            card = json.loads(args.data.read_text(encoding='utf-8'))
            result = (library.record(args.video, args.start, args.end, card) if args.command == 'record-shot'
                      else library.update(args.shot, card))
        elif args.command == 'show':
            result = library.get(args.shot)
        elif args.command == 'search':
            result = library.search(args.query, args.tag, args.purpose, args.video,
                                    args.include_archived, args.project)
        elif args.command == 'use':
            result = library.use(args.shot, args.project, args.target_shot, args.note)
        elif args.command == 'check':
            result = library.check()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if all(v['usable'] for v in result) else 1
        elif args.command == 'extract':
            result = library.extract(args.shot, args.count, args.ffmpeg)
        else:
            result = library.export()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, sqlite3.Error, subprocess.CalledProcessError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        if library:
            library.close()


if __name__ == '__main__':
    sys.exit(main())
