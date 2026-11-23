# Simulator physics

The simulator uses the continuous four-bar assembly branch to compute crank pin and beam connection. The opposite beam end drives a calibrated vertical polished-rod stroke. The configuration controls crank, rocker, pitman and pivot dimensions, stroke and strokes per minute. A sinusoidal mode is available for tests. The stock linkage and stroke are illustrative geometries.

Steel rod sections are discretized into lumped-mass elastic elements, about 55 m or shorter per element. Elements carry longitudinal elastic force. Nodes carry mass, linear damping and optional friction. The model takes buoyant rod weight about static equilibrium and evolves dynamic displacement. The plunger adds a 25 kg effective mass. Section transitions conserve force. Engine warm-up runs five cycles.

The plunger displaces the pump chamber volume. A pressure balance uses finite compressibility, a lumped gas fraction and rectified standing and traveling valves. Closed-valve conductance represents valve leakage. Plunger/barrel wear is represented separately as laminar annular slippage, `q = π D δ³ Δp / (12 μ L)`, where `δ` is radial clearance, `D` plunger diameter, `L` plunger length, and `μ` fluid viscosity. Configured radial clearance grows linearly with normalized wear severity, so predicted slippage has a cubic response. This reduced quasi-steady model omits eccentricity, Couette flow, solids, non-Newtonian behavior, and transient annular flow. The default pump dimensions are illustrative assumptions, not measured field values. The discharge pressure includes tubing pressure and full-depth hydrostatic head. Intake pressure uses casing pressure, fluid head and a velocity-dependent inflow restriction. Net delivery subtracts predicted plunger slippage.

Electrical telemetry assumes prescribed crank speed and quasi-static reflected torque. The motor and gearbox calculation uses the configured ratio, operating efficiency, voltage and assumed power factor. Counterbalance, startup motor dynamics, active speed control and regenerative braking are outside this model.

| Preset | Rod depths and diameters | Stroke | Speed |
|---|---|---:|---:|
| SRP_001 | 450 m × 22.2 mm | 1.65 m | 8 SPM |
| SRP_002 | 650 m × 25.4 mm, 550 m × 22.2 mm | 2.10 m | 6 SPM |
| SRP_003 | 800 m × 28.6 mm, 750 m × 25.4 mm, 650 m × 22.2 mm | 2.55 m | 5 SPM |

Representative steel values are 7850 kg/m³ and 205 GPa. The cited finite-element study uses the same density and 210 GPa. The example stiffness was selected for synthetic runs. Example well fluid is 880 kg/m³ and 0.015 Pa·s. Other defaults live in shared equipment schemas and are illustrative engineering assumptions. The reference paper documents the use of elastic-rod forward and inverse methods. [Eisner, Langbauer and Fruhwirth](https://pure.unileoben.ac.at/en/publications/sucker-rod-pump-downhole-dynamometer-card-determination-based-on-/).

The pump leakage equation follows the concentric-cylinder approximation in [Lv et al. (2022)](https://www.cup.edu.cn/petroleumscience/docs/2022-05/c25c5cca6dc64b24bc48.pdf), which treats plunger leakage separately from standing/traveling-valve leakage. The configured 38.1 μm radial clearance is half a 3-mil diametral fit; the 76.2 μm full-severity clearance growth is an explicit scenario assumption. Replace both with pump specifications/inspection measurements and calibrate against independent observations before making field claims. [Li et al. (2026)](https://www.mdpi.com/2673-3161/7/1/25) discusses pressure-driven Poiseuille and motion-driven Couette slippage; this implementation currently includes only the pressure-driven term.
