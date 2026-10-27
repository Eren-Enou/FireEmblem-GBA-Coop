"""Deterministic acceptance tactics using only public legal command hints.

This is a test driver, not enemy AI or character restoration. It also generates
replayable client scripts for the independent graphical-process smoke.
"""


def choose(state, team):
    if state['status'] == 'intermission':
        return 'ready', {}
    units = {u['id']: u for u in state['units']}
    ready = [u for u in units.values() if u['team'] == team and not u['dead'] and not u['finished']]
    enemies = [u for u in units.values() if u['team'] == 'enemy' and not u['dead']]
    for healer in ready:
        if healer['heals']:
            choice = min(healer['heals'], key=lambda h: (units[h['target']]['hp'] / units[h['target']]['max_hp'], units[h['target']]['team'] == team))
            return 'heal', {'unit': healer['id'], **choice}
    for unit in ready:
        if state['turn'] > 1 and unit['attacks'] and unit['hp'] >= 10:
            choice = min(unit['attacks'], key=lambda a: units[a['target']]['hp'])
            return 'attack', {'unit': unit['id'], **choice}
    # Hold the protected crossings while the pursuing enemies approach. Advance
    # only after turn 3 if a surviving enemy cannot yet be attacked.
    if state['turn'] > 3 and enemies:
        for unit in ready:
            if unit['moves'] and 'Captain' in unit['id'] and unit['hp'] >= 16:
                pos = min(unit['moves'], key=lambda p: (min(abs(p[0]-e['pos'][0])+abs(p[1]-e['pos'][1]) for e in enemies), p))
                return 'move', {'unit': unit['id'], 'pos': pos}
    return ('wait', {'unit': ready[0]['id']}) if ready else ('end_phase', {})


def plan():
    from app.coop.simulation import Simulation
    from app.coop.server import Session
    from app.coop.protocol import VERSION
    sim = Simulation(scenario='campaign')
    scripts = {'player': [], 'other': []}
    try:
        session = Session(sim)
        for index in range(120):
            packet = session.packet
            state = packet['state']
            if state['status'] in ('victory', 'defeat', 'fault'):
                break
            team = state['phase']
            if state['status'] == 'intermission':
                team = 'other' if 'player' in state['campaign']['ready'] else 'player'
            kind, args = choose(state, team)
            # Revision barriers serialize readiness and prevent a stale base when
            # both commanders reach the intermission at almost the same instant.
            scripts[team].append({'action': 'wait_revision', 'revision': packet['revision']})
            scripts[team].append({'action': kind, **args})
            request = {'v': VERSION, 'type': 'command', 'session': session.id,
                       'revision': packet['revision'], 'digest': packet['digest'],
                       'phase': state['phase'], 'id': 'plan_' + str(index), 'action': kind, **args}
            session.command(team, request, ('player', 'other'))
        assert session.packet['state']['status'] == 'victory', session.packet['result']
        for script in scripts.values():
            script.append({'action': 'wait_for', 'status': 'victory'})
        return scripts, session.packet['revision']
    finally:
        sim.close()
