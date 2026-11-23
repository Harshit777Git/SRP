import math

import numpy as np

from fault_injection.scenarios import Fault
from shared.contracts import GRAVITY

PHYSICS_MODEL_VERSION = "srp-forward-2.1-configured-contact"


class Mechanism:
    def __init__(self, well):
        self.well = well
        angles = np.linspace(0, math.tau, 2049)
        values = [self.geometry(a)[0] for a in angles]
        self.low, self.span = min(values), max(values)-min(values)

    def geometry(self, phase):
        w = self.well
        cx, cy = w.crank_m * math.cos(phase), w.crank_m * math.sin(phase)
        dx, dy = cx-w.pivot_x_m, cy-w.pivot_y_m
        distance = math.hypot(dx, dy)
        projection = (w.rocker_m**2 - w.pitman_m**2 + distance**2) / (2*distance)
        if abs(projection) >= w.rocker_m:
            raise ValueError("four-bar cannot complete a full rotation")
        height = math.sqrt(w.rocker_m**2-projection**2)
        bx = w.pivot_x_m + (projection*dx-height*dy)/distance
        by = w.pivot_y_m + (projection*dy+height*dx)/distance
        return w.pivot_y_m-by, [[0., 0.], [cx, cy], [bx, by], [w.pivot_x_m, w.pivot_y_m],
                                [2*w.pivot_x_m-bx, 2*w.pivot_y_m-by]]

    def position(self, phase):
        if self.well.mechanism == "sinusoidal_test":
            return self.well.stroke_m * (1-math.cos(phase))/2
        return self.well.stroke_m * (self.geometry(phase)[0]-self.low)/self.span


