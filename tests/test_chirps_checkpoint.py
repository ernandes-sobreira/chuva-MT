"""Testes de retomada/publicação com fixtures sintéticas; NUNCA chamam CHC.

Biblioteca padrão apenas. O kernel GeoTIFF é substituído por valores conhecidos;
Git de integração usa exclusivamente um repositório bare local temporário.
"""
import copy
import datetime as dt
import io
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import chirps_checkpoint as cp
import processar_chirps_v3 as process
import publicar_chirps_v3 as publish
import verificar_status_chirps as audit

GRID = {'width': 20, 'height': 20, 'count': 1, 'crs': 'EPSG:4326',
        'transform': [0.05, 0., -60., 0., -0.05, -10., 0., 0., 1.]}
CODES = [str(5100000 + i) for i in range(142)]


class Clock:
    def __init__(self):
        self.value = dt.datetime(2026, 11, 8, 18, tzinfo=cp.UTC)
        self.sleeps = []

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.value += dt.timedelta(seconds=seconds)

    def tomorrow(self):
        self.value += dt.timedelta(days=1, seconds=1)


class Fixture:
    def __init__(self, case):
        self.case = case
        self.temp = tempfile.TemporaryDirectory()
        case.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'worker'
        self.root.mkdir()
        self.state = self.root / '.state/chirps-v3'
        self.candidate = self.root / '.work/chirps-v3-result.json'
        self.months = self.root / 'dados/meses.json'
        self.status = self.root / 'dados/status_chirps.json'
        self.geo = self.root / 'dados/municipios_mt.geojson'
        self.months.parent.mkdir()
        self.geo.write_text('{}')
        self.data = {'_meta': {'retained': 'unchanged'},
                     '2026-08': {'colecao': 'UCSB-CHG/CHIRPS/DAILY', 'v': {'5100000': 77}},
                     '2026-10': {'colecao': 'CHIRPS-v3.0-sat-official', 'preliminar': True,
                                 'parcial': False, 'dias_observados': 31, 'v': {'5100000': 99}}}
        self.months.write_text(json.dumps(self.data, indent=2))
        self.status.write_text(json.dumps({'meses': {
            '2026-08': {'final_completo': True, 'dias_preliminar': 31},
            '2026-10': {'final_completo': False, 'dias_preliminar': 31}}}))
        self.original_bytes = self.months.read_bytes()
        self.clock, self.requests, self.failures = Clock(), [], {}
        mappings = [(process, 'ROOT', self.root), (process, 'STATE', self.state),
                    (process, 'GEO', self.geo), (process, 'MONTHS', self.months),
                    (process, 'STATUS', self.status), (process, 'CANDIDATE', self.candidate),
                    (publish, 'ROOT', self.root), (publish, 'STATE', self.state),
                    (publish, 'PATH', self.months), (publish, 'CANDIDATE', self.candidate),
                    (audit, 'ROOT', self.root), (cp, 'now_utc', self.clock.now),
                    (process, 'now_utc', self.clock.now)]
        for module, key, value in mappings:
            case.enterContext(patch.object(module, key, value))
        case.enterContext(patch.object(process.time, 'sleep', self.clock.sleep))
        case.enterContext(patch.object(process, 'read_geometry', return_value=([(c, {}) for c in CODES], [0, 0, 1, 1])))
        case.enterContext(patch.object(process, 'raster_signature', return_value=GRID))
        case.enterContext(patch.object(process, 'grid_values', side_effect=self.grid))
        case.enterContext(patch.object(process, 'urlopen', side_effect=self.urlopen))

    def urlopen(self, req, timeout):
        url = req.full_url
        self.requests.append((url, self.clock.now()))
        day = int(re.search(r'\.(\d{2})\.tif$', url).group(1))
        if day in self.failures:
            code, headers = self.failures[day]
            raise HTTPError(url, code, 'fixture HTTP failure', headers, None)
        return io.BytesIO(str(day).encode())

    def grid(self, path, shapes, bounds):
        day = int(path.read_text())
        return [2 * (day / 10 + i / 1000) for i in range(142)], [2] * 142

    def checkpoint(self):
        return json.loads(next(self.state.glob('work-*.json')).read_text())

    def run(self):
        process.main()

    def finish(self):
        for _ in range(7):
            self.run()
            if self.candidate.exists():
                return
            self.clock.tomorrow()
        raise AssertionError('Fixture did not finish in seven batches')

    def git(self, *args, cwd=None):
        result = subprocess.run(['git', *args], cwd=cwd or self.root, check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env={**os.environ, 'GIT_ALLOW_PROTOCOL': 'file'})
        return result.stdout.decode()

    def init_git(self):
        self.remote = self.base / 'remote.git'
        self.git('init', '--bare', '--initial-branch=main', str(self.remote), cwd=self.base)
        self.git('init', '--initial-branch=main')
        self.git('config', 'user.name', 'Offline Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('add', 'dados')
        self.git('commit', '-m', 'Initial fixture')
        self.git('remote', 'add', 'origin', str(self.remote))
        self.git('push', '-u', 'origin', 'main')

    def publish(self, checkpoint_only=False):
        with patch.object(sys, 'argv', ['publish'] + (['--checkpoint-only'] if checkpoint_only else [])):
            publish.main()


class OfflineCase(unittest.TestCase):
    def setUp(self):
        # Última linha de defesa: nenhum teste pode abrir socket de rede.
        self.enterContext(patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden in offline tests')))
        self.enterContext(patch.dict(os.environ, {'GIT_ALLOW_PROTOCOL': 'file'}))
        self.enterContext(patch('sys.stdout', new_callable=io.StringIO))


class RetryAndStateTests(OfflineCase):
    def test_retry_after_seconds_are_not_capped(self):
        now = Clock().now()
        self.assertEqual(cp.retry_after_until('86400', now), now + dt.timedelta(days=1))

    def test_retry_after_http_date(self):
        now = Clock().now()
        self.assertEqual(cp.retry_after_until('Tue, 10 Nov 2026 18:00:00 GMT', now), now + dt.timedelta(days=2))

    def test_huge_retry_after_is_not_shortened(self):
        self.assertEqual(cp.retry_after_until('999999999999999999999999', Clock().now()),
                         dt.datetime.max.replace(tzinfo=cp.UTC))

    def test_bad_retry_after_waits_a_day(self):
        now = Clock().now()
        for value in (None, '', 'invalid', '-5'):
            self.assertEqual(cp.retry_after_until(value, now), now + dt.timedelta(days=1))

    def test_expired_retry_after_keeps_polite_minimum(self):
        now = Clock().now()
        self.assertEqual(cp.retry_after_until('Sun, 08 Nov 2026 17:00:00 GMT', now), now + dt.timedelta(seconds=60))

    def test_cooldown_merge_never_shortens_pause(self):
        now = Clock().now()
        short = {'schema': 1, 'not_before': cp.iso(now + dt.timedelta(hours=1))}
        long = {'schema': 1, 'not_before': cp.iso(now + dt.timedelta(days=2))}
        self.assertEqual(cp.merge_state(short, long, 'control.json')['not_before'], long['not_before'])

    def test_checkpoint_context_versions_and_geometry_have_distinct_paths(self):
        fx = Fixture(self)
        fx.run()
        ctx = fx.checkpoint()['context']
        for altered in ({**ctx, 'stage': 'prelim'}, {**ctx, 'geometry_sha256': 'f'*64}, {**ctx, 'ndays': 30}):
            self.assertNotEqual(cp.checkpoint_path(fx.state, ctx), cp.checkpoint_path(fx.state, altered))


class ProcessingTests(OfflineCase):
    def test_five_files_then_resume_without_redownload(self):
        fx = Fixture(self)
        fx.run()
        self.assertEqual(len(fx.requests), 5)
        self.assertEqual(set(fx.checkpoint()['days']), {'01', '02', '03', '04', '05'})
        self.assertFalse(fx.candidate.exists())
        self.assertEqual(fx.months.read_bytes(), fx.original_bytes)
        fx.clock.tomorrow()
        fx.run()
        self.assertEqual(len(fx.requests), 10)
        self.assertTrue(fx.requests[5][0].endswith('.06.tif'))
        for (_, before), (_, after) in zip(fx.requests, fx.requests[1:]):
            self.assertGreaterEqual((after-before).total_seconds(), 60)

    def test_resumed_result_matches_integral_sum_and_preserves_october(self):
        fx = Fixture(self)
        fx.finish()
        self.assertEqual(len(fx.requests), 31)
        result = json.loads(fx.candidate.read_text())
        expected = {}
        for i, code in enumerate(CODES):
            total = 0.0
            for day in range(1, 32):
                total += day/10 + i/1000
            expected[code] = round(total, 2)
        self.assertEqual(result['record']['v'], expected)
        self.assertFalse(result['record']['preliminar'])
        self.assertEqual(fx.months.read_bytes(), fx.original_bytes)
        states = {p.name: json.loads(p.read_text()) for p in fx.state.glob('*.json')}
        self.assertEqual(publish.validate_candidate(result, states)[0], '2026-08')

    def test_http_429_at_last_day_saves_30_and_resumes_only_31(self):
        fx = Fixture(self)
        fx.failures[31] = (429, {'Retry-After': '86400'})
        for _ in range(7):
            fx.run()
            if len(fx.requests) < 31:
                fx.clock.tomorrow()
        self.assertEqual(len(fx.requests), 31)
        self.assertEqual(len(fx.checkpoint()['days']), 30)
        self.assertFalse(fx.candidate.exists())
        self.assertEqual(fx.months.read_bytes(), fx.original_bytes)
        fx.run()  # Still cooling down: zero additional request.
        self.assertEqual(len(fx.requests), 31)
        fx.failures.clear()
        fx.clock.tomorrow()
        fx.run()
        self.assertEqual(len(fx.requests), 32)
        self.assertTrue(fx.requests[-1][0].endswith('.31.tif'))
        self.assertTrue(fx.candidate.exists())

    def test_first_503_stops_without_retry(self):
        fx = Fixture(self)
        fx.failures[1] = (503, {'Retry-After': '172800'})
        fx.run()
        self.assertEqual(len(fx.requests), 1)
        fx.clock.tomorrow()
        fx.run()
        self.assertEqual(len(fx.requests), 1)
        self.assertFalse(fx.candidate.exists())

    def test_corrupted_checkpoint_fails_before_network(self):
        fx = Fixture(self)
        fx.run()
        path = next(fx.state.glob('work-*.json'))
        data = fx.checkpoint()
        data['days']['01']['values'][0] += 1
        path.write_text(json.dumps(data))
        fx.clock.tomorrow()
        with self.assertRaises(ValueError):
            fx.run()
        self.assertEqual(len(fx.requests), 5)
        self.assertEqual(fx.months.read_bytes(), fx.original_bytes)

    def test_negative_values_do_not_enter_checkpoint(self):
        fx = Fixture(self)
        with patch.object(process, 'grid_values', return_value=([-1.] * 142, [2] * 142)):
            with self.assertRaises(ValueError):
                fx.run()
        self.assertFalse(fx.candidate.exists())
        self.assertFalse(list(fx.state.glob('work-*.json')))
        self.assertEqual(fx.months.read_bytes(), fx.original_bytes)

    def test_zero_coverage_never_publishes(self):
        fx = Fixture(self)
        with patch.object(process, 'grid_values', return_value=([1.] * 142, [0] * 142)):
            with self.assertRaises(ValueError):
                fx.run()
        self.assertFalse(fx.candidate.exists())

    def test_changed_grid_blocks_mixing(self):
        fx = Fixture(self)
        fx.run()
        fx.clock.tomorrow()
        with patch.object(process, 'raster_signature', return_value={**GRID, 'width': 25}):
            with self.assertRaises(ValueError):
                fx.run()
        self.assertEqual(len(fx.checkpoint()['days']), 5)
        self.assertFalse(fx.candidate.exists())

    def test_incomplete_candidate_cannot_publish(self):
        fx = Fixture(self)
        fx.run()
        with self.assertRaises(ValueError):
            process.completed_values(fx.checkpoint())

    def test_new_preliminary_days_do_not_restart_unfinished_target(self):
        fx = Fixture(self)
        fx.status.write_text(json.dumps({'meses': {'2026-11': {'final_completo': False, 'dias_preliminar': 8}}}))
        fx.run()
        self.assertEqual(len(fx.requests), 5)
        fx.clock.tomorrow()
        fx.status.write_text(json.dumps({'meses': {'2026-11': {'final_completo': False, 'dias_preliminar': 10}}}))
        fx.run()
        self.assertEqual(len(fx.requests), 8)
        self.assertTrue(fx.requests[5][0].endswith('.06.tif'))
        candidate = json.loads(fx.candidate.read_text())
        self.assertEqual(candidate['record']['dias_observados'], 8)
        self.assertTrue(candidate['record']['preliminar'])
        self.assertTrue(candidate['record']['parcial'])

    def test_preliminary_available_days_keep_both_flags(self):
        fx = Fixture(self)
        fx.status.write_text(json.dumps({'meses': {'2026-11': {'final_completo': False, 'dias_preliminar': 3}}}))
        fx.run()
        candidate = json.loads(fx.candidate.read_text())
        self.assertTrue(candidate['record']['preliminar'])
        self.assertTrue(candidate['record']['parcial'])
        self.assertEqual(candidate['record']['dias_observados'], 3)
        self.assertEqual(candidate['record']['dias_no_mes'], 30)
        self.assertTrue(all('/prelim/sat/' in url for url, _ in fx.requests))

    def test_final_month_skipped_prelim_not_relabelled(self):
        report = {'meses': {'2026-10': {'final_completo': False, 'dias_preliminar': 31}}}
        data = {'2026-10': {'colecao': 'CHIRPS-v3.0-sat-official', 'preliminar': True,
                            'parcial': False, 'dias_observados': 31}}
        self.assertIsNone(process.choose_target(report, data))
        report['meses']['2026-10']['final_completo'] = True
        self.assertEqual(process.choose_target(report, data), ('2026-10', 'final', 31))

    def test_audit_expired_cooldown_allows_normal_path(self):
        fx = Fixture(self)
        cp.defer_origin(fx.state, '60', 429, fx.clock.now())
        fx.clock.tomorrow()
        with patch.object(audit, 'audit', side_effect=RuntimeError('Normal audit reached')) as call:
            with self.assertRaises(SystemExit):
                audit.main()
            call.assert_called_once()

    def test_audit_respects_origin_cooldown_without_request(self):
        fx = Fixture(self)
        cp.defer_origin(fx.state, '86400', 429, fx.clock.now())
        original = fx.status.read_bytes()
        with patch.object(audit, 'audit', side_effect=AssertionError('Must not request')):
            audit.main()
        self.assertEqual(fx.status.read_bytes(), original)


class PublicationTests(OfflineCase):
    def test_publisher_independently_blocks_version_and_coverage_regression(self):
        final = {'colecao': 'CHIRPS-v3.0-sat-official', 'preliminar': False, 'parcial': False, 'dias_observados': 31}
        prelim = {**final, 'preliminar': True}
        self.assertTrue(publish.would_regress(final, prelim))
        self.assertTrue(publish.would_regress(prelim, {**prelim, 'dias_observados': 20, 'parcial': True}))
        self.assertFalse(publish.would_regress(prelim, final))

    def test_persist_partial_checkpoint_without_mutating_published_bytes(self):
        fx = Fixture(self)
        fx.init_git()
        fx.run()
        fx.publish()
        self.assertEqual(fx.months.read_bytes(), fx.original_bytes)
        names = fx.git('ls-tree', '-r', '--name-only', 'origin/main')
        self.assertIn('.state/chirps-v3/work-', names)
        self.assertNotIn('.work/', names)

    def test_complete_candidate_publishes_only_expected_month(self):
        fx = Fixture(self)
        fx.init_git()
        fx.finish()
        expected = json.loads(fx.candidate.read_text())['record']
        fx.publish()
        new = json.loads(fx.months.read_text())
        self.assertEqual(new['2026-08'], expected)
        self.assertEqual(new['2026-10'], fx.data['2026-10'])
        self.assertEqual(new['_meta']['retained'], 'unchanged')
        self.assertEqual(len((fx.root/'dados/mensal/2026-08.csv').read_text().splitlines()), 143)

    def test_checkpoint_only_ignores_even_complete_candidate(self):
        fx = Fixture(self)
        fx.init_git()
        fx.finish()
        fx.publish(checkpoint_only=True)
        self.assertEqual(fx.months.read_bytes(), fx.original_bytes)

    def test_remote_newer_version_never_overwritten(self):
        fx = Fixture(self)
        fx.init_git()
        fx.finish()
        other = fx.base / 'other'
        fx.git('clone', str(fx.remote), str(other), cwd=fx.base)
        fx.git('config', 'user.name', 'Other', cwd=other)
        fx.git('config', 'user.email', 'other@example.invalid', cwd=other)
        updated = copy.deepcopy(fx.data)
        updated['2026-08'] = {'colecao': 'CHIRPS-v3.0-sat-official', 'preliminar': False, 'v': {'5100000': 777}}
        (other/'dados/meses.json').write_text(json.dumps(updated))
        fx.git('add', 'dados/meses.json', cwd=other)
        fx.git('commit', '-m', 'Concurrent data update', cwd=other)
        fx.git('push', cwd=other)
        fx.publish()
        self.assertEqual(json.loads(fx.months.read_text())['2026-08'], updated['2026-08'])

    def test_remote_geometry_change_blocks_candidate(self):
        fx = Fixture(self)
        fx.init_git()
        fx.finish()
        other = fx.base / 'other'
        fx.git('clone', str(fx.remote), str(other), cwd=fx.base)
        fx.git('config', 'user.name', 'Other', cwd=other)
        fx.git('config', 'user.email', 'other@example.invalid', cwd=other)
        (other/'dados/municipios_mt.geojson').write_text('{"changed": true}')
        fx.git('add', 'dados/municipios_mt.geojson', cwd=other)
        fx.git('commit', '-m', 'Concurrent geometry update', cwd=other)
        fx.git('push', cwd=other)
        fx.publish()
        self.assertEqual(fx.months.read_bytes(), fx.original_bytes)
        self.assertIn('.state/chirps-v3/work-', fx.git('ls-tree', '-r', '--name-only', 'origin/main'))

    def test_new_checkout_resumes_persisted_checkpoint(self):
        fx = Fixture(self)
        fx.init_git()
        fx.run()
        fx.publish()
        fresh = fx.base / 'fresh'
        fx.git('clone', str(fx.remote), str(fresh), cwd=fx.base)
        fx.clock.tomorrow()
        with patch.object(process, 'ROOT', fresh), patch.object(process, 'STATE', fresh/'.state/chirps-v3'), \
             patch.object(process, 'GEO', fresh/'dados/municipios_mt.geojson'), \
             patch.object(process, 'MONTHS', fresh/'dados/meses.json'), \
             patch.object(process, 'STATUS', fresh/'dados/status_chirps.json'), \
             patch.object(process, 'CANDIDATE', fresh/'.work/chirps-v3-result.json'):
            process.main()
        self.assertEqual(len(fx.requests), 10)
        self.assertTrue(fx.requests[5][0].endswith('.06.tif'))

    def test_changed_candidate_values_rejected(self):
        fx = Fixture(self)
        fx.finish()
        result = json.loads(fx.candidate.read_text())
        result['record']['v'][CODES[0]] += 1
        states = {p.name: json.loads(p.read_text()) for p in fx.state.glob('*.json')}
        with self.assertRaises(ValueError):
            publish.validate_candidate(result, states)

    def test_remote_progress_merged_without_regression(self):
        fx = Fixture(self)
        fx.run()
        older = fx.checkpoint()
        fx.clock.tomorrow()
        fx.run()
        newer = fx.checkpoint()
        name = cp.checkpoint_path(fx.state, older['context']).name
        self.assertEqual(len(cp.merge_state(older, newer, name)['days']), 10)


if __name__ == '__main__':
    unittest.main()
