"""Version 1, bounded JSON only. No engine imports or executable serialization."""
import hashlib
import json
import re

VERSION = 1
MAX_FRAME = 262144
TEAMS = ('player', 'other')


class ProtocolError(ValueError):
    pass


def require(condition, reason='malformed'):
    if not condition:
        raise ProtocolError(reason)


def fields(value, expected):
    require(type(value) is dict and set(value) == set(expected))


def integer(value, lo=0, hi=2147483647):
    require(type(value) is int and lo <= value <= hi)


def string(value, maximum=128):
    require(type(value) is str and 0 < len(value) <= maximum)


def position(value, width=64, height=64):
    require(type(value) is list and len(value) == 2)
    integer(value[0], 0, width - 1)
    integer(value[1], 0, height - 1)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def encode(value):
    data = canonical(value) + b'\n'
    require(len(data) <= MAX_FRAME, 'frame_too_large')
    return data


def decode(data):
    require(len(data) <= MAX_FRAME and data.endswith(b'\n'), 'frame_too_large_or_truncated')

    def pairs(entries):
        result = {}
        for key, value in entries:
            require(key not in result, 'duplicate_json_key')
            result[key] = value
        return result

    def invalid_constant(value):
        raise ProtocolError('non_finite_json')

    try:
        value = json.loads(data, object_pairs_hook=pairs, parse_constant=invalid_constant,
                           parse_float=invalid_constant)
        require(type(value) is dict)
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ProtocolError('invalid_json') from exc


def validate_request(value):
    require(type(value) is dict and value.get('v') == VERSION and type(value.get('v')) is int,
            'protocol_version')
    kind = value.get('type')
    if kind == 'hello':
        fields(value, ('v', 'type', 'token'))
        string(value['token'], 256)
    elif kind == 'pong':
        fields(value, ('v', 'type', 'nonce'))
        integer(value['nonce'])
    elif kind == 'sync':
        fields(value, ('v', 'type'))
    elif kind == 'command':
        action = value.get('action')
        extra = {'move': ('unit', 'pos'), 'attack': ('unit', 'item', 'target'),
                 'wait': ('unit',), 'end_phase': ()}
        require(type(action) is str and action in extra, 'unknown_action')
        fields(value, ('v', 'type', 'session', 'id', 'revision', 'phase', 'digest', 'action') + extra[action])
        for key in ('session', 'id', 'phase', 'digest'):
            string(value[key])
        require(re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value['id']) is not None)
        require(re.fullmatch('[0-9a-f]{64}', value['digest']) is not None)
        integer(value['revision'])
        if 'unit' in value:
            string(value['unit'])
        if 'pos' in value:
            position(value['pos'])
        if 'item' in value:
            integer(value['item'])
            string(value['target'])
    else:
        raise ProtocolError('unknown_message')
    return value


def validate_state(value):
    fields(value, ('scenario', 'ruleset', 'width', 'height', 'terrain', 'phase',
                   'turn', 'status', 'objective', 'rng', 'units'))
    for key in ('scenario', 'ruleset', 'phase', 'objective'):
        string(value[key], 512)
    integer(value['width'], 1, 64)
    integer(value['height'], 1, 64)
    integer(value['turn'], 1)
    require(value['phase'] in ('player', 'other', 'enemy', 'enemy2'))
    require(value['status'] in ('playing', 'victory', 'defeat', 'fault'))
    fields(value['rng'], ('seed', 'combat', 'growth', 'other'))
    for number in value['rng'].values():
        integer(number)
    require(type(value['terrain']) is list and len(value['terrain']) == value['height'])
    for row in value['terrain']:
        require(type(row) is list and len(row) == value['width'])
        require(all(t in ('plain', 'forest', 'wall') for t in row))
    require(type(value['units']) is list and len(value['units']) <= 100)
    ids, item_ids, occupied = set(), set(), set()
    for unit in value['units']:
        fields(unit, ('id', 'name', 'team', 'pos', 'hp', 'max_hp', 'dead', 'finished',
                      'moved', 'attacked', 'movement', 'level', 'exp', 'stats',
                      'inventory', 'moves', 'attacks'))
        string(unit['id'])
        string(unit['name'])
        require(unit['id'] not in ids)
        ids.add(unit['id'])
        require(unit['team'] in ('player', 'other', 'enemy', 'enemy2'))
        if unit['pos'] is not None:
            position(unit['pos'], value['width'], value['height'])
            pos = tuple(unit['pos'])
            require(pos not in occupied)
            occupied.add(pos)
        for key in ('hp', 'max_hp', 'movement', 'level', 'exp'):
            integer(unit[key], 0, 10000)
        require(unit['hp'] <= unit['max_hp'])
        for key in ('dead', 'finished', 'moved', 'attacked'):
            require(type(unit[key]) is bool)
        require(type(unit['stats']) is dict and len(unit['stats']) <= 64)
        for key, number in unit['stats'].items():
            string(key)
            integer(number, -10000, 10000)
        require(type(unit['inventory']) is list and len(unit['inventory']) <= 20)
        for item in unit['inventory']:
            fields(item, ('uid', 'nid', 'name', 'uses'))
            integer(item['uid'])
            require(item['uid'] not in item_ids)
            item_ids.add(item['uid'])
            string(item['nid'])
            string(item['name'])
            if item['uses'] is not None:
                integer(item['uses'], 0, 10000)
        require(type(unit['moves']) is list and len(unit['moves']) <= 4096)
        for pos in unit['moves']:
            position(pos, value['width'], value['height'])
        require(type(unit['attacks']) is list and len(unit['attacks']) <= 2000)
        for attack in unit['attacks']:
            fields(attack, ('item', 'target'))
            integer(attack['item'])
            string(attack['target'])
            require(attack['item'] in {i['uid'] for i in unit['inventory']})
    for unit in value['units']:
        require(all(a['target'] in ids for a in unit['attacks']))
    return value


def validate_packet(packet):
    fields(packet, ('v', 'type', 'session', 'revision', 'digest', 'state', 'result'))
    require(type(packet['v']) is int and packet['v'] == VERSION, 'protocol_version')
    require(packet['type'] == 'state')
    string(packet['session'])
    integer(packet['revision'])
    validate_state(packet['state'])
    require(packet['digest'] == digest(packet['state']), 'digest_mismatch')
    if packet['result'] is not None:
        fields(packet['result'], ('id', 'team', 'action', 'summary'))
        for text in packet['result'].values():
            string(text, 4096)
        require(packet['result']['team'] in TEAMS)
    return packet
