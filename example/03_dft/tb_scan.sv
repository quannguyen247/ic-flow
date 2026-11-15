`timescale 1ns / 1ps

module tb_scan;

    // DUT signals
    reg clk, scan_clk, rst_n, enable;
    reg scan_enable, scan_in, test_mode;
    wire [3:0] count;
    wire scan_out;

    // Testbench control & monitoring
    integer word_index, bit_index, error_count;
    reg observed;
    reg [3:0] word_in, word_out, before_count, captured_count;
    reg [8*256-1:0] vcd_file;

    counter4 u_dut (
        .clk(clk), .rst_n(rst_n), .enable(enable), .count(count),
        .scan_clk(scan_clk), .test_mode(test_mode), .scan_enable(scan_enable),
        .scan_in(scan_in), .scan_out(scan_out)
    );

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    // Waveform dump, enabled by: vvp sim.vvp +vcd=<file>
    initial begin
        if ($value$plusargs("vcd=%s", vcd_file)) begin
            $dumpfile(vcd_file);
            $dumpvars(0, u_dut);
        end
    end

    // Shift one bit into the chain, sample scan_out before the clock edge
    task shift_bit(input value);
    begin
        scan_clk = 1'b0;
        scan_in = value;
        #1 observed = scan_out;
        scan_clk = 1'b1;
        #1 scan_clk = 1'b0;
        #1;
    end
    endtask

    // Shift word_in into the chain
    task load_chain;
    begin
        for (bit_index = 3; bit_index >= 0; bit_index = bit_index - 1)
            shift_bit(word_in[bit_index]);
    end
    endtask

    // Shift the chain out into word_out
    task read_chain;
    begin
        for (bit_index = 3; bit_index >= 0; bit_index = bit_index - 1) begin
            shift_bit(1'b0);
            word_out[bit_index] = observed;
        end
    end
    endtask

    // Compare two four-bit values, count mismatches
    task check4(input [3:0] got, input [3:0] expected, input [8*24-1:0] what);
    begin
        if (got !== expected) begin
            $display("[%0t] FAIL: %0s: expected %b, got %b", $time, what, expected, got);
            error_count = error_count + 1;
        end
    end
    endtask

    initial begin
        error_count = 0;
        scan_clk = 1'b0; enable = 1'b0;
        scan_enable = 1'b0; scan_in = 1'b0; test_mode = 1'b0;

        // Reset: falling edge on rst_n fires the async reset
        rst_n = 1'b1;
        #0.1 rst_n = 1'b0;
        #1 check4(count, 4'd0, "initial reset");
        @(negedge clk);
        rst_n = 1'b1;

        // Test every four-bit word
        for (word_index = 0; word_index < 16; word_index = word_index + 1) begin
            word_in = word_index;

            // Serial round trip
            @(negedge clk);
            test_mode = 1'b1;
            scan_enable = 1'b1;
            load_chain;
            read_chain;
            check4(word_out, word_in, "scan round trip");

            // Reload, capture one functional increment
            load_chain;
            before_count = count;
            @(negedge clk);
            test_mode = 1'b0;
            scan_enable = 1'b0;
            enable = 1'b1;
            @(posedge clk);
            #1 check4(count, before_count + 4'd1, "functional capture");
            captured_count = count;

            // Read the captured state back serially
            @(negedge clk);
            enable = 1'b0;
            test_mode = 1'b1;
            scan_enable = 1'b1;
            read_chain;
            check4(word_out, captured_count, "captured scan state");
        end

        if (error_count == 0)
            $display("PASS: inserted scan chain, 16 words and functional capture");
        else
            $display("FAIL: %0d errors", error_count);
        $finish;
    end

endmodule
