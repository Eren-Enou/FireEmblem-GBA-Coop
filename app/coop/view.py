"""Small independent tactical client. Draws state, never runs combat or AI."""
import json
import os
from pathlib import Path
import textwrap
import time

from app.coop.protocol import VERSION, require
from app.coop.tactical_view import danger, danger_label, forecast_for, threat_layers

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
    if kind == 'wait_revision':
        return model.packet['revision'] >= operation['revision']
    if kind == 'wait_for':
        return all(state.get(key) == value for key, value in operation.items() if key != 'action')
    if not (model.can_prepare if kind in ('equip', 'deposit', 'withdraw') else model.can_save if kind == 'save_checkpoint' else model.can_ready if kind == 'ready' else model.can_act):
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
    for action, field in (('use', 'consumables'), ('heal', 'heals'), ('attack', 'attacks')):
        if choice in unit.get(field, []):
            return action, choice
    return None


def run(connection, script=None, report=None, screenshot=None, timeout=45):
    import pygame
    pygame.init()
    screen = pygame.display.set_mode((1240, 960))
    pygame.display.set_caption('Two Banners - ' + NAMES[connection.model.team] + ' network client')
    font = pygame.font.SysFont('consolas', 16)
    large = pygame.font.SysFont('consolas', 26, bold=True)
    clock = pygame.time.Clock()
    model = connection.model
    selected = next((unit['id'] for unit in model.packet['state']['units']
                     if unit['team'] == model.team and not unit['dead']), None)
    item_index = 0
    convoy_index = 0
    combined_threat = False
    error = None
    index = 0
    started = time.monotonic()
    buttons = {'wait': pygame.Rect(32, 610, 150, 36),
               'end_phase': pygame.Rect(200, 610, 190, 36),
               'sync': pygame.Rect(408, 610, 180, 36)}

    confirm_button = pygame.Rect(32, 704, 265, 36)
    cancel_button = pygame.Rect(312, 704, 276, 36)

    def text(value, x, y, color=(220, 228, 239), big=False):
        screen.blit((large if big else font).render(str(value), True, color), (x, y))

    def disconnect(exc):
        nonlocal error
        error = str(exc)
        connection.close()
        model.pending = None
        model.cancel_decision('Disconnected; proposal cleared')
        model.message = 'Disconnected: ' + error + '. Reopen the same session file to rejoin; never replay an uncertain command.'

    def send(packet):
        try:
            connection.send(packet)
        except (OSError, ValueError) as exc:
            disconnect(exc)

    def command(action, **args):
        if (model.can_prepare if action in ('equip', 'deposit', 'withdraw') else model.can_save if action == 'save_checkpoint' else model.can_ready if action == 'ready' else model.can_act) and not error:
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
            tile = min(TILE, 600 // state['width'], 400 // state['height'])
            continuation = 'ready' if state['status'] == 'intermission' else 'end_phase'
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
                        model.cancel_decision()
                    elif event.key == pygame.K_f:
                        combined_threat = not combined_threat
                    elif event.key == pygame.K_RETURN and model.decision and model.can_act:
                        send(model.confirm_decision())
                    elif event.key == pygame.K_r and not error:
                        model.cancel_decision('Resynchronizing; proposal cleared')
                        model.syncing = True
                        send({'v': VERSION, 'type': 'sync'})
                    elif event.key == pygame.K_s:
                        command('save_checkpoint')
                    elif event.key == pygame.K_u and unit and 0 <= item_index < len(unit['inventory']):
                        command('use', unit=unit['id'], item=unit['inventory'][item_index]['uid'], target=unit['id'])
                    elif event.key in (pygame.K_q, pygame.K_d, pygame.K_t) and unit and state['status'] == 'intermission':
                        kind = {pygame.K_q: 'equip', pygame.K_d: 'deposit', pygame.K_t: 'withdraw'}[event.key]
                        choices = state['campaign']['convoys'][model.team] if kind == 'withdraw' else unit['inventory']
                        choice_index = convoy_index if kind == 'withdraw' else item_index
                        if 0 <= choice_index < len(choices):
                            command(kind, unit=unit['id'], item=choices[choice_index]['uid'])
                    elif event.key in (pygame.K_UP, pygame.K_DOWN) and state['status'] == 'intermission':
                        count = len(state['campaign']['convoys'][model.team])
                        if count:
                            convoy_index = (convoy_index + (1 if event.key == pygame.K_DOWN else -1)) % count
                    elif event.key == pygame.K_e:
                        command(continuation)
                    elif event.key == pygame.K_w and unit and unit['team'] == model.team and not unit['finished']:
                        command('wait', unit=unit['id'])
                    elif pygame.K_1 <= event.key <= pygame.K_9:
                        model.cancel_decision()
                        item_index = event.key - pygame.K_1
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 3:
                        model.cancel_decision()
                        pos = [(event.pos[0]-LEFT)//tile, (event.pos[1]-TOP)//tile]
                        enemy = next((u for u in units.values() if u['pos'] == pos and u['team'] in ('enemy', 'enemy2')), None)
                        if enemy:
                            selected, item_index = enemy['id'], 0
                        continue
                    if event.button != 1:
                        continue
                    mouse = event.pos
                    if state['status'] != 'intermission' and confirm_button.collidepoint(mouse) and model.decision and model.can_act:
                        send(model.confirm_decision())
                    elif state['status'] != 'intermission' and cancel_button.collidepoint(mouse):
                        model.cancel_decision()
                    elif state['status'] != 'intermission' and buttons['end_phase'].collidepoint(mouse):
                        command(continuation)
                    elif state['status'] != 'intermission' and buttons['wait'].collidepoint(mouse) and unit and unit['team'] == model.team and not unit['finished']:
                        command('wait', unit=unit['id'])
                    elif state['status'] != 'intermission' and buttons['sync'].collidepoint(mouse) and not error:
                        model.cancel_decision('Resynchronizing; proposal cleared')
                        model.syncing = True
                        send({'v': VERSION, 'type': 'sync'})
                    elif state['status'] == 'intermission':
                        convoy = state['campaign']['convoys'][model.team]
                        start = max(0, convoy_index - 2)
                        for i in range(start, min(len(convoy), start + 3)):
                            if pygame.Rect(48, 506 + (i-start)*24, 580, 24).collidepoint(mouse):
                                convoy_index = i
                        roster = [u for u in units.values() if u['owner'] is not None]
                        row = (mouse[1] - 250) // 48
                        if 48 <= mouse[0] < 620 and 0 <= row < len(roster):
                            selected, item_index = roster[row]['id'], 0
                    else:
                        pos = [(mouse[0] - LEFT) // tile, (mouse[1] - TOP) // tile]
                        clicked = next((u for u in units.values() if u['pos'] == pos), None)
                        choice = target_choice(unit, clicked, item_index) if unit and clicked and unit['team'] == model.team else None
                        if choice and model.can_act:
                            action, args = choice
                            if action == 'attack':
                                model.propose(action, unit=unit['id'], **args)
                            else:
                                command(action, unit=unit['id'], **args)
                        elif clicked:
                            model.cancel_decision()
                            selected, item_index = clicked['id'], 0
                        elif unit and unit['team'] == model.team and pos in unit['moves']:
                            if model.can_act:
                                model.propose('move', unit=unit['id'], pos=pos)
                    if unit:
                        for i in range(len(unit['inventory'])):
                            if pygame.Rect(670, 318 + i * 20, 320, 20).collidepoint(mouse):
                                model.cancel_decision()
                                item_index = i
            if script is not None:
                require(time.monotonic() - started < timeout, 'script_timeout')
                require(not model.message.startswith('Rejected:'), model.message)
                if index < len(script):
                    if script[index]['action'] == 'overlay':
                        combined_threat = script[index].get('enabled', True)
                        index += 1
                    elif script[index]['action'] == 'cancel':
                        model.cancel_decision()
                        index += 1
                    elif script[index]['action'] == 'select_item':
                        model.cancel_decision()
                        item_index = script[index]['index']
                        index += 1
                    elif script[index]['action'] == 'propose':
                        model.propose(script[index]['kind'], **script[index]['args'])
                        index += 1
                    elif script[index]['action'] == 'capture':
                        pygame.image.save(screen, script[index]['path'])
                        index += 1
                    elif script[index]['action'] == 'inspect':
                        model.cancel_decision()
                        require(script[index]['unit'] in units, 'script_unknown_unit')
                        selected, item_index = script[index]['unit'], 0
                        index += 1
                    elif scripted_step(connection, script[index]):
                        index += 1
            unit = units.get(selected)

            # Only original geometric tokens and system fonts are used here.
            screen.fill((19, 25, 37))
            text(state['campaign']['title'] if state['campaign'] else 'TWO BANNERS / CO-OP', 32, 22, big=True)
            text(f"You: {NAMES[model.team]}   Turn {state['turn']}   Phase: {NAMES[state['phase']]}   {state['status'].upper()}", 32, 64)
            connected = ', '.join(NAMES[t] for t in model.peers) or 'none'
            text(f"Connected: {connected}   Revision {model.packet['revision']}   Check {model.packet['digest'][:12]}", 32, 90)
            movement_threat, current_threat, potential_threat = threat_layers(state, selected, combined_threat) if model.preview_readable else (set(), set(), set())
            for y, row in enumerate(state['terrain']):
                for x, terrain in enumerate(row):
                    rect = pygame.Rect(LEFT + x * tile, TOP + y * tile, tile - 1, tile - 1)
                    color = {'wall': (48, 58, 72), 'forest': (39, 86, 66), 'plain': (70, 104, 81)}[terrain]
                    pygame.draw.rect(screen, color, rect)
                    if (x, y) in potential_threat or (x, y) in current_threat:
                        tint = pygame.Surface((tile-1, tile-1), pygame.SRCALPHA)
                        tint.fill((240, 60, 80, 70) if (x, y) in current_threat else (245, 150, 55, 55))
                        screen.blit(tint, rect)
                        pygame.draw.rect(screen, (245, 92, 112) if (x, y) in current_threat else (240, 164, 76), rect, 2)
                    elif (x, y) in movement_threat:
                        pygame.draw.rect(screen, (180, 132, 224), rect, 1)
                    if unit and model.can_act and unit['team'] == model.team and [x, y] in unit['moves']:
                        pygame.draw.rect(screen, (94, 210, 240), rect.inflate(-6, -6), 2)
                    if model.decision and model.decision['action'] == 'move' and model.decision['args']['pos'] == [x, y]:
                        pygame.draw.rect(screen, (255, 245, 160), rect.inflate(-2, -2), 4)
            for current in units.values():
                if not current['pos']:
                    continue
                x, y = current['pos']
                cx, cy = LEFT + x * tile + tile // 2, TOP + y * tile + tile // 2
                color = COLORS[current['team']] if not current['finished'] else (117, 127, 139)
                pygame.draw.circle(screen, color, (cx, cy - 2), 13)
                choice = target_choice(unit, current, item_index) if unit and model.can_act and unit['team'] == model.team else None
                if choice:
                    color = (115, 255, 215) if choice[0] in ('heal', 'use') else (255, 125, 80)
                    pygame.draw.circle(screen, color, (cx, cy - 2), 19, 2)
                if current['team'] in ('player', 'other') and (tuple(current['pos']) in current_threat or tuple(current['pos']) in potential_threat):
                    pygame.draw.polygon(screen, (255, 190, 80), [(cx+10, cy-19), (cx+18, cy-7), (cx+2, cy-7)])
                if current['id'] == selected:
                    pygame.draw.circle(screen, (255, 246, 204), (cx, cy - 2), 17, 2)
                text(current['id'].split('_')[-1][0:1], cx - 5, cy - 11, (12, 23, 34))
                pygame.draw.rect(screen, (15, 20, 25), (cx - 15, cy + 14, 30, 4))
                pygame.draw.rect(screen, (122, 225, 139), (cx - 15, cy + 14, 30 * current['hp'] // max(1, current['max_hp']), 4))
            text('SELECTED UNIT', 670, 137, big=True)
            text('All threats [F]: ' + ('ON' if combined_threat else 'OFF / selected enemy only'), 670, 90)
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
                info = next((i for i in state['tactics']['units'] if i['unit'] == unit['id']), None)
                text((info['class_name'] if info else unit['class']) + ' / ' + NAMES[unit['team']], 670, 300)
                for i, item in enumerate(unit['inventory']):
                    text(f"{'>' if i == item_index else ' '} {i+1}. {item['name']} ({item['uses']})", 670, 318 + i * 20)
                if 0 <= item_index < len(unit['inventory']):
                    selected_item = unit['inventory'][item_index]
                    for row, line in enumerate(textwrap.wrap(selected_item['effect'], 32)[:2]):
                        text(line, 670, 448 + row*19, (143, 213, 239))
                    legal = any(c['item'] == selected_item['uid'] for c in unit['consumables'])
                    if selected_item['nid'] == 'Vulnerary':
                        text('Use [U]: ' + ('available' if legal and model.can_act else 'needs wound/turn/action'), 670, 424)
                text('Equipped: ' + next((i['name'] for i in unit['inventory'] if i['uid'] == unit['equipped']), 'none'), 670, 404)
                text('Mint: heal/use; orange: preview attack', 670, 486)
                stats = list(unit['stats'].items())
                for row in range(0, len(stats), 3):
                    text('  '.join(f'{key}:{value}' for key, value in stats[row:row+3]), 670, 514 + row // 3 * 22)
                text(f"Mana {unit['mana']}/{unit['max_mana']}", 670, 612)
                weapons = ', '.join(f'{key}:{value}' for key, value in unit['wexp'].items() if float(value))
                text('WEXP ' + weapons, 670, 636)
            if unit and unit['pos'] and unit['team'] in ('player', 'other') and state['status'] == 'playing':
                sources, complete = danger(state, unit['pos'])
                text('Current unit: ' + ('preview paused' if not model.preview_readable else 'THREATENED' if sources else 'outside shown reach' if complete else 'threat unknown'), 670, 656, (255, 195, 120))
            if state['status'] == 'intermission':
                pygame.draw.rect(screen, (22, 32, 47), (32, 135, 600, 490))
                text('CHAPTER COMPLETE', 48, 150, big=True)
                text('Next: ' + state['campaign']['next_title'], 48, 190)
                text('Ready: ' + ', '.join(NAMES[t] for t in state['campaign']['ready']), 48, 218)
                roster = [u for u in units.values() if u['owner'] is not None]
                for row, member in enumerate(roster):
                    items = ', '.join(i['name'] + ':' + str(i['uses']) for i in member['inventory'])
                    text(f"{NAMES[member['owner']]} {member['name']} L{member['level']} XP {member['exp']} " + ('FALLEN' if member['dead'] else 'SURVIVED'), 48, 255 + row*48, COLORS[member['team']])
                    text(items, 48, 276 + row*48)
                text(state['campaign']['checkpoint']['message'][:60], 48, 445, (242, 199, 119))
                text('Select own roster + item; Equip [Q] / Deposit [D]', 48, 465)
                text('Your convoy: click or arrows; Take [T]', 48, 486)
                convoy = state['campaign']['convoys'][model.team]
                convoy_index = min(convoy_index, max(0, len(convoy)-1))
                start = max(0, convoy_index - 2)
                for row in range(start, min(len(convoy), start + 3)):
                    item = convoy[row]
                    text(('> ' if row == convoy_index else '  ') + item['name'] + ' (' + str(item['uses']) + ')', 48, 506 + (row-start)*24)
                if convoy:
                    text(convoy[convoy_index]['effect'][:59], 48, 578, (143, 213, 239))
                text('Save [S] then both Ready [E]. Prep clears votes.', 48, 598)
            mouse_x, mouse_y = pygame.mouse.get_pos()
            hover = ((mouse_x - LEFT) // tile, (mouse_y - TOP) // tile)
            tile_hint = f'Tile {hover}: ' if 0 <= hover[0] < state['width'] and 0 <= hover[1] < state['height'] else ''
            if state['status'] != 'intermission':
                proposed_pos = model.decision['args']['pos'] if model.decision and model.decision['action'] == 'move' else None
                terrain_pos = tuple(proposed_pos) if proposed_pos else hover if 0 <= hover[0] < state['width'] and 0 <= hover[1] < state['height'] else tuple(unit['pos']) if unit and unit['pos'] else None
                if terrain_pos:
                    x, y = terrain_pos
                    terrain = state['tactics']['terrain'][y][x]
                    info = next((i for i in state['tactics']['units'] if unit and i['unit'] == unit['id']), None)
                    occupied = any(u['pos'] == [x, y] for u in units.values())
                    accessible = bool(unit and [x, y] in unit['moves'])
                    cost = info['costs'][y][x] if info else '?'
                    text(f"Tile {x},{y}: {terrain['name']} | DEF {terrain['defense']} RES {terrain['resistance']} AVO {terrain['avoid']}", 32, 532)
                    text(f"Step cost {cost}; " + ('OCCUPIED' if occupied else 'REACHABLE' if accessible else 'BLOCKED / UNREACHABLE'), 32, 554)
                    text(danger_label(state, terrain_pos) if model.preview_readable else 'Previews paused; showing last committed board', 32, 576, (255, 195, 120))
                text('Red=now Orange=after walk Purple=move only', 670, 112, (240, 192, 135))
                proposal = model.decision
                text(model.decision_notice[:62], 32, 654, (255, 237, 155))
                if proposal and proposal['action'] == 'move':
                    info = next(i for i in state['tactics']['units'] if i['unit'] == proposal['args']['unit'])
                    route = next(r for r in info['routes'] if r['pos'] == proposal['args']['pos'])
                    text(f"MOVE {route['pos']} cost {route['cost']}, movement left {route['left']}", 32, 677)
                elif proposal:
                    text('ATTACK proposed; inspect forecast before confirming', 32, 677)
                for rect, label in ((confirm_button, 'Confirm [Enter]'), (cancel_button, 'Cancel [Esc / right click]')):
                    pygame.draw.rect(screen, (65, 80, 100) if proposal else (30, 35, 45), rect, border_radius=5)
                    text(label, rect.x+8, rect.y+8)
                target = proposal['args'].get('target') if proposal and proposal['action'] == 'attack' else next((u['id'] for u in units.values() if u['pos'] == list(hover)), None)
                selected_item = unit['inventory'][item_index]['uid'] if unit and 0 <= item_index < len(unit['inventory']) else None
                forecast = forecast_for(state, unit['id'], selected_item, target) if unit and target and model.preview_readable else None
                pygame.draw.rect(screen, (27, 37, 51), (670, 675, 548, 265))
                text('COMBAT FORECAST / READ ONLY', 688, 686, (155, 220, 244))
                if not model.preview_readable:
                    text('Preview unavailable until fresh active state.', 688, 722)
                    text('Pending / resync / disconnect / battle ended.', 688, 752)
                elif proposal and proposal['action'] == 'move':
                    text('MOVE proposed only; no command sent', 688, 714)
                    text('Destination: ' + str(proposal['args']['pos']), 688, 744)
                    text(danger_label(state, proposal['args']['pos']), 688, 774, (255, 195, 120))
                    text('Reach assumes CURRENT blockers.', 688, 814)
                    text('Moving a guard can open new enemy paths.', 688, 838)
                    text('Recheck ranges after a confirmed move.', 688, 862)
                    text('Terrain bonuses shown are base values.', 688, 894)
                elif forecast:
                    defender = units[forecast['target']]
                    item = next(i for i in unit['inventory'] if i['uid'] == forecast['item'])
                    text(unit['name'] + ' -> ' + defender['name'] + ' ' + str(defender['pos']) + ' / ' + item['name'], 688, 714)
                    if forecast['supported']:
                        a, c = forecast['attack'], forecast['counter']
                        text(f"DMG {a['damage']} x{a['count']}  HIT {a['hit']}/100  CRIT {str(a['crit'])+'%' if a['crit'] is not None else '--'}", 688, 744)
                        text('Counter: ' + (f"{c['damage']} x{c['count']}  HIT {c['hit']}/100  CRIT {str(c['crit'])+'%' if c['crit'] is not None else '--'}" if c else 'NO (native range/availability rules)'), 688, 774)
                        text('Range ' + ','.join(map(str, forecast['range'])) + ' | Triangle: ' + forecast['advantage'], 688, 804)
                        text('HIT = displayed rating; native ' + state['tactics']['hit_mode'], 688, 834)
                        text('Up to shown strikes; KO/death can stop combat.', 688, 864)
                        text('Counter only if defender survives the opening.', 688, 886)
                    else:
                        for row, line in enumerate(textwrap.wrap(forecast['note'], 51)):
                            text(line, 688, 748+row*22, (255, 195, 120))
                elif unit and unit['team'] in ('enemy', 'enemy2'):
                    text('Potential threat, not AI intent', 688, 722)
                    threat = next((t for t in state['tactics']['threats'] if t['unit'] == unit['id']), None)
                    for row, weapon in enumerate(threat['weapons'][:3] if threat else []):
                        item = next(i for i in unit['inventory'] if i['uid'] == weapon['item'])
                        text(item['name'] + ' / range ' + ','.join(map(str, weapon['range'])), 688, 754+row*24)
                    if threat and not threat['supported']:
                        text('INCOMPLETE: unsupported effects', 688, 816, (255, 180, 120))
                    for row, line in enumerate(textwrap.wrap(state['tactics']['note'], 51)):
                        text(line, 688, 836+row*22)
                else:
                    text('Select your weapon; hover a legal enemy.', 688, 722)
                    text('Click target to propose; Enter confirms.', 688, 752)
                if terrain_pos:
                    sources, complete = danger(state, terrain_pos) if model.preview_readable else ([], False)
                    source_text = '; '.join(s['enemy'] + ' ' + s['weapon'] + ' R' + ','.join(map(str, s['range'])) for s in sources)
                    for row, line in enumerate(textwrap.wrap(source_text or ('No shown weapon reaches this tile' if complete else 'Incomplete threat information'), 62)[:2]):
                        text(line, 32, 900+row*20, (240, 192, 135))

            for kind, rect in buttons.items():
                if state['status'] == 'intermission':
                    continue
                enabled = not error and (kind == 'sync' or kind == 'end_phase' and model.can_ready or model.can_act and (kind != 'wait' or unit and unit['team'] == model.team and not unit['finished']))
                pygame.draw.rect(screen, (53, 76, 100) if enabled else (30, 35, 45), rect, border_radius=5)
                text({'wait': 'Wait [W]', 'end_phase': 'Ready [E]' if continuation == 'ready' else 'End phase [E]', 'sync': 'Resync [R]'}[kind], rect.x + 12, rect.y + 8)
            message = ('Both armies connected; inspect before committing.' if model.message == 'Connected; waiting for both armies' and len(model.peers) == 2 else model.message)
            for i, line in enumerate(textwrap.wrap(message, 62)[:3]):
                text(line, 32, 758 + i * 19, (242, 199, 119))
            text('RECENT CHARACTER GROWTH', 32, 825, (143, 213, 239))
            recent = ' | '.join(model.level_ups[-2:] + model.progression[-1:]) or 'Combat XP and level-ups appear here; select a unit to inspect stats.'
            for i, line in enumerate(textwrap.wrap(recent, 62)[:2]):
                text(line, 32, 850 + i * 19, (161, 230, 172))
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
