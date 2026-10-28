"""Narrow native inventory operations; no arbitrary item or effect execution."""
from app.coop.protocol import ProtocolError
from app.coop.campaign import PARTIES

SUPPORTED = ('Iron_Axe', 'Hand_Axe', 'Heal', 'Mend', 'Vulnerary')
ACTIONS = ('equip', 'deposit', 'withdraw')


def consumables(sim, unit):
    from app.engine import item_funcs
    if not unit.position or unit.dead or unit.is_dying or unit.finished or unit.has_attacked:
        return []
    return [{'item': item.uid, 'target': unit.nid} for item in unit.items
            if item.nid == 'Vulnerary' and not item.multi_item and not item.sequence_item
            and item_funcs.can_use(unit, item)
            and unit.position in sim.game.target_system.get_valid_targets(unit, item)]


def item_view(item):
    # Audited descriptions of the five trusted prefabs; never effect input.
    details = {'Iron_Axe': 'Vanguard E axe: range 1, might 8, hit 75',
               'Hand_Axe': 'Vanguard E axe: range 1-2, might 7, hit 60',
               'Heal': 'Cleric E staff: adjacent ally, MAG+10 HP',
               'Mend': 'Cleric D staff: adjacent ally, MAG+20 HP',
               'Vulnerary': 'Any character: self +10 HP (cap); ends action'}
    return {'uid': item.uid, 'nid': item.nid, 'name': item.name,
            'uses': item.data.get('uses'), 'effect': details.get(item.nid, 'Unsupported preparation item')}


def prepare(sim, team, command):
    from app.engine import action, item_funcs, item_system
    if sim.status != 'intermission' or not sim.campaign:
        raise ProtocolError('not_intermission')
    if not sim.checkpoint_store:
        raise ProtocolError('checkpoint_required')
    game = sim.game
    unit = game.get_unit(command['unit'])
    if not unit or sim.campaign_owner(unit.nid) != team or unit.team != team or unit.party != PARTIES[team]:
        raise ProtocolError('not_owner')
    if unit.dead or unit.is_dying:
        raise ProtocolError('unit_unavailable')
    party = game.parties[PARTIES[team]]
    kind = command['action']
    source = party.convoy if kind == 'withdraw' else unit.items
    item = next((i for i in source if i.uid == command['item']), None)
    if not item or item.nid not in SUPPORTED or item.multi_item or item.sequence_item:
        raise ProtocolError('invalid_item')
    # Check the actual native registry and uniqueness before any mutation.
    references = [i for u in game.units for i in u.items]
    references += [i for p in game.parties.values() for i in p.convoy]
    if game.item_registry.get(item.uid) is not item or sum(i.uid == item.uid for i in references) != 1:
        raise ProtocolError('invalid_item_reference')
    if item.owner_nid != (None if kind == 'withdraw' else unit.nid):
        raise ProtocolError('invalid_item_owner')
    if kind == 'equip':
        if not item_system.is_weapon(unit, item) or not unit.can_equip(item) or not item_funcs.available(unit, item):
            raise ProtocolError('ineligible_equipment')
        if unit.get_weapon() is item:
            raise ProtocolError('already_equipped')
    elif kind == 'withdraw':
        if item_funcs.inventory_full(unit, item):
            raise ProtocolError('inventory_full')
        if item.nid != 'Vulnerary' and not item_funcs.available(unit, item):
            raise ProtocolError('ineligible_equipment')
    elif len(party.convoy) >= 20:
        raise ProtocolError('convoy_full')
    # Native hooks may mutate derived state: freeze rather than continuing after failure.
    try:
        if kind == 'equip':
            action.do(action.EquipItem(unit, item))
        elif kind == 'deposit':
            action.do(action.RemoveItem(unit, item))
            action.do(action.PutItemInConvoy(item, PARTIES[team]))
        else:
            action.do(action.TakeItemFromConvoy(unit, item, PARTIES[team]))
        sim.campaign.ready.clear()
        sim.campaign.checkpoint.update(status='dirty', message='UNSAVED preparation; press S before Ready or closing')
    except Exception:
        sim.fault = True
        raise
