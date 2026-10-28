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


def plan(preparation=False):
    from app.coop.simulation import Simulation
    from app.coop.server import Session
    from app.coop.protocol import VERSION
    import tempfile
    folder = tempfile.TemporaryDirectory(prefix='lt-plan-')
    sim = Simulation(scenario='campaign', checkpoint_dir=folder.name if preparation else None)
    prep = []
    prepared = False
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
            if preparation and state['status'] == 'intermission' and not prepared:
                # Decisions retain only a ranged axe and stronger staff for Chapter 2.
                units = {u['id']: u for u in state['units']}
                for owner, prefix in (('player', 'Blue'), ('other', 'Green')):
                    captain, healer = prefix + '_Captain', prefix + '_Healer'
                    convoy = state['campaign']['convoys'][owner]
                    hand = next(i['uid'] for i in convoy if i['nid'] == 'Hand_Axe')
                    mend = next(i['uid'] for i in convoy if i['nid'] == 'Mend')
                    prep.extend([(owner, 'withdraw', {'unit': captain, 'item': hand}),
                                 (owner, 'equip', {'unit': captain, 'item': hand}),
                                 (owner, 'deposit', {'unit': captain, 'item': units[captain]['inventory'][0]['uid']}),
                                 (owner, 'deposit', {'unit': healer, 'item': units[healer]['inventory'][0]['uid']}),
                                 (owner, 'withdraw', {'unit': healer, 'item': mend})])
                # Two confirmed generations keep the prepared boundary in fallback too.
                prep += [('player', 'save_checkpoint', {}), ('other', 'save_checkpoint', {})]
                prepared = True
            if prep:
                team, kind, args = prep.pop(0)
            else:
                kind, args = choose(state, team)
                if preparation and state['status'] == 'playing' and state['campaign']['chapter'] == 'alliance' and state['turn'] == 1:
                    personal = next((u for u in state['units'] if u['owner'] == team and u['consumables']), None)
                    if personal:
                        kind, args = 'use', {'unit': personal['id'], **personal['consumables'][0]}
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
        folder.cleanup()


def verify_preparation(packets):
    """Inspect actual process observations, including capped healing and resources."""
    uses, stronger_heals = set(), 0
    for index, packet in enumerate(packets):
        state = packet['state']
        refs = [i['uid'] for u in state['units'] for i in u['inventory']]
        refs += [i['uid'] for convoy in state['campaign']['convoys'].values() for i in convoy]
        assert len(refs) == len(set(refs)), 'Duplicate public item reference'
        if not index or not packet['result']:
            continue
        result = packet['result']
        old = {u['id']: u for u in packets[index-1]['state']['units']}
        new = {u['id']: u for u in state['units']}
        if result['action'] == 'use':
            nid = ('Blue' if result['team'] == 'player' else 'Green') + '_Captain'
            before, after = old[nid], new[nid]
            assert after['hp'] - before['hp'] == min(10, before['max_hp']-before['hp'])
            item = next(i for i in before['inventory'] if i['nid'] == 'Vulnerary')
            assert next(i for i in after['inventory'] if i['uid'] == item['uid'])['uses'] == item['uses']-1
            assert after['finished'] and after['attacked']
            uses.add(result['team'])
        if result['action'] == 'heal' and state['campaign']['chapter'] == 'holding':
            healer = old[('Blue' if result['team'] == 'player' else 'Green') + '_Healer']
            assert [i['nid'] for i in healer['inventory']] == ['Mend']
            if any(new[nid]['hp']-unit['hp'] > healer['stats']['MAG']+10 for nid, unit in old.items() if nid in new):
                stronger_heals += 1
    holding = next(p['state'] for p in packets if p['state']['campaign']['chapter'] == 'holding')
    for prefix, owner in (('Blue', 'player'), ('Green', 'other')):
        captain = next(u for u in holding['units'] if u['id'] == prefix+'_Captain')
        assert {i['nid'] for i in captain['inventory']} == {'Hand_Axe', 'Vulnerary'}
        assert next(i for i in captain['inventory'] if i['uid'] == captain['equipped'])['nid'] == 'Hand_Axe'
        assert next(i for i in captain['inventory'] if i['nid'] == 'Vulnerary')['uses'] == 2
        assert {i['nid'] for i in holding['campaign']['convoys'][owner]} == {'Iron_Axe', 'Heal'}
    assert uses == {'player', 'other'} and stronger_heals > 0
    return {'personal_use_owners': sorted(uses), 'mend_heals_exceeding_heal': stronger_heals}
