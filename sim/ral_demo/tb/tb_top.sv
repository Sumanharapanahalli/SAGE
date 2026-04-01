`timescale 1ns/1ps
// ====================================================================
// tb_top.sv — UVM RAL testbench top
// Instantiates DUT, APB interface, clock/reset, starts UVM test
// ====================================================================
module tb_top;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  import ral_test_pkg::*;

  // ------------------------------------------------------------------
  // Clock & reset
  // ------------------------------------------------------------------
  logic pclk;
  logic presetn;

  initial pclk = 1'b0;
  always #5ns pclk = ~pclk;  // 100 MHz

  initial begin
    presetn = 1'b0;
    repeat (10) @(posedge pclk);
    @(negedge pclk);           // deassert synchronously on negedge
    presetn = 1'b1;
    `uvm_info("TB_TOP", "Reset released", UVM_LOW)
  end

  // ------------------------------------------------------------------
  // APB interface
  // ------------------------------------------------------------------
  apb_if apb_bus (.pclk(pclk), .presetn(presetn));

  // ------------------------------------------------------------------
  // DUT
  // ------------------------------------------------------------------
  peripheral u_dut (
    .pclk    (pclk),
    .presetn (presetn),
    .psel    (apb_bus.psel),
    .penable (apb_bus.penable),
    .pwrite  (apb_bus.pwrite),
    .paddr   (apb_bus.paddr),
    .pwdata  (apb_bus.pwdata),
    .prdata  (apb_bus.prdata),
    .pready  (apb_bus.pready),
    .irq_out ()
  );

  // ------------------------------------------------------------------
  // UVM startup
  // ------------------------------------------------------------------
  initial begin
    // Make APB vif available to every agent component under the env
    uvm_config_db #(virtual apb_if)::set(
      null, "uvm_test_top.env.apb_agt.*", "vif", apb_bus);

    // Enable all register coverage groups
    uvm_reg::include_coverage("*", UVM_CVR_ALL);

    // Launch test (override with +UVM_TESTNAME=ral_reset_test etc.)
    run_test("ral_full_test");
  end

  // ------------------------------------------------------------------
  // Simulation timeout watchdog
  // ------------------------------------------------------------------
  initial begin
    #100_000ns;
    `uvm_fatal("TIMEOUT", "Simulation exceeded 100 us — check for hang")
  end

  // ------------------------------------------------------------------
  // Waveform dump
  // ------------------------------------------------------------------
  initial begin
    $dumpfile("ral_sim.vcd");
    $dumpvars(0, tb_top);
  end

endmodule
