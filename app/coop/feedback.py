"""Short display feedback derived only from committed authoritative packets."""


def committed(packet, previous):
    state, result = packet['state'], packet['result']
    if state['outcome']:
        return state['outcome']
    if not result or not previous:
        return 'Select your character. Click to propose; Enter confirms.'
    old = {u['id']: u for u in previous['state']['units']}
    changes = []
    for unit in state['units']:
        before = old.get(unit['id'])
        if before and before['hp'] != unit['hp']:
            changes.append(f"{unit['name']}: HP {before['hp']} -> {unit['hp']}" +
                           (' (fallen)' if unit['dead'] else ''))
    who = 'Blue' if result['team'] == 'player' else 'Green'
    label = ('Ready' if state['turns']['mode'] == 'shared' else 'End phase') if result['action'] == 'end_phase' else result['action'].capitalize()
    return (f"COMMITTED: {who} {label}. " + '; '.join(changes))[:400]
