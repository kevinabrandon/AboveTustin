# Running AboveTustin as a service

The bot is a long-running process: it polls the receiver once a second and keeps a
headless browser page open on tar1090. Run it under systemd so it starts at boot,
restarts if it fails, and logs to the journal.

## Prerequisites

- readsb and tar1090 serving `aircraft.json` on the same machine or the LAN.
  wiedehopf's installers set both up:
  [readsb](https://github.com/wiedehopf/adsb-scripts/wiki/Automatic-installation-for-readsb),
  [tar1090](https://github.com/wiedehopf/tar1090).
- Google Chrome (or run `uv run playwright install chromium` and set
  `browser_channel = ""` in the config).
- A config file at `~/.config/abovetustin/config.toml`, copied from
  `config.example.toml`, with the receiver position set and, to post, a
  `[bluesky]` section holding the handle and an app password. Keep it mode 0600.

## Install

```sh
git clone https://github.com/kevinabrandon/AboveTustin ~/src/AboveTustin
cd ~/src/AboveTustin
uv sync
uv run abovetustin check                   # config, receiver and login all good?
uv run abovetustin run --dry-run           # watch a few sightings land in the log
mkdir -p ~/.config/systemd/user
cp deploy/abovetustin.service ~/.config/systemd/user/
# If the checkout is somewhere other than ~/src/AboveTustin, edit the two paths
# in the unit.
systemctl --user daemon-reload
systemctl --user enable --now abovetustin
loginctl enable-linger "$USER"             # run without an interactive login
```

## Operate

```sh
systemctl --user status abovetustin
journalctl --user -u abovetustin -f        # live log
systemctl --user restart abovetustin       # after changing the config
abovetustin compose --last 5               # what recent sightings would post as
```

Sightings are appended to `~/.local/share/abovetustin/sightings.jsonl` and images
to `~/.local/share/abovetustin/images/` by default, posted or not.

## Upgrade

```sh
cd ~/src/AboveTustin && git pull && uv sync && systemctl --user restart abovetustin
```
