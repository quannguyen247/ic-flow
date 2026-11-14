# 01. Functional RTL

The counter has one four-bit register. On a rising clock edge, `enable=1`
increments it modulo 16; otherwise it holds its value. `rst_n=0` clears it
asynchronously. There are no scan ports or scan multiplexers in the RTL.

## Files

| File | Purpose |
| --- | --- |
| [counter4.v](counter4.v) | Synthesizable functional counter |
| [tb_counter4.sv](tb_counter4.sv) | Reset, count, rollover and hold checks |
| [Makefile](Makefile) | Stage entry point |

## Run

From this directory:

```sh
make
```

Open `build/sim_rtl.log` and `build/rtl/waveform.vcd` (view with GTKWave).
The expected message is `PASS: counter reset, count, rollover and hold`.
The test counts through two rollovers, holds for three cycles, resumes and
checks reset between clock edges.

## Exercise

Change the RTL increment from 1 to 2 and run `make` again. The test should fail
on its first expected count, showing it detects the functional mismatch.
Restore the increment to 1 and rerun before continuing.

Next: [synthesis](../02_synthesis/README.md).
