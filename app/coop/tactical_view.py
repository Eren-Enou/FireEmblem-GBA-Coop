"""Presentation helpers. Interpret only host-issued tactical fields."""

def danger(state, pos):
    sources = []
    for threat in state['tactics']['threats']:
        unit = next(u for u in state['units'] if u['id'] == threat['unit'])
        for weapon in threat['weapons']:
            if list(pos) in weapon['reach'] or list(pos) in weapon['current']:
                item = next(i for i in unit['inventory'] if i['uid'] == weapon['item'])
                sources.append({'enemy': unit['name'] + ' (' + ','.join(map(str, unit['pos'])) + ')', 'weapon': item['name'], 'range': weapon['range'],
                                'current': list(pos) in weapon['current']})
    complete = state['tactics']['status'] == 'available' and all(t['supported'] for t in state['tactics']['threats'])
    return sources, complete


def danger_label(state, pos):
    sources, complete = danger(state, pos)
    if sources:
        return 'DANGER: in current attack reach' if any(s['current'] for s in sources) else 'DANGER: reachable after enemy movement'
    return 'Outside shown enemy weapon reach' if complete else 'Threat coverage unavailable/incomplete'


def forecast_for(state, unit, item, target):
    return next((f for f in state['tactics']['forecasts']
                 if (f['unit'], f['item'], f['target']) == (unit, item, target)), None)


def threat_layers(state, selected, combined):
    movement, current, potential = set(), set(), set()
    for threat in state['tactics']['threats']:
        if combined or threat['unit'] == selected:
            movement.update(tuple(p) for p in threat['moves'])
            for weapon in threat['weapons']:
                current.update(tuple(p) for p in weapon['current'])
                potential.update(tuple(p) for p in weapon['reach'])
    return movement - potential - current, current, potential - current
