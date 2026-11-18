# 06. Signoff

This stage runs every check on the GDS from step 05 and on the routed netlist,
then packs the results into a handoff folder. The 3D viewer in
[view3d/](view3d/README.md) also reads the GDS here; no check depends on it.

| Group | Checks |
| --- | --- |
| Physical | KLayout DRC and LVS, Magic DRC, Magic + Netgen LVS, antenna |
| Logic | Post-route simulation, LEC |
| Timing | RC extraction, multi-corner STA |
| Package | Handoff folder with checksums |
| View | 3D viewer of the GDS (optional) |

## Files

| File | Purpose |
| --- | --- |
| [run_signoff.py](run_signoff.py) | Runs every check and the packaging |
| [check_lvs.py](check_lvs.py) | Reads the KLayout LVS database and checks every circuit pair |
| [lec.tcl](lec.tcl) | Yosys proves two netlists equivalent |
| [scan_off.v](scan_off.v) | Scan netlist with the scan inputs tied to 0, for LEC |
| [extract_rc.tcl](extract_rc.tcl) | OpenRCX extracts wire parasitics for one RC corner |
| [sta.tcl](sta.tcl) | OpenROAD timing for one mode and corner |
| [magic_drc.tcl](magic_drc.tcl) | Magic DRC with the full SKY130 deck |
| [magic_extract.tcl](magic_extract.tcl) | Magic extracts a SPICE netlist from the GDS |
| [write_netlist.tcl](write_netlist.tcl) | OpenROAD writes the netlist with power pins |
| [netgen_lvs.tcl](netgen_lvs.tcl) | Netgen compares the layout and the netlist |
| [antenna.tcl](antenna.tcl) | OpenROAD antenna check |
| [view3d/](view3d/README.md) | GDS → three.js 3D viewer |
| [Makefile](Makefile) | Stage entry point |

## Checks

| Check | Tool | Question it answers |
| --- | --- | --- |
| DRC | KLayout | Geometry rules, FEOL and BEOL, off-grid |
| LVS | KLayout | Layout vs netlist, virtual substrate, tap cells left out |
| Post-route sim | Icarus | Do `tb_counter4` and `tb_scan` still pass on the routed netlist (no SDF)? |
| LEC | Yosys | Is each netlist logically the same as the one before it? |
| RC extraction | OpenRCX | Wire R and C for min, nom and max corners |
| STA | OpenROAD | Setup, hold, reset recovery/removal, slew, cap and fanout |
| DRC | Magic | Geometry rules with the full SKY130 deck (second DRC engine) |
| LVS | Magic + Netgen | Layout vs netlist, with real substrate and tap cells (second LVS engine) |
| Antenna | OpenROAD | Can long wires damage gates during manufacturing? |

LEC compares three pairs:

| Gold | Gate | Proves |
| --- | --- | --- |
| RTL | synthesized netlist | Synthesis kept the function |
| RTL | scan netlist, scan inputs at 0 | Scan insertion did not change functional mode |
| scan netlist | routed netlist | P&R (buffers, clock tree) kept the function, scan mode included |

STA runs 5 PVT corners (ss, tt, ff) × 3 RC corners × 2 modes = 30 runs.
Every run must have non-negative setup and hold slack and no slew, capacitance or
fanout violation. `check_setup` must find no unclocked or unconstrained pin.

## Run

From this directory:

```sh
make drc       # KLayout DRC
make lvs       # KLayout LVS
make lec
make sta
make signoff   # all checks above, post-route simulation, Magic DRC, netgen LVS, antenna
make           # signoff plus the handoff package
make view3d    # optional 3D viewer, see view3d/README.md
```

Magic, Netgen and the sky130A PDK must be in `PDK_ROOT`
(default `~/.local/share/eda/pdk-digital`). `make doctor` checks them.

Outputs in `build/`:

| File | Contents |
| --- | --- |
| `drc.lyrdb` | KLayout DRC results (open in the marker browser) |
| `lvs.lvsdb` | KLayout LVS results |
| `counter4_extracted.cir` | Netlist KLayout extracted from the layout |
| `post_route/`, `post_route_scan/` | Post-route simulation waveforms |
| `lec_*.log` | Equivalence proofs |
| `counter4_{min,nom,max}.spef` | Wire parasitics per RC corner |
| `sta_<pvt>_<rc>_<mode>.log` | Timing reports |
| `magic_drc.log` | Magic DRC results |
| `lvs_netgen.rpt` | Netgen LVS report |
| `antenna.log` | Antenna check results |
| `handoff/` | GDS, DEF, netlist, SPEFs, SDCs and `manifest.json` |

The other files are intermediates: patched decks (`drc_full.lydrc`,
`lvs_compat.lylvs`), the LVS reference `functional_reference.cdl`, Magic's
`counter4_layout.spice` and `*.ext`, the power-pin netlist `counter4_pwr.v`,
and one log per command (`lvs*.log`, `rcx_*.log`, `magic_extract.log`,
`netgen_lvs.log`, ...).

`manifest.json` lists every file with its SHA-256 checksum and the check
results. The worst slacks are also in `../build/latest/summary.json` under `sta`.

## Limits

Not checked: power, IR drop, electromigration and crosstalk (OpenSTA has no
signal-integrity analysis).

The block is a hard macro. Before fabrication it must go into a full chip,
for example a Tiny Tapeout or Caravel harness, which adds the pad ring, metal
density fill, the seal ring and the shuttle's own precheck. The manifest
records `foundry_signoff=false`.

The SDC assumes the parent releases `rst_n` through a reset synchronizer
clocked by `clk`.

## Exercise

In `lec_scan_vs_route.log`, find how many net pairs were proven. Then open
the worst setup report (ss corner, max RC) and the worst hold report (ff
corner, min RC) and explain why those corners are the worst. Load `drc.lyrdb`
in the KLayout marker browser and check that it is empty. Compare the
checksum of `build/handoff/counter4.gds` with the one in `manifest.json`.
