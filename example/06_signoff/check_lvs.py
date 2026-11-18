import pya

# lvs_file comes from KLayout's -rd option
database = pya.LayoutVsSchematic()
database.read(lvs_file)
reference = database.xref()

# Every circuit pair (top and standard cells) must match
matched = 0
top_matched = False
for pair in reference.each_circuit_pair():
    layout_circuit = pair.first()
    netlist_circuit = pair.second()

    if layout_circuit is None or netlist_circuit is None or pair.status() != reference.Match:
        raise RuntimeError("Unmatched circuit pair in LVS database")

    matched += 1
    if layout_circuit.name.lower() == "counter4" and netlist_circuit.name.lower() == "counter4":
        top_matched = True

if not top_matched or matched < 2:
    raise RuntimeError("Top or standard-cell comparisons missing")

print("LVS database: %d matching circuit pairs including counter4" % matched)
