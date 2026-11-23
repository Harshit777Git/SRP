# Equations and assumptions

Use upward displacement u and downward depth z. Tension is positive. In each homogeneous rod section the equation is

```text
ρ A (u_tt + d u_t) = (E A u_z)_z
T = −E A u_z
```

The forward discretization uses k = EA/h for each element of length h. Dynamic nodal force is the tension difference minus velocity damping and optional smooth Coulomb friction. Nodal masses sum one half of each adjacent element mass. The forward integrator evaluates rod forces at a common old timestep, advances velocity, then advances position. The prescribed surface boundary is inserted at the new timestep. The step is bounded by 0.7h/√(E/ρ). Export uses a distinct sampling clock.

The pump chamber balance is C dp/dt = Q_in − Q_out − A_p v_p. The effective compliance is V[(1−α)/K_l + α/p]. The implicit update solves one of the valve branches selected by pressure residuals at the intake and discharge boundaries. A floor approximates cavitation without tracking gas transport. The plunger force is A_p(p_discharge−p_chamber). The pressure closure approximates valve flow and ignores ball inertia, wave coupling in fluid and tubing stretch.

For diagnostic inversion, apply a periodic FFT to acquired x(t) and buoyant-weight-corrected T(t). For each angular frequency ω define k² = (ω²−iωd)ρ/E. Across section length L the state changes by

```text
[ u(L) ]   [ cos(kL)           −sin(kL)/(EA k) ] [ u(0) ]
[ T(L) ] = [ EA k sin(kL)       cos(kL)        ] [ T(0) ]
```

Transfer both displacement and tension across each interface. The zero-frequency limit reduces to u(L)=u(0)−LT(0)/EA, T(L)=T(0). Fixed harmonic truncation regularizes amplification from damping and noise. A time-domain inverse FFT returns paired samples at 200 or 256 points. The spectral method evaluates a closed form and reports numerical safeguards and discarded load-spectrum fraction.

Depth and sign conventions are explicit. Static reference offset, unmodeled friction, surface acquisition errors, slope discontinuities, taper geometry, nonperiodic strokes and geometry mismatch affect reconstructed cards.
