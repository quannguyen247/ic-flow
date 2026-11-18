// The scan netlist with every scan input tied to 0 (functional mode),
// so it has the same ports as the RTL
module scan_off (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       enable,
    output wire [3:0] count
);

    counter4 u_dut (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .count(count),
        .scan_in(1'b0),
        .scan_enable(1'b0),
        .scan_clk(1'b0),
        .test_mode(1'b0),
        .scan_out()
    );
endmodule
