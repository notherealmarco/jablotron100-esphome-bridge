# jablo2esphome

Expose a **Jablotron 100** alarm system to Home Assistant as if it were an
**ESPHome device**.

Home Assistant's built-in ESPHome integration speaks the native API over TCP;
this bridge implements that protocol on the Jablotron side. No YAML, hardware
or add-on changes are needed — just add the bridge as a device in the ESPHome
integration and every Jablotron entity (alarm panels, sensors, binary sensors,
programmable outputs, the wrong-code login event) appears natively, grouped
into sub-devices mirroring the real alarm devices and sections.

## Architecture

- `src/jablo2esphome/core.py` — a *hard fork* of the Home Assistant
  `jablotron100` integration. All protocol logic is byte-for-byte identical to
  upstream so fixes can be synced verbatim; the Home Assistant imports/coupling
  were removed and replaced by a thin runtime seam (`self._rt`, see
  `runtime.py`). There is a file-backed store (`storage.py`) instead of the
  Home Assistant configuration entry store.
- `src/jablo2esphome/{entities,state_sync,mapping}.py` — translates the core's
  entity model onto the ESPHome native API (entity categories, device classes,
  alarm control panel commands, events, sub-devices).
- `src/aioesphomeserver/` — a vendored and pruned copy of
  [aioesphomeserver](https://github.com/cjber/aioesphomeserver) (plaintext API
  password auth, `device_id`-aware list/states responses, no web server).
- `src/jablo2esphome/{bridge,cli,config,hub,runtime}.py` — the standalone
  application wiring: YAML config, event loop, native API server on `:6053`
  with mDNS advertisement, and a state poller pushing core state out.

## Run it

### natively

```sh
pip install .            # or: uv sync
cp config.example.yaml config.yaml
# edit config.yaml (set alarm_password at minimum)
jablo2esphome config.yaml
```

### with Docker

```sh
cp config.example.yaml config.yaml
# edit config.yaml; make sure serial_port points at the container path
docker compose up -d --build
```

Pass the Jablotron USB adapter through (see `devices:` in
`docker-compose.yml` and the udev rule documented there). For a lamp-path
container without compose, mount `/dev/hidraw*` yourself.

### validate a config

```sh
jablo2esphome config.yaml --check
```

## Home Assistant

1. In HA, go to **Settings → Devices & Services → Add Integration → ESPHome**.
2. Either pick the discovered bridge (mDNS advertises on `:6053`) or add it by
   IP address.
3. No password or encryption key is required — the bridge uses modern plaintext
   ESPHome transport (legacy `api_password` was removed in ESPHome 2026.1).
   Leave the encryption key field blank.

## Configuration

See [config.example.yaml](config.example.yaml) for all keys and defaults.

Notable points:

- `serial_port: auto` autodetects the Jablotron USB adapter (`16D6:0008`, i.e.
  `hidraw*`). Give a fixed `/dev/...` path to avoid surprises when other USB
  HID devices change `hidraw` numbering.
- `alarm_password` is the alarm panel master code. The bridge never sends it
  over the network; it is used only for panel login and the wrong-code event.
- `unique_id` pins the device's ESPHome MAC address so Home Assistant keeps
  device identity across restarts.

## Development

```sh
uv sync
uv run pytest            # 364 protocol tests against the de-HA'd core
uv run jablo2esphome --help
```

## Acknowledgements

This project stands almost entirely on other people's work, and it would not
exist without it:

- **[kukulich/home-assistant-jablotron100](https://github.com/kukulich/home-assistant-jablotron100)**
  — the original Home Assistant integration by Jaroslav Hanslík (@kukulich) and
  contributors. The entire Jablotron protocol implementation in
  `src/jablo2esphome/core.py` is a hard fork of it: reverse-engineering the
  Jablotron 100 serial protocol, the device/section/PG packet formats, and the
  packet captures behind the tests are their work, and are what make this
  bridge possible.
- **[cjber/aioesphomeserver](https://github.com/cjber/aioesphomeserver)** by
  Pete Keen — the native API server that `src/aioesphomeserver/` is vendored
  and pruned from.
- **[esphome/aioesphomeapi](https://github.com/esphome/aioesphomeapi)** and
  **[ESPHome](https://esphome.io)** by Otto Winter and the ESPHome project —
  the native API protocol definitions, message types and reference client that
  this bridge implements against.