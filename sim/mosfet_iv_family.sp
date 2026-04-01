* ============================================================
* MOSFET I-V Family Curves: Id vs Vds
* NMOS 0.25um CMOS  --  SPICE Level-1 Model
*
* Device:    M1  W=10um  L=0.25um  (W/L = 40)
* Vto = 0.70V   KP = 200uA/V2   lambda = 0.01 V-1
*
* Nested DC sweep:
*   Inner: Vds = 0 -> 5V  (20mV step,  251 points)
*   Outer: Vgs = 1.0 -> 5.0V  (0.5V step, 9 curves)
*
* Run with ngspice:   ngspice -b mosfet_iv_family.sp
* Run with LTspice:   open and press Run  (.control block is ignored)
* Run with Xyce:      xyce mosfet_iv_family.sp
*
* Expected saturation onset (Vdsat = Vgs - Vto):
*   Vgs=1.0V -> Vdsat=0.30V  |  Vgs=3.0V -> Vdsat=2.30V  |  Vgs=5.0V -> Vdsat=4.30V
* ============================================================

.TITLE MOSFET_IdVds_Family

* ---- Netlist -----------------------------------------------

* NMOS transistor: Drain=nd  Gate=ng  Source=0  Bulk=0
M1  nd  ng  0  0  NMOS1  W=10u  L=0.25u

* Bias supplies
* Vds is the swept source; Vgs is the parametric step source
Vds  nd  0  0      ; Drain supply  -- swept 0 -> 5V  in .DC
Vgs  ng  0  1      ; Gate voltage  -- stepped in outer .DC loop

* ---- NMOS Level-1 Model  (0.25um bulk CMOS) ----------------
* Parameters derived from a representative 0.25um process PDK.
* Replace with your foundry model card for silicon-accurate results.
.MODEL NMOS1 NMOS (
+  LEVEL  = 1
+  VTO    = 0.70      $ threshold voltage              [V]
+  KP     = 200E-6    $ process transconductance u*Cox  [A/V2]
+  GAMMA  = 0.45      $ body-effect coefficient        [V^0.5]
+  PHI    = 0.65      $ surface potential (2*phi_F)    [V]
+  LAMBDA = 0.010     $ channel-length modulation      [1/V]
+  TOX    = 8E-9      $ gate oxide thickness           [m]
+  NSUB   = 1.5E17    $ substrate doping concentration [cm-3]
+  LD     = 25E-9     $ lateral source/drain diffusion [m]
+  UO     = 450       $ low-field surface mobility     [cm2/V-s]
+  CGSO   = 220E-12   $ gate-source overlap cap        [F/m]
+  CGDO   = 220E-12   $ gate-drain overlap cap         [F/m]
+  CJ     = 560E-6    $ zero-bias bulk junction cap    [F/m2]
+  MJ     = 0.45      $ bulk junction grading coeff
+  CJSW   = 350E-12   $ sidewall junction cap          [F/m]
+  MJSW   = 0.20      $ sidewall grading coefficient
+ )

* ---- DC Analysis -------------------------------------------
* Syntax: .DC inner_src start stop step  outer_src start stop step
* -> 9 curves (Vgs loop) x 251 points each (Vds loop)
.DC Vds 0 5 0.02  Vgs 1 5 0.5

* ---- Measurements at fixed points -------------------------
* Saturation-region currents at Vds = 4V per Vgs value:
*   Id_sat(Vgs=1V) ~ KP/2*(W/L)*(1.0-0.7)^2*(1+0.01*4) ~ 0.374 mA
*   Id_sat(Vgs=3V) ~ KP/2*(W/L)*(3.0-0.7)^2*(1+0.01*4) ~ 10.94 mA
*   Id_sat(Vgs=5V) ~ KP/2*(W/L)*(5.0-0.7)^2*(1+0.01*4) ~ 38.27 mA

* ---- ngspice batch-mode output ----------------------------
.control
  run

  * Write ASCII raw file -- one dataset per outer Vgs step
  set filetype = ascii
  set wr_singlescale
  write output/id_vds.raw @m1[id]

  echo "Simulation complete."
  echo "Output -> output/id_vds.raw"
  echo "  Variable: @m1[id]  (Id, positive = conventional current into drain)"
  echo ""
  echo "Saturation boundary: Vdsat = Vgs - Vto = Vgs - 0.70V"
  echo "  Linear region  : Vds < Vdsat   => Id ~ KP*(W/L)*[Veff*Vds - Vds^2/2]"
  echo "  Saturation     : Vds >= Vdsat  => Id ~ KP/2*(W/L)*Veff^2*(1+lambda*Vds)"

  quit
.endc

* ---- Simulation options ------------------------------------
.OPTIONS RELTOL=1E-6  ABSTOL=1E-15  VNTOL=1E-8  ITL4=100

.END
