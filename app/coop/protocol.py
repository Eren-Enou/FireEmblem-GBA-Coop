"""Version 7, bounded JSON only. No engine imports or executable serialization."""
import hashlib
import json
import math
import re

VERSION = 7
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
                 'heal': ('unit', 'item', 'target'), 'use': ('unit', 'item', 'target'),
                 'equip': ('unit', 'item'), 'deposit': ('unit', 'item'), 'withdraw': ('unit', 'item'), 'wait': ('unit',), 'end_phase': (), 'ready': (), 'save_checkpoint': ()}
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
        if 'target' in value:
            string(value['target'])
    else:
        raise ProtocolError('unknown_message')
    return value


def validate_state(value):
    fields(value, ('campaign', 'scenario', 'ruleset', 'width', 'height', 'terrain', 'phase',
                   'turn', 'status', 'objective', 'rng', 'units', 'tactics'))
    for key in ('scenario', 'ruleset', 'phase', 'objective'):
        string(value[key], 512)
    integer(value['width'], 1, 64)
    integer(value['height'], 1, 64)
    integer(value['turn'], 1)
    require(value['phase'] in ('player', 'other', 'enemy', 'enemy2'))
    require(value['status'] in ('playing', 'intermission', 'victory', 'defeat', 'fault'))
    campaign = value['campaign']
    if campaign is not None:
        fields(campaign, ('id', 'chapter', 'title', 'next_title', 'completed', 'ready', 'checkpoint', 'convoys'))
        fields(campaign['checkpoint'], ('status', 'generation', 'message'))
        require(campaign['checkpoint']['status'] in ('disabled', 'pending', 'saved', 'error', 'restored', 'dirty'))
        integer(campaign['checkpoint']['generation'])
        string(campaign['checkpoint']['message'], 256)
        for key in ('id', 'chapter', 'title'):
            string(campaign[key])
        if campaign['next_title'] is not None:
            string(campaign['next_title'])
        require(type(campaign['completed']) is list and len(campaign['completed']) <= 16)
        for chapter in campaign['completed']:
            string(chapter)
        require(len(set(campaign['completed'])) == len(campaign['completed']))
        require(type(campaign['ready']) is list and len(campaign['ready']) <= 2)
        require(all(t in TEAMS for t in campaign['ready']) and len(set(campaign['ready'])) == len(campaign['ready']))
    require(value['status'] != 'intermission' or campaign is not None and campaign['next_title'] is not None)
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
        fields(unit, ('owner', 'party', 'faction', 'class', 'persistent', 'skills', 'equipped', 'id', 'name', 'team', 'pos', 'hp', 'max_hp', 'dead', 'finished',
                      'moved', 'attacked', 'movement', 'level', 'exp', 'stats', 'wexp', 'mana', 'max_mana',
                      'inventory', 'moves', 'attacks', 'heals', 'consumables'))
        string(unit['id'])
        string(unit['name'])
        require(unit['owner'] is None or unit['owner'] in TEAMS)
        for key in ('party', 'faction'):
            if unit[key] is not None:
                string(unit[key])
        string(unit['class'])
        require(type(unit['persistent']) is bool)
        require(type(unit['skills']) is list and len(unit['skills']) <= 100)
        for skill in unit['skills']:
            string(skill)
        if unit['equipped'] is not None:
            integer(unit['equipped'])
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
        integer(unit['mana'], 0, 10000)
        integer(unit['max_mana'], 0, 10000)
        require(unit['mana'] <= unit['max_mana'])
        require(type(unit['wexp']) is dict and len(unit['wexp']) <= 64)
        for weapon, amount in unit['wexp'].items():
            string(weapon)
            string(amount, 64)
            require(re.fullmatch(r'[0-9]+(?:\.[0-9]+)?(?:e[+-]?[0-9]{1,3})?', amount) is not None)
            require(math.isfinite(float(amount)) and 0 <= float(amount) <= 10000)
        for key in ('dead', 'finished', 'moved', 'attacked'):
            require(type(unit[key]) is bool)
        require(type(unit['stats']) is dict and len(unit['stats']) <= 64)
        for key, number in unit['stats'].items():
            string(key)
            integer(number, -10000, 10000)
        require(type(unit['inventory']) is list and len(unit['inventory']) <= 20)
        for item in unit['inventory']:
            fields(item, ('uid', 'nid', 'name', 'uses', 'effect'))
            string(item['effect'], 256)
            integer(item['uid'])
            require(item['uid'] not in item_ids)
            item_ids.add(item['uid'])
            string(item['nid'])
            string(item['name'])
            if item['uses'] is not None:
                integer(item['uses'], 0, 10000)
        require(unit['equipped'] is None or unit['equipped'] in {i['uid'] for i in unit['inventory']})
        require(type(unit['moves']) is list and len(unit['moves']) <= 4096)
        for pos in unit['moves']:
            position(pos, value['width'], value['height'])
        for kind in ('attacks', 'heals', 'consumables'):
            require(type(unit[kind]) is list and len(unit[kind]) <= 2000)
            for choice in unit[kind]:
                fields(choice, ('item', 'target'))
                integer(choice['item'])
                string(choice['target'])
                require(choice['item'] in {i['uid'] for i in unit['inventory']})
    if campaign is not None:
        fields(campaign['convoys'], TEAMS)
        for convoy in campaign['convoys'].values():
            require(type(convoy) is list and len(convoy) <= 20)
            for item in convoy:
                fields(item, ('uid', 'nid', 'name', 'uses', 'effect'))
                integer(item['uid'])
                require(item['uid'] not in item_ids)
                item_ids.add(item['uid'])
                for key in ('nid', 'name', 'effect'):
                    string(item[key], 256)
                if item['uses'] is not None:
                    integer(item['uses'], 0, 10000)
    for unit in value['units']:
        require(all(choice['target'] in ids for kind in ('attacks', 'heals', 'consumables') for choice in unit[kind]))
    validate_tactics(value['tactics'], value)
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


