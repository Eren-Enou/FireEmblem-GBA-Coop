"""Opt-in shared rounds, serialized on the native engine thread.

The sequential adapter and its checkpoint fingerprint remain unchanged.
No action is allowed between the two opening upkeeps or closing endsteps.
"""
from app.coop.protocol import ProtocolError, TEAMS
from app.coop.simulation import Simulation


class SharedSimulation(Simulation):
    def __init__(self, seed=0, scenario="training", growth_method=None, checkpoint_dir=None, restore_dir=None):
        if checkpoint_dir or restore_dir:
            raise ValueError('Shared turns do not support checkpoints or restore; use sequential mode')
        self.allied_ready = set()
        super().__init__(seed=seed, scenario=scenario, growth_method=growth_method)
        self._open_green()

    def _team(self, team):
        from app.data.database.database import DB
        self.game.phase.current = DB.teams.index(team)

    def _open_green(self):
        for _ in self._open_green_steps():
            pass

    def _open_green_steps(self):
        # Blue's native TurnChange has already incremented the round, triggered
        # Blue/round events, reset actions and performed Blue upkeep. Enter Green
        # once before publishing the allied barrier, including native triggers,
        # ResetAll, status timers, terrain/item healing and MarkPhase.
        from app.events import triggers
        self._team('other')
        try:
            self.game.state.change('status_upkeep')
            self.game.state.change('phase_change')
            self.game.events.trigger(triggers.PhaseChange('other'))
            self.game.events.trigger(triggers.OtherTurnChange())
            yield from self.settle_steps()
        finally:
            self._team('player')
        self.allied_ready.clear()

    def execute_steps(self, team, command):
        kind = command['action']
        if kind == 'save_checkpoint':
            raise ProtocolError('shared_checkpoints_disabled')
        if self.status == 'intermission':
            old_chapter = self.campaign.index
            yield from super().execute_steps(team, command)
            if self.campaign.index != old_chapter:
                yield from self._open_green_steps()
            return
        if self.status != 'playing':
            raise ProtocolError('session_finished')
        if team not in TEAMS:
            raise ProtocolError('not_owner')
        if team in self.allied_ready:
            raise ProtocolError('army_already_ready')
        if kind == 'end_phase':
            self.allied_ready.add(team)
            if len(self.allied_ready) < 2:
                return
            try:
                # Native human AI state is a no-op. Run Blue endstep once, then
                # let the unchanged Green end-phase path run Green endstep,
                # native Red AI/endstep and the next Blue turn/upkeep/reset.
                self._team('player')
                self.game.state.change('status_endstep')
                yield from self.settle_steps()
                if self.status == 'playing':
                    self._team('other')
                    yield from super().execute_steps('other', command)
                if self.status == 'playing':
                    yield from self._open_green_steps()
            except Exception:
                self.fault = True
                raise
            finally:
                self._team('player')
            return
        # Select the acting native army for selection/canto/combat hooks, without
        # advancing a phase, resetting flags, firing triggers or running upkeep.
        # Session holds its lock until this generator and publication finish.
        self._team(team)
        try:
            yield from super().execute_steps(team, command)
        finally:
            self._team('player')


def project_turns(simulation):
    shared = isinstance(simulation, SharedSimulation)
    return {'mode': 'shared' if shared else 'sequential',
            'ready': sorted(simulation.allied_ready) if shared else []}


def outcome(state):
    if state['status'] == 'defeat':
        eliminated = [team for team in TEAMS if not any(
            u['team'] == team and u['pos'] and not u['dead'] for u in state['units'])]
        names = {'player': 'Blue', 'other': 'Green'}
        return (' and '.join(names[t] for t in eliminated) + ' army eliminated. Both commanders lose.'
                if eliminated else 'The shared defeat objective was triggered. Both commanders lose.')
    if state['status'] == 'victory':
        return 'All enemies defeated. Both commanders win!'
    if state['status'] == 'fault':
        return 'Host resolution stopped. Inspect the host log before restarting.'
    return None
