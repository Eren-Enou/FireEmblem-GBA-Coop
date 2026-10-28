"""SDL input acceptance against the real native Session through a local UI harness."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from app.coop.client import Model
from app.coop.protocol import VERSION
from app.coop.server import Session
from app.coop.simulation import Simulation
from app.tests.test_coop_checkpoint import boundary
from app.tests.test_network_coop import command


class InventoryInputTests(unittest.TestCase):
    def render_inputs(self, sim, session, events, folder):
        import pygame
        from app.coop.view import run
        model = Model()
        model.apply({'v': VERSION, 'type': 'welcome', 'team': 'player', 'snapshot': deepcopy(session.packet)})
        model.apply({'v': VERSION, 'type': 'peers', 'teams': ['player', 'other']})

        class LocalConnection:
            security = 'Local SDL acceptance harness'
            def __init__(self):
                self.model = model
                self.inputs = iter(events)
                self.sent = []
            def poll(self):
                event = next(self.inputs, None)
                if event: pygame.event.post(pygame.event.Event(*event))
            def send(self, request):
                self.sent.append(request['action'])
                model.apply(deepcopy(session.command('player', request, ('player', 'other'))))
            def close(self): pass

        connection = LocalConnection()
        run(connection, script=[{'action': 'wait_revision', 'revision': session.revision+1},
                               {'action': 'inspect', 'unit': 'Blue_Captain'}],
            screenshot=str(Path(folder)/'inventory-input.png'), timeout=5)
        self.assertTrue((Path(folder)/'inventory-input.png').exists())
        return connection

    def test_number_selection_and_use_key_run_native_consumable(self):
        import pygame
        with tempfile.TemporaryDirectory(prefix='lt-input-use-') as folder:
            sim = Simulation(scenario='campaign'); self.addCleanup(sim.close)
            session = Session(sim)
            connection = self.render_inputs(sim, session,
                [(pygame.KEYDOWN, {'key': pygame.K_2}), (pygame.KEYDOWN, {'key': pygame.K_u})], folder)
            self.assertEqual(connection.sent, ['use'])
            captain = sim.game.get_unit('Blue_Captain')
            self.assertEqual(captain.get_hp(), 26)
            self.assertEqual(captain.items[-1].data['uses'], 2)
            self.assertTrue(captain.finished)

    def test_convoy_click_over_hidden_battle_buttons_then_take_key(self):
        import pygame
        with tempfile.TemporaryDirectory(prefix='lt-input-convoy-') as folder:
            sim, session = boundary(folder); self.addCleanup(sim.close)
            session.command('player', command(session.packet, 'deposit', 'ui_deposit',
                            unit='Blue_Captain', item=100), ('player', 'other'))
            # Third convoy row overlaps the old invisible Wait battle button.
            connection = self.render_inputs(sim, session,
                [(pygame.MOUSEBUTTONDOWN, {'button': 1, 'pos': (100, 558)}),
                 (pygame.KEYDOWN, {'key': pygame.K_t})], folder)
            self.assertEqual(connection.sent, ['withdraw'])
            self.assertIn(100, [i.uid for i in sim.game.get_unit('Blue_Captain').items])
            self.assertEqual(sim.campaign.ready, set())
            self.assertEqual(sim.campaign.checkpoint['status'], 'dirty')


if __name__ == '__main__': unittest.main()