def validate_tactics(value, state):
    fields(value, ('status', 'note', 'hit_mode', 'terrain', 'units', 'threats', 'forecasts'))
    require(value['status'] in ('available', 'unavailable'))
    string(value['note'], 256)
    string(value['hit_mode'], 64)
    width, height = state['width'], state['height']
    units = {u['id']: u for u in state['units']}
    def positions(values):
        require(type(values) is list and len(values) <= width*height)
        for pos in values: position(pos, width, height)
        require(len({tuple(p) for p in values}) == len(values))
    require(type(value['terrain']) is list and len(value['terrain']) == height)
    for row in value['terrain']:
        require(type(row) is list and len(row) == width)
        for cell in row:
            fields(cell, ('name', 'defense', 'resistance', 'avoid', 'note'))
            string(cell['name']); string(cell['note'], 256)
            for key in ('defense', 'resistance', 'avoid'):
                if cell[key] is not None: integer(cell[key], -10000, 10000)
    for key, maximum in (('units', 100), ('threats', 100), ('forecasts', 2000)):
        require(type(value[key]) is list and len(value[key]) <= maximum)
    infos = set()
    for info in value['units']:
        fields(info, ('unit', 'class_name', 'costs', 'routes'))
        string(info['unit'])
        require(info['unit'] in units and info['unit'] not in infos)
        infos.add(info['unit']); string(info['class_name'])
        require(type(info['costs']) is list and len(info['costs']) == height)
        for row in info['costs']:
            require(type(row) is list and len(row) == width)
            for cost in row: integer(cost, 0, 10000)
        require(type(info['routes']) is list and len(info['routes']) <= width*height)
        destinations = []
        for route in info['routes']:
            fields(route, ('pos', 'cost', 'left'))
            position(route['pos'], width, height)
            integer(route['cost'], 0, 10000); integer(route['left'], 0, 10000)
            require(route['pos'] in units[info['unit']]['moves'])
            destinations.append(route['pos'])
        positions(destinations)
    enemies = set()
    for threat in value['threats']:
        fields(threat, ('unit', 'supported', 'moves', 'weapons'))
        string(threat['unit'])
        require(threat['unit'] in units and threat['unit'] not in enemies)
        enemies.add(threat['unit'])
        require(units[threat['unit']]['team'] in ('enemy', 'enemy2'))
        require(type(threat['supported']) is bool)
        positions(threat['moves'])
        require(type(threat['weapons']) is list and len(threat['weapons']) <= 20)
        weapons = set()
        for weapon in threat['weapons']:
            fields(weapon, ('item', 'range', 'current', 'reach'))
            integer(weapon['item'])
            require(weapon['item'] in {i['uid'] for i in units[threat['unit']]['inventory']} and weapon['item'] not in weapons)
            weapons.add(weapon['item'])
            ranges(weapon['range']); positions(weapon['current']); positions(weapon['reach'])
    choices = set()
    for forecast in value['forecasts']:
        fields(forecast, ('unit', 'item', 'target', 'supported', 'note', 'range', 'advantage', 'attack', 'counter', 'can_counter'))
        string(forecast['unit']); string(forecast['target'])
        require(forecast['unit'] in units and forecast['target'] in units)
        integer(forecast['item'])
        choice = (forecast['unit'], forecast['item'], forecast['target'])
        require(choice not in choices); choices.add(choice)
        require({'item': forecast['item'], 'target': forecast['target']} in units[forecast['unit']]['attacks'])
        require(type(forecast['supported']) is bool)
        string(forecast['note'], 256); ranges(forecast['range'], empty=not forecast['supported'])
        require(forecast['advantage'] in ('advantage', 'disadvantage', 'neutral', 'unknown'))
        require(forecast['can_counter'] is None or type(forecast['can_counter']) is bool)
        for key in ('attack', 'counter'):
            if forecast[key] is not None:
                fields(forecast[key], ('damage', 'hit', 'crit', 'count'))
                for stat, maximum in (('damage', 10000), ('hit', 100), ('crit', 100), ('count', 20)):
                    if stat == 'crit' and forecast[key][stat] is None: continue
                    integer(forecast[key][stat], 0, maximum)
        if forecast['supported']:
            require(forecast['attack'] is not None and type(forecast['can_counter']) is bool)
            require((forecast['counter'] is not None) == forecast['can_counter'])
        else:
            require(forecast['attack'] is None and forecast['counter'] is None and forecast['can_counter'] is None)
    if value['status'] == 'unavailable':
        require(not value['units'] and not value['threats'] and not value['forecasts'])


def ranges(value, empty=False):
    require(type(value) is list and (0 if empty else 1) <= len(value) <= 64)
    for distance in value: integer(distance, 0, 99)
    require(len(set(value)) == len(value))
