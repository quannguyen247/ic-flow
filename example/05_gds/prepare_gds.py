import re

import pya

# 12 signal pins: clk, rst_n, enable, scan_in, scan_enable, scan_clk, test_mode
# (7 inputs) and count[3:0], scan_out (5 outputs)
EXPECTED_PINS = 12

# in_gds, in_def, out_gds and lvs_gds come from KLayout's -rd option
layout = pya.Layout()
layout.read(in_gds)
top = layout.cell("counter4")
if top is None:
    raise RuntimeError("counter4 missing from GDS")

# Copy the pin shapes (purpose 16) to the drawing layer (purpose 20)
pin_count = 0
for number in (67, 68, 69, 70, 71, 72):
    pin = layout.find_layer(number, 16)
    if pin is None:
        continue

    drawing = layout.layer(number, 20)
    for shape in top.shapes(pin).each():
        if not shape.is_text():
            top.shapes(drawing).insert(shape)
            pin_count += 1

if pin_count != EXPECTED_PINS:
    raise RuntimeError("Expected %d top-level signal pin shapes, got %d" % (EXPECTED_PINS, pin_count))

# Read the pins and power stripes from the final DEF
with open(in_def) as f:
    text = f.read()

metal_layers = {"met1": 68, "met2": 69, "met3": 70, "met4": 71, "met5": 72}

# KLayout labels each pin with its net name; relabel it with the pin name
pins_match = re.search(r"(?ms)^PINS\b.*?^END PINS", text)
if pins_match is None:
    raise RuntimeError("DEF has no PINS section: " + in_def)
pins_section = pins_match.group(0)
pins = re.findall(
    r"-\s+(\S+)\s+\+\s+NET\s+\S+.*?LAYER\s+(met[1-5])\b.*?PLACED\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)",
    pins_section,
    re.S,
)
if len(pins) != EXPECTED_PINS:
    raise RuntimeError("Expected %d pins in the DEF, got %d" % (EXPECTED_PINS, len(pins)))

labels_fixed = 0
for name, layer, x, y in pins:
    label = layout.find_layer(metal_layers[layer], 5)
    texts = []
    if label is not None:
        texts = [s for s in top.shapes(label).each()
                 if s.is_text() and s.text.x == int(x) and s.text.y == int(y)]
    if len(texts) != 1:
        raise RuntimeError("Expected one label at pin " + name)

    if texts[0].text.string != name:
        texts[0].text = pya.Text(name, texts[0].text.trans)
        labels_fixed += 1
stripe = re.compile(
    r"\+\s+ROUTED\s+(met[1-5])\s+\d+.*?"
    r"\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)",
    re.S,
)

# Put a VDD and a VSS label on one stripe of each net
for net in ("VDD", "VSS"):
    block = re.search(r"(?ms)^\s*-\s+%s\s+\(.*?;" % net, text)
    if block is None:
        raise RuntimeError("Missing power special net " + net)

    route = stripe.search(block.group(0))
    if route is None:
        raise RuntimeError("Missing power stripe geometry for " + net)

    layer, x1, y1, x2, y2 = route.groups()
    x = (int(x1) + int(x2)) // 2
    y = (int(y1) + int(y2)) // 2
    number = metal_layers[layer]

    metal = layout.find_layer(number, 20)
    point = pya.Point(x, y)
    if metal is None or not any(s.bbox().contains(point) for s in top.shapes(metal).each()):
        raise RuntimeError("No matching drawing geometry at " + net + " stripe")

    top.shapes(layout.layer(number, 5)).insert(pya.Text(net, pya.Trans(x, y)))

# Write the deliverable GDS
layout.write(out_gds)

# Write the LVS input: same layout plus a virtual substrate on layer 236/0
top.shapes(layout.layer(236, 0)).insert(top.bbox())
layout.write(lvs_gds)

print("Prepared GDS: %d signal pin shapes; %d pin labels renamed; VDD and VSS labels added"
      % (pin_count, labels_fixed))
