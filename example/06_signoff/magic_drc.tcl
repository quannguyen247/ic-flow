# Read the final layout
drc off
gds read $::env(GDS_FILE)
load counter4

# Flatten so every shape is checked together with its neighbours
select top cell
flatten counter4_flat
load counter4_flat
select top cell

# Run the full SKY130 rule deck
drc euclidean on
drc style drc(full)
drc on
drc check
drc catchup

# Print each error type and the total
set total 0
foreach {message boxes} [drc listall why] {
    puts "MAGIC_DRC_ERROR [llength $boxes] $message"
    incr total [llength $boxes]
}
puts "MAGIC_DRC_TOTAL $total"

quit -noprompt
