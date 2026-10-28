"""Bounded chapter-boundary JSON contract and atomic two-generation storage.

No engine imports, object restoration, client projections or executable records.
Checksums detect corruption; they are not authentication against a file editor.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from app.coop.campaign import ID, OWNERS, PARTIES, FACTIONS

FORMAT = 'coop-chapter-checkpoint/1'
MAX_BYTES = 1048576
MAX_UID = 1000000000  # Leave room for native chapter-local allocations.
STATS = ('HP', 'STR', 'MAG', 'SKL', 'SPD', 'LCK', 'DEF', 'RES', 'CON', 'MOV')
WEAPONS = ('Sword', 'Lance', 'Axe', 'Bow', 'Staff', 'Light', 'Anima', 'Dark', 'Default')
ITEMS = {'Iron_Axe': 45, 'Heal': 30, 'Mend': 20, 'Hand_Axe': 20, 'Vulnerary': 3}
SKILLS = ('Strength_Plus2', 'Strength_Plus5', 'Resistance_Plus5', 'Defense_Plus5',
          'Speed_Plus5', 'Skill_Plus5', 'Luck_Plus5', 'Canto')
RECORDS = {
    'kills': ('killer', 'killee'), 'death': ('killer', 'killee'),
    'damage': ('dealer', 'receiver', 'item_nid', 'over_damage', 'damage', 'kind'),
    'healing': ('dealer', 'receiver', 'item_nid', 'over_damage', 'damage', 'kind'),
    'item_use': ('user', 'item_nid'), 'steal': ('stealer', 'stealee', 'item_nid'),
    'combat_results': ('attacker', 'defender', 'result'), 'turns_taken': (),
    'levels': ('unit_nid', 'num', 'klass'), 'exp': ('unit_nid', 'num', 'klass'),
    'money': ('party_nid', 'num')}


class CheckpointError(ValueError):
    pass


def check(condition, reason):
    if not condition:
        raise CheckpointError(reason)


def exact(value, keys):
    check(type(value) is dict and set(value) == set(keys), 'unexpected or missing fields')


def number(value, low=0, high=10000):
    check(type(value) is int and low <= value <= high, 'integer outside supported range')


def text_value(value, limit=128):
    check(type(value) is str and 0 < len(value) <= limit, 'invalid bounded string')


def sequence(value, maximum):
    check(type(value) is list and len(value) <= maximum, 'invalid bounded list')


def scalar_map(value):
    check(type(value) is dict and len(value) <= 32, 'unsupported personal fields')
    for key, item in value.items():
        text_value(key, 64)
        check(item is None or type(item) in (bool, int, str), 'unsupported personal field type')
        if type(item) is int:
            number(item, -1000000, 1000000)
        elif type(item) is str:
            check(len(item) <= 256, 'personal field too long')


def decimal_value(value, low=0, high=10000):
    check(type(value) is str and len(value) <= 64 and
          re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]{1,3})?', value) is not None,
          'invalid decimal encoding')
    try:
        amount = Decimal(value)
        check(amount.is_finite() and low <= amount <= high, 'decimal outside range')
        native = float(value) if any(c in value for c in '.eE') else int(value)
        check(str(native) == value, 'noncanonical native decimal')
    except InvalidOperation as exc:
        raise CheckpointError('invalid decimal') from exc


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def compatibility():
    """Exact rules compatibility, normalized across Windows/Unix source endings."""
    root = Path(__file__).resolve().parents[2]
    paths = sorted(set((root / 'app/engine').rglob('*.py')) |
                   {root / 'app/coop' / name for name in
                    ('campaign.py', 'simulation.py', 'checkpoint.py', 'checkpoint_native.py', 'preparation.py')} |
                   set((root / 'default.ltproj/game_data').rglob('*.json')))
    hasher = hashlib.sha256(FORMAT.encode())
    for path in paths:
        data = path.read_text(encoding='utf-8-sig').replace('\r\n', '\n')
        if path.suffix == '.json':
            data = canonical(json.loads(data)).decode('utf-8')
        hasher.update(path.relative_to(root).as_posix().encode() + b'\0' + data.encode('utf-8'))
    return hasher.hexdigest()


def validate(payload, manifest=None):
    exact(payload, ('format', 'compatibility', 'campaign', 'boundary', 'completed', 'next',
                    'mode', 'rng', 'next_uids', 'units', 'items', 'skills', 'parties',
                    'events', 'records'))
    check(payload['format'] == FORMAT, 'unsupported checkpoint version')
    check(payload['compatibility'] == (manifest or compatibility()), 'incompatible rules manifest')
    check(payload['campaign'] == ID and payload['boundary'] == 'alliance/intermission' and
          payload['completed'] == ['alliance'] and payload['next'] == 'holding', 'unsupported chapter boundary')
    exact(payload['mode'], ('nid', 'permadeath', 'growths', 'rng_mode'))
    check(payload['mode']['nid'] == 'Normal' and payload['mode']['permadeath'] is True and
          payload['mode']['growths'] in ('Fixed', 'Random', 'Dynamic') and
          payload['mode']['rng_mode'] == 'True Hit', 'unsupported campaign mode')
    exact(payload['rng'], ('seed', 'combat', 'growth', 'other'))
    number(payload['rng']['seed'], 0, 1023)
    for key in ('combat', 'growth', 'other'):
        number(payload['rng'][key], 0, 2147483647)
    exact(payload['next_uids'], ('item', 'skill'))
    for uid in payload['next_uids'].values():
        number(uid, 100, MAX_UID)
    sequence(payload['units'], 4)
    check(len(payload['units']) == 4, 'incomplete permanent roster')
    unit_ids, item_refs, skill_refs = set(), [], []
    for unit in payload['units']:
        exact(unit, ('id', 'owner', 'team', 'party', 'faction', 'class', 'level', 'exp',
                     'stats', 'growths', 'growth_points', 'wexp', 'caps', 'hp', 'mana', 'fatigue',
                     'guard', 'dead', 'items', 'skills', 'equipped', 'fields', 'tags'))
        text_value(unit['id'])
        check(unit['id'] in OWNERS and unit['id'] not in unit_ids, 'unknown or duplicate character')
        unit_ids.add(unit['id'])
        owner = OWNERS[unit['id']]
        check(unit['owner'] == owner and unit['team'] == owner and unit['party'] == PARTIES[owner]
              and unit['faction'] == FACTIONS[owner], 'invalid character ownership/party/faction')
        check(unit['class'] == ('Banner_Cleric' if 'Healer' in unit['id'] else 'Banner_Vanguard'), 'unsupported class')
        number(unit['level'], 1, 20)
        number(unit['exp'], 0, 99)
        for key, low, high in (('stats', 0, 1000), ('growths', -1000, 1000), ('caps', -1000, 1000)):
            exact(unit[key], STATS)
            for value in unit[key].values():
                number(value, low, high)
        exact(unit['growth_points'], STATS)
        exact(unit['wexp'], WEAPONS)
        for value in unit['wexp'].values():
            decimal_value(value)
        for value in unit['growth_points'].values():
            decimal_value(value, -10000, 10000)
        for key in ('hp', 'mana', 'fatigue', 'guard'):
            number(unit[key])
        check(unit['hp'] <= unit['stats']['HP'], 'HP exceeds supported maximum')
        check(type(unit['dead']) is bool, 'invalid death flag')
        sequence(unit['items'], 20)
        sequence(unit['skills'], 32)
        for uid in unit['items'] + unit['skills']:
            number(uid, 0, 2147483646)
        item_refs.extend(unit['items'])
        skill_refs.extend(unit['skills'])
        if unit['equipped'] is not None:
            number(unit['equipped'], 0, 2147483646)
            check(unit['equipped'] in unit['items'], 'equipped item not owned')
        scalar_map(unit['fields'])
        sequence(unit['tags'], 0)  # This original roster has no mutable tag mechanics.
    check(unit_ids == set(OWNERS), 'invalid roster')
    check(all(any(u['owner'] == team and not u['dead'] for u in payload['units']) for team in PARTIES), 'eliminated army is not a continuation boundary')
    sequence(payload['parties'], 2)
    check(len(payload['parties']) == 2, 'incomplete parties')
    party_ids = set()
    for party in payload['parties']:
        exact(party, ('id', 'leader', 'money', 'bexp', 'convoy', 'order'))
        text_value(party['id'])
        check(party['id'] in PARTIES.values() and party['id'] not in party_ids, 'invalid party')
        party_ids.add(party['id'])
        check(party['leader'] in OWNERS and PARTIES[OWNERS[party['leader']]] == party['id'], 'invalid party leader')
        number(party['money'], 0, 100000000)
        number(party['bexp'], 0, 100000000)
        sequence(party['convoy'], 20)
        sequence(party['order'], 4)
        for nid in party['order']:
            text_value(nid)
            check(nid in OWNERS and PARTIES[OWNERS[nid]] == party['id'], 'foreign deployment order')
        check(len(set(party['order'])) == len(party['order']), 'duplicate deployment entry')
        for uid in party['convoy']:
            number(uid, 0, 2147483646)
        item_refs.extend(party['convoy'])
    sequence(payload['items'], 80)
    item_ids = set()
    for item in payload['items']:
        exact(item, ('uid', 'nid', 'owner', 'droppable', 'data'))
        number(item['uid'], 0, 2147483646)
        text_value(item['nid'])
        check(item['uid'] not in item_ids and item['nid'] in ITEMS, 'unknown or duplicate item')
        item_ids.add(item['uid'])
        check(item['owner'] is None or type(item['owner']) is str and item['owner'] in OWNERS, 'unknown item owner')
        check(type(item['droppable']) is bool, 'invalid droppable flag')
        exact(item['data'], ('uses', 'starting_uses'))
        number(item['data']['starting_uses'])
        check(item['data']['starting_uses'] == ITEMS[item['nid']], 'unsupported item maximum uses')
        number(item['data']['uses'], 0, ITEMS[item['nid']])
        owners = [u['id'] for u in payload['units'] if item['uid'] in u['items']]
        check(owners == ([item['owner']] if item['owner'] else []), 'item owner/reference mismatch')
    check(len(set(item_refs)) == len(item_refs) and set(item_refs) == item_ids, 'missing/duplicate/orphan item reference')
    check(payload['next_uids']['item'] > max(item_ids, default=-1), 'item UID generator would reuse identities')
    by_uid = {item['uid']: item for item in payload['items']}
    for unit in payload['units']:
        if unit['equipped'] is not None:
            item = by_uid[unit['equipped']]
            check(item['nid'] in ('Iron_Axe', 'Hand_Axe') and unit['class'] == 'Banner_Vanguard' and
                  Decimal(unit['wexp']['Axe']) >= 1 and item['data']['uses'] > 0,
                  'invalid native equipment eligibility')
        check(unit['dead'] or unit['hp'] > 0, 'living character has zero HP')
    sequence(payload['skills'], 128)
    skill_ids = set()
    for skill in payload['skills']:
        exact(skill, ('uid', 'nid', 'owner', 'data', 'source', 'source_type'))
        number(skill['uid'], 0, 2147483646)
        text_value(skill['nid'])
        check(skill['nid'] in SKILLS and skill['uid'] not in skill_ids, 'unknown or duplicate persistent skill')
        skill_ids.add(skill['uid'])
        text_value(skill['owner'])
        check(skill['owner'] in OWNERS, 'unknown skill owner')
        exact(skill['data'], ())
        check(skill['source_type'] in ('default', 'personal', 'klass'), 'unsupported skill source')
        check(skill['source'] is None or skill['source'] in (*OWNERS, 'Banner_Cleric', 'Banner_Vanguard'), 'unknown skill source reference')
        owner = next(u for u in payload['units'] if u['id'] == skill['owner'])
        check(skill['source_type'] != 'personal' or skill['source'] == owner['id'], 'foreign personal skill source')
        check(skill['source_type'] != 'klass' or skill['source'] == owner['class'], 'foreign class skill source')
        check([u['id'] for u in payload['units'] if skill['uid'] in u['skills']] == [skill['owner']], 'skill ownership mismatch')
    check(len(set(skill_refs)) == len(skill_refs) and set(skill_refs) == skill_ids, 'missing/duplicate/orphan skill reference')
    check(payload['next_uids']['skill'] > max(skill_ids, default=-1), 'skill UID generator would reuse identities')
    sequence(payload['events'], 32)
    for event in payload['events']:
        check(event in ['alliance Campaign victory ' + t for t in ('combat_end', 'unit_wait', 'phase_change')], 'unsupported completion event')
    check(len(set(payload['events'])) == len(payload['events']), 'duplicate completion event')
    exact(payload['records'], RECORDS)
    for kind, records in payload['records'].items():
        sequence(records, 2048)
        for record in records:
            exact(record, ('turn', 'level_nid') + RECORDS[kind])
            number(record['turn'], 1, 10000)
            check(record['level_nid'] == 'alliance', 'unsupported record chapter')
            for key, value in record.items():
                if key in ('turn', 'num', 'damage', 'over_damage'):
                    number(value, -100000000, 100000000)
                else:
                    text_value(value)
                if key in ('killer', 'killee', 'dealer', 'receiver', 'user', 'stealer', 'stealee', 'attacker', 'defender', 'unit_nid'):
                    check(value in (*OWNERS, 'alliance_Red_1', 'alliance_Red_2', 'alliance_Red_3'), 'unknown record unit reference')
                elif key == 'item_nid':
                    check(value in ITEMS, 'unknown record item')
                elif key == 'klass':
                    check(value in ('Banner_Cleric', 'Banner_Vanguard'), 'unknown record class')
                elif key == 'party_nid':
                    check(value in PARTIES.values(), 'unknown record party')
                elif key in ('kind', 'result'):
                    check(value in ('hit', 'miss', 'crit'), 'unknown combat record outcome')
    check(len(canonical(payload)) <= MAX_BYTES - 256, 'checkpoint too large')
    return payload


def unpack(raw, manifest=None):
    check(len(raw) <= MAX_BYTES, 'checkpoint exceeds byte limit')
    def pairs(entries):
        result = {}
        for key, value in entries:
            check(key not in result, 'duplicate JSON field')
            result[key] = value
        return result
    def invalid(value):
        raise CheckpointError('floating/nonfinite JSON number is unsupported')
    try:
        envelope = json.loads(raw, object_pairs_hook=pairs, parse_float=invalid, parse_constant=invalid)
        exact(envelope, ('generation', 'checksum', 'payload'))
        number(envelope['generation'], 1, 2147483647)
        check(type(envelope['checksum']) is str and envelope['checksum'] ==
              hashlib.sha256(canonical({'generation': envelope['generation'], 'payload': envelope['payload']})).hexdigest(), 'checkpoint checksum mismatch')
        validate(envelope['payload'], manifest)
        return envelope
    except (UnicodeError, ValueError, RecursionError, TypeError) as exc:
        raise CheckpointError(str(exc)) from exc


class Store:
    def __init__(self, folder):
        self.folder = Path(folder).resolve()
        self.manifest = compatibility()

    def load(self):
        diagnostics = []
        for name in ('current.json', 'previous.json'):
            try:
                with (self.folder / name).open('rb') as stream:
                    envelope = unpack(stream.read(MAX_BYTES + 1), self.manifest)
                return envelope, diagnostics
            except (OSError, CheckpointError) as exc:
                diagnostics.append(name + ': ' + str(exc))
        raise CheckpointError('No valid checkpoint generation. ' + '; '.join(diagnostics))

    def _replace(self, destination, raw):
        pending = self.folder / ('.pending-' + uuid.uuid4().hex + '.tmp')
        try:
            with pending.open('xb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pending, self.folder / destination)
        finally:
            pending.unlink(missing_ok=True)

    def save(self, payload):
        validate(payload, self.manifest)
        self.folder.mkdir(parents=True, exist_ok=True)
        try:
            old, _ = self.load()
        except CheckpointError:
            check(not any((self.folder / n).exists() for n in ('current.json', 'previous.json')),
                  'Existing generations are invalid; choose a new checkpoint directory')
            old = None
        generation = old['generation'] + 1 if old else 1
        number(generation, 1, 2147483647)
        content = {'generation': generation, 'payload': deepcopy(payload)}
        raw = canonical({**content, 'checksum': hashlib.sha256(canonical(content)).hexdigest()})
        if old:
            # Never rotate a corrupt current over the previous-good generation.
            self._replace('previous.json', canonical(old))
        self._replace('current.json', raw)
        # A first successful save also keeps a verified mirror for corruption
        # recovery. A power loss before this copy still leaves committed current.
        if old is None:
            self._replace('previous.json', raw)
        return generation
