"""Native consumable, preparation authority and dirty-checkpoint acceptance."""
from copy import deepcopy
import tempfile
import unittest
from unittest.mock import patch

from app.coop.protocol import ProtocolError, digest, validate_request
from app.coop.server import Session
from app.coop.simulation import Simulation
from app.tests.test_network_coop import command
from app.tests.test_coop_checkpoint import boundary


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='lt-preparation-')
        self.addCleanup(self.folder.cleanup)
        self.number = 0

    def start(self, completed=False):
        if completed:
            self.sim, self.session = boundary(self.folder.name)
        else:
            self.sim = Simulation(scenario='campaign', checkpoint_dir=self.folder.name)
            self.session = Session(self.sim)
        self.addCleanup(self.sim.close)

    def issue(self, action, team='player', **args):
        self.number += 1
        return self.session.command(team, command(self.session.packet, action,
            'prep_' + str(self.number), **args), ('player', 'other'))

    def reject(self, code, action, **args):
        before = deepcopy(self.session.packet)
        with self.assertRaisesRegex(ProtocolError, '^' + code + '$'):
            self.issue(action, **args)
        self.assertEqual(self.session.packet, before)
        self.assertEqual(digest(self.sim.snapshot()), before['digest'])

    def test_native_consumable_heal_cap_last_charge_removal_and_finished_action(self):
        self.start()
        unit = self.sim.game.get_unit('Blue_Captain')
        item = unit.items[-1]
        # Controlled final-charge fixture: the real combat path removes it.
        item.data['uses'] = 1
        unit.set_hp(unit.get_max_hp()-3)
        self.session.packet = self.session.make_packet()
        old_weapon = unit.get_weapon()
        self.issue('use', unit=unit.nid, item=item.uid, target=unit.nid)
        self.assertEqual(unit.get_hp(), unit.get_max_hp())
        self.assertEqual(item.data['uses'], 0)
        self.assertNotIn(item, unit.items)
        self.assertIs(unit.get_weapon(), old_weapon)
        self.assertTrue(unit.finished and unit.has_attacked)
        self.reject('unit_unavailable', 'attack', unit=unit.nid, item=old_weapon.uid, target='alliance_Red_1')

    def test_consumable_owner_phase_target_item_and_native_availability(self):
        self.start()
        unit = self.sim.game.get_unit('Blue_Captain'); item = unit.items[-1]
        self.reject('not_owner', 'use', unit='Green_Captain', item=item.uid, target='Green_Captain')
        self.reject('wrong_phase', 'use', team='other', unit='Green_Captain', item=item.uid, target='Green_Captain')
        self.reject('illegal_use', 'use', unit=unit.nid, item=item.uid, target='Green_Captain')
        self.reject('illegal_use', 'use', unit=unit.nid, item=unit.items[0].uid, target=unit.nid)
        for hp, uses in ((unit.get_max_hp(), 3), (10, 0)):
            unit.set_hp(hp); item.data['uses'] = uses
            self.session.packet = self.session.make_packet()
            self.reject('illegal_use', 'use', unit=unit.nid, item=item.uid, target=unit.nid)
        request = command(self.session.packet, 'use', 'injection', unit=unit.nid, item=item.uid, target=unit.nid)
        request['amount'] = 999
        with self.assertRaises(ProtocolError): validate_request(request)

    def test_preparation_dirty_clears_votes_requires_save_and_retries_error(self):
        self.start(True)
        self.issue('ready')
        hand = self.sim.game.parties['Green_Banner'].convoy[0]
        self.issue('withdraw', 'other', unit='Green_Captain', item=hand.uid)
        cp = self.session.packet['state']['campaign']
        self.assertEqual(cp['ready'], [])
        self.assertEqual(cp['checkpoint']['status'], 'dirty')
        self.reject('checkpoint_required', 'ready')
        with patch('app.coop.checkpoint.Store.save', side_effect=OSError('disk unavailable')):
            self.issue('save_checkpoint')
        self.assertEqual(self.sim.campaign.checkpoint['status'], 'error')
        self.reject('checkpoint_required', 'ready')
        self.issue('save_checkpoint')
        self.assertEqual(self.sim.campaign.checkpoint['status'], 'saved')
        self.assertEqual(self.sim.campaign.checkpoint['generation'], 2)

    def test_owner_rank_capacity_uniqueness_and_stale_duplicate_reject(self):
        self.start(True)
        blue = self.sim.game.get_unit('Blue_Captain')
        hand, mend = self.sim.game.parties['Blue_Banner'].convoy
        self.reject('not_owner', 'withdraw', unit='Green_Captain', item=hand.uid)
        green = self.sim.game.parties['Green_Banner'].convoy[0]
        self.reject('invalid_item', 'withdraw', unit=blue.nid, item=green.uid)
        self.reject('ineligible_equipment', 'withdraw', unit='Blue_Healer', item=hand.uid)
        self.reject('ineligible_equipment', 'withdraw', unit=blue.nid, item=mend.uid)
        from app.engine import action, item_funcs
        extras = []
        while len(blue.items) < item_funcs.get_num_items(blue):
            extra = item_funcs.create_item(blue, 'Vulnerary')
            self.sim.game.register_item(extra)
            action.do(action.GiveItem(blue, extra))
            extras.append(extra)
        self.session.packet = self.session.make_packet()
        self.reject('inventory_full', 'withdraw', unit=blue.nid, item=hand.uid)
        for extra in extras:
            action.do(action.RemoveItem(blue, extra))
        self.session.packet = self.session.make_packet()
        request = command(self.session.packet, 'withdraw', 'once', unit=blue.nid, item=hand.uid)
        stale = command(self.session.packet, 'deposit', 'stale', unit=blue.nid, item=blue.items[0].uid)
        original = {i.uid for u in self.sim.game.units for i in u.items} | {i.uid for p in self.sim.game.parties.values() for i in p.convoy}
        self.session.command('player', request, ('player', 'other'))
        before = deepcopy(self.session.packet)
        for req, code in ((request, 'duplicate_command'), (stale, 'stale_revision')):
            with self.assertRaisesRegex(ProtocolError, code): self.session.command('player', req, ('player', 'other'))
            self.assertEqual(self.session.packet, before)
        self.issue('equip', unit=blue.nid, item=hand.uid)
        self.assertIs(blue.get_weapon(), hand)
        self.issue('deposit', unit=blue.nid, item=hand.uid)
        self.assertNotIn(hand, blue.items)
        self.assertIsNone(hand.owner_nid)
        self.issue('withdraw', unit=blue.nid, item=hand.uid)
        refs = [i.uid for u in self.sim.game.units for i in u.items] + [i.uid for p in self.sim.game.parties.values() for i in p.convoy]
        self.assertEqual(len(refs), len(set(refs)))
        self.assertEqual(set(refs), original)

    def test_equip_and_withdraw_use_native_rank_rules(self):
        self.start(True)
        unit = self.sim.game.get_unit('Blue_Captain')
        hand = self.sim.game.parties['Blue_Banner'].convoy[0]
        self.issue('withdraw', unit=unit.nid, item=hand.uid)
        unit.wexp['Axe'] = 0
        self.session.packet = self.session.make_packet()
        self.reject('ineligible_equipment', 'equip', unit=unit.nid, item=hand.uid)

    def test_prepared_hand_axe_adds_real_chapter_two_range(self):
        self.start(True)
        unit = self.sim.game.get_unit('Blue_Captain')
        hand = self.sim.game.parties['Blue_Banner'].convoy[0]
        iron = unit.items[0]
        self.issue('withdraw', unit=unit.nid, item=hand.uid)
        self.issue('equip', unit=unit.nid, item=hand.uid)
        self.issue('save_checkpoint')
        self.issue('ready'); self.issue('ready', 'other')
        self.issue('move', unit=unit.nid, pos=[9, 3])
        choices = self.sim.attacks(unit)
        self.assertIn({'item': hand.uid, 'target': 'holding_Red_1'}, choices)
        self.assertNotIn({'item': iron.uid, 'target': 'holding_Red_1'}, choices)
        before = hand.data['uses']
        self.issue('attack', unit=unit.nid, item=hand.uid, target='holding_Red_1')
        self.assertLess(hand.data['uses'], before)

    def test_preparation_rejects_mid_map(self):
        self.start()
        self.reject('not_intermission', 'deposit', unit='Blue_Captain', item=100)


class PreparationProcessTests(unittest.TestCase):
    def test_uninterrupted_prepared_campaign_two_graphical_clients(self):
        from utilities.smoke_network import run_smoke
        with tempfile.TemporaryDirectory(prefix='lt-prepared-live-') as folder:
            result = run_smoke(folder, preparation=True)
            self.assertEqual(result['revision'], 58)
            self.assertEqual(result['snapshots_compared'], 59)

    def test_prepared_campaign_shutdown_restore_and_finish(self):
        from utilities.smoke_checkpoint import run_smoke
        with tempfile.TemporaryDirectory(prefix='lt-prepared-restart-') as folder:
            result = run_smoke(folder, preparation=True)
            self.assertEqual(result['final_revision'], 29)
            self.assertEqual(result['snapshots_compared'], [30, 30])


if __name__ == '__main__': unittest.main()
