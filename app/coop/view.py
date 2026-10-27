"""Small independent tactical client. Draws state, never runs combat or AI."""
import json
import os
from pathlib import Path
import textwrap
import time

from app.coop.protocol import VERSION, require

COLORS = {'player': (75, 151, 246), 'other': (66, 198, 132),
          'enemy': (236, 91, 102), 'enemy2': (180, 100, 220)}
NAMES = {'player': 'BLUE', 'other': 'GREEN', 'enemy': 'RED', 'enemy2': 'PURPLE'}
TILE, LEFT, TOP = 40, 32, 120


def scripted_step(connection, operation):
    """Drive the same command/model interface for reproducible process tests."""
    model = connection.model
    if model.pending or model.syncing:
        return False
    state = model.packet['state']
    kind = operation['action']
    if kind == 'wait_for':
        return all(state.get(key) == value for key, value in operation.items() if key != 'action')
    if not model.can_act:
        return False
    if kind in ('advance', 'attack_nearest'):
        unit = next(u for u in state['units'] if u['id'] == operation['unit'])
        enemies = [u for u in state['units'] if u['team'] == 'enemy' and u['pos']]
        if kind == 'attack_nearest' and unit['attacks']:
            connection.send(model.command('attack', unit=unit['id'], **unit['attacks'][0]))
            return True
        candidates = list(unit['moves'])
        if kind == 'attack_nearest':
            candidates = [p for p in candidates if any(
                abs(p[0] - e['pos'][0]) + abs(p[1] - e['pos'][1]) == 1 for e in enemies)]
        require(candidates and enemies, 'script_no_legal_destination')
        pos = min(candidates, key=lambda p: (min(abs(p[0] - e['pos'][0]) + abs(p[1] - e['pos'][1])
                                                 for e in enemies), p))
        connection.send(model.command('move', unit=unit['id'], pos=pos))
        return kind == 'advance'
    args = {key: value for key, value in operation.items() if key != 'action'}
    connection.send(model.command(kind, **args))
    return True


