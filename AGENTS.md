# Project instructions

Write project files, documentation, source comments and reports in English.
`README_VI.md` is the Vietnamese documentation exception. Reply to the user in
Vietnamese unless they ask for another language.

Keep the user's `example/` layout. Reuse the existing ORFS scripts and local
compatibility code before adding another implementation. Keep generated outputs
under ignored `build/` directories and preserve earlier runs.

Use Icarus Verilog (`iverilog` + `vvp`) for direct RTL and netlist simulation. Check `iverilog` before
choosing a simulator. Fault uses its own Icarus backend; identify it separately
in results. Record the tools, constraints and scope of measured results.

Run `make test` for driver changes and `make all` when the tool flow changes.
Update the knowledge graph with `graphify update .` after code changes.

Keep functional RTL free of pre-inserted scan. Step 03 must add scan with tools;
physical design must consume that generated netlist. Every numbered folder
needs runnable practice files and stage-local output access.
