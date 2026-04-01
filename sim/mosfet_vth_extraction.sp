* ============================================================
* MOSFET Threshold Voltage Extraction: Id vs Vgs
* NMOS 0.25um CMOS  --  SPICE Level-1 Model
*
* Two analysis runs:
*   1) Linear-region method:  Vds = 50mV  -- linear extrapolation of Id at peak gm
*   2) Saturation method:     Vds = 3.0V  -- linear extrapolation of sqrt(Id) vs Vgs
*
* Both methods should yield Vth ~ 0.70V  (Level-1 VTO parameter)
*
* Run with ngspice:  ngspice -b mosfet_vth_extraction.sp
* ============================================================

.TITLE MOSFET_Vth_Extraction

* ---- Netlist -----------------------------------------------

M1  nd  ng  0  0  NMOS1  W=10u  L=0.25u

Vds  nd  0  0.05   ; Fixed at 50mV for linear-region method (Analysis 1)
Vgs  ng  0  0      ; Swept 0 -> 5V in both runs

* ---- NMOS Level-1 Model  (same as mosfet_iv_family.sp) -----
.MODEL NMOS1 NMOS (
+  LEVEL  = 1
+  VTO    = 0.70
+  KP     = 200E-6
+  GAMMA  = 0.45
+  PHI    = 0.65
+  LAMBDA = 0.010
+  TOX    = 8E-9
+  NSUB   = 1.5E17
+  LD     = 25E-9
+  UO     = 450
+  CGSO   = 220E-12
+  CGDO   = 220E-12
+ )

* ---- Analysis 1: Linear-region Vth extraction ---------------
* Vds = 50mV  (< Vgs - Vto for any Vgs > 0.75V -> linear region)
* Id  ~= KP*(W/L)*(Vgs-Vto)*Vds  (linear approx, valid for small Vds)
* Extrapolating the Id-Vgs tangent at max gm to Id=0 gives Vth.
* Step: 5mV for smooth gm = dId/dVgs derivative
.DC Vgs 0 5 0.005

* ---- Measurements (linear method) -------------------------
* Find Vgs at which gm = d(Id)/d(Vgs) is maximum -> tangent intercept = Vth
* Note: in Level-1 at small Vds, gm peaks just above Vto and is constant in saturation
.MEAS DC gm_peak_lin  MAX  d(@m1[id])/d(V(ng))
.MEAS DC Vgs_at_gm    WHEN d(@m1[id])/d(V(ng)) = 'gm_peak_lin'

* ---- ngspice batch-mode output (Analysis 1) ----------------
.control
  * --- Run 1: Vds=50mV, linear-region method ---
  alter @Vds[dc] = 0.05
  dc Vgs 0 5 0.005
  set filetype = ascii
  write output/id_vgs_lin.raw @m1[id]
  echo "Run 1 complete (Vds=50mV) -> output/id_vgs_lin.raw"
  meas dc id_max_lin MAX @m1[id]
  echo "  Id_max at Vgs=5V, Vds=50mV:"
  print id_max_lin

  * --- Run 2: Vds=3.0V, saturation method ---
  * Id_sat = KP/2*(W/L)*(Vgs-Vto)^2*(1+lambda*Vds)
  * sqrt(Id_sat) = sqrt(KP*W/2L) * (Vgs-Vto)  -> linear with Vgs
  * x-intercept of sqrt(Id) vs Vgs extrapolation = Vto
  alter @Vds[dc] = 3.0
  dc Vgs 0 5 0.005
  write output/id_vgs_sat.raw @m1[id]
  echo "Run 2 complete (Vds=3.0V) -> output/id_vgs_sat.raw"

  echo ""
  echo "Vth extraction summary:"
  echo "  Method 1 (linear):    run mosfet_analysis.py -- Id vs Vgs at Vds=50mV"
  echo "  Method 2 (sqrt):      run mosfet_analysis.py -- sqrt(Id) vs Vgs at Vds=3V"
  echo "  Expected result:      Vth ~ 0.70V"

  quit
.endc

* ---- Simulation options ------------------------------------
.OPTIONS RELTOL=1E-6  ABSTOL=1E-15  VNTOL=1E-8  ITL4=100

.END
