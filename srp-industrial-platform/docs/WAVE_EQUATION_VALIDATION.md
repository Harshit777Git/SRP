# Wave-equation validation

Run `python scripts/evaluate_wave.py`. The offline script uses raw simulated surface measurements, reconstructs downhole state through APM and compares with independently retained simulator plunger data on a common time grid. The 12 cases include three rod geometries and speeds, including two tapered strings, healthy and reduced-fillage conditions, and noise-free and noisy sensors. Nominal noise is 2 mm position and 60 N force standard deviation.

The executed sweep measured 1.81–3.03 mm position RMSE, 119–236 N load RMSE, 0.008–0.052° fundamental displacement phase offset and 0.30–0.72% absolute relative card-area error. Load correlation was 0.9987–0.9998. Values are simulated-only. [Case metrics](../data/evaluation/wave.json).

The analytic static benchmark exercises the sum of each tapered section's elastic compliance. The test suite also checks timestep refinement and unavailable status for missing metadata or degraded samples. The forward solver includes pump mass while the inverse reconstructs tip tension, so the comparison includes the local inertial-damping difference. Independent field measurements and a reproducible QRod case are pending.
