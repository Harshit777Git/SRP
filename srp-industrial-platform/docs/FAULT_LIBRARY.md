# Fault library

Fault scheduling uses simulation-clock onset, severity in [0,1], duration and a linear ramp. The truth log records the actual factor applied. The signatures below are expected mechanisms and symptoms.

| Scenario | Simulator state | Mechanism and potential symptom |
|---|---|---|
| Healthy | SUPPORTED_BY_SIMULATOR | Nominal valving, compressibility and inflow |
| Incomplete fillage | SUPPORTED_BY_SIMULATOR | Restricts intake supply and models the missing liquid charge as compressible chamber void. A delayed unloading signature is also consistent with gas interference |
| Gas interference | SUPPORTED_BY_SIMULATOR | Increases chamber compressibility, extending the load transition |
| Gas lock | UNSUPPORTED | Persistent phase transfer and gas-only behavior need separate validation |
| Traveling valve leakage | SUPPORTED_BY_SIMULATOR | Reverse conductance at the plunger valve reduces pressure differential and adds fallback |
| Standing valve leakage | SUPPORTED_BY_SIMULATOR | Reverse flow at the intake valve reduces retained chamber pressure |
| Rod parting | UNSUPPORTED | Disconnected rod sections and transient contact are unimplemented |
| Rod/tubing friction | SUPPORTED_BY_SIMULATOR | Adds distributed smooth Coulomb force opposing motion |
| Pump wear | SUPPORTED_BY_SIMULATOR | Increases plunger-barrel bypass; can resemble traveling valve leakage |
| Restricted inflow | SUPPORTED_BY_SIMULATOR | Drawdown approximation, lower intake conductance and compressible void from the reduced liquid charge |
| Mechanical loading anomaly | UNSUPPORTED | No generic mechanical anomaly has a validated mechanism |
| Load-cell drift | SUPPORTED_BY_SIMULATOR | Adds severity-ramped force bias to virtual measurement |
| Position sensor fault | SUPPORTED_BY_SIMULATOR | Simulates encoder gain loss |
| Abnormal speed | SUPPORTED_BY_SIMULATOR | Changes crank rotation rate and therefore all coupled responses |

The synthetic ML training covers healthy, gas interference and traveling valve leakage. Other injected mechanisms carry INSUFFICIENT_EVIDENCE for detection. Overlapping symptoms, especially leakage and reduced supply, need investigation with additional observations.
