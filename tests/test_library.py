"""Behaviour tests; the media test uses generated colours, never private footage."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'library.py'
spec = importlib.util.spec_from_file_location('shot_library', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lib = module.Library(self.root / 'catalogue', create=True)
        self.addCleanup(self.lib.close)
        self.probe = patch.object(module, 'probe', return_value={'duration_seconds': 12, 'width': 100,
                                'height': 100, 'fps': '30/1', 'audio_streams': 0})
        self.probe.start()
        self.addCleanup(self.probe.stop)
        self.source = self.root / 'reference.mp4'
        self.source.write_bytes(b'original synthetic contents')
        self.video = self.lib.ingest(self.source)['video_id']

    def shot(self, **extra):
        return self.lib.record(self.video, 1, 4, {
            'title': '立体关键词', 'purpose': '开头强调',
            'tags': ['立体', '人物遮挡'], **extra})

    def test_same_content_new_path_preserves_shots(self):
        shot = self.shot()
        moved = self.root / 'moved.mp4'
        self.source.rename(moved)
        registered = self.lib.ingest(moved)
        self.assertTrue(registered['duplicate'])
        self.assertEqual(registered['video_id'], self.video)
        self.assertEqual(self.lib.get(shot['id'])['revision'], 1)
        self.assertEqual(self.lib.source(self.video), moved.resolve())
        self.assertTrue(self.lib.check()[0]['usable'])
        self.assertEqual(len(self.lib.export()['videos']), 1)

    def test_replaced_file_is_new_video_and_old_source_is_unusable(self):
        self.shot()
        self.source.write_bytes(b'replaced synthetic contents')
        new = self.lib.ingest(self.source)
        self.assertNotEqual(new['video_id'], self.video)
        self.assertFalse(new['duplicate'])
        with self.assertRaises(ValueError):
            self.lib.source(self.video)
        statuses = {v['video_id']: v for v in self.lib.check()}
        self.assertEqual(statuses[self.video]['sources'][0]['state'], 'content_changed')
        self.assertTrue(statuses[new['video_id']]['usable'])

    def test_invalid_intervals_and_observations_are_not_saved(self):
        for start, end in ((2, 2), (-1, 4), (0, 13), (0, float('nan')), (0, float('inf')), (True, 2)):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                self.lib.record(self.video, start, end, {})
        for evidence in ([], [''], ['   ']):
            with self.assertRaises(ValueError):
                self.shot(observations={'motion': {'status': 'observed', 'evidence': evidence}})
        self.assertEqual(self.lib.search(), [])

    def test_update_keeps_history_and_used_revision(self):
        shot = self.shot(recipe={'subject': '人物', 'motion_beats': ['进入']},
                         observations={'static': {'status': 'observed', 'evidence': ['review.md#frame-30']}})
        used = self.lib.use(shot['id'], 'film-a', 'S01', 'first use')
        revised = self.lib.update(shot['id'], {'recipe': {'motion_beats': ['进入', '停留']},
                                              'observations': {'motion': {'status': 'inferred', 'evidence': []}}})
        self.assertEqual(used['revision'], 1)
        self.assertEqual(revised['revision'], 2)
        self.assertEqual(revised['card']['recipe']['subject'], '人物')
        self.assertEqual(revised['card']['observations']['static']['status'], 'observed')
        export = self.lib.export()
        self.assertEqual(export['revisions'][0]['card']['recipe']['motion_beats'], ['进入'])
        self.assertEqual(export['usage'][0]['revision'], 1)
        same = self.lib.record(self.video, 1.0, 4.0, {'notes': '补充观察'})
        self.assertEqual(same['id'], shot['id'])
        self.assertEqual(same['revision'], 3)
        self.assertEqual(len(self.lib.search()), 1)

    def test_search_filters_usage_archive_and_restore(self):
        shot = self.shot()
        self.lib.record(self.video, 4, 8, {'title': '纸页', 'tags': ['纸张'], 'purpose': '解释'})
        self.lib.use(shot['id'], 'film-a', 'S02')
        found = self.lib.search(query='立体 关键词', tags=['人物遮挡'], purpose='开头', project='film-a')
        self.assertEqual([s['id'] for s in found], [shot['id']])
        self.assertEqual(found[0]['project_usage'][0]['target_shot'], 'S02')
        self.assertEqual(self.lib.search(tags=['人物遮挡', '纸张']), [])
        self.lib.update(shot['id'], {'status': 'archived'})
        self.assertEqual(self.lib.search(query='立体'), [])
        self.assertEqual(len(self.lib.search(query='立体', include_archived=True)), 1)
        with self.assertRaises(ValueError):
            self.lib.use(shot['id'], 'film-a', 'S03')
        self.lib.update(shot['id'], {'status': 'active'})
        self.assertEqual(len(self.lib.search(query='立体')), 1)

    def test_database_reopens_and_missing_source_is_reported(self):
        shot = self.shot()
        reopened = module.Library(self.lib.root)
        try:
            self.assertEqual(reopened.get(shot['id'])['card']['title'], '立体关键词')
            self.source.unlink()
            self.assertFalse(reopened.search()[0]['source_exists_unverified'])
            self.assertFalse(reopened.check()[0]['usable'])
        finally:
            reopened.close()


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg/ffprobe not installed')
class MediaWorkflowTests(unittest.TestCase):
    def test_real_multi_video_cli_and_frame_extraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalogue = root / 'library'

            def cli(*args, expected=0):
                run = subprocess.run([sys.executable, str(SCRIPT), '--library', str(catalogue), *args],
                                     capture_output=True, text=True)
                self.assertEqual(run.returncode, expected, run.stdout + run.stderr)
                return json.loads(run.stdout)

            videos = []
            for colour in ('red', 'blue'):
                video = root / (colour + '.mp4')
                subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                                f'color=c={colour}:s=160x90:r=10:d=2', '-c:v', 'mpeg4', str(video)],
                               check=True, capture_output=True)
                videos.append(str(video))
            cli('init')
            imported = cli('ingest', *videos)
            self.assertEqual(len(imported['registered']), 2)
            self.assertNotEqual(imported['registered'][0]['video_id'], imported['registered'][1]['video_id'])
            partial = cli('ingest', videos[0], str(root / 'missing.mp4'), expected=1)
            self.assertTrue(partial['registered'][0]['duplicate'])
            self.assertEqual(len(partial['errors']), 1)
            card = root / 'card.json'
            card.write_text(json.dumps({'title': 'synthetic red', 'tags': ['colour']}))
            shot = cli('record-shot', '--video', imported['registered'][0]['video_id'],
                       '--start', '0.2', '--end', '1.8', '--data', str(card))
            frames = cli('extract', '--shot', shot['id'], '--count', '3')
            self.assertFalse(frames['observation_status_changed'])
            self.assertEqual(len(frames['frames']), 3)
            for frame in frames['frames']:
                self.assertGreater(Path(frame['path']).stat().st_size, 0)
                subprocess.run(['ffmpeg', '-v', 'error', '-i', frame['path'], '-f', 'null', '-'],
                               check=True, capture_output=True)
            shown = cli('show', '--shot', shot['id'])
            self.assertTrue(all(o['status'] == 'not_run' for o in shown['card']['observations'].values()))
            self.assertEqual(len(cli('search', '--tag', 'colour')), 1)
            self.assertTrue(all(v['usable'] for v in cli('check')))
            self.assertEqual(len(cli('export')['shots']), 1)


if __name__ == '__main__':
    unittest.main()