def run(connection, script=None, report=None, screenshot=None, timeout=45):
    import pygame
    pygame.init()
    screen = pygame.display.set_mode((1000, 680))
    pygame.display.set_caption('Two Banners - ' + NAMES[connection.model.team] + ' network client')
    font = pygame.font.SysFont('consolas', 16)
    large = pygame.font.SysFont('consolas', 26, bold=True)
    clock = pygame.time.Clock()
    model = connection.model
    selected = None
    item_index = 0
    error = None
    index = 0
    started = time.monotonic()
    buttons = {'wait': pygame.Rect(32, 550, 150, 36),
               'end_phase': pygame.Rect(200, 550, 190, 36),
               'sync': pygame.Rect(408, 550, 180, 36)}

    def text(value, x, y, color=(220, 228, 239), big=False):
        screen.blit((large if big else font).render(str(value), True, color), (x, y))

    def command(action, **args):
        if model.can_act and not error:
            connection.send(model.command(action, **args))

    try:
        running = True
        while running:
            try:
                connection.poll()
            except (OSError, ValueError) as exc:
                error = str(exc)
                model.peers = []
                model.pending = None
                model.message = 'Disconnected: ' + error + '. Reopen with the same session file to rejoin.'
                if script is not None:
                    raise
            state = model.packet['state']
            units = {u['id']: u for u in state['units']}
            unit = units.get(selected)
            if unit and not unit['pos']:
                selected = None
                unit = None
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        selected = None
                    elif event.key == pygame.K_r and not error:
                        model.syncing = True
                        connection.send({'v': VERSION, 'type': 'sync'})
                    elif event.key == pygame.K_e:
                        command('end_phase')
                    elif event.key == pygame.K_w and unit and unit['team'] == model.team:
                        command('wait', unit=unit['id'])
                    elif pygame.K_1 <= event.key <= pygame.K_9:
                        item_index = event.key - pygame.K_1
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 3:
                        selected = None
                        continue
                    if event.button != 1:
                        continue
                    mouse = event.pos
                    if buttons['end_phase'].collidepoint(mouse):
                        command('end_phase')
                    elif buttons['wait'].collidepoint(mouse) and unit and unit['team'] == model.team:
                        command('wait', unit=unit['id'])
                    elif buttons['sync'].collidepoint(mouse) and not error:
                        model.syncing = True
                        connection.send({'v': VERSION, 'type': 'sync'})
                    else:
                        pos = [(mouse[0] - LEFT) // TILE, (mouse[1] - TOP) // TILE]
                        clicked = next((u for u in units.values() if u['pos'] == pos), None)
                        if unit and unit['team'] == model.team and clicked and clicked['team'] == 'enemy':
                            inventory = unit['inventory']
                            if item_index < len(inventory):
                                choice = {'item': inventory[item_index]['uid'], 'target': clicked['id']}
                                if choice in unit['attacks']:
                                    command('attack', unit=unit['id'], **choice)
                        elif clicked:
                            selected, item_index = clicked['id'], 0
                        elif unit and unit['team'] == model.team and pos in unit['moves']:
                            command('move', unit=unit['id'], pos=pos)
            if script is not None:
                require(time.monotonic() - started < timeout, 'script_timeout')
                require(not model.message.startswith('Rejected:'), model.message)
                if index < len(script) and scripted_step(connection, script[index]):
                    index += 1

            # Only original geometric tokens and system fonts are used here.
            screen.fill((19, 25, 37))
            text('TWO BANNERS / LOCAL NETWORK', 32, 22, big=True)
            text(f"You: {NAMES[model.team]}   Turn {state['turn']}   Phase: {NAMES[state['phase']]}   {state['status'].upper()}", 32, 64)
            connected = ', '.join(NAMES[t] for t in model.peers) or 'none'
            text(f"Connected: {connected}   Revision {model.packet['revision']}   Check {model.packet['digest'][:12]}", 32, 90)
            for y, row in enumerate(state['terrain']):
                for x, terrain in enumerate(row):
                    rect = pygame.Rect(LEFT + x * TILE, TOP + y * TILE, TILE - 1, TILE - 1)
                    color = {'wall': (48, 58, 72), 'forest': (39, 86, 66), 'plain': (70, 104, 81)}[terrain]
                    pygame.draw.rect(screen, color, rect)
                    if unit and model.can_act and unit['team'] == model.team and [x, y] in unit['moves']:
                        pygame.draw.rect(screen, (94, 169, 189), rect, 2)
            for current in units.values():
                if not current['pos']:
                    continue
                x, y = current['pos']
                cx, cy = LEFT + x * TILE + TILE // 2, TOP + y * TILE + TILE // 2
                color = COLORS[current['team']] if not current['finished'] else (117, 127, 139)
                pygame.draw.circle(screen, color, (cx, cy - 2), 13)
                if current['id'] == selected:
                    pygame.draw.circle(screen, (255, 246, 204), (cx, cy - 2), 17, 2)
                text(current['id'].split('_')[-1][0:1], cx - 5, cy - 11, (12, 23, 34))
                pygame.draw.rect(screen, (15, 20, 25), (cx - 15, cy + 14, 30, 4))
                pygame.draw.rect(screen, (122, 225, 139), (cx - 15, cy + 14, 30 * current['hp'] // max(1, current['max_hp']), 4))
            text('COMMANDER', 670, 125, big=True)
            text(connection.security, 670, 192)
            if state['status'] != 'playing':
                text('Shared ' + state['status'], 670, 167)
            elif not model.can_act:
                status = 'Resolving command...' if model.pending else 'Waiting for both players' if len(model.peers) != 2 else 'Waiting for your phase'
                text(status, 670, 167)
            else:
                text('Your army is ready', 670, 167, COLORS[model.team])
            if unit:
                text(unit['name'].replace('_', ' '), 670, 218, COLORS[unit['team']])
                text(f"HP {unit['hp']}/{unit['max_hp']}   Level {unit['level']} XP {unit['exp']}", 670, 248)
                text('Finished' if unit['finished'] else 'Moved' if unit['moved'] else 'Ready to move', 670, 278)
                for i, item in enumerate(unit['inventory']):
                    text(f"{i+1}. {item['name']} ({item['uses']})", 670, 318 + i * 24)
                text('Click an enemy to attack', 670, 410)
            text('Click a unit to inspect/select', 32, 527)
            for kind, rect in buttons.items():
                pygame.draw.rect(screen, (40, 52, 73), rect, border_radius=5)
                text({'wait': 'Wait [W]', 'end_phase': 'End phase [E]', 'sync': 'Resync [R]'}[kind], rect.x + 12, rect.y + 8)
            for i, line in enumerate(textwrap.wrap(model.message, 96)[:3]):
                text(line, 32, 608 + i * 21, (242, 199, 119))
            pygame.display.flip()
            if script is not None and index == len(script) and not model.pending:
                if screenshot:
                    Path(screenshot).parent.mkdir(parents=True, exist_ok=True)
                    pygame.image.save(screen, screenshot)
                if report:
                    Path(report).parent.mkdir(parents=True, exist_ok=True)
                    Path(report).write_text(json.dumps({'pid': os.getpid(), 'team': model.team,
                        'observed': model.observed, 'final': model.packet}), encoding='utf-8')
                return
            clock.tick(30)
    finally:
        connection.close()
        pygame.quit()
