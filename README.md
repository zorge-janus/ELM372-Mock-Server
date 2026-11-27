# ELM372 Mock Server

A local **ELM327 / Renault KWP2000** emulator for testing DDT Mobile. The repository retains the ELM372 name, while the emulated adapter protocol is ELM327. There is no graphical scenario selector: select the required JSON scenario using the `--scenario` argument.

**No vehicle connection is required.** The server operates over Windows Bluetooth Serial Port Profile (incoming COM port) or local TCP. Write and fault-clearing commands are not executed.

## Windows Quick Start

1. Install Python 3.10 or later (`py -3 --version`).
2. For Bluetooth support, run `py -3 -m pip install pyserial`.
3. Create an **incoming** Bluetooth COM port in Windows settings, pair the PC with the Android device, and identify the COM port number.
4. For the `climate_ddt_0456` scenario, place the original `Clim_J81_Serie_(vers07).json` file in the repository directory. This file is **not distributed** with the server.
5. Run `START_BLUETOOTH.bat` and enter the scenario name and incoming COM port number.
6. In DDT Mobile 0.4.5.6, select the PC as the Bluetooth device, run Scan, open CLIMAT (address `29`), and start continuous reading. Export and share the diagnostic log after completing the scenario.

Direct command-line usage:

```bat
py -3 elm_mock.py --list-scenarios
py -3 elm_mock.py --scenario climate_ddt_0456 --serial COM9 --definition "Clim_J81_Serie_(vers07).json"
py -3 elm_mock.py --scenario climate_faults_fast --serial COM9 --definition "Clim_J81_Serie_(vers07).json"
py -3 elm_mock.py --scenario replay --serial COM9
py -3 elm_mock.py --scenario climate_ddt_0456 --host 127.0.0.1 --port 35000 --definition "Clim_J81_Serie_(vers07).json"
```

The batch files select scenarios by name without a graphical interface. Scenario names correspond to JSON files in `scenarios/`. The `--scenario` argument accepts only names from this directory; arbitrary paths and absolute paths are rejected.

By default, TCP listens **only** on 127.0.0.1. Android TCP connections require TCP transport support in the APK and configuration of the PC's private IP address. TCP is not password-protected: **do not expose it to the internet**.

## Available Scenarios

| Name | Mode | Purpose |
|---|---|---|
| `replay` | Cyclic recorded responses | Baseline testing of seven ECUs, including ABS, climate control, and other modules |
| `climate_nominal` | Dynamic CLIMAT | Temperature, PTC heating, A/C, and equipment without injected faults |
| `climate_ddt_0456` | Dynamic CLIMAT | Complete 240-second acceptance test for DDT Mobile 0.4.5.6 |
| `climate_faults_fast` | Dynamic CLIMAT | The same fault cycle at four times the speed (60 seconds) |

### climate_ddt_0456 — Scenario Timeline

| Time since reading 21C0/21C1/21C2/2182 began | Expected data |
|---|---|
| 0–30 s | Cold cabin, engine stopped |
| 30–120 s | Engine running, PTC heating stages, warm-up |
| 120–180 s | A/C request, compressor operation, and simulated pressure |
| 180–200 s | `CC présent capteur freon condenseur=Defaut` (active fault) |
| 180–240 s | `CC mémo capteur freon condenseur=Defaut` (stored fault) |
| 200–220 s | `CO présent sonde évapo=Defaut` |
| 200–240 s | `CO mémo sonde évapo=Defaut` |
| 210–230 s | `ABS absent=Absent`, fault counter = 3 in 2182 |
| 210–220 s | `21C1 → NO DATA`, testing data recovery |
| 240 s | Scenario repeats and simulated fault flags reset |

These faults are **synthetic** and are not based on Renault's physical operating thresholds. Register `21C0` contains faults as ordinary bit-level diagnostic parameters, while `2182` contains communication flags and counters. Fields not modified dynamically retain their recorded values.

## Supported Commands and Data

The server emulates ATZ, ATI, ATRV, ATE0/1, ATL0/1, ATS0/1, ATH0, ATAT0, ATSTFF, ATSP5, ATPC, ATSH81xxF1, ATFI, ATDP, ATDPN, and KWP requests 21xx/22xxxx/1Axx/17FF00 available in the replay corpus.

Unknown ECU or register returns NO DATA; unsupported commands return ?. Write requests are not simulated. Use `--speed 0` for no response delay or `--speed 1` to reproduce recorded delays (default: 0.1). ATRV reports a simulated 14.2 V, not an actual vehicle voltage.

The `scenarios/replay_corpus.xz.b64` corpus contains 368 previously recorded responses from seven ECUs (01, 0D, 12, 26, 29, 2C, 7A). It is compressed for storage in Git and decompressed in memory at startup.

**The VIN has been replaced with the test identifier `VF1MOCK0000000001`.** The original vehicle identifier is not published in the public repository.

Dynamic values require the original DDT JSON definition, which specifies exact bit offsets, field sizes, and scaling factors. Without this definition, only the `replay` scenario can run.

The server prints the ECU address, request, and response to the terminal. After testing, export Diagnostic Logs from DDT Mobile: these contain `sample`, `fault_snapshot`, and raw HEX frames. **The server does not automatically save the Android application's diagnostic log.**

## Testing

Run the test suite manually:

```bat
py -3 -m unittest discover -s tests -v
```

The tests cover initialization of seven ECUs, ABS and CLIMAT replay, scenario selection, dynamic bit encoding, active and stored faults, network flags, and the 240-second cycle. These tests do not replace real Bluetooth SPP integration testing or vehicle testing with the original DDT JSON definition.

**No GitHub Actions:** this repository contains no CI workflows. Tests are run manually.

## Repository Structure

```text
elm_mock.py
dynamic.py
dataset.py
START_BLUETOOTH.bat
START_TCP.bat
scenarios/
  replay.json
  climate_nominal.json
  climate_ddt_0456.json
  climate_faults_fast.json
  replay_corpus.xz.b64
tests/
  test_mock.py
  test_dynamic.py
README.md
```
