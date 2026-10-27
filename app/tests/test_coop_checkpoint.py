"""Checkpoint schemas, actual Windows file failures, and fresh-process recovery."""
from copy import deepcopy
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from app.coop import checkpoint as dto
from app.coop.checkpoint_native import capture, validate_catalog
from app.coop.protocol import ProtocolError, VERSION, validate_request
from app.coop.server import Session
from app.coop.simulation import Simulation
from app.tests.test_network_coop import command
from utilities.campaign_playtest import choose

_fixture = None


def boundary(folder=None, **options):
    sim = Simulation(scenario='campaign', checkpoint_dir=folder, **options)
    session = Session(sim)
    for index in range(120):
        state = session.packet['state']
        if state['status'] != 'playing':
            assert state['status'] == 'intermission'
            return sim, session
        kind, args = choose(state, state['phase'])
        session.command(state['phase'], command(session.packet, kind, 'cp_'+str(index), **args), ('player', 'other'))
    sim.close()
    raise AssertionError('No legitimate chapter completion')


def fixture():
    global _fixture
    if _fixture is None:
        sim, _ = boundary()
        try:
            _fixture = capture(sim)
        finally:
            sim.close()
    return deepcopy(_fixture)


def envelope(payload, generation=1):
    body = {'generation': generation, 'payload': payload}
    return dto.canonical({**body, 'checksum': hashlib.sha256(dto.canonical(body)).hexdigest()})


def fresh_python(script, *args):
    return subprocess.run([sys.executable, '-c', script, *map(str, args)],
        cwd=Path(__file__).resolve().parents[2], capture_output=True, timeout=40,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)


