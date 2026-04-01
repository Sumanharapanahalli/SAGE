package ral_test_pkg;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  import peripheral_ral_pkg::*;
  import peripheral_env_pkg::*;
  import ral_seq_pkg::*;

  // ================================================================
  // Base Test
  // ================================================================
  class ral_base_test extends uvm_test;
    `uvm_component_utils(ral_base_test)
    peripheral_env env;

    function new(string name, uvm_component parent);
      super.new(name, parent);
    endfunction

    virtual function void build_phase(uvm_phase phase);
      super.build_phase(phase);
      env = peripheral_env::type_id::create("env", this);
    endfunction

    virtual function void end_of_elaboration_phase(uvm_phase phase);
      uvm_top.print_topology();  // Print RAL + component hierarchy
    endfunction

    task run_phase(uvm_phase phase);
      phase.raise_objection(this);
      run_sequences();
      #100ns;
      phase.drop_objection(this);
    endtask

    virtual task run_sequences(); endtask
  endclass : ral_base_test

  // ================================================================
  // ral_full_test — runs all five sequences in order
  // ================================================================
  class ral_full_test extends ral_base_test;
    `uvm_component_utils(ral_full_test)

    function new(string name, uvm_component parent);
      super.new(name, parent);
    endfunction

    virtual task run_sequences();
      reg_hw_reset_seq     rst_seq;
      ral_frontdoor_seq    fd_seq;
      ral_backdoor_seq     bd_seq;
      ral_mirror_check_seq mc_seq;
      ral_coverage_seq     cov_seq;

      rst_seq  = reg_hw_reset_seq::type_id::create("rst_seq");
      fd_seq   = ral_frontdoor_seq::type_id::create("fd_seq");
      bd_seq   = ral_backdoor_seq::type_id::create("bd_seq");
      mc_seq   = ral_mirror_check_seq::type_id::create("mc_seq");
      cov_seq  = ral_coverage_seq::type_id::create("cov_seq");

      rst_seq.regmodel  = env.regmodel;
      fd_seq.regmodel   = env.regmodel;
      bd_seq.regmodel   = env.regmodel;
      mc_seq.regmodel   = env.regmodel;
      cov_seq.regmodel  = env.regmodel;

      rst_seq.start (env.apb_agt.sequencer);
      fd_seq.start  (env.apb_agt.sequencer);
      bd_seq.start  (env.apb_agt.sequencer);
      mc_seq.start  (env.apb_agt.sequencer);
      cov_seq.start (env.apb_agt.sequencer);

      `uvm_info("FULL_TEST", "All RAL sequences complete", UVM_LOW)
    endtask
  endclass : ral_full_test

  // ================================================================
  // ral_reset_test — reset check only (smoke test)
  // ================================================================
  class ral_reset_test extends ral_base_test;
    `uvm_component_utils(ral_reset_test)
    function new(string name, uvm_component parent); super.new(name, parent); endfunction

    virtual task run_sequences();
      reg_hw_reset_seq rst_seq = reg_hw_reset_seq::type_id::create("rst_seq");
      rst_seq.regmodel = env.regmodel;
      rst_seq.start(env.apb_agt.sequencer);
    endtask
  endclass : ral_reset_test

  // ================================================================
  // ral_backdoor_test — backdoor-only (no bus, fast regression)
  // ================================================================
  class ral_backdoor_test extends ral_base_test;
    `uvm_component_utils(ral_backdoor_test)
    function new(string name, uvm_component parent); super.new(name, parent); endfunction

    virtual task run_sequences();
      ral_backdoor_seq bd_seq = ral_backdoor_seq::type_id::create("bd_seq");
      bd_seq.regmodel = env.regmodel;
      bd_seq.start(env.apb_agt.sequencer);
    endtask
  endclass : ral_backdoor_test

endpackage : ral_test_pkg
