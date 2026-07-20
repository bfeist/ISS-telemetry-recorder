# ISS Telemetry Recording — Data Format

This document describes the on-disk format produced by
[ISS-telemetry-recorder.py](src/ISS-telemetry-recorder.py). It is intended for
anyone reading, parsing, or archiving the recorded data.

## Monitored channels (PUIs)

The recorder currently subscribes to **337 PUIs**, grouped below by ISS
segment / module. Each PUI has its own `<PUI>.txt` file in every day folder
(the two `TIME_*` channels are the exception — see
[Special channels](#special-channels)). The authoritative list is the `items`
array in [ISS-telemetry-recorder.py](src/ISS-telemetry-recorder.py).

Two views of the same 337 channels are given below: a **by-location** summary
(which module/segment each PUI belongs to) and, at the end of this document, a
[**full per-PUI reference**](#full-pui-reference) with a description and
engineering units for every channel, grouped by the responsible flight-control
discipline. See [Where the PUI definitions come from](#where-the-pui-definitions-come-from)
for the source of that metadata.

### By location (ISS segment / module)

**Quest Joint Airlock** (58): `AIRLOCK000001`–`AIRLOCK000058` (contiguous)

**Nodes 1/2/3 — Unity, Harmony, Tranquility** (29): `NODE1000001`, `NODE1000002`, `NODE2000001`–`NODE2000007`, `NODE3000001`–`NODE3000020`

**US Laboratory — Destiny** (102): `USLAB000001`–`USLAB000102` (contiguous)

**Z1 truss segment** (15): `Z1000001`–`Z1000015` (contiguous)

**Port truss segments P1–P6** (27): `P1000001`–`P1000009`, `P3000001`, `P3000002`, `P4000001`–`P4000008`, `P6000001`–`P6000008`

**Starboard truss segments S0–S6** (40): `S0000001`–`S0000013`, `S1000001`–`S1000009`, `S3000001`, `S3000002`, `S4000001`–`S4000008`, `S6000001`–`S6000008`

**Russian Segment** (25): `RUSSEG000001`–`RUSSEG000025` (contiguous)

**Station time / AOS** (2): `TIME_000001`, `TIME_000002`

**Mobile Transporter — CSA** (2): `CSAMT000001`, `CSAMT000002`

**SSRMS / Canadarm2 — CSA** (11): `CSASSRMS001`–`CSASSRMS011` (contiguous)

**SPDM / Dextre — CSA** (22): `CSASPDM0001`–`CSASPDM0022` (contiguous)

**Mobile Base System — CSA** (4): `CSAMBS00001`, `CSAMBS00002`, `CSAMBA00003`, `CSAMBA00004`

> Note: subscribing to a PUI does not guarantee a file every day — a channel
> only produces a `.txt` file on days it actually sent updates. (For example, a
> given day folder may contain far fewer than 337 files.)

## Where the PUI definitions come from

PUI descriptions, engineering units, and enumerated state values are **not**
present in the recorded data or anywhere in this repository — the recorder only
stores `TimeStamp Value` pairs. The metadata in the reference below is compiled
from two external catalogs:

- **`PUIList.xml`** — the official ISSLIVE symbol catalog published by NASA via
  Lightstreamer at
  `https://demos.lightstreamer.com/ISSLive/assets/PUIList.xml`
  (fetched by [get_puis.py](src/test_scripts/get_puis.py); it is downloaded on
  demand and is **not** checked into this repo). It is a UTF-16 XML file
  (root `<ISSLivePUIList created="Sep Tue 20 17:22 2011">`) that groups
  `<Symbol>` entries under `<Discipline>` elements. For each symbol it provides,
  among other fields:
  - `Public_PUI` — the PUI used on the feed (e.g. `USLAB000058`)
  - `Description` — human-readable meaning (e.g. "Cabin pressure")
  - `UNITS` — engineering units (e.g. `PSI`, `DEG`, `CNT` = counts)
  - `ENUM` — value→meaning map for discrete/status channels
  - `ENG_NOM` / `OPS_NOM` — engineering & operations nomenclature
  - `Format_Spec`, `MIN`, `MAX` — display format and expected range
    This catalog covers 298 of the 337 monitored PUIs.
- **ISS-Mimic public-telemetry catalog** — the remaining 39 channels are the CSA
  robotics PUIs (`CSASSRMS*`, `CSASPDM*`, `CSAMBS*`, `CSAMBA*`, `CSAMT*`), which
  are carried on the ISSLIVE feed but are **absent from `PUIList.xml`**. Their
  definitions come from the community ISS-Mimic project's
  `Telemetry/ISS_Public_Telemetry.xlsx`
  (<https://github.com/ISS-Mimic/Mimic>); the `CSASSRMS*` joint meanings are also
  documented inline in [canadarm-telemetry.py](src/test_scripts/canadarm-telemetry.py).

The `Discipline` names are NASA flight-control console call signs — e.g. **EVA**
(Extravehicular Activity), **ETHOS** (Environmental & Thermal Operating Systems),
**CDH** (Command & Data Handling), **SPARTAN** (Station Power, Articulation,
Thermal & Analysis), **CATO** (Communication & Tracking Officer), **ADCO**
(Attitude Determination & Control Officer), **VVO** (Visiting Vehicle Officer),
**ODIN** (Onboard, Data, Interfaces & Networks), and **TOPO** (Trajectory
Operations Officer). A `/` (e.g. `ADCO/TOPO`) marks a channel shared between
consoles.

## Source of the data

The recorder subscribes to the public **ISSLIVE** Lightstreamer feed at
`push.lightstreamer.com` (adapter set `ISSLIVE`). Each telemetry channel is
identified by a **PUI** (Public Payload Unique Identifier) such as
`AIRLOCK000001` or `USLAB000006`. The recorder subscribes to a fixed subset
(337 PUIs) defined in the `items` list in the main script; see
[Monitored channels (PUIs)](#monitored-channels-puis) for the list and
[Where the PUI definitions come from](#where-the-pui-definitions-come-from) for
how each channel is documented.

For each subscribed item the feed delivers two fields:

- `TimeStamp` — the sample time as GMT decimal (see [Timestamp format](#timestamp-format))
- `Value` — the sample value, as a string

## Directory layout

Data is written under the folder given by the `RAW_FOLDER` environment variable
(`/data` inside Docker), into a UTC date-partitioned tree:

```
<RAW_FOLDER>/
└── iss_telemetry/
    └── YYYY/            # UTC year
        └── MM/          # UTC month
            └── DD/      # UTC day
                ├── <PUI>.txt      # one file per telemetry channel
                ├── AOS.log        # signal-acquisition status log
                ├── master.log     # session / heartbeat / memory log
                ├── connection.log # Lightstreamer connection events
                └── error.log      # errors (only present if errors occurred)
```

The date used for partitioning is the **UTC wall-clock date at the moment the
update is written** (not derived from the sample's own timestamp). A single
recording session that crosses UTC midnight therefore writes into two adjacent
day folders.

Example folder:
`.../iss_telemetry/2026/06/25/`

## Per-channel telemetry files (`<PUI>.txt`)

Each telemetry channel is appended to a plain-text file named after its PUI,
e.g. `AIRLOCK000001.txt`, `Z1000013.txt`, `USLAB000006.txt`.

- One sample per line.
- Each line is: `<TimeStamp> <Value>` separated by a single space, terminated
  by `\n`.
- Lines are appended in arrival order (which is normally, but not strictly
  guaranteed to be, chronological).
- **Consecutive duplicate suppression:** if an update has the exact same
  `(TimeStamp, Value)` as the previous update for that same PUI, it is skipped
  and not written. (This de-duplication does _not_ apply to the special
  `TIME_000001` channel — which is not written to disk at all; see below.)

Example (`AIRLOCK000001.txt`):

```
4224.014583888915 -0.004250000230967998504638671875
4224.014861666693 -0.02866799943149089813232421875
4224.021528333359 -0.004250000230967998504638671875
```

### Value column

The value is written verbatim as received from the feed. Its meaning and format
depend on the channel:

- Many analog channels are full double-precision floats printed with all
  significant digits (e.g. `-0.32370645123589036895594972520484589040279388427734375`).
- Discrete / status channels are small integers, commonly `0` / `1`
  (e.g. `Z1000013.txt`).

There is no unit or type metadata in the file itself. Refer to the ISSLIVE PUI
list / NASA documentation to interpret a given PUI's engineering units.

## Timestamp format

The `TimeStamp` is the ISSLIVE **GMT decimal** value: fractional hours elapsed
since the start of the (GMT/UTC) year.

```
TimeStamp = day_of_year * 24 + hour + minute/60 + second/3600
```

where `day_of_year` is 1-based (Jan 1 = day 1).

To decode it (see [convert_zips_to_utc_folders.py](src/process_historical_telemetry/convert_zips_to_utc_folders.py)):

```
day_of_year = int(TimeStamp // 24)
remainder   = TimeStamp - day_of_year * 24
hour        = int(remainder)
remainder  -= hour
minute      = int(remainder * 60)
second      = (remainder * 60 - minute) * 60
```

**Worked example:** `4224.014583888915`
→ `day_of_year = 176`, i.e. the 176th day of 2026 = **2026-06-25 00:00:52.502 UTC**.

Notes / caveats:

- The value carries **no year**. The year is inferred from context (the
  containing date folder, or the source archive's date). A value near the
  year boundary can roll over — decoding logic must handle `day_of_year`
  exceeding 365/366 by incrementing the year.
- Because it is hour-of-year, the same TimeStamp value repeats every year.

## Log / sidecar files

### `AOS.log`

Records **AOS (Acquisition Of Signal)** status transitions for the ISS
Ku-band link, derived from the `TIME_000001` channel. Format per line:

```
AOS <TimeStamp> <status>
```

where `<status>` is:

| value | meaning         |
| ----- | --------------- |
| `0`   | Signal Lost     |
| `1`   | Signal Acquired |
| `2`   | Stale Signal    |

A line is written whenever the status changes, and at least once every ~5
minutes even if unchanged.

Example:

```
AOS 4224.037777777778 1
AOS 4224.1386111111115 0
AOS 4224.14594388889 1
```

### `master.log`

Human-readable session log. Contains session start/restart banners, a
once-per-minute heartbeat ("Still recording: N total updates received …"),
periodic memory-usage lines, watchdog warnings, and shutdown notices. Lines are
prefixed with a `YYYY-MM-DD HH:MM:SS` UTC wall-clock timestamp.

### `connection.log`

Lightstreamer client connection lifecycle events (status changes such as
`CONNECTING`, `CONNECTED:WS-STREAMING`, `DISCONNECTED`, and property changes).
Also UTC-timestamped. Useful for correlating data gaps with connection drops.

### `error.log`

Only created if an error occurs. Contains UTC-timestamped error messages and
tracebacks from update handling, item errors, or unhandled exceptions.

## Special channels

- **`TIME_000001`** — subscribed to for AOS computation but **never written to a
  `.txt` file**. Its effect is reflected only in `AOS.log`.

## Historical archive conversion

Historical telemetry provided as dated ZIPs by the ISSMimic team can be
normalized into this same UTC-dated, one-file-per-PUI layout using
[convert_zips_to_utc_folders.py](src/process_historical_telemetry/convert_zips_to_utc_folders.py).
That script additionally **sorts each file chronologically**, discards
timestamps that don't fall within the expected date, and fully deduplicates
lines (not just consecutive duplicates). Live recordings are only
consecutive-duplicate suppressed and are not guaranteed globally sorted, so
consumers that need strict ordering should sort on read.

---

## Full PUI reference

All 337 monitored channels, grouped by NASA flight-control discipline (the console responsible for that system). Descriptions, units, and enumerated values are taken verbatim from the source catalogs described above; enumerations are shown only where short.

#### EVA — Extravehicular Activity (spacewalks, Quest airlock, EMU spacesuits)

| PUI             | Units | Description                                                                                                                      |
| --------------- | ----- | -------------------------------------------------------------------------------------------------------------------------------- |
| `AIRLOCK000001` | CNT   | Supplies power through the Umbilical Interface Assembly (UIA) to the spacesuits (EMU 1), Voltage                                 |
| `AIRLOCK000002` | CNT   | Supplies power through the Umbilical Interface Assembly (UIA) to the spacesuits (EMU 1), Current                                 |
| `AIRLOCK000003` | CNT   | Supplies power through the Umbilical Interface Assembly (UIA) to the spacesuits (EMU 2), Voltage                                 |
| `AIRLOCK000004` | CNT   | Supplies power through the Umbilical Interface Assembly (UIA) to the spacesuits (EMU 2), Current                                 |
| `AIRLOCK000005` | CNT   | In-flight Refill Unit (IRU), Voltage                                                                                             |
| `AIRLOCK000006` | CNT   | In-flight Refill Unit (IRU), Current                                                                                             |
| `AIRLOCK000007` | CNT   | Supplies power to the spacesuits (EVA Mobility Unit, EMU 1), Voltage                                                             |
| `AIRLOCK000008` | CNT   | Supplies power to the spacesuits (EVA Mobility Unit, EMU 1), Current                                                             |
| `AIRLOCK000009` | CNT   | Supplies power to the spacesuits (EVA Mobility Unit, EMU 2), Voltage                                                             |
| `AIRLOCK000010` | CNT   | Supplies power to the spacesuits (EVA Mobility Unit, EMU 2), Current                                                             |
| `AIRLOCK000011` | CNT   | Battery Charger Assembly (BCA) 1 Voltage                                                                                         |
| `AIRLOCK000012` | CNT   | Battery Charger Assembly (BCA) 1 Current                                                                                         |
| `AIRLOCK000013` | CNT   | Battery Charger Assembly (BCA) 2 Voltage                                                                                         |
| `AIRLOCK000014` | CNT   | Battery Charger Assembly (BCA) 2 Current                                                                                         |
| `AIRLOCK000015` | CNT   | Battery Charger Assembly (BCA) 3 Voltage                                                                                         |
| `AIRLOCK000016` | CNT   | Battery Charger Assembly (BCA) 3 Current                                                                                         |
| `AIRLOCK000017` | CNT   | Battery Charger Assembly (BCA) 4 Voltage                                                                                         |
| `AIRLOCK000018` | CNT   | Battery Charger Assembly (BCA) 4 Current                                                                                         |
| `AIRLOCK000019` | —     | Battery Charger Assembly (BCA) 1 Status — _values:_ 0=Normal; 1=No Data; 2=Missing Data; 3=Extra Data                            |
| `AIRLOCK000020` | —     | Battery Charger Assembly (BCA) 2 Status — _values:_ 0=Normal; 1=No Data; 2=Missing Data; 3=Extra Data                            |
| `AIRLOCK000021` | —     | Battery Charger Assembly (BCA) 3 Status — _values:_ 0=Normal; 1=No Data; 2=Missing Data; 3=Extra Data                            |
| `AIRLOCK000022` | —     | Battery Charger Assembly (BCA) 4 Status — _values:_ 0=Normal; 1=No Data; 2=Missing Data; 3=Extra Data                            |
| `AIRLOCK000023` | —     | Battery Charger Assembly (BCA) 1 Channel 1 Status _(enumerated)_                                                                 |
| `AIRLOCK000024` | —     | Battery Charger Assembly (BCA) 1 Channel 2 Status _(enumerated)_                                                                 |
| `AIRLOCK000025` | —     | Battery Charger Assembly (BCA) 1 Channel 3 Status _(enumerated)_                                                                 |
| `AIRLOCK000026` | —     | Battery Charger Assembly (BCA) 1 Channel 4 Status _(enumerated)_                                                                 |
| `AIRLOCK000027` | —     | Battery Charger Assembly (BCA) 1 Channel 5 Status _(enumerated)_                                                                 |
| `AIRLOCK000028` | —     | Battery Charger Assembly (BCA) 1 Channel 6 Status _(enumerated)_                                                                 |
| `AIRLOCK000029` | —     | Battery Charger Assembly (BCA) 2 Channel 1 Status _(enumerated)_                                                                 |
| `AIRLOCK000030` | —     | Battery Charger Assembly (BCA) 2 Channel 2 Status _(enumerated)_                                                                 |
| `AIRLOCK000031` | —     | Battery Charger Assembly (BCA) 2 Channel 3 Status _(enumerated)_                                                                 |
| `AIRLOCK000032` | —     | Battery Charger Assembly (BCA) 2 Channel 4 Status _(enumerated)_                                                                 |
| `AIRLOCK000033` | —     | Battery Charger Assembly (BCA) 2 Channel 5 Status _(enumerated)_                                                                 |
| `AIRLOCK000034` | —     | Battery Charger Assembly (BCA) 2 Channel 6 Status _(enumerated)_                                                                 |
| `AIRLOCK000035` | —     | Battery Charger Assembly (BCA) 3 Channel 1 Status _(enumerated)_                                                                 |
| `AIRLOCK000036` | —     | Battery Charger Assembly (BCA) 3 Channel 2 Status _(enumerated)_                                                                 |
| `AIRLOCK000037` | —     | Battery Charger Assembly (BCA) 3 Channel 3 Status _(enumerated)_                                                                 |
| `AIRLOCK000038` | —     | Battery Charger Assembly (BCA) 3 Channel 4 Status _(enumerated)_                                                                 |
| `AIRLOCK000039` | —     | Battery Charger Assembly (BCA) 3 Channel 5 Status _(enumerated)_                                                                 |
| `AIRLOCK000040` | —     | Battery Charger Assembly (BCA) 3 Channel 6 Status _(enumerated)_                                                                 |
| `AIRLOCK000041` | —     | Battery Charger Assembly (BCA) 4 Channel 1 Status _(enumerated)_                                                                 |
| `AIRLOCK000042` | —     | Battery Charger Assembly (BCA) 4 Channel 2 Status _(enumerated)_                                                                 |
| `AIRLOCK000043` | —     | Battery Charger Assembly (BCA) 4 Channel 3 Status _(enumerated)_                                                                 |
| `AIRLOCK000044` | —     | Battery Charger Assembly (BCA) 4 Channel 4 Status _(enumerated)_                                                                 |
| `AIRLOCK000045` | —     | Battery Charger Assembly (BCA) 4 Channel 5 Status _(enumerated)_                                                                 |
| `AIRLOCK000046` | —     | Battery Charger Assembly (BCA) 4 Channel 6 Status _(enumerated)_                                                                 |
| `AIRLOCK000047` | —     | Pumps atmosphere from Airlock into Node one during depress, voltage status. — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed |
| `AIRLOCK000048` | —     | Pumps atmosphere from Airlock into Node one during depress, switch status. — _values:_ 0=PUMP OFF CMD; 1=PUMP ON CMD             |

#### ETHOS — Environmental & Thermal Operating Systems (atmosphere, water recovery, cabin cooling)

| PUI             | Units | Description                                                                                                                                  |
| --------------- | ----- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `AIRLOCK000049` | CNT   | Crewlock Pressure                                                                                                                            |
| `AIRLOCK000050` | —     | Hi P O2 Supply valve position — _values:_ 0=CLOSED; 1=OPEN; 2=IN-TRANSIT; 3=FAILED                                                           |
| `AIRLOCK000051` | —     | Lo P O2 Supply Valve position — _values:_ 0=CLOSED; 1=OPEN; 2=IN-TRANSIT; 3=FAILED                                                           |
| `AIRLOCK000052` | —     | N2 Supply Valve position — _values:_ 0=CLOSED; 1=OPEN; 2=IN-TRANSIT; 3=FAILED                                                                |
| `AIRLOCK000053` | —     | Airlock Air Conditioner State — _values:_ 0=RESET; 1=DRAIN; 2=DRYOUT; 3=EIB OFF; 4=OFF; 5=ON; 6=STARTUP; 7=TEST                              |
| `AIRLOCK000054` | PSI   | Airlock Pressure                                                                                                                             |
| `AIRLOCK000055` | CNT   | Airlock Hi P O2 Tank Pressure                                                                                                                |
| `AIRLOCK000056` | CNT   | Airlock Lo P O2 Tank Pressure                                                                                                                |
| `AIRLOCK000057` | CNT   | Airlock N2 Tank Pressure                                                                                                                     |
| `NODE2000001`   | CNT   | Coolant water quantity (Node 2), MT                                                                                                          |
| `NODE2000002`   | CNT   | Coolant water quantity (Node 2), LT                                                                                                          |
| `NODE2000003`   | —     | Node 2 Air Conditioner State — _values:_ 0=RESET; 1=DRAIN; 2=DRYOUT; 3=EIB OFF; 4=OFF; 5=ON; 6=STARTUP; 7=TEST                               |
| `NODE2000006`   | CNT   | Air Cooling Fluid Temp (Node 2)                                                                                                              |
| `NODE2000007`   | CNT   | Avionics Cooling Fluid Temp (Node 2)                                                                                                         |
| `NODE3000001`   | PSIA  | Node 3 ppO2                                                                                                                                  |
| `NODE3000002`   | PSIA  | Node 3 ppN2                                                                                                                                  |
| `NODE3000003`   | PSIA  | Node 3 ppCO2                                                                                                                                 |
| `NODE3000004`   | —     | Urine Processor State — _values:_ 2=STOP; 4=SHUTDOWN; 8=MAINTENANCE; 16=NORMAL; 32=STANDBY; 64=IDLE; 128=SYSTEM INITIALIZED                  |
| `NODE3000005`   | PCT   | Urine Tank Qty                                                                                                                               |
| `NODE3000006`   | —     | Water Processor State — _values:_ 1=STOP; 2=SHUTDOWN; 3=STANDBY; 4=PROCESS; 5=HOT SERVICE; 6=FLUSH; 7=WARM SHUTDOWN                          |
| `NODE3000007`   | —     | Water Processor Step — _values:_ 0=NONE; 1=VENT; 2=HEATUP; 3=PURGE; 4=FLOW; 5=TEST; 6=TEST_SV_1; 7=TEST_SV_2; 8=SERVICE                      |
| `NODE3000008`   | PCT   | Waste Water Tank Qty                                                                                                                         |
| `NODE3000009`   | PCT   | Clean Water Tank Qty                                                                                                                         |
| `NODE3000010`   | —     | Oxygen Generator State — _values:_ 1=PROCESS; 2=STANDBY; 3=SHUTDOWN; 4=STOP; 5=VENT_DOME; 6=INERT_DOME; 7=FAST_SHUTDOWN; 8=N2_PURGE_SHUTDOWN |
| `NODE3000011`   | LBM/D | O2 Production rate                                                                                                                           |
| `NODE3000012`   | CNT   | Avionics Cooling Fluid Temp (Node 3)                                                                                                         |
| `NODE3000013`   | CNT   | Air Cooling Fluid Temp (Node 3)                                                                                                              |
| `NODE3000017`   | CNT   | Coolant water quantity (Node 3)                                                                                                              |
| `NODE3000018`   | —     | Node 3 Air Conditioner State — _values:_ 0=RESET; 1=DRAIN; 2=DRYOUT; 3=EIB OFF; 4=OFF; 5=ON; 6=STARTUP; 7=TEST                               |
| `NODE3000019`   | CNT   | Coolant water quantity (Node 3)                                                                                                              |
| `USLAB000053`   | PSIA  | Lab ppO2                                                                                                                                     |
| `USLAB000054`   | PSIA  | Lab ppN2                                                                                                                                     |
| `USLAB000055`   | PSIA  | Lab ppCO2                                                                                                                                    |
| `USLAB000056`   | CNT   | Coolant water quantity, LT (Lab)                                                                                                             |
| `USLAB000057`   | CNT   | Coolant water quantity, MT (Lab)                                                                                                             |
| `USLAB000058`   | PSI   | Cabin pressure                                                                                                                               |
| `USLAB000059`   | CNT   | Cabin temperature                                                                                                                            |
| `USLAB000060`   | CNT   | Avionics Cooling Fluid Temp (Lab)                                                                                                            |
| `USLAB000061`   | CNT   | Air Cooling Fluid Temp (Lab)                                                                                                                 |
| `USLAB000062`   | CNT   | Vacuum Resource System Valve Position                                                                                                        |
| `USLAB000063`   | CNT   | Vacuum Exhaust System Valve Position                                                                                                         |
| `USLAB000064`   | —     | Lab Port Air Conditioner State — _values:_ 0=RESET; 1=DRAIN; 2=DRYOUT; 3=EIB OFF; 4=OFF; 5=ON; 6=STARTUP; 7=TEST                             |
| `USLAB000065`   | —     | Lab Starboard Air Conditioner State — _values:_ 0=RESET; 1=DRAIN; 2=DRYOUT; 3=EIB OFF; 4=OFF; 5=ON; 6=STARTUP; 7=TEST                        |

#### CDH — Command & Data Handling (Multiplexer/Demultiplexer computers)

| PUI             | Units | Description                                                                                                                                     |
| --------------- | ----- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `AIRLOCK000058` | —     | Airlock Multiplexer/Demultiplexer (MDM) on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                      |
| `NODE1000001`   | —     | Node 1 Multiplexer/Demultiplexer (MDM) 1 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                     |
| `NODE1000002`   | —     | Node 1 Multiplexer/Demultiplexer (MDM) 2 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                     |
| `NODE2000004`   | —     | Node 2 Multiplexer/Demultiplexer (MDM) 2 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                     |
| `NODE2000005`   | —     | Node 2 Multiplexer/Demultiplexer (MDM) 1 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                     |
| `NODE3000014`   | —     | Hub Control Zone (HCZ) Multiplexer/Demultiplexer 2 (MDM) on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                     |
| `NODE3000015`   | —     | Node 3 Multiplexer/Demultiplexer (MDM) 2 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                     |
| `NODE3000016`   | —     | Hub Control Zone (HCZ) Multiplexer/Demultiplexer 1 (MDM) on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                     |
| `NODE3000020`   | —     | Node 3 Multiplexer/Demultiplexer (MDM) 1 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                     |
| `P1000006`      | —     | P1 Truss Multiplexer/Demultiplexer (MDM) 1 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                   |
| `P1000008`      | —     | Port Thermal Radiator (STR) Multiplexer/Demultiplexer (MDM) on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                  |
| `P1000009`      | —     | P1 Truss Multiplexer/Demultiplexer (MDM) 2 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                   |
| `P3000001`      | —     | P3 Truss Multiplexer/Demultiplexer (MDM) 1 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                   |
| `P3000002`      | —     | P3 Truss Multiplexer/Demultiplexer (MDM) 2 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                   |
| `P4000003`      | —     | Photovolatic Control Unit (PVCU) - Solar Array - 2A Multiplexer/Demultiplexer (MDM) 120 Volt On-Off Status — _values:_ 0=Not Enabled; 1=Enabled |
| `P4000006`      | —     | Photovolatic Control Unit (PVCU) - Solar Array - 4A Multiplexer/Demultiplexer (MDM) 120 Volt On-Off Status — _values:_ 0=Not Enabled; 1=Enabled |
| `P6000003`      | —     | Photovolatic Control Unit (PVCU) - Solar Array - 4B Multiplexer/Demultiplexer (MDM) 120 Volt On-Off Status — _values:_ 0=Not Enabled; 1=Enabled |
| `P6000006`      | —     | Photovolatic Control Unit (PVCU) - Solar Array - 2B Multiplexer/Demultiplexer (MDM) 120 Volt On-Off Status — _values:_ 0=Not Enabled; 1=Enabled |
| `S0000010`      | —     | External Control Zone Multiplexer/Demultiplexer (MDM) 1 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                      |
| `S0000011`      | —     | S0 Truss Multiplexer/Demultiplexer (MDM) 1 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                   |
| `S0000012`      | —     | External Control Zone Multiplexer/Demultiplexer (MDM) 2 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                      |
| `S0000013`      | —     | S0 Truss Multiplexer/Demultiplexer (MDM) 2 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                   |
| `S1000006`      | —     | Starboard Thermal Radiator (STR) Multiplexer/Demultiplexer (MDM) on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed             |
| `S1000007`      | —     | S1 Truss Multiplexer/Demultiplexer (MDM) 1 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                   |
| `S1000008`      | —     | S1 Truss Multiplexer/Demultiplexer (MDM) 2 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                   |
| `S3000001`      | —     | S3 Truss Multiplexer/Demultiplexer (MDM) 1 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                   |
| `S3000002`      | —     | S3 Truss Multiplexer/Demultiplexer (MDM) 2 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                   |
| `S4000003`      | —     | Photovolatic Control Unit (PVCU) - Solar Array - 1A Multiplexer/Demultiplexer (MDM) 120 Volt On-Off Status — _values:_ 0=Not Enabled; 1=Enabled |
| `S4000006`      | —     | Photovolatic Control Unit (PVCU) - Solar Array - 3A Multiplexer/Demultiplexer (MDM) 120 Volt On-Off Status — _values:_ 0=Not Enabled; 1=Enabled |
| `S6000003`      | —     | Photovolatic Control Unit (PVCU) - Solar Array - 3B Multiplexer/Demultiplexer (MDM) 120 Volt On-Off Status — _values:_ 0=Not Enabled; 1=Enabled |
| `S6000006`      | —     | Photovolatic Control Unit (PVCU) - Solar Array - 1B Multiplexer/Demultiplexer (MDM) 120 Volt On-Off Status — _values:_ 0=Not Enabled; 1=Enabled |
| `USLAB000066`   | —     | Command and Control (C&C) Multiplexer/Demultiplexer (MDM) 1 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                  |
| `USLAB000067`   | —     | Command and Control (C&C) Multiplexer/Demultiplexer (MDM) 2 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                  |
| `USLAB000068`   | —     | Command and Control (C&C) Multiplexer/Demultiplexer (MDM) 3 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                  |
| `USLAB000069`   | —     | Internal Control Zone Multiplexer/Demultiplexer (MDM) 1 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                      |
| `USLAB000070`   | —     | Internal Control Zone Multiplexer/Demultiplexer (MDM) 2 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                      |
| `USLAB000071`   | —     | Payload (PL) Multiplexer/Demultiplexer (MDM) 1 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                               |
| `USLAB000072`   | —     | Payload (PL) Multiplexer/Demultiplexer (MDM) 2 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                               |
| `USLAB000073`   | —     | Guidance, Navigation and Control (GNC) Multiplexer/Demultiplexer 1 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed           |
| `USLAB000074`   | —     | Guidance, Navigation and Control (GNC) Multiplexer/Demultiplexer 2 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed           |
| `USLAB000075`   | —     | Power Mangement Controller Unit (PMCU) 1 Multiplexer/Demultiplexer 1 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed         |
| `USLAB000076`   | —     | Power Mangement Controller Unit (PMCU) 2 Multiplexer/Demultiplexer 1 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed         |
| `USLAB000077`   | —     | US Lab Multiplexer/Demultiplexer (MDM) 1 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                     |
| `USLAB000078`   | —     | US Lab Multiplexer/Demultiplexer (MDM) 2 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                     |
| `USLAB000079`   | —     | US Lab Multiplexer/Demultiplexer (MDM) 3 on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                     |
| `USLAB000080`   | —     | Permanent Multipurpose Module - System Power voltage status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                                |

#### SPARTAN — Station Power, Articulation, Thermal & Analysis (solar arrays, thermal loops)

| PUI        | Units | Description                                                                                         |
| ---------- | ----- | --------------------------------------------------------------------------------------------------- |
| `P1000001` | CNT   | Loop B Pump Flowrate (kg/hr)                                                                        |
| `P1000002` | CNT   | Loop B PM Out Press (kPa)                                                                           |
| `P1000003` | CNT   | Loop B PM Out Temp (deg C)                                                                          |
| `P4000001` | CNT   | Photovolatic Control Unit (PVCU) - Solar Array - 2A - Drive Voltage                                 |
| `P4000002` | CNT   | Photovolatic Control Unit (PVCU) - Solar Array - 2A - Drive Current                                 |
| `P4000004` | CNT   | Photovolatic Control Unit (PVCU) - Solar Array - 4A - Drive Voltage                                 |
| `P4000005` | CNT   | Photovolatic Control Unit (PVCU) - Solar Array - 4A - Drive Current                                 |
| `P4000007` | DEG   | Photovolatic Control Unit (PVCU) - Solar Array - 2A - Beta Gimble Assembly (BGA) Position (degrees) |
| `P4000008` | DEG   | Photovolatic Control Unit (PVCU) - Solar Array - 4A - Beta Gimble Assembly (BGA) Position (degrees) |
| `P6000001` | CNT   | Photovolatic Control Unit (PVCU) - Solar Array - 4B - Drive Voltage                                 |
| `P6000002` | CNT   | Photovolatic Control Unit (PVCU) - Solar Array - 4B - Drive Current                                 |
| `P6000004` | CNT   | Photovolatic Control Unit (PVCU) - Solar Array - 2B - Drive Voltage                                 |
| `P6000005` | CNT   | Photovolatic Control Unit (PVCU) - Solar Array - 2B - Drive Current                                 |
| `P6000007` | DEG   | Photovolatic Control Unit (PVCU) - Solar Array - 4B - Beta Gimble Assembly (BGA) Position (degrees) |
| `P6000008` | DEG   | Photovolatic Control Unit (PVCU) - Solar Array - 2B - Beta Gimble Assembly (BGA) Position (degrees) |
| `S1000001` | CNT   | Loop A Pump Flowrate (kg/hr)                                                                        |
| `S1000002` | CNT   | Loop A PM Out Press (kPa)                                                                           |
| `S1000003` | CNT   | Loop A PM Out Temp (deg C)                                                                          |
| `S4000001` | CNT   | Photovolatic Control Unit (PVCU) - Solar Array - 1A - Drive Voltage                                 |
| `S4000002` | CNT   | Photovolatic Control Unit (PVCU) - Solar Array - 1A - Drive Current                                 |
| `S4000004` | CNT   | Photovolatic Control Unit (PVCU) - Solar Array - 3B - Drive Voltage                                 |
| `S4000005` | CNT   | Photovolatic Control Unit (PVCU) - Solar Array - 3B - Drive Current                                 |
| `S4000007` | DEG   | Photovolatic Control Unit (PVCU) - Solar Array - 1A - Beta Gimble Assembly (BGA) Position (degrees) |
| `S4000008` | DEG   | Photovolatic Control Unit (PVCU) - Solar Array - 3A - Beta Gimble Assembly (BGA) Position (degrees) |
| `S6000001` | CNT   | Photovolatic Control Unit (PVCU) - Solar Array - 3B - Drive Voltage                                 |
| `S6000002` | CNT   | Photovolatic Control Unit (PVCU) - Solar Array - 3B - Drive Current                                 |
| `S6000004` | CNT   | Photovolatic Control Unit (PVCU) - Solar Array - 1B - Drive Voltage                                 |
| `S6000005` | CNT   | Photovolatic Control Unit (PVCU) - Solar Array - 1B - Drive Current                                 |
| `S6000007` | DEG   | Photovolatic Control Unit (PVCU) - Solar Array - 3B - Beta Gimble Assembly (BGA) Position (degrees) |
| `S6000008` | DEG   | Photovolatic Control Unit (PVCU) - Solar Array - 1B - Beta Gimble Assembly (BGA) Position (degrees) |

#### CATO — Communication & Tracking Officer (S-band, Ku-band, UHF, audio, video)

| PUI           | Units  | Description                                                                                              |
| ------------- | ------ | -------------------------------------------------------------------------------------------------------- |
| `P1000004`    | DEG    | S-Band Radio Frequency Group (RFG 2) Azimuth Gimbal Position                                             |
| `P1000005`    | DEG    | S-Band Radio Frequency Group (RFG 2) Elevation Gimbal Position                                           |
| `P1000007`    | —      | S-Band Radio Frequency Group (RFG 2), on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed |
| `S1000004`    | DEG    | S-Band Radio Frequency Group (RFG 1) Azimuth Gimbal Position                                             |
| `S1000009`    | —      | S-Band Radio Frequency Group (RFG 1), on-off status — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed |
| `USLAB000088` | —      | Ku-Band Video Downlink Channel 1 Activity — _values:_ 0=INACTIVE; 1=ACTIVE                               |
| `USLAB000089` | —      | Ku-Band Video Downlink Channel 2 Activity — _values:_ 0=INACTIVE; 1=ACTIVE                               |
| `USLAB000090` | —      | Ku-Band Video Downlink Channel 3 Activity — _values:_ 0=INACTIVE; 1=ACTIVE                               |
| `USLAB000091` | —      | Ku-Band Video Downlink Channel 4 Activity — _values:_ 0=INACTIVE; 1=ACTIVE                               |
| `USLAB000092` | INTEGR | Active String of S-Band                                                                                  |
| `USLAB000093` | —      | Internal Audio Controller (IAC) - IAC-1 Active/Backup Indication — _values:_ 0=Backup; 1=Active          |
| `USLAB000094` | —      | Internal Audio Controller (IAC) - IAC-2 Active/Backup Indication — _values:_ 0=Backup; 1=Active          |
| `USLAB000095` | INTEGR | Video Source Routed to Downlink 1                                                                        |
| `USLAB000096` | INTEGR | Video Source Routed to Downlink 2                                                                        |
| `USLAB000097` | INTEGR | Video Source Routed to Downlink 3                                                                        |
| `USLAB000098` | INTEGR | Video Source Routed to Downlink 4                                                                        |
| `USLAB000099` | —      | Space-To-Space Radio (UHF) 1 Power — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                  |
| `USLAB000100` | —      | Space-To-Space Radio (UHF) 2 Power — _values:_ 0=Off-Ok; 1=Not-Off Ok; 3=Not-Off Failed                  |
| `USLAB000101` | —      | Space-To-Space Radio Frame Sync Lock — _values:_ 0=Frame Sync unlocked; 1=Frame Sync locked              |
| `Z1000013`    | —      | Ku-Band Transmit — _values:_ 0=RESET; 1=NORMAL                                                           |
| `Z1000014`    | DEG    | Ku-Band SGANT Elevation Position                                                                         |
| `Z1000015`    | —      | Ku-Band SGANT Cross-Elevation Position                                                                   |

#### SPARTAN / VVO (shared — rotary joints)

| PUI        | Units | Description                                                              |
| ---------- | ----- | ------------------------------------------------------------------------ |
| `S0000001` | DEG   | Starboard Thermal Radiator Rotating Joint (TRRJ) Position (degrees)      |
| `S0000002` | DEG   | Port Thermal Radiator Rotating Joint (TRRJ) Position (degrees)           |
| `S0000003` | DEG   | Solar Alpha Rotary Joint (SARJ) Starboard Joint Angle Position (degrees) |
| `S0000004` | DEG   | Solar Alpha Rotary Joint (SARJ) Port Joint Angle Position (degrees)      |

#### VVO — Visiting Vehicle Officer (rendezvous/docking, rotary joints, attitude)

| PUI            | Units | Description                                                                                                                                                                                                                                 |
| -------------- | ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `S0000005`     | DEG   | Solar Alpha Rotary Joint (SARJ) Port Joint Angle Commanded Position (degrees)                                                                                                                                                               |
| `S0000006`     | —     | External Thermal Control System (ETCS) - Thermal Radiator Rotating Joint (TRRJ) - Loop B - Software mode — _values:_ 1=STANDBY; 2=RESTART; 3=CHECKOUT; 4=DIRECTED_POSITION; 5=AUTOTRACK; 6=BLIND; 7=SHUTDOWN; 8=SWITCHOVER                  |
| `S0000007`     | —     | External Thermal Control System (ETCS) - Thermal Radiator Rotating Joint (TRRJ) - Loop A - Software mode — _values:_ 1=STANDBY; 2=RESTART; 3=CHECKOUT; 4=DIRECTED_POSITION; 5=AUTOTRACK; 6=BLIND; 7=SHUTDOWN; 8=SWITCHOVER                  |
| `S0000008`     | —     | External Primary Solar Alpha Rotary Joint (SARJ) Port Mode — _values:_ 1=STANDBY; 2=RESTART; 3=CHECKOUT; 4=DIRECTED_POSITION; 5=AUTOTRACK; 6=BLIND; 7=SHUTDOWN; 8=SWITCHOVER                                                                |
| `S0000009`     | —     | External Primary Solar Alpha Rotary Joint (SARJ) Starboard Mode — _values:_ 1=STANDBY; 2=RESTART; 3=CHECKOUT; 4=DIRECTED_POSITION; 5=AUTOTRACK; 6=BLIND; 7=SHUTDOWN; 8=SWITCHOVER                                                           |
| `USLAB000081`  | —     | Attitude Maneuver In Progress status — _values:_ 0=FALSE; 1=TRUE                                                                                                                                                                            |
| `RUSSEG000001` | —     | Russian Segment Station Mode - Service Module (SM) — _values:_ 1=Crew Rescue; 2=Survival; 3=Reboost; 4=Proximity Operations; 5=EVA; 6=Microgravity; 7=Standard                                                                              |
| `RUSSEG000002` | —     | First Kurs Equipment Kit Operating — _values:_ 0=Undetermined State; 1=SM KURS Equipment Set1 Operating-RS                                                                                                                                  |
| `RUSSEG000003` | —     | Second Kurs Equipment Kit Operating — _values:_ 0=Undetermined State; 1=SM KURS Equipment Set2 Operating-RS                                                                                                                                 |
| `RUSSEG000004` | —     | Service Module Kurs P1, P2 Failure - Russian Segment — _values:_ 0=Undeterminated State; 1=SM KURS P1, P2 Failure-RS                                                                                                                        |
| `RUSSEG000005` | M     | Distance from Service Module (SM) Kurs (Range)                                                                                                                                                                                              |
| `RUSSEG000006` | M/S   | Rate from Service Module (SM) Kurs (Range Rate)                                                                                                                                                                                             |
| `RUSSEG000007` | —     | Service Module (SM) Kurs-P Test Mode - Russian Segment — _values:_ 0=Undetermined State; 1=SM KURS-P Test Mode-RS                                                                                                                           |
| `RUSSEG000008` | —     | Service Module (SM) Kurs-P "Capture" Signal Availability — _values:_ 0=Undetermined State; 1=SM KURS-P Capture Signal -RS                                                                                                                   |
| `RUSSEG000009` | —     | Service Module (SM) Kurs-P Target Acquisition Signal - Russian Segment — _values:_ 0=Undetermined State; 1=SM KURS-P Target Acquisition Signal-RS                                                                                           |
| `RUSSEG000010` | —     | Service Module (SM) Kurs-P Functional Mode Signal - Russian Segment — _values:_ 0=Undetermined State; 1=SM KURS-P Functional Mode Signal-RS                                                                                                 |
| `RUSSEG000011` | —     | Service Module (SM) Kurs-P Standby Mode - Russian Segment — _values:_ 0=Undetermined State; 1=SM KURS-P In Standby Mode-RS                                                                                                                  |
| `RUSSEG000012` | —     | Service Module Docking Flag — _values:_ 0=Undetermined State; 1=SM Docking Flag-RS                                                                                                                                                          |
| `RUSSEG000013` | —     | Service Module (SM) Forward Docking Port Engaged — _values:_ 0=Undetermined State; 1=SM Docking Port Engaged from Xfer Side-RS                                                                                                              |
| `RUSSEG000014` | —     | Service Module (SM) Aft Docking Port Engaged — _values:_ 0=Undetermined State; 1=SM Docking Port Engaged from Instr Compartment Side-RS                                                                                                     |
| `RUSSEG000015` | —     | Service Module (SM) Nadir (Down-looking) Docking Port Engaged - Along Y-Axis — _values:_ 0=Undetermined State; 1=SM Docking Port Engaged Below (along SM -Y Axis)-RS                                                                        |
| `RUSSEG000016` | —     | Functional Cargo Block (FGB) Nadir (Down-looking) Docking Port Engaged - Along Y-Axis — _values:_ 0=Undetermined State; 1=FGB Bottom Docking Port Engaged (along SM -Y Axis)-RS                                                             |
| `RUSSEG000017` | —     | Service Module (SM) Nadir (Down-looking) Universal Docking Module (UDM) Docking Port Engaged - Along Y-Axis — _values:_ 0=Undetermined State; 1=SM Bottom UDM Docking Port Engaged (along SM -Y Axis)-RS                                    |
| `RUSSEG000018` | —     | Mini Research Module (MRM) 1 Docking Port Engaged - Russian Segment — _values:_ 0=Undetermined State; 1=MRM1 Docking Port Engaged-RS                                                                                                        |
| `RUSSEG000019` | —     | Mini Research Module (MRM) 2 Docking Port Engaged - Russian Segment — _values:_ 0=Undetermined State; 1=MRM2 Docking Port Engaged-RS                                                                                                        |
| `RUSSEG000020` | —     | Service Module - Docked Vehicle Hooks Closed - Russian Segment — _values:_ 0=Undetermined State; 1=Docked Vehicle Hooks Closed-RS                                                                                                           |
| `RUSSEG000021` | —     | Service Module - Russian Guidance, Navigation, and Control - Active Attitude Mode - Russian Segment — _values:_ 0=Inertial Attitude; 1=LVLH SM; 2=Solar Orientation; 3=Current LVLH; 4=Current Inertial Attitude; 5=Damping; 6=TEA; 7=X-POP |
| `RUSSEG000022` | —     | Service Module - Russian Guidance, Navigation, and Control - Motion Control - Russian Segment — _values:_ 0=Undetermined State; 1=SM SUDN Controls the Motion (RS master)-RS                                                                |
| `RUSSEG000023` | —     | Service Module - Russian Guidance, Navigation, and Control - Prepared to Free Drift Mode Transition - Russian Segment — _values:_ 0=Undetermined State; 1=SM SUDN Prepared to Free Drift Mode Transition-RS                                 |
| `RUSSEG000024` | —     | Service Module - Russian Guidance, Navigation, and Control - Thruster Operation Mode Terminated - Russian Segment — _values:_ 0=Pre-Starting Procedure Or Thruster Operation Readiness; 1=Thruster Operation Mode is Terminated             |

#### CATO / VVO (shared)

| PUI        | Units | Description                                                    |
| ---------- | ----- | -------------------------------------------------------------- |
| `S1000005` | DEG   | S-Band Radio Frequency Group (RFG 1) Elevation Gimbal Position |

#### ADCO — Attitude Determination & Control Officer (CMGs, attitude, GPS, state vector)

| PUI           | Units   | Description                                                                                                                         |
| ------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `USLAB000001` | —       | Control Moment Gyroscope (CMG)-1 On-Line — _values:_ 0=NOT IN USE; 1=IN USE                                                         |
| `USLAB000002` | —       | Control Moment Gyroscope (CMG)-2 On-Line — _values:_ 0=NOT IN USE; 1=IN USE                                                         |
| `USLAB000003` | —       | Control Moment Gyroscope (CMG)-3 On-Line — _values:_ 0=NOT IN USE; 1=IN USE                                                         |
| `USLAB000004` | —       | Control Moment Gyroscope (CMG)-4 On-Line — _values:_ 0=NOT IN USE; 1=IN USE                                                         |
| `USLAB000005` | —       | Number of Control Moment Gyroscope (CMG)s Online                                                                                    |
| `USLAB000006` | FT-LB   | Control Moment Gyroscope (CMG) Control Torque - Roll (N-m)                                                                          |
| `USLAB000007` | FT-LB   | Control Moment Gyroscope (CMG) Control Torque - Pitch (N-m)                                                                         |
| `USLAB000008` | FT-LB   | Control Moment Gyroscope (CMG) Control Torque - Yaw (N-m)                                                                           |
| `USLAB000009` | FT-LB-S | Active Control Moment Gyroscope (CMG) Momentum (Nms)                                                                                |
| `USLAB000011` | —       | Desaturation Request (Enabled/Inhibited) — _values:_ 0=ENABLED; 1=INHIBITED                                                         |
| `USLAB000013` | —       | US Attitude Source — _values:_ 0=NONE; 1=GPS1; 2=GPS2; 3=Russian_Attitude; 4=Ku_Band                                                |
| `USLAB000014` | —       | US Rate Source — _values:_ 0=NONE; 1=RGA1; 2=RGA2; 3=RUSSIAN                                                                        |
| `USLAB000015` | —       | US State Vector Source — _values:_ 0=NO_SOURCE; 1=Unused; 2=Unused; 3=RUSSIAN; 4=GPS1_DETERMINISTIC; 5=GPS2_DETERMINISTIC; 6=GROUND |
| `USLAB000016` | —       | Attitude Controller Type — _values:_ 0=ATTITUDE HOLD; 1=TEA                                                                         |
| `USLAB000017` | —       | Attitude Control Reference Frame — _values:_ 0=LVLH; 1=Inertial; 2=XPOP                                                             |
| `USLAB000018` | —       | US Current Local Vertical Local Horizontal (LVLH) Attitude Quaternion Component 0                                                   |
| `USLAB000019` | —       | US Current Local Vertical Local Horizontal (LVLH) Attitude Quaternion Component 1                                                   |
| `USLAB000020` | —       | US Current Local Vertical Local Horizontal (LVLH) Attitude Quaternion Component 2                                                   |
| `USLAB000021` | —       | US Current Local Vertical Local Horizontal (LVLH) Attitude Quaternion Component 3                                                   |
| `USLAB000022` | RAD     | US Attitude Roll Error (deg)                                                                                                        |
| `USLAB000023` | RAD     | US Attitude Pitch Error (deg)                                                                                                       |
| `USLAB000024` | RAD     | US Attitude Yaw Error (deg)                                                                                                         |
| `USLAB000025` | RAD/S   | US Inertial Attitude Rate X (deg/s)                                                                                                 |
| `USLAB000026` | RAD/S   | US Inertial Attitude Rate Y (deg/s)                                                                                                 |
| `USLAB000027` | RAD/S   | US Inertial Attitude Rate Z (deg/s)                                                                                                 |
| `USLAB000028` | —       | US Commanded Attitude Quaternion Component 0                                                                                        |
| `USLAB000029` | —       | US Commanded Attitude Quaternion Component 1                                                                                        |
| `USLAB000030` | —       | US Commanded Attitude Quaternion Component 2                                                                                        |
| `USLAB000031` | —       | US Commanded Attitude Quaternion Component 3                                                                                        |
| `USLAB000038` | FT-LB-S | Active Control Moment Gyroscope (CMG) Momentum Capacity (Nms)                                                                       |
| `USLAB000039` | KG      | ISS Total Mass (kg)                                                                                                                 |
| `USLAB000040` | DEG     | Solar Beta Angle (degrees)                                                                                                          |
| `USLAB000041` | —       | Loss of CMG Attitude Control (LOAC) Caution Message In Alarm — _values:_ 0=FALSE; 1=TRUE                                            |
| `USLAB000042` | —       | Loss of ISS Attitude Control (LOAC) Caution Message In Alarm — _values:_ 0=FALSE; 1=TRUE                                            |
| `USLAB000043` | —       | Global Positioning System (GPS-1) Ops Status _(enumerated)_                                                                         |
| `USLAB000044` | —       | Global Positioning System (GPS-2) Ops Status _(enumerated)_                                                                         |
| `USLAB000045` | DEGF    | Spin Motor Spin Bearing Temperature - Control Moment Gyroscope (CMG) 1 (deg C)                                                      |
| `USLAB000046` | DEGF    | Spin Motor Spin Bearing Temperature - Control Moment Gyroscope (CMG) 2 (deg C)                                                      |
| `USLAB000047` | DEGF    | Spin Motor Spin Bearing Temperature - Control Moment Gyroscope (CMG) 3 (deg C)                                                      |
| `USLAB000048` | DEGF    | Spin Motor Spin Bearing Temperature - Control Moment Gyroscope (CMG) 4 (deg C)                                                      |
| `USLAB000049` | DEGF    | Hall Resolver Spin Bearing Temperature - Control Moment Gyroscope (CMG) 1 (deg C)                                                   |
| `USLAB000050` | DEGF    | Hall Resolver Spin Bearing Temperature - Control Moment Gyroscope (CMG) 2 (deg C)                                                   |
| `USLAB000051` | DEGF    | Hall Resolver Spin Bearing Temperature - Control Moment Gyroscope (CMG) 3 (deg C)                                                   |
| `USLAB000052` | DEGF    | Hall Resolver Spin Bearing Temperature - Control Moment Gyroscope (CMG) 4 (deg C)                                                   |
| `Z1000001`    | G       | Control Moment Gyroscope (CMG)-1 Vibration (g)                                                                                      |
| `Z1000002`    | G       | Control Moment Gyroscope (CMG)-2 Vibration (g)                                                                                      |
| `Z1000003`    | G       | Control Moment Gyroscope (CMG)-3 Vibration (g)                                                                                      |
| `Z1000004`    | G       | Control Moment Gyroscope (CMG)-4 Vibration (g)                                                                                      |
| `Z1000005`    | AMP     | Control Moment Gyroscope (CMG)-1 Spin Motor Current (amps)                                                                          |
| `Z1000006`    | AMP     | Control Moment Gyroscope (CMG)-2 Spin Motor Current (amps)                                                                          |
| `Z1000007`    | AMP     | Control Moment Gyroscope (CMG)-3 Spin Motor Current (amps)                                                                          |
| `Z1000008`    | AMP     | Control Moment Gyroscope (CMG)-4 Spin Motor Current (amps)                                                                          |
| `Z1000009`    | RPM     | Control Moment Gyroscope (CMG) 1 Wheel Speed (rpm)                                                                                  |
| `Z1000010`    | RPM     | Control Moment Gyroscope (CMG) 2 Wheel Speed (rpm)                                                                                  |
| `Z1000011`    | RPM     | Control Moment Gyroscope (CMG) 3 Wheel Speed (rpm)                                                                                  |
| `Z1000012`    | RPM     | Control Moment Gyroscope (CMG) 4 Wheel Speed (rpm)                                                                                  |

#### ADCO / VVO (shared)

| PUI            | Units | Description                                                                                                        |
| -------------- | ----- | ------------------------------------------------------------------------------------------------------------------ |
| `USLAB000010`  | PCT   | Control Moment Gyroscope (CMG) Momentum Percentage (%)                                                             |
| `USLAB000012`  | —     | US Guidance, Navigation and Control (GNC) Mode _(enumerated)_                                                      |
| `RUSSEG000025` | —     | Service Module - Russian Guidance, Navigation, and Control - Current Dynamic Mode - Russian Segment _(enumerated)_ |

#### ADCO / TOPO (shared — propagated state vector)

| PUI           | Units | Description                                                                       |
| ------------- | ----- | --------------------------------------------------------------------------------- |
| `USLAB000032` | FT    | US Guidance, Navigation and Control (GNC) J2000 Propagated State Vector - X (km)  |
| `USLAB000033` | FT    | US Guidance, Navigation and Control (GNC) J2000 Propagated State Vector - Y (km)  |
| `USLAB000034` | FT    | US Guidance, Navigation and Control (GNC) J2000 Propagated State Vector - Z (km)  |
| `USLAB000035` | FT/S  | US Guidance, Navigation and Control (GNC) J2000 Propagated State Vector - X (m/s) |
| `USLAB000036` | FT/S  | US Guidance, Navigation and Control (GNC) J2000 Propagated State Vector - Y (m/s) |
| `USLAB000037` | FT/S  | US Guidance, Navigation and Control (GNC) J2000 Propagated State Vector - Z (m/s) |

#### ODIN — Onboard, Data, Interfaces & Networks (C&C computers, onboard time, command counters)

| PUI           | Units  | Description                                                                                                                                                          |
| ------------- | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USLAB000082` | INTEGR | Standard Command Counter - Count of standard commands received by the ISS Command and Control Computer                                                               |
| `USLAB000083` | INTEGR | Data Load Command Counter - Count of data load commands received by the ISS Command and Control Computer                                                             |
| `USLAB000084` | S      | ISS Command and Control Multiplexer/Demultiplexer Onboard Time (course)                                                                                              |
| `USLAB000085` | S      | ISS Command and Control Multiplexer/Demultiplexer Onboard Time (fine)                                                                                                |
| `USLAB000087` | INTEGR | PCS Connection Count - Number of crew Portable Computer System laptops active and connected to the Primary Command and Control (C&C) Multiplexer/Demultiplexer (MDM) |

#### ODIN / VVO (shared — station mode)

| PUI           | Units | Description                                                                                                                               |
| ------------- | ----- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `USLAB000086` | —     | ISS Station Mode — _values:_ 1=Standard; 2=Microgravity; 4=Reboost; 8=Proximity_Ops; 16=External_Ops; 32=Survival; 64=ASCR; 127=all_modes |

#### TOPO — Trajectory Operations Officer (state vector)

| PUI           | Units | Description           |
| ------------- | ----- | --------------------- |
| `USLAB000102` | S     | State vector time tag |

#### Station time

| PUI           | Units | Description               |
| ------------- | ----- | ------------------------- |
| `TIME_000001` | MS    | Greenwich Mean Time (GMT) |
| `TIME_000002` | YR    | Year                      |

#### CSA robotics — Mobile Servicing System (SSRMS / Canadarm2, SPDM / Dextre, MBS, MT)

These channels are **not** in the ISSLIVE `PUIList.xml`; definitions come from the ISS-Mimic public-telemetry catalog. `SR/SY/SP` = Shoulder Roll/Yaw/Pitch, `EP` = Elbow Pitch, `WP/WY/WR` = Wrist Pitch/Yaw/Roll.

| PUI           | Units | Description                                                                                                                                               |
| ------------- | ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `CSAMT000001` | cm    | MSS MT Position Float                                                                                                                                     |
| `CSAMT000002` | —     | MSS MT Utility Port ID (which Worksite MT is connected to, WS1 though WS8) — _values:_ 1=WS1 \| 2=WS2 \| 3=WS3 \| 4=WS4 \| 5=WS5 \| 6=WS6 \|7=WS7 \|8=WS8 |
| `CSASSRMS001` | —     | MSS EDCD SSRMS Base Location                                                                                                                              |
| `CSASSRMS002` | —     | MSS EDCD SSRMS Base Location                                                                                                                              |
| `CSASSRMS003` | —     | MSS EDCD SSRMS Operating Base (Which LEE is Base) — _values:_ 0=Lee A \| 5=Lee B                                                                          |
| `CSASSRMS004` | DEG   | SSRMS SR Measured Joint Position                                                                                                                          |
| `CSASSRMS005` | DEG   | SSRMS SY Measured Joint Position                                                                                                                          |
| `CSASSRMS006` | DEG   | SSRMS SP Measured Joint Position                                                                                                                          |
| `CSASSRMS007` | DEG   | SSRMS EP Measured Joint Position                                                                                                                          |
| `CSASSRMS008` | DEG   | SSRMS WP Measured Joint Position                                                                                                                          |
| `CSASSRMS009` | DEG   | SSRMS WY Measured Joint Position                                                                                                                          |
| `CSASSRMS010` | DEG   | SSRMS WR Measured Joint Position                                                                                                                          |
| `CSASSRMS011` | —     | MSS OCS Payload Status SSRMS Tip LEE — _values:_ 0=Released\|1=Captive\|2=Captured                                                                        |
| `CSASPDM0001` | —     | MSS OCS Base Location SPDM                                                                                                                                |
| `CSASPDM0002` | —     | MSS OCS Base Location SPDM                                                                                                                                |
| `CSASPDM0003` | DEG   | MSS OCS SPDM 1 SR Measured Joint Position                                                                                                                 |
| `CSASPDM0004` | DEG   | MSS OCS SPDM 1 SY Measured Joint Position                                                                                                                 |
| `CSASPDM0005` | DEG   | MSS OCS SPDM 1 SP Measured Joint Position                                                                                                                 |
| `CSASPDM0006` | DEG   | MSS OCS SPDM 1 EP Measured Joint Position                                                                                                                 |
| `CSASPDM0007` | DEG   | MSS OCS SPDM 1 WP Measured Joint Position                                                                                                                 |
| `CSASPDM0008` | DEG   | MSS OCS SPDM 1 WY Measured Joint Position                                                                                                                 |
| `CSASPDM0009` | DEG   | MSS OCS SPDM 1 WR Measured Joint Position                                                                                                                 |
| `CSASPDM0010` | —     | MSS Payload Status OCS SPDM Arm 1 OTCM — _values:_ 0=Released\|1=Captive\|2=Captured                                                                      |
| `CSASPDM0011` | DEG   | MSS OCS SPDM 2 SR Measured Joint Position                                                                                                                 |
| `CSASPDM0012` | DEG   | MSS OCS SPDM 2 SY Measured Joint Position                                                                                                                 |
| `CSASPDM0013` | DEG   | MSS OCS SPDM 2 SP Measured Joint Position                                                                                                                 |
| `CSASPDM0014` | DEG   | MSS OCS SPDM 2 EP Measured Joint Position                                                                                                                 |
| `CSASPDM0015` | DEG   | MSS OCS SPDM 2 WP Measured Joint Position                                                                                                                 |
| `CSASPDM0016` | DEG   | MSS OCS SPDM 2 WY Measured Joint Position                                                                                                                 |
| `CSASPDM0017` | DEG   | MSS OCS SPDM 2 WR Measured Joint Position                                                                                                                 |
| `CSASPDM0018` | —     | MSS Payload Status OCS SPDM Arm 2 OTCM?                                                                                                                   |
| `CSASPDM0019` | —     | MSS Payload Status OCS SPDM Arm 2 OTCM — _values:_ 0=Released\|1=Captive\|2=Captured                                                                      |
| `CSASPDM0020` | DEG   | MSS OCS SPDM Body Roll Joint Position                                                                                                                     |
| `CSASPDM0021` | —     | MSS Payload Status OCS SPDM Body?                                                                                                                         |
| `CSASPDM0022` | —     | MSS Payload Status OCS SPDM Body — _values:_ 0=Released\|1=Captive\|2=Captured                                                                            |
| `CSAMBS00001` | —     | MSS OCS Payload Status MBS MCAS?                                                                                                                          |
| `CSAMBS00002` | —     | MSS OCS Payload Status MBS MCAS — _values:_ 0=Released\|1=Captured                                                                                        |
| `CSAMBA00003` | —     | MSS OCS Payload Status MBS POA?                                                                                                                           |
| `CSAMBA00004` | —     | MSS OCS Payload Status MBS POA — _values:_ 0=Released\|1=Captive\|2=Captured                                                                              |