class Engine:
    """Explicit staggered rod dynamics about the static buoyant-weight equilibrium."""

    def __init__(self, well):
        self.well = well
        self.motion = Mechanism(well)
        self.fault = Fault()
        self.time = self.phase = self.production_m3 = 0.
        stiffness, mass, limits, lengths = [], [], [], []
        for rod in well.rods:
            count = math.ceil(rod.length_m / 55)
            length = rod.length_m / count
            area = math.pi * rod.diameter_m**2 / 4
            stiffness.extend([rod.modulus * area / length] * count)
            mass.extend([rod.density * area * length] * count)
            lengths.extend([length]*count)
            limits.append(.7 * length / math.sqrt(rod.modulus/rod.density))
        self.step_s = min(well.physics_step_s, *limits)
        self.k = np.array(stiffness)
        elements = np.array(mass)
        self.mass = (np.r_[elements, 0.] + np.r_[0., elements])/2
        self.mass[-1] += 25.
        element_lengths=np.asarray(lengths)
        self.node_contact_lengths=(np.r_[element_lengths,0.]+np.r_[0.,element_lengths])/2
        self.weight = sum(r.length_m * math.pi*r.diameter_m**2/4 *
                          (r.density-well.fluid_kg_m3)*GRAVITY for r in well.rods)
        self.x = np.full(len(mass)+1, self.motion.position(0.))
        self.v = np.zeros_like(self.x)
        self.tension = np.empty_like(self.k)
        self.forces = np.empty(len(self.k))
        self.area = math.pi*well.plunger_m**2/4
        self.discharge = well.tubing_pa + well.fluid_kg_m3*GRAVITY*well.depth
        self.reservoir = well.casing_pa + well.fluid_kg_m3*GRAVITY*well.intake_head_m
        if self.discharge <= self.reservoir:
            raise ValueError("pump discharge pressure must exceed reservoir boundary pressure")
        self.intake = self.chamber = self.reservoir
        self.warmup(5)

    def advance(self, interval):
        count = max(1, math.ceil(interval/self.step_s))
        dt = interval/count
        for _ in range(count):
            self.step(dt)
        return self.state()

    def warmup(self, cycles):
        for _ in range(cycles):
            self.advance(60/self.well.spm)

    def step(self, dt):
        w, f, t = self.well, self.fault, self.time
        self.spm = w.spm * (1+.35*f.at(t, "abnormal_speed"))
        self.phase += math.tau*self.spm/60*dt
        self.time += dt
        position = self.motion.position(self.phase)
        self.surface_velocity = (position-self.x[0])/dt
        x, v = self.x[-1], self.v[-1]
        restriction = f.at(t, "restricted_inflow")
        self.intake = max(w.casing_pa, self.reservoir -
                          (self.reservoir-w.casing_pa)*restriction*min(1., max(v, 0.)/.4))
        underfill = f.at(t, "incomplete_fillage")
        supply = (1-.95*underfill)*(1-.92*restriction)
        # Unanchored tubing dynamic axial displacement (breathing / stretch)
        unanchored = f.at(t, "unanchored_tubing")
        tbg_stiffness = getattr(w, "tubing_stiffness_n_m", 4.2e6)
        x_tubing = (unanchored * (self.chamber - self.intake) * self.area / tbg_stiffness) if unanchored > 0 else 0.
        rel_x = x - x_tubing

        # Model the unfilled portion of the swept chamber as compressible void.
        # Reducing valve conductance alone can still admit a full liquid charge.
        aeration = w.chamber_gas_fraction + .48*f.at(t, "gas_interference") + .85*f.at(t, "gas_lock")
        # Direct underfill changes the chamber's initial liquid charge.
        # A restricted reservoir acts through intake pressure/conductance below;
        # treating it as the same instantaneous void fabricated identical cards.
        missing_charge = underfill
        gas = min(0.99, aeration+(1-aeration)*missing_charge)
        # Linearized valve conductances and an effective compressible chamber.
        sv_leak = 2e-11*f.at(t, "standing_valve_leak")
        tv_leak = 2e-11*f.at(t, "traveling_valve_leak")
        # Laminar annular Poiseuille leakage through plunger/barrel clearance:
        # q = pi*D*delta^3/(12*mu*L) * (p_discharge - p_chamber).
        # Wear severity grows the configured radial clearance; the cubic law
        # produces the nonlinear slippage response described by the model.
        wear = f.at(t, "pump_wear")
        clearance = w.plunger_radial_clearance_m + w.pump_wear_clearance_growth_m*wear
        plunger_leak = (math.pi*w.plunger_m*clearance**3 /
                        (12*w.viscosity_pa_s*w.plunger_length_m))
        viscosity = .015/w.viscosity_pa_s
        volume = self.area*(w.stroke_m+max(-.8*w.stroke_m, rel_x))
        compliance = volume*((1-gas)/1.4e9+gas/max(self.chamber, 1e5))
        pressure_input = compliance*self.chamber-dt*self.area*v
        # The monotone implicit balance can be solved by selecting its active valve branch.
        residual_intake = compliance*self.intake-pressure_input-dt*tv_leak*viscosity*(self.discharge-self.intake)
        residual_discharge = compliance*self.discharge-pressure_input+dt*sv_leak*viscosity*(self.discharge-self.intake)
        g_in = (8e-9*supply if residual_intake>0 else sv_leak)*viscosity
        g_out = (8e-9 if residual_discharge<0 else tv_leak)*viscosity
        pressure = pressure_input+dt*(g_in*self.intake+(g_out+plunger_leak)*self.discharge)
        self.chamber = max(6e4,pressure/(compliance+dt*(g_in+g_out+plunger_leak)))
        # This high-side-to-chamber slippage is separate from traveling-valve
        # leakage and reduces net delivered volume.
        self.plunger_slippage_m3_s = plunger_leak*(self.discharge-self.chamber)
        self.plunger_leak_conductance = plunger_leak
        self.pump_clearance_m = clearance
        self.production_m3 += dt*(g_out*(self.chamber-self.discharge)-self.plunger_slippage_m3_s)
        self.pump_load = self.area*(self.discharge-self.chamber)

        # Mechanical Tagging Impact (at bottom and top turnaround)
        tag_severity = f.at(t, "tagging_down")
        if tag_severity > 0:
            tag_bottom = 0.015 * w.stroke_m
            if x < tag_bottom:
                impact = tag_severity * (8e6 * (tag_bottom - x) + 8e4 * max(0., -v))
                self.pump_load -= impact

        tag_up = f.at(t, "tagging_up")
        if tag_up > 0:
            tag_top = 0.985 * w.stroke_m
            if x > tag_top:
                impact = tag_up * (8e6 * (x - tag_top) + 8e4 * max(0., v))
                self.pump_load += impact

        # Reuse force buffers rather than allocate np.r_ arrays on every substep.
        np.subtract(self.x[:-1],self.x[1:],out=self.tension)
        np.multiply(self.k,self.tension,out=self.tension)

        # Rod Parting tensile break
        parting = f.at(t, "rod_parting")
        if parting > 0:
            part_idx = max(1, int((1.0 - 0.75 * parting) * len(self.tension)))
            self.tension[part_idx:] = 0.
        np.subtract(self.tension[:-1],self.tension[1:],out=self.forces[:-1])
        self.forces[-1] = self.tension[-1]-self.pump_load
        friction = 2.5*f.at(t, "rod_friction")*self.mass[1:]*np.tanh(self.v[1:]/.03)
        if w.rod_contact_friction_n_m>0:
            friction+=w.rod_contact_friction_n_m*self.node_contact_lengths[1:]*np.tanh(self.v[1:]/.01)
        self.v[1:] += dt*((self.forces-friction)/self.mass[1:]-w.damping_s*self.v[1:])
        self.x[1:] += dt*self.v[1:]
        self.x[0] = position
        self.v[0] = self.surface_velocity

    def state(self):
        w = self.well
        omega = math.tau*self.spm/60
        # The first element tension approximates the wellhead tension.
        load = self.weight+self.k[0]*(self.x[0]-self.x[1])
        derivative = (self.motion.position(self.phase+1e-4)-self.motion.position(self.phase-1e-4))/2e-4
        torque = load*derivative
        power = max(0., torque*omega)/w.running_efficiency+350.
        return dict(position_m=float(self.x[0]), load_n=float(load),
                    physics_model_version=PHYSICS_MODEL_VERSION,
                    pump_position_m=float(self.x[-1]), pump_load_n=float(self.pump_load),
                    crank_angle_deg=math.degrees(self.phase % math.tau), spm=self.spm,
                    linkage=self.motion.geometry(self.phase)[1],
                    motor_rpm=self.spm*w.gear_ratio, voltage_v=w.voltage_v,
                    current_a=power/(math.sqrt(3)*w.voltage_v*.85), power_w=power,
                    gearbox_torque_nm=float(torque), tubing_pa=w.tubing_pa,
                    casing_pa=w.casing_pa, intake_pa=self.intake, chamber_pa=self.chamber,
                    plunger_slippage_m3_s=float(self.plunger_slippage_m3_s),
                    pump_clearance_m=float(self.pump_clearance_m),
                    plunger_leak_conductance_m3_pa_s=float(self.plunger_leak_conductance),
                    net_delivered_m3=self.production_m3, simulation_time_s=self.time)
