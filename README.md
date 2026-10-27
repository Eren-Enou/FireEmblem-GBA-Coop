# Two Banners — cooperative tactical prototype

The project provides one authoritative Lex Talionis host and **two independent
graphical clients**. Blue and Green command their own armies; the host resolves
movement, combat, durability, objectives and Red AI. Local automation verifies
complete battles, identical authoritative state, heartbeat failures and live-host
rejoin. Network processing runs between LT steps without parallel engine work.

Verified TLS supports private remote endpoints. Follow the
[Windows two-PC playtest procedure](docs/INTERNET_PLAY.md) for environment setup,
identity creation, private army invitations, controls, a complete battle and
reconnection. **Actual two-PC Internet play remains unverified.** Campaign saves,
public matchmaking and advanced tactical parity are not implemented. Blue and
Green now gain combat XP and level through the same player growth rules. See the
[progression drill](docs/PROGRESSION.md) for a reproducible two-army level-up.
Blue and Green can also heal one another with real LT staves. The separate
[Mutual Aid encounter](docs/HEALING.md) demonstrates frontliners protecting
healers and cross-army support. Protocol v3 requires matching host and clients.
[Campaign/parity methods](docs/CAMPAIGN_AND_PARITY.md) describe future work.

Run these in three terminals from this repository root:

```powershell
.venv\Scripts\python.exe run_network.py host
.venv\Scripts\python.exe run_network.py client --session-file artifacts/network/blue.json
.venv\Scripts\python.exe run_network.py client --session-file artifacts/network/green.json
```

Wait for `HOST_READY` before starting clients. Click your unit, then a highlighted
tile to move or an adjacent enemy to attack. W waits; E ends your army's phase;
R resynchronizes. The other player's units are inspectable but cannot be
commanded. Keep generated credential files private and untracked.

See [network contract](docs/NETWORK_PROTOCOL.md), [launch/testing procedures](docs/TESTING.md),
[current progress](docs/PROGRESS.md), and [roadmap](docs/ROADMAP.md).

## Existing hot-seat experiment

Run `.venv\Scripts\python.exe run_coop.py` for the original Blue -> Green -> Red
hot-seat test map. Two allied armies share the battlefield against the existing
enemy AI. See [testing](docs/TESTING.md) for controls, setup and verification,
[architecture](docs/ARCHITECTURE.md) for the engine assessment, and
[roadmap](docs/ROADMAP.md) / [progress](docs/PROGRESS.md) for scope and status.
The original hot-seat launcher remains available. Campaign progression is not implemented.

Development is maintained at [Eren-Enou/FireEmblem-GBA-Coop](https://github.com/Eren-Enou/FireEmblem-GBA-Coop).
`origin` is this GitHub repository; `upstream` is the original
[Lex Talionis / LT-Maker engine](https://gitlab.com/rainlash/lt-maker).
See [AGENTS.md](AGENTS.md) for the milestone workflow and
[asset policy](docs/ASSET_POLICY.md) for licensing and publication constraints.

---

**Lex Talionis** is a game engine and editor for creating your own custom Fire Emblem fangame. If you've wanted to make your own Fire Emblem fangame but were fed up with the hackery that's required to master ROM-hacking, or you just want to work with total control over the code itself, **Lex Talionis** is for you.

![TitleScreen](/utilities/readme/title_screen.png)
![AOE](/utilities/readme/aoe.gif)
![ActivatedSkill](/utilities/readme/activated_skill.gif)
![Turnwheel](/utilities/readme/turnwheel.gif)
![Conversation](/utilities/readme/conversation.png)
![EnemyRange](/utilities/readme/enemy_range.png)
![MultiPromotion](/utilities/readme/multi_promotion.png)
![Aura](/utilities/readme/aura.png)
![Base](/utilities/readme/base.png)

**Lex Talionis** was originally released without a dedicated graphical editor, which meant all game creation was done through modification of text files and xml files. But no longer!

**LT-maker** is the easy-to-use but powerful editor built on top of the **Lex Talionis** engine. The **Lex Talionis** engine itself has been completely rewritten using the knowledge gained over seven years of development to be faster, better, and easier-to-use. You can create a whole new game without touching any code.

## Getting Started

![EditorScreenshot](utilities/readme/editor_screenshot.png)

**LT-maker** includes two sample projects. The default project contains the first six chapters of *the Sacred Stones*. You should modify this project to build your own game. **LT-maker** also includes *the Lion Throne*, which is an original fangame created during development of the legacy **Lex Talionis engine**. It has been recreated in **LT-maker** and should be used freely as reference.

Visit the Discord server for more information and help: https://discord.gg/dC6VWGh4sw

# Installation

## Executable Version
> Recommended for beginners and those without programming experience

> **LT-maker** can be run directly as an executable on Windows. Download it here:   https://gitlab.com/rainlash/lt-maker/-/releases
. Unzip the downloaded files, and then double-click *double_click_to_run.bat* to begin creating your own game.

## Python Version
If you have Python programming experience and want to make direct changes to the code itself, you can download the Python version of the engine and start tinkering today. The code is entirely open-source and can be changed to meet your needs. Follow these instructions to get the python version up and running: https://lt-maker.readthedocs.io/en/latest/source/getting_started/Python-Installation.html

## Features

- Multi-tier and branching class promotions
- Fixed growths, Dynamic growths
- Dark mode!
- Controller support in engine
- Mouse support in engine
- Stat and equation editing (complete freedom to change the Fire Emblem formula)
- Turnwheel
- Overworld Editor
- Combat Animation Editor
- Powerful and Expressive Item and Skill creation system
- AOE and multi-target spells and attacks
- Bonus Exp

## Contributing

Visit the Discord server (https://discord.gg/dC6VWGh4sw) to discuss how you can help with this project.

## License

Lex Talionis engine code is licensed under the MIT License - see [LICENSE.txt](LICENSE.txt).
Game assets have separate rights; see the [asset policy](docs/ASSET_POLICY.md).
