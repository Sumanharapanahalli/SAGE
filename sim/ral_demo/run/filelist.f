// UVM RAL peripheral filelist — Questa / VCS / Xcelium compatible
// Usage: vlog -f run/filelist.f  (Questa)
//        vcs  -f run/filelist.f  (VCS)
//        xrun -f run/filelist.f  (Xcelium/xrun)

// ---- UVM library (adjust path to your installation) ----
+incdir+${UVM_HOME}/src
${UVM_HOME}/src/uvm_pkg.sv
${UVM_HOME}/src/dpi/uvm_dpi.cc   // for backdoor HDL access DPI

// ---- RTL ----
dut/peripheral.sv

// ---- Testbench interfaces ----
tb/apb_if.sv

// ---- Testbench packages (dependency order) ----
tb/peripheral_ral_pkg.sv
tb/apb_pkg.sv
tb/peripheral_env_pkg.sv
tb/ral_seq_pkg.sv
tb/ral_test_pkg.sv

// ---- Top ----
tb/tb_top.sv
