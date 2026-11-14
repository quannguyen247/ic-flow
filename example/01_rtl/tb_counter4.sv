`timescale 1ns / 1ps
module tb_counter4;

    // Clock & reset
    reg clk = 0, rst_n = 1;
    always #5 clk = ~clk;

    // DUT I/O
    reg        enable = 0;
    wire [3:0] count;

    // Tied-off scan ports (only the post-DFT netlist has them)
    reg  scan_clk = 0, test_mode = 0, scan_enable = 0, scan_in = 0;
    wire scan_out;

    // Error counter & waveform file name
    integer errors = 0;
    reg [8*256-1:0] vcd_file;

    // .* connects ports by name: works for both RTL and scan netlist
    counter4 u_dut (.*);

    // Waveform dump: vvp sim.vvp +vcd=<file>
    initial if ($value$plusargs("vcd=%s", vcd_file)) begin
        $dumpfile(vcd_file);
        $dumpvars(0, u_dut);
    end

    // Reference model: expected count
    reg [3:0] expected = 0;
    always @(posedge clk or negedge rst_n)
        if (!rst_n)      expected <= 0;
        else if (enable) expected <= expected + 1;

    // Checker: compare DUT with the model at every falling edge
    always @(negedge clk)
        if (count !== expected) begin
            $display("[%0t] FAIL: expected %0d, got %0d", $time, expected, count);
            errors = errors + 1;
        end

    // Stimulus: reset, count, hold, resume, short reset
    initial begin
        // Test 1: async reset (1 -> 0 edge)
        #1 rst_n = 0;

        // Test 2: count up through rollover (32 cycles)
        @(negedge clk) rst_n = 1; enable = 1;
        repeat (32) @(posedge clk);

        // Test 3: hold while disabled
        @(negedge clk) enable = 0;
        repeat (3) @(posedge clk);

        // Test 4: resume counting
        @(negedge clk) enable = 1;
        repeat (3) @(posedge clk);

        // Test 5: short reset pulse between clock edges (only an async reset sees it)
        @(negedge clk) #2 rst_n = 0;
        #1 rst_n = 1;
        repeat (3) @(posedge clk);

        @(negedge clk) #1; // let the checker finish its last comparison
        if (errors == 0) $display("PASS: counter reset, count, rollover and hold");
        else             $display("FAIL: %0d errors", errors);
        $finish;
    end

endmodule