class CheckpointSchemaTests(unittest.TestCase):
    def test_separate_native_contract_round_trip_and_no_display_state(self):
        payload = fixture()
        self.assertEqual(dto.unpack(envelope(payload))['payload'], payload)
        self.assertNotIn('terrain', payload)
        self.assertNotIn('digest', payload)
        self.assertNotIn('token', dto.canonical(payload).decode())
        self.assertEqual(payload['completed'], ['alliance'])
        self.assertEqual(payload['next'], 'holding')

    def test_ownership_identity_and_reference_rejections(self):
        changes = (
            lambda p: p['units'].append(deepcopy(p['units'][0])),
            lambda p: p['units'][0].update(owner='other'),
            lambda p: p['units'][0].update(party='Green_Banner'),
            lambda p: p['units'][0].update(id='Eirika'),
            lambda p: p['units'][0].update(equipped=99999),
            lambda p: p['units'][1].update(equipped=101),
            lambda p: p['units'][0]['items'].append(p['units'][1]['items'][0]),
            lambda p: p['items'][0].update(owner='Green_Captain'),
            lambda p: p['items'][0].update(uid=p['items'][1]['uid']),
            lambda p: p['parties'][0]['convoy'].append(p['items'][0]['uid']),
            lambda p: p['parties'][0].update(order=['Green_Captain']),
            lambda p: p['units'][0].update(skills=[99999]),
            lambda p: p['next_uids'].update(item=100),
            lambda p: p['next_uids'].update(item=2147483647))
        for mutate in changes:
            payload = fixture()
            mutate(payload)
            with self.subTest(mutate=mutate), self.assertRaises(dto.CheckpointError):
                dto.validate(payload)

    def test_numeric_bounds_versions_unknown_fields_and_components(self):
        changes = (
            lambda p: p.update(format='coop-chapter-checkpoint/999'),
            lambda p: p.update(compatibility='unknown'),
            lambda p: p.update(boundary='mid-map'),
            lambda p: p.update(next='arbitrary.ltproj'),
            lambda p: p['units'][0].update(exp=True),
            lambda p: p['units'][0].update(level=999),
            lambda p: p['units'][0]['growth_points'].update(HP='NaN'),
            lambda p: p['units'][0]['growth_points'].update(HP='1e-999'),
            lambda p: p['units'][0]['wexp'].update(Axe='Infinity'),
            lambda p: p['items'][0]['data'].update(uses=99999),
            lambda p: p['items'][0].update(components=[['event_on_hit', 'win_game']]),
            lambda p: p['records']['kills'][0].update(__class__='eval'),
            lambda p: p['records']['kills'][0].update(killee='unknown'),
            lambda p: p['events'].append('arbitrary event'),
            lambda p: p['mode'].update(permadeath=False),
            lambda p: p['rng'].update(combat=-1))
        for mutate in changes:
            payload = fixture()
            mutate(payload)
            with self.subTest(mutate=mutate), self.assertRaises(dto.CheckpointError):
                dto.unpack(envelope(payload))

    def test_json_checksum_size_duplicates_and_truncation(self):
        raw = envelope(fixture())
        for malformed in (raw[:len(raw)//2], raw.replace(b'"generation":1', b'"generation":2'),
                          b'{"generation":1,"generation":1}', b'{"x":NaN}', b'{"x":1.5}',
                          b'['*2000+b']'*2000, b'x'*(dto.MAX_BYTES+1), b'\xff'):
            with self.subTest(size=len(malformed)), self.assertRaises(dto.CheckpointError):
                dto.unpack(malformed)

    def test_native_catalog_caps_reject_before_reconstruction(self):
        payload = fixture()
        payload['units'][0]['stats']['STR'] = 999
        with self.assertRaisesRegex(dto.CheckpointError, 'native class cap'):
            validate_catalog(payload)

    def test_save_command_cannot_choose_file_or_inject_state(self):
        request = {'v': VERSION, 'type': 'command', 'session': 'test', 'id': 'save',
                   'revision': 0, 'phase': 'player', 'digest': 'a'*64, 'action': 'save_checkpoint'}
        validate_request(request)
        for fields in ({'path': 'C:/arbitrary'}, {'payload': fixture()}, {'team': 'other'}, {'event': 'win_game'}):
            with self.assertRaises(ProtocolError):
                validate_request({**request, **fields})
        with self.assertRaises(ProtocolError):
            validate_request({**request, 'v': 4})


class CheckpointStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lt-checkpoint-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.store = dto.Store(self.folder)
        self.payload = fixture()

    def test_generations_keep_previous_and_first_verified_mirror(self):
        self.assertEqual(self.store.save(self.payload), 1)
        self.assertEqual((self.folder/'current.json').read_bytes(), (self.folder/'previous.json').read_bytes())
        updated = deepcopy(self.payload)
        updated['parties'][0]['money'] = 73
        self.assertEqual(self.store.save(updated), 2)
        current, diagnostics = self.store.load()
        self.assertEqual(current['generation'], 2)
        self.assertEqual(current['payload'], updated)
        self.assertFalse(diagnostics)
        self.assertEqual(dto.unpack((self.folder/'previous.json').read_bytes())['payload'], self.payload)
        # Overflow must fail before rotating/writing either committed generation.
        largest = envelope(self.payload, 2147483647)
        (self.folder/'current.json').write_bytes(largest)
        previous = (self.folder/'previous.json').read_bytes()
        with self.assertRaises(dto.CheckpointError):
            self.store.save(updated)
        self.assertEqual((self.folder/'current.json').read_bytes(), largest)
        self.assertEqual((self.folder/'previous.json').read_bytes(), previous)

    def test_corrupt_and_truncated_current_fall_back_with_diagnostics(self):
        self.store.save(self.payload)
        for damaged in (b'{"truncated":', envelope(self.payload).replace(b'"checksum":"', b'"checksum":"bad', 1)):
            (self.folder/'current.json').write_bytes(damaged)
            loaded, diagnostics = self.store.load()
            self.assertEqual(loaded['payload'], self.payload)
            self.assertTrue(diagnostics[0].startswith('current.json:'))
        (self.folder/'previous.json').write_bytes(b'corrupt too')
        with self.assertRaisesRegex(dto.CheckpointError, 'No valid checkpoint generation'):
            self.store.load()
        with self.assertRaisesRegex(dto.CheckpointError, 'Existing generations are invalid'):
            self.store.save(self.payload)

    def test_orphan_partial_write_is_ignored(self):
        self.store.save(self.payload)
        (self.folder/'.pending-interrupted.tmp').write_bytes(b'{"generation":2,"payload":')
        self.assertEqual(self.store.load()[0]['generation'], 1)

    def test_flush_and_replace_failures_leave_a_valid_committed_generation(self):
        self.store.save(self.payload)
        updated = deepcopy(self.payload)
        updated['parties'][0]['money'] = 999
        replace = os.replace
        for destination in ('previous.json', 'current.json'):
            def fail(source, target):
                if Path(target).name == destination:
                    raise PermissionError('injected locked destination')
                replace(source, target)
            with patch('app.coop.checkpoint.os.replace', side_effect=fail), self.assertRaises(OSError):
                self.store.save(updated)
            self.assertEqual(self.store.load()[0]['payload'], self.payload)
            self.assertFalse(list(self.folder.glob('.pending-*.tmp')))
        with patch('app.coop.checkpoint.os.fsync', side_effect=OSError('injected flush failure')):
            with self.assertRaises(OSError):
                self.store.save(updated)
        self.assertEqual(self.store.load()[0]['payload'], self.payload)
        self.assertEqual(self.store.save(updated), 2)

    @unittest.skipUnless(os.name == 'nt', 'Windows sharing semantics')
    def test_actual_windows_locked_current_recovery(self):
        from ctypes import wintypes
        self.store.save(self.payload)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                           wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        create.restype = wintypes.HANDLE
        close = kernel.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        handle = create(str(self.folder/'current.json'), 0x80000000, 1, None, 3, 0, None)
        self.assertNotEqual(handle, wintypes.HANDLE(-1).value)
        try:
            with self.assertRaises(OSError):
                self.store.save(self.payload)
            self.assertEqual(self.store.load()[0]['generation'], 1)
        finally:
            close(handle)
        self.assertEqual(self.store.save(self.payload), 2)


class CheckpointNativeTests(unittest.TestCase):
    def test_random_and_dynamic_native_growth_state_recovers(self):
        for method in ('Random', 'Dynamic'):
            with self.subTest(method=method), tempfile.TemporaryDirectory(prefix='lt-growth-checkpoint-') as folder:
                producer = '''import sys
from app.tests.test_coop_checkpoint import boundary
from app.coop.checkpoint_native import capture
from app.coop.checkpoint import Store
s, _ = boundary(growth_method=sys.argv[2])
p = capture(s)
assert p['mode']['growths'] == sys.argv[2]
Store(sys.argv[1]).save(p)
s.close()
'''
                produced = fresh_python(producer, folder, method)
                self.assertEqual(produced.returncode, 0, produced.stderr.decode(errors='replace'))
                restored = fresh_python('''import sys
from app.coop.simulation import Simulation
s = Simulation(restore_dir=sys.argv[1])
assert s.game.current_mode.growths == sys.argv[2]
print('GROWTH_RESTORE_OK')
s.close()
''', folder, method)
                self.assertEqual(restored.returncode, 0, restored.stdout.decode(errors='replace') + restored.stderr.decode(errors='replace'))
                self.assertIn(b'NATIVE_CHECKPOINT_VERIFIED', restored.stdout)
                self.assertIn(b'GROWTH_RESTORE_OK', restored.stdout)

    def test_dead_characters_skills_fields_parties_and_instances_across_fresh_process(self):
        from app.engine import action, item_funcs
        from app.engine.source_type import SourceType
        sim, _ = boundary()
        self.addCleanup(sim.close)
        unit = sim.game.get_unit('Blue_Captain')
        action.do(action.AddSkill(unit, 'Strength_Plus2', source=unit.nid, source_type=SourceType.PERSONAL))
        unit.set_field('oath', 'River Wardens')
        unit.set_fatigue(3)
        unit.set_mana(7)
        action.do(action.Die(sim.game.get_unit('Green_Healer')))
        party = sim.game.parties['Blue_Banner']
        party.money, party.bexp = 73, 11
        spare = item_funcs.create_item(None, 'Mend')
        spare.data['uses'] = 9
        sim.game.register_item(spare)
        party.convoy.append(spare)
        with tempfile.TemporaryDirectory(prefix='lt-native-checkpoint-') as folder:
            dto.Store(folder).save(capture(sim))
            sim.close()
            script = '''import sys
from app.coop.simulation import Simulation
s = Simulation(restore_dir=sys.argv[1])
u = s.game.get_unit('Blue_Captain')
assert u.get_stat('STR') == u.stats['STR'] + 2
assert u.get_field('oath') == 'River Wardens' and u.get_mana() == 7
fallen = s.game.get_unit('Green_Healer')
assert fallen.dead and fallen.position is None and fallen.items[0].uid == 103
p = s.game.parties['Blue_Banner']
assert p.money == 73 and p.bexp == 11 and p.convoy[0].data['uses'] == 9
assert len(s.game.unit_registry) == 4 and len(s.game.item_registry) == 5
print('NATIVE_EXTRA_STATE_OK')
s.close()
'''
            result = fresh_python(script, folder)
            self.assertEqual(result.returncode, 0, result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace'))
            self.assertIn(b'NATIVE_CHECKPOINT_VERIFIED', result.stdout)
            self.assertIn(b'NATIVE_EXTRA_STATE_OK', result.stdout)

    def test_restore_refused_inside_previously_used_process(self):
        fixture()
        with self.assertRaisesRegex(dto.CheckpointError, 'fresh host process'):
            Simulation(restore_dir='never-loaded')

    def test_save_error_blocks_ready_until_explicit_successful_retry(self):
        with tempfile.TemporaryDirectory(prefix='lt-retry-checkpoint-') as folder:
            with patch('app.coop.checkpoint.Store.save', side_effect=OSError('injected disk error')):
                sim, session = boundary(folder)
            self.addCleanup(sim.close)
            self.assertEqual(session.packet['state']['campaign']['checkpoint']['status'], 'error')
            self.assertFalse(sim.fault)
            before = deepcopy(session.packet)
            with self.assertRaisesRegex(ProtocolError, 'checkpoint_required'):
                session.command('player', command(before, 'ready', 'ready_error'), ('player', 'other'))
            self.assertEqual(session.packet, before)
            session.command('player', command(before, 'save_checkpoint', 'retry_save'), ('player', 'other'))
            self.assertEqual(session.packet['state']['campaign']['checkpoint']['status'], 'saved')
            self.assertEqual(dto.Store(folder).load()[0]['generation'], 1)

    def test_mid_map_save_and_unsupported_skill_state_reject_without_rng_mutation(self):
        sim = Simulation(scenario='campaign')
        self.addCleanup(sim.close)
        session = Session(sim)
        before = deepcopy(session.packet)
        with self.assertRaisesRegex(ProtocolError, 'not_intermission'):
            session.command('player', command(before, 'save_checkpoint'), ('player', 'other'))
        self.assertEqual(session.packet, before)
        sim.close()
        sim, _ = boundary()
        self.addCleanup(sim.close)
        from app.engine import action
        action.do(action.AddSkill(sim.game.get_unit('Blue_Captain'), 'Strength_Plus2'))
        sim.game.get_unit('Blue_Captain').get_skill('Strength_Plus2').data['unsupported'] = 1
        with self.assertRaises(dto.CheckpointError):
            capture(sim)

    def test_invalid_restore_never_listens_or_emits_invitations(self):
        with tempfile.TemporaryDirectory(prefix='lt-invalid-checkpoint-') as folder:
            root = Path(folder)
            dto.Store(root).save(fixture())
            (root/'current.json').write_bytes(b'bad')
            (root/'previous.json').write_bytes(b'truncated{')
            result = subprocess.run([sys.executable, 'run_network.py', 'host', '--restore', folder,
                '--session-dir', str(root/'credentials'), '--port', '0'], capture_output=True, timeout=15,
                cwd=Path(__file__).resolve().parents[2],
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(b'HOST_READY', result.stdout)
            self.assertIn(b'No valid checkpoint generation', result.stderr)
            self.assertFalse((root/'credentials').exists())


class CheckpointProcessTests(unittest.TestCase):
    def smoke(self, recovery):
        from utilities.smoke_checkpoint import run_smoke
        with tempfile.TemporaryDirectory(prefix='lt-restart-test-') as folder:
            result = run_smoke(folder, recovery=recovery)
            self.assertEqual(result['snapshots_compared'], [19, 21])
            self.assertEqual(result['final_revision'], 20)

    def test_complete_shutdown_restore_rejoin_and_chapter_two_victory(self):
        self.smoke('none')

    def test_corrupt_current_recovers_and_finishes_campaign(self):
        self.smoke('corrupt')

    def test_truncated_current_recovers_and_finishes_campaign(self):
        self.smoke('truncated')

    def test_abrupt_writer_process_exit_recovers_and_finishes_campaign(self):
        self.smoke('interrupted')
