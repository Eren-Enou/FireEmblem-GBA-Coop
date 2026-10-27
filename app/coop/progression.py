"""Read-only descriptions of authoritative progression; never awards rewards."""


def progression_changes(before, after):
    previous = {unit['id']: unit for unit in before['units']}
    changes = []
    for unit in after['units']:
        old = previous[unit['id']]
        parts = []
        xp = 100 * (unit['level'] - old['level']) + unit['exp'] - old['exp']
        if xp:
            parts.append(f'XP {xp:+d} ({old["exp"]} -> {unit["exp"]})')
        if unit['level'] != old['level']:
            parts.append(f'LEVEL UP {old["level"]} -> {unit["level"]}')
        stats = [f'{key} {value-old["stats"][key]:+d}' for key, value in unit['stats'].items()
                 if value != old['stats'][key]]
        if stats:
            parts.append(', '.join(stats))
        weapon_changes = [f'{key} {value}' for key, value in unit['wexp'].items()
                          if float(value) != float(old['wexp'][key])]
        if weapon_changes:
            parts.append('WEXP ' + ', '.join(weapon_changes))
        if unit['mana'] != old['mana']:
            parts.append(f'Mana {old["mana"]} -> {unit["mana"]}')
        if parts:
            changes.append(unit['id'] + ': ' + '; '.join(parts))
    return changes
