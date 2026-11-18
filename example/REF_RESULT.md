# Reference results

Recorded on 18 November 2026 from the functional-only counter and tool-inserted
scan flow. `make all` completed; the summary records `requested_stage=all`,
`status=passed`.

## Tool versions

| Tool | Version |
| --- | --- |
| Icarus Verilog | 13.0 |
| Yosys | 0.68+, commit `a34d3baae` |
| Fault | 0.9.4 |
| OpenROAD | `v2.0-17598-ga008522d8` |
| KLayout | 0.26.9, OpenLane v0.22 image |
| Magic | 8.3.685 |
| Netgen | 1.5.325 |
| ORFS | `68b1f26134c63d072a19b3a514c5a99effd08501` |
| PDK | sky130A (ciel), in `PDK_ROOT` |

## Observed results

| Stage | Result |
| --- | --- |
| RTL | Four functional ports; no scan hardware; Icarus PASS |
| Synthesis | Four mapped FFs; post-synthesis Icarus PASS |
| Scan insertion | Fault generated a four-bit internal chain |
| DFT simulation | Functional counter and all 16 serial words/capture cases PASS in Icarus |
| ATPG | 102/122 stuck-at faults (83.6066%), 7 compacted vectors |
| Scan fault simulation | 44 more faults detected by `tb_scan`; total 146/146 (100%) |
| Physical input | SHA-256 matches the generated DFT netlist |
| KLayout DRC | 0 items; FEOL, BEOL and off-grid |
| KLayout LVS | Matched; virtual substrate, 13 tap instances excluded |
| Post-route simulation (06) | Functional and scan tests PASS in Icarus |
| LEC | RTL = synth, RTL = scan netlist (scan off), scan = routed (270 pairs) |
| Magic DRC | 0 errors |
| Netgen LVS | Circuits match uniquely |
| Antenna | 0 violations |
| GDSII | `05_gds/build/counter4.gds`, 112,518 bytes |
| Handoff | GDS, DEF, final netlist, 3 SPEFs, two SDCs and SHA-256 manifest |

STA: 5 PVT corners × 3 RC corners, no slew, capacitance or fanout violation.

| Timing mode | Clock period | Setup slack (tt, nom RC) | Worst setup | Worst hold |
| --- | --- | --- | --- | --- |
| Functional | 10 ns | +7.13 ns | +6.22 ns (ss_n40C, max RC) | +0.41 ns |
| Scan shift | 100 ns | +89.12 ns | +88.22 ns | +0.35 ns (ff_n40C, min RC) |

Functional hold includes the reset removal check. Six direct simulations used
Icarus without SDF. ATPG used Fault's internal Icarus backend.

## Evidence and scope

Run: `~/.cache/ic-flow/800ab5fb0487/20261118T151227_604023Z/`.
Stage-local `build/` links expose its outputs. Read `run.json`, `summary.json`,
stage logs and `06_signoff/build/handoff/manifest.json`.

GDS SHA-256 (the GDS stores a write timestamp, so each run gets a new hash):

```text
0f8048dbd2cb8227167523552f2e531bd32ead94c318848b44c168f9292302af
```

Not covered: power, IR drop, electromigration, crosstalk, and the chip-level
pad ring, density fill and seal ring. The package records
`foundry_signoff=false`.
