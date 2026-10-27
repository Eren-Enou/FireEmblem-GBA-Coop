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


def target_choice(unit, clicked, item_index):
    """Same selection rule for mouse interaction and focused UI acceptance."""
    if not 0 <= item_index < len(unit['inventory']):
        return None
    choice = {'item': unit['inventory'][item_index]['uid'], 'target': clicked['id']}
    for action, field in (('heal', 'heals'), ('attack', 'attacks')):
        if choice in unit[field]:
            return action, choice
    return None


def run(connection, script=None, report=None, screenshot=None, timeout=45):
    import pygame
    pygame.init()
    screen = pygame.display.set_mode((1000, 800))
    pygame.display.set_caption('Two Banners - ' + NAMES[connection.model.team] + ' network client')
    font = pygame.font.SysFont('consolas', 16)
    large = pygame.font.SysFont('consolas', 26, bold=True)
    clock = pygame.time.Clock()
    model = connection.model
    selected = next((unit['id'] for unit in model.packet['state']['units']
                     if unit['team'] == model.team and not unit['dead']), None)
    item_index = 0
    error = None
    index = 0
    started = time.monotonic()
    buttons = {'wait': pygame.Rect(32, 550, 150, 36),
               'end_phase': pygame.Rect(200, 550, 190, 36),
               'sync': pygame.Rect(408, 550, 180, 36)}

    def text(value, x, y, color=(220, 228, 239), big=False):
        screen.blit((large if big else font).render(str(value), True, color), (x, y))

    def disconnect(exc):
        nonlocal error
        error = str(exc)
        connection.close()
        model.pending = None
        model.message = 'Disconnected: ' + error + '. Reopen the same session file to rejoin; never replay an uncertain command.'

    def send(packet):
        try:
            connection.send(packet)
        except (OSError, ValueError) as exc:
            disconnect(exc)

    def command(action, **args):
        if model.can_act and not error:
            send(model.command(action, **args))

    try:
        running = True
        while running:
            try:
                if not error:
                    connection.poll()
            except (OSError, ValueError) as exc:
                disconnect(exc)
                if script is not None:
                    raise
            state = model.packet['state']
            units = {u['id']: u for u in state['units']}
            unit = units.get(selected)
            if unit and not unit['pos']:
                selected = None
                unit = None
            for event in pygame.event.get():
                unit = units.get(selected)
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        selected = None
                    elif event.key == pygame.K_r and not error:
                        model.syncing = True
                        send({'v': VERSION, 'type': 'sync'})
                    elif event.key == pygame.K_e:
                        command('end_phase')
                    elif event.key == pygame.K_w and unit and unit['team'] == model.team and not unit['finished']:
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
                    elif buttons['wait'].collidepoint(mouse) and unit and unit['team'] == model.team and not unit['finished']:
                        command('wait', unit=unit['id'])
                    elif buttons['sync'].collidepoint(mouse) and not error:
                        model.syncing = True
                        send({'v': VERSION, 'type': 'sync'})
                    else:
                        pos = [(mouse[0] - LEFT) // TILE, (mouse[1] - TOP) // TILE]
                        clicked = next((u for u in units.values() if u['pos'] == pos), None)
                        choice = target_choice(unit, clicked, item_index) if unit and clicked and unit['team'] == model.team else None
                        if choice:
                            action, args = choice
                            command(action, unit=unit['id'], **args)
                        elif clicked:
                            selected, item_index = clicked['id'], 0
                        elif unit and unit['team'] == model.team and pos in unit['moves']:
                            command('move', unit=unit['id'], pos=pos)
                    if unit:
                        for i in range(len(unit['inventory'])):
                            if pygame.Rect(670, 318 + i * 24, 320, 24).collidepoint(mouse):
                                item_index = i
            if script is not None:
                require(time.monotonic() - started < timeout, 'script_timeout')
                require(not model.message.startswith('Rejected:'), model.message)
                if index < len(script):
                    if script[index]['action'] == 'inspect':
                        require(script[index]['unit'] in units, 'script_unknown_unit')
                        selected, item_index = script[index]['unit'], 0
                        index += 1
                    elif scripted_step(connection, script[index]):
                        index += 1
            unit = units.get(selected)

            # Only original geometric tokens and system fonts are used here.
            screen.fill((19, 25, 37))
            text('TWO BANNERS / CO-OP', 32, 22, big=True)
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
                choice = target_choice(unit, current, item_index) if unit and model.can_act and unit['team'] == model.team else None
                if choice:
                    color = (115, 255, 215) if choice[0] == 'heal' else (255, 125, 80)
                    pygame.draw.circle(screen, color, (cx, cy - 2), 19, 2)
                if current['id'] == selected:
                    pygame.draw.circle(screen, (255, 246, 204), (cx, cy - 2), 17, 2)
                text(current['id'].split('_')[-1][0:1], cx - 5, cy - 11, (12, 23, 34))
                pygame.draw.rect(screen, (15, 20, 25), (cx - 15, cy + 14, 30, 4))
                pygame.draw.rect(screen, (122, 225, 139), (cx - 15, cy + 14, 30 * current['hp'] // max(1, current['max_hp']), 4))
            text('COMMANDER', 670, 125, big=True)
            text(connection.security, 670, 192)
            if state['status'] != 'playing':
                text('Shared ' + state['status'], 670, 167)
            elif error:
                text('DISCONNECTED / REJOIN', 670, 167, (255, 125, 80))
            elif not model.can_act:
                status = 'Resolving command...' if model.pending else 'Resynchronizing...' if model.syncing else 'Waiting for both players' if len(model.peers) != 2 else 'Waiting for your phase'
                text(status, 670, 167)
            else:
                text('Your army is ready', 670, 167, COLORS[model.team])
            if unit:
                text(unit['name'].replace('_', ' '), 670, 218, COLORS[unit['team']])
                text(f"HP {unit['hp']}/{unit['max_hp']}   Level {unit['level']} XP {unit['exp']}", 670, 248)
                text('Finished' if unit['finished'] else 'Moved' if unit['moved'] else 'Ready to move', 670, 278)
                text(f"Tile {unit['pos']}", 670, 300)
                for i, item in enumerate(unit['inventory']):
                    text(f"{'>' if i == item_index else ' '} {i+1}. {item['name']} ({item['uses']})", 670, 318 + i * 24)
                text(f"Move: {unit['movement']} / {len(unit['moves'])} tiles", 670, 386)
                text(f"Attack: {len(unit['attacks'])} Heal: {len(unit['heals'])}", 670, 410)
                text('Mint: heal / orange: attack', 670, 434)
                text('Moves commit immediately', 670, 458)
                stats = list(unit['stats'].items())
                for row in range(0, len(stats), 3):
                    text('  '.join(f'{key}:{value}' for key, value in stats[row:row+3]), 670, 490 + row // 3 * 22)
                text(f"Mana {unit['mana']}/{unit['max_mana']}", 670, 592)
                weapons = ', '.join(f'{key}:{value}' for key, value in unit['wexp'].items() if float(value))
                text('WEXP ' + weapons, 670, 616)
            mouse_x, mouse_y = pygame.mouse.get_pos()
            hover = ((mouse_x - LEFT) // TILE, (mouse_y - TOP) // TILE)
            tile_hint = f'Tile {hover}: ' if 0 <= hover[0] < state['width'] and 0 <= hover[1] < state['height'] else ''
            text(tile_hint + 'Click a unit to inspect/select', 32, 527)
            for kind, rect in buttons.items():
                enabled = not error and (kind == 'sync' or model.can_act and (kind != 'wait' or unit and unit['team'] == model.team and not unit['finished']))
                pygame.draw.rect(screen, (53, 76, 100) if enabled else (30, 35, 45), rect, border_radius=5)
                text({'wait': 'Wait [W]', 'end_phase': 'End phase [E]', 'sync': 'Resync [R]'}[kind], rect.x + 12, rect.y + 8)
            for i, line in enumerate(textwrap.wrap(model.message, 62)[:3]):
                text(line, 32, 608 + i * 21, (242, 199, 119))
            text('RECENT CHARACTER GROWTH', 32, 687, (143, 213, 239))
            recent = ' | '.join(model.level_ups[-2:] + model.progression[-1:]) or 'Combat XP and level-ups appear here; select a unit to inspect stats.'
            for i, line in enumerate(textwrap.wrap(recent, 96)[:4]):
                text(line, 32, 714 + i * 19, (161, 230, 172))
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
