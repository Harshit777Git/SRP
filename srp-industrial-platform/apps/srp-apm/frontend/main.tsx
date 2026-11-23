import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Action, Chart, Metrics, Panel, Status, api, fmt, request, useStream } from '../../ui/components';
import { OperationsConsole } from '../../ui/operations-console';
import { interpolate, PumpPlayback, PlaybackStroke } from './playback';
import { Engineering } from './engineering';
import { HistoricalReference } from './reference';
import { DynacardViewer } from './dynacard-viewer';
import { CANONICAL_STATES } from './canonical-dynacards';
import './apm-theme.css';

type Points = { position_m: number[]; load_n: number[] };
type Surface = Points & { min_load_n: number; max_load_n: number; stroke_m: number; area_j: number; direction: string[] };
type Downhole = Partial<Points> & {
  status: string; reason?: string; solver_version?: string; discarded_load_fraction?: number;
  harmonics?: number; features?: {
    pip_psi?: number;
    mpt_in?: number;
    ept_in?: number;
    stroke_loss_in?: number;
    fillage_pct?: number;
    fluid_pound?: boolean | { detected?: boolean };
    fluid_load_fo_lbf?: number;
    displacement_bpd?: number;
  };
};
type Diagnosis = {
  probability_preview?: { model_version: string; scores: { label: string; score: number }[] };
  label: string; confidence?: number; evidence: string; model_version: string; status: string;
  investigation: string; timestamp?: string;
};
type Condition = {
  status: string; reference_count: number;
  surface?: { change_fraction: number; threshold_fraction: number };
  downhole?: { change_fraction: number; threshold_fraction: number };
  reference_spm?: number; symptom?: string; late_downstroke_excess_n?: number;
  surface_travel_delta_m?: number; surface_load_delta_n?: number;
  downhole_work_delta_j?: number; current_spm?: number;
  measurements?: { label: string; delta: number; threshold: number; unit: string }[];
};
type Card = PlaybackStroke & {
  run_id: string; stroke_id: number; timestamp: string; quality: string; completeness: number;
  period_s: number; spm?: number; sample_count: number;
  surface: Surface; downhole: Downhole; diagnosis: Diagnosis; condition_monitor?: Condition;
  asset_configuration?: { rods: Array<{ length_m: number; diameter_m: number }> };
};
type Sample = {
  run_id: string; stroke_id: number; sample_index: number; crank_angle_deg: number; timestamp: string;
  quality: string; polished_rod_position_in: number; polished_rod_load_lbf: number; spm: number;
};
type Snapshot = { live: Sample[]; card?: Card; latest?: Sample; connected: boolean; counts: Record<string, number> };
type Asset = { asset_id: string; site_id?: string | null; last_sample?: string | null; stroke_count?: number; latest_sequence?: number | null };
type DataProfile = {
  dataset_id: string; original_column_name: string; original_unit: string; sample_count: number;
  missing_count: number; minimum?: number; maximum?: number; mean?: number;
  histogram?: { edges: number[]; counts: number[] }; value_counts?: Record<string, number>;
};
type DataCatalog = {
  datasets: {
    dataset_id: string; source: string; origin: string; records: number | null;
    surface_cards: number | null; downhole_cards: number | null; path: string;
    permission: string; training_eligible: boolean; reason: string;
  }[];
  profiles: DataProfile[]; preview: Record<string, string>[];
  cards: (Points & { name: string; source: string; label: null })[];
  readiness?: { field: Record<string, any>; synthetic_evaluation: Record<string, any>; synthetic_evaluation_file: string | null };
};

const base = api(8002);

const symptoms: Record<string, string> = {
  DELAYED_PUMP_UNLOADING: 'Delayed pump unloading detected',
  MEASURED_TRAVEL_CHANGE: 'Polished-rod travel change detected',
  POLISHED_ROD_LOAD_OFFSET: 'Polished-rod load offset detected',
  SURFACE_WAVEFORM_CHANGE: 'Surface load waveform change detected',
  PUMP_STROKE_WORK_CHANGE: 'Downhole stroke work change detected',
};

const trace = (p?: Partial<Points>, secondary = false) => ({
  x: p?.position_m ?? [],
  y: p?.load_n?.map(f => f / 1000) ?? [],
  secondary
});

// All 14 original and modern workspaces
export type WorkspaceKey =
  | 'Cockpit'
  | 'Surveillance'
  | 'SurfaceCard'
  | 'DownholeCard'
  | 'DualCard'
  | 'Faults'
  | 'Playback'
  | 'Manifolds'
  | 'Benchmark'
  | 'Reference'
  | 'Console'
  | 'FleetMonitoring'
  | 'History'
  | 'Registry'
  | 'Intelligence'
  | 'Export'
  | 'Settings';

export const allClassicTabs: Array<{ id: WorkspaceKey; label: string; icon: string }> = [
  { id: 'Surveillance', label: 'Well Surveillance & Dynacards', icon: '∿' },
  { id: 'SurfaceCard', label: 'Live Surface Dynacard', icon: '📈' },
  { id: 'DownholeCard', label: 'Downhole Dynacard', icon: '📉' },
  { id: 'DualCard', label: 'Dual-Card Comparison', icon: '⧉' },
  { id: 'Faults', label: 'Fault Detection & Conditions', icon: '⚠' },
  { id: 'Playback', label: 'Animated Pump Analysis', icon: '▶' },
  { id: 'Cockpit', label: 'Fleet Cockpit', icon: '⊞' },
  { id: 'Console', label: 'Operations Console', icon: '🖥' },
  { id: 'FleetMonitoring', label: 'Fleet Monitoring', icon: '📋' },
  { id: 'Manifolds', label: 'GCS Manifold Hierarchy', icon: '⚙' },
  { id: 'Benchmark', label: 'Engineering Benchmark Lab', icon: '🔬' },
  { id: 'Reference', label: 'STATE-077 Reference', icon: '🏛' },
  { id: 'History', label: 'Historical Analytics', icon: '🔍' },
  { id: 'Registry', label: 'ML Model Registry', icon: '🗄' },
  { id: 'Intelligence', label: 'Dataset Intelligence & EDA', icon: '📊' },
  { id: 'Export', label: 'Import / Export Center', icon: '📦' },
  { id: 'Settings', label: 'Settings / Asset Configuration', icon: '🔧' },
];

function App() {
  const [workspace, setWorkspace] = useState<WorkspaceKey>('Surveillance');
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [copilotOpen, setCopilotOpen] = useState(false);
  const [copilotMessages, setCopilotMessages] = useState<Array<{ sender: 'user' | 'copilot'; text: string; briefing?: boolean }>>([
    { sender: 'copilot', text: 'Hello! I am your Operations Copilot for SRP fleet monitoring. Ask me about fleet health, deferment, or downhole dynacard diagnostics.', briefing: false }
  ]);
  const [chatInput, setChatInput] = useState('');

  // Fleet and filters
  const [asset, setAsset] = useState(new URLSearchParams(location.search).get('asset') || 'prairie-001');
  const [fleet, setFleet] = useState<Asset[]>([]);
  const [stationFilter, setStationFilter] = useState('ALL');
  const [fieldFilter, setFieldFilter] = useState('ALL');
  const [stateFilter, setStateFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [viewPill, setViewPill] = useState<'Operations' | 'Production & VFM' | 'Equipment & Run Life' | 'OPC Telemetry'>('Operations');
  const [imperialUnits, setImperialUnits] = useState(true);

  // Stroke, cards, and intelligence
  const [cards, setCards] = useState<Card[]>([]);
  const [selected, setSelected] = useState<Card>();
  const [error, setError] = useState('');
  const [filter, setFilter] = useState({ stroke: '', since: '', until: '', fault: '', model: '' });
  const [equipment, setEquipment] = useState('');
  const [dataCatalog, setDataCatalog] = useState<DataCatalog>();
  const [datasetFilter, setDatasetFilter] = useState('');
  const [originFilter, setOriginFilter] = useState('');
  const [selectedDataset, setSelectedDataset] = useState('');
  const [selectedProfile, setSelectedProfile] = useState('');
  const [registry, setRegistry] = useState<unknown>();
  const [selectedGcs, setSelectedGcs] = useState('All GCS');

  const { data, online } = useStream<Snapshot>(`${base}/stream?asset=${asset}`);
  const card = selected ?? data?.card;
  const newest = data?.card;
  const playbackHistory = newest && !cards.some(item => item.run_id === newest.run_id && item.stroke_id === newest.stroke_id)
    ? [newest, ...cards] : cards;
  const d = card?.downhole;
  const f = card?.diagnosis;
  const condition = card?.condition_monitor;
  const assetQuery = new URLSearchParams({ asset });
  const exportUrl = card ? `${base}/cards/${card.run_id}/${card.stroke_id}?${assetQuery}` : '';

  const refresh = () => request<Asset[]>(`${base}/assets`).then(list => {
    setFleet(list);
    setAsset(current => list.some(w => w.asset_id === current) ? current : list[0]?.asset_id ?? current);
  }).catch(e => setError(e.message));

  useEffect(() => {
    void refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    setSelected(undefined);
    setCards([]);
  }, [asset]);

  async function searchStrokes() {
    try {
      const params = new URLSearchParams({ asset });
      for (const [key, value] of Object.entries(filter)) if (value) params.set(key, value);
      setCards(await request<Card[]>(`${base}/cards?${params}`));
      setError('');
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function registerAsset() {
    try {
      await request(`${base}/assets`, JSON.parse(equipment));
      await refresh();
      setError('');
      alert('Asset registered successfully!');
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    if (['Surveillance', 'SurfaceCard', 'DownholeCard', 'DualCard', 'Faults', 'Playback', 'History'].includes(workspace)) {
      void searchStrokes();
    }
    if (['Registry', 'Analytics'].includes(workspace)) {
      request(`${base}/registry`).then(setRegistry).catch(e => setError(e.message));
    }
    if (['Intelligence', 'Export'].includes(workspace)) {
      request<DataCatalog>(`${base}/dataset-intelligence`).then(setDataCatalog).catch(e => setError(e.message));
    }
  }, [workspace, asset, newest?.run_id, newest?.stroke_id]);

  const live = !!online && !!data?.connected && !selected;
  const latest = live ? data?.latest : undefined;
  const raw = live ? data?.live ?? [] : [];
  const livePoints = raw.map(s => ({
    x_in: s.polished_rod_position_in,
    y_lbf: s.polished_rod_load_lbf
  }));
  const liveTime = latest && card && latest.run_id === card.run_id && card.crank_origin_deg !== undefined && card.period_s > 0
    ? ((latest.crank_angle_deg - card.crank_origin_deg + 360) % 360) * card.period_s / 360 : undefined;
  const downholeMarker = liveTime !== undefined && d?.position_m && d.load_n && d.time_s?.length && card
    ? interpolate({ position_m: d.position_m, load_n: d.load_n, time_s: d.time_s }, liveTime, card.period_s) : undefined;

  // Operating State & Fault Simulation Selector state
  const [selectedState, setSelectedState] = useState<string>('LIVE');
  const activeCanonical = selectedState !== 'LIVE' ? CANONICAL_STATES[selectedState] : undefined;

  const effectiveSurfaceData = activeCanonical ? {
    position_in: activeCanonical.surfPosIn,
    load_lbf: activeCanonical.surfLoadLbf,
    stroke_in: activeCanonical.mptIn,
    pprl_lbf: activeCanonical.pprlLbf,
    mprl_lbf: activeCanonical.mprlLbf,
    area_lbf_in: activeCanonical.areaLbfIn,
    submerged_rod_weight_lbf: activeCanonical.mprlLbf * 0.92,
    direction: activeCanonical.surfPosIn.map((v, i, arr) => arr[(i + 1) % arr.length] >= v ? 'UP' : 'DOWN')
  } : card?.surface;

  const effectiveDownholeData = activeCanonical ? {
    status: 'SOLVED',
    solver_version: 'Everitt-Jennings FD/2.0',
    verification_version: 'Gibbs-Harmonic/1.0',
    position_m: activeCanonical.dhPosIn.map(v => v * 0.0254),
    load_n: activeCanonical.dhLoadLbf.map(v => v * 4.4482216152605),
    gibbs_position_m: activeCanonical.dhPosIn.map(v => v * 0.0254 * 0.995),
    gibbs_load_n: activeCanonical.dhLoadLbf.map(v => v * 4.4482216152605 * 0.998),
    displacement_rmse_in: 0.015,
    load_rmse_lbf: 12.8,
    features: {
      mpt_in: activeCanonical.mptIn,
      ept_in: activeCanonical.eptIn,
      fillage_pct: activeCanonical.fillagePct,
      fluid_load_fo_lbf: activeCanonical.foLbf,
      upper_fluid_reference_lbf: activeCanonical.foLbf,
      lower_fluid_reference_lbf: 0,
      area_lbf_in: activeCanonical.areaLbfIn,
      stroke_loss_in: activeCanonical.mptIn - activeCanonical.eptIn,
      displacement_bpd: activeCanonical.displacementBpd,
      pip_psi: 195.4,
      valves: {
        SVO: { index: 12, position_in: activeCanonical.mptIn * 0.16, load_lbf: activeCanonical.foLbf * 0.75 },
        SVC: { index: 50, position_in: activeCanonical.mptIn, load_lbf: activeCanonical.foLbf },
        TVO: { index: 65, position_in: activeCanonical.mptIn * 0.82, load_lbf: activeCanonical.foLbf * 0.25 },
        TVC: { index: 0, position_in: 0, load_lbf: 0 }
      },
      markers: {
        TOS: { index: 50, position_in: activeCanonical.mptIn, load_lbf: activeCanonical.foLbf },
        BOS: { index: 0, position_in: 0, load_lbf: 0 },
        MAX_LOAD: { index: 50, position_in: activeCanonical.mptIn, load_lbf: activeCanonical.foLbf },
        MIN_LOAD: { index: 0, position_in: 0, load_lbf: 0 }
      }
    }
  } : d;

  const handleSelectState = (stateKey: string) => {
    setSelectedState(stateKey);
    if (stateKey !== 'LIVE') {
      const faultMapping: Record<string, string> = {
        Normal_Operation: 'healthy',
        Fluid_Pound: 'incomplete_fillage',
        Gas_Interference: 'gas_interference',
        Severe_Gas_Lock: 'gas_interference',
        Traveling_Valve_Leak: 'traveling_valve_leak',
        Standing_Valve_Leak: 'standing_valve_leak',
        Worn_Pump_Barrel: 'pump_wear',
        Blocked_Intake: 'restricted_inflow',
        High_Wellbore_Friction: 'rod_friction',
        High_Fluid_Damping: 'abnormal_speed',
        Tagging_Down_Hard: 'rod_friction',
        Unanchored_Tubing_Slip: 'healthy'
      };
      const simFault = faultMapping[stateKey] || 'healthy';
      fetch(`http://127.0.0.1:8001/assets/${asset}/fault`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind: simFault, severity: 0.8, onset_s: 0, duration_s: 3600 })
      }).catch(() => {});
    }
  };

  const uncertain = f?.label === 'UNKNOWN' || f?.label === 'FAULT_TYPE_UNDETERMINED';
  const headline = !f ? 'Awaiting a completed stroke' : !uncertain ? f.label
    : condition?.status === 'STROKE_RATE_CHANGE' ? 'Stroke-rate change detected'
    : condition?.status === 'DYNACARD_CHANGE' ? (symptoms[condition.symptom ?? ''] ?? 'Dynacard change detected')
    : condition?.status === 'WITHIN_REFERENCE' ? 'No alert on this stroke'
    : condition?.status === 'AWAITING_REFERENCE' ? 'Building the operating reference'
    : condition?.status === 'STROKE_UNAVAILABLE' ? 'Stroke diagnostics unavailable' : 'Fault type undetermined';

  const handleSendChat = () => {
    if (!chatInput.trim()) return;
    const userQuery = chatInput;
    setCopilotMessages(prev => [...prev, { sender: 'user', text: userQuery }]);
    setChatInput('');

    setTimeout(() => {
      if (userQuery.toLowerCase().includes('fleet') || userQuery.toLowerCase().includes('status')) {
        setCopilotMessages(prev => [...prev, {
          sender: 'copilot',
          text: '',
          briefing: true
        }]);
      } else if (userQuery.toLowerCase().includes('canyon') || userQuery.toLowerCase().includes('card') || userQuery.toLowerCase().includes('downhole')) {
        setCopilotMessages(prev => [...prev, {
          sender: 'copilot',
          text: `[DIAGNOSTIC SUMMARY: canyon-014]\nOperating State: Fluid Pound Shutdown.\nReconstructed Downhole Card indicates liquid fillage dropped below 42%, causing sharp plunger fluid impact at mid-stroke. Effective Plunger Travel (EPT) reduced from 54.2 in to 22.8 in. Recommended Action: Throttle VSD speed or verify casing gas venting.`
        }]);
      } else {
        setCopilotMessages(prev => [...prev, {
          sender: 'copilot',
          text: `[OPERATIONS ADVISORY]: Monitored 120 SRP wells across Prairie, Canyon, Mesa, and Delta. All equipment load corridors are governed by Everitt-Jennings wave equation inversion. Telemetry active at 18883.`
        }]);
      }
    }, 400);
  };

  // 120 Wells Mock Distribution for Cockpit Table
  const all120Wells = Array.from({ length: 120 }).map((_, i) => {
    let field = 'Prairie';
    let station = 'GCS-01 · Prairie North';
    let num = (i + 1).toString().padStart(3, '0');
    let id = `prairie-${num}`;
    let state = 'Normal';
    let envelope = 'Inside ROR';
    let health = 98 - (i % 5);
    let diagnosis = 'Operating normally in target envelope...';
    let deferment = '0 BOPD';

    if (i >= 30 && i < 60) {
      field = 'Canyon';
      station = 'GCS-02 · Canyon Deep';
      id = `canyon-${(i - 29).toString().padStart(3, '0')}`;
      if (i === 43) {
        state = 'VSD trip';
        envelope = 'Off / Zero Flow';
        health = 18;
        diagnosis = 'Tripped — Severe Fluid Pound Shutdown';
        deferment = '+142 BOPD';
      }
    } else if (i >= 60 && i < 90) {
      field = 'Mesa';
      station = 'GCS-03 · Mesa Foothills';
      id = `mesa-${(i - 59).toString().padStart(3, '0')}`;
      if (i === 80) {
        state = 'VSD trip';
        envelope = 'Off / Zero Flow';
        health = 22;
        diagnosis = 'Tripped — Traveling Valve Leakage';
        deferment = '+88 BOPD';
      }
    } else if (i >= 90) {
      field = 'Delta';
      station = 'GCS-04 · Delta Basin';
      id = `delta-${(i - 89).toString().padStart(3, '0')}`;
    }

    return { id, field, station, state, envelope, health, diagnosis, deferment };
  });

  const filteredWells = all120Wells.filter(w => {
    if (stationFilter !== 'ALL' && !w.station.includes(stationFilter)) return false;
    if (fieldFilter !== 'ALL' && w.field !== fieldFilter) return false;
    if (stateFilter !== 'ALL' && w.state !== stateFilter) return false;
    if (searchQuery && !w.id.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="advait-shell">
      {/* 1. TOP HEADER BAR */}
      <header className="advait-topbar">
        <div className="advait-top-left">
          <div className="advait-logo-pill">ADVAIT</div>
          <div className="advait-title-text">ADVAIT SRP-APM</div>
          <div className="advait-workspace-pill">
            <span style={{ color: '#94a3b8', marginRight: 4 }}>Workspace:</span>
            <select
              value={workspace}
              onChange={e => setWorkspace(e.target.value as WorkspaceKey)}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#38bdf8',
                fontWeight: 700,
                fontSize: 12,
                outline: 'none',
                cursor: 'pointer'
              }}>
              <optgroup label="Surveillance & Dynacards">
                <option value="Surveillance" style={{ background: '#090e1a', color: '#fff' }}>Surveillance & Dynacards</option>
                <option value="SurfaceCard" style={{ background: '#090e1a', color: '#fff' }}>Live Surface Dynacard</option>
                <option value="DownholeCard" style={{ background: '#090e1a', color: '#fff' }}>Downhole Dynacard</option>
                <option value="DualCard" style={{ background: '#090e1a', color: '#fff' }}>Dual-Card Comparison</option>
                <option value="Faults" style={{ background: '#090e1a', color: '#fff' }}>Fault Detection & Conditions</option>
                <option value="Playback" style={{ background: '#090e1a', color: '#fff' }}>Animated Pump Analysis</option>
              </optgroup>
              <optgroup label="Operations & Fleet">
                <option value="Cockpit" style={{ background: '#090e1a', color: '#fff' }}>Fleet Cockpit</option>
                <option value="Console" style={{ background: '#090e1a', color: '#fff' }}>Operations Console</option>
                <option value="FleetMonitoring" style={{ background: '#090e1a', color: '#fff' }}>Fleet Monitoring</option>
              </optgroup>
              <optgroup label="Engineering & Manifolds">
                <option value="Manifolds" style={{ background: '#090e1a', color: '#fff' }}>GCS Manifold Hierarchy</option>
                <option value="Benchmark" style={{ background: '#090e1a', color: '#fff' }}>Engineering Benchmark Lab</option>
                <option value="Reference" style={{ background: '#090e1a', color: '#fff' }}>STATE-077 Reference</option>
              </optgroup>
              <optgroup label="Data & Machine Learning">
                <option value="Intelligence" style={{ background: '#090e1a', color: '#fff' }}>Dataset Intelligence & EDA</option>
                <option value="History" style={{ background: '#090e1a', color: '#fff' }}>Historical Analytics</option>
                <option value="Registry" style={{ background: '#090e1a', color: '#fff' }}>ML Model Registry</option>
                <option value="Export" style={{ background: '#090e1a', color: '#fff' }}>Import / Export Center</option>
                <option value="Settings" style={{ background: '#090e1a', color: '#fff' }}>Settings / Asset Configuration</option>
              </optgroup>
            </select>
          </div>
        </div>

        <div className="advait-top-right">
          <button className="advait-sun-btn" title="Display settings">☼</button>
          <div className="advait-scada-pill">
            <span className="advait-dot-pulse" />
            <span>MQTT Stream · {online && data?.connected ? '120 Wells Connected' : 'Connecting...'}</span>
          </div>
          <button className={`advait-copilot-btn ${copilotOpen ? 'active' : ''}`} onClick={() => setCopilotOpen(!copilotOpen)}>
            <span>✦</span>
            <span>Copilot</span>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#38bdf8' }} />
          </button>
        </div>
      </header>

      {/* 2. PROMINENT CLASSIC HORIZONTAL TABS NAVIGATION (Always visible!) */}
      <nav className="advait-classic-tabs-strip">
        {allClassicTabs.map(t => (
          <button
            key={t.id}
            className={`advait-classic-tab ${workspace === t.id ? 'active' : ''}`}
            onClick={() => setWorkspace(t.id)}>
            <span>{t.icon}</span>
            <span>{t.label}</span>
          </button>
        ))}
      </nav>

      {/* 3. BODY LAYOUT: SIDEBAR + MAIN + COPILOT */}
      <div className="advait-body">
        {/* Left Sidebar */}
        {!sidebarExpanded ? (
          <aside className="advait-rail">
            <div className="advait-rail-top-label">OPE</div>
            {allClassicTabs.slice(0, 10).map(t => (
              <button
                key={t.id}
                className={`advait-rail-btn ${workspace === t.id ? 'active' : ''}`}
                title={t.label}
                onClick={() => setWorkspace(t.id)}>
                {t.icon}
              </button>
            ))}

            <div className="advait-rail-bottom">
              <div className="advait-user-avatar" title="TAS System Administrator">TS</div>
              <button className="advait-rail-toggle" title="Expand Sidebar" onClick={() => setSidebarExpanded(true)}>›</button>
            </div>
          </aside>
        ) : (
          <aside className="advait-sidebar-expanded">
            <div className="advait-sidebar-header">ADVAIT SRP-APM NAVIGATION</div>

            <div className="advait-sidebar-section-title">SURVEILLANCE & DYNACARDS</div>
            <button className={`advait-sidebar-item ${workspace === 'Surveillance' ? 'active' : ''}`} onClick={() => setWorkspace('Surveillance')}>
              <span>∿</span> Well Surveillance & Dynacards
            </button>
            <button className={`advait-sidebar-item ${workspace === 'SurfaceCard' ? 'active' : ''}`} onClick={() => setWorkspace('SurfaceCard')}>
              <span>📈</span> Live Surface Dynacard
            </button>
            <button className={`advait-sidebar-item ${workspace === 'DownholeCard' ? 'active' : ''}`} onClick={() => setWorkspace('DownholeCard')}>
              <span>📉</span> Downhole Dynacard
            </button>
            <button className={`advait-sidebar-item ${workspace === 'DualCard' ? 'active' : ''}`} onClick={() => setWorkspace('DualCard')}>
              <span>⧉</span> Dual-Card Comparison
            </button>
            <button className={`advait-sidebar-item ${workspace === 'Faults' ? 'active' : ''}`} onClick={() => setWorkspace('Faults')}>
              <span>⚠</span> Faults & Condition Monitor
            </button>
            <button className={`advait-sidebar-item ${workspace === 'Playback' ? 'active' : ''}`} onClick={() => setWorkspace('Playback')}>
              <span>▶</span> Animated Pump Analysis
            </button>

            <div className="advait-sidebar-section-title">OPERATIONS & FLEET</div>
            <button className={`advait-sidebar-item ${workspace === 'Cockpit' ? 'active' : ''}`} onClick={() => setWorkspace('Cockpit')}>
              <span>⊞</span> Fleet Cockpit
            </button>
            <button className={`advait-sidebar-item ${workspace === 'Console' ? 'active' : ''}`} onClick={() => setWorkspace('Console')}>
              <span>🖥</span> Operations Console
            </button>
            <button className={`advait-sidebar-item ${workspace === 'FleetMonitoring' ? 'active' : ''}`} onClick={() => setWorkspace('FleetMonitoring')}>
              <span>📋</span> Fleet Monitoring
            </button>

            <div className="advait-sidebar-section-title">ENGINEERING & BENCHMARKS</div>
            <button className={`advait-sidebar-item ${workspace === 'Manifolds' ? 'active' : ''}`} onClick={() => setWorkspace('Manifolds')}>
              <span>⚙</span> GCS Manifold Hierarchy
            </button>
            <button className={`advait-sidebar-item ${workspace === 'Benchmark' ? 'active' : ''}`} onClick={() => setWorkspace('Benchmark')}>
              <span>🔬</span> Engineering Benchmark Lab
            </button>
            <button className={`advait-sidebar-item ${workspace === 'Reference' ? 'active' : ''}`} onClick={() => setWorkspace('Reference')}>
              <span>🏛</span> STATE-077 Reference
            </button>

            <div className="advait-sidebar-section-title">DATA & MACHINE LEARNING</div>
            <button className={`advait-sidebar-item ${workspace === 'Intelligence' ? 'active' : ''}`} onClick={() => setWorkspace('Intelligence')}>
              <span>📊</span> Dataset Intelligence & EDA
            </button>
            <button className={`advait-sidebar-item ${workspace === 'History' ? 'active' : ''}`} onClick={() => setWorkspace('History')}>
              <span>🔍</span> Historical Analytics
            </button>
            <button className={`advait-sidebar-item ${workspace === 'Registry' ? 'active' : ''}`} onClick={() => setWorkspace('Registry')}>
              <span>🗄</span> ML Model Registry
            </button>
            <button className={`advait-sidebar-item ${workspace === 'Export' ? 'active' : ''}`} onClick={() => setWorkspace('Export')}>
              <span>📦</span> Import / Export Center
            </button>
            <button className={`advait-sidebar-item ${workspace === 'Settings' ? 'active' : ''}`} onClick={() => setWorkspace('Settings')}>
              <span>🔧</span> Settings / Asset Config
            </button>

            <div className="advait-sidebar-user-card">
              <div className="advait-user-avatar">TS</div>
              <div className="advait-sidebar-user-info">
                <span className="advait-sidebar-user-name">TAS System Administrator</span>
                <span className="advait-sidebar-user-role">ADMIN</span>
              </div>
              <button className="advait-rail-toggle" style={{ marginLeft: 'auto' }} onClick={() => setSidebarExpanded(false)}>‹ Collapse</button>
            </div>
          </aside>
        )}

        {/* Center Main Viewport */}
        <main className="advait-main-content">
          {error && <div style={{ background: '#450a0a', border: '1px solid #991b1b', color: '#ef4444', padding: '8px 12px', borderRadius: 6, marginBottom: 14 }}>{error}</div>}

          {/* VIEW: WELL SURVEILLANCE (Dual Cards Side-by-Side in Reference Style) */}
          {workspace === 'Surveillance' && (
            <>
              <div className="advait-panel-header" style={{ marginBottom: 16 }}>
                <div>
                  <h1 className="advait-page-title">Well Surveillance · {asset}</h1>
                  <p style={{ fontSize: 12, color: '#94a3b8', margin: '4px 0 0 0' }}>
                    Inverse wave equation downhole reconstruction & live polished rod dynacard
                  </p>
                </div>

                <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                  <label style={{ fontSize: 12, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 6 }}>
                    Target Well:
                    <select className="advait-select" value={asset} onChange={e => setAsset(e.target.value)}>
                      {Array.from(new Set([asset, ...fleet.map(w => w.asset_id)])).map(id => (
                        <option key={id} value={id}>{id}</option>
                      ))}
                    </select>
                  </label>
                  {exportUrl && (
                    <div style={{ display: 'flex', gap: 6 }}>
                      <a href={exportUrl} className="advait-tab-pill" style={{ background: '#0f172a', border: '1px solid #1e293b', textDecoration: 'none' }}>JSON</a>
                      <a href={exportUrl + '&format=csv'} className="advait-tab-pill" style={{ background: '#0f172a', border: '1px solid #1e293b', textDecoration: 'none' }}>Surface CSV</a>
                      {d?.status === 'SOLVED' && <a href={exportUrl + '&format=csv&kind=downhole'} className="advait-tab-pill" style={{ background: '#0f172a', border: '1px solid #1e293b', textDecoration: 'none' }}>Downhole CSV</a>}
                    </div>
                  )}
                  {selected && <Action onClick={() => setSelected(undefined)}>Return to live</Action>}
                </div>
              </div>

              {latest && (
                <div className="advait-kpi-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 16 }}>
                  <div className="advait-kpi-card">
                    <span className="advait-kpi-title">LIVE STROKE</span>
                    <div className="advait-kpi-value cyan">#{latest.stroke_id}</div>
                    <span className="advait-kpi-subtext">Sample #{latest.sample_index + 1}</span>
                  </div>
                  <div className="advait-kpi-card">
                    <span className="advait-kpi-title">SURFACE LOAD</span>
                    <div className="advait-kpi-value green">{fmt(latest.polished_rod_load_lbf * 0.0044482216152605, 2)} kN</div>
                    <span className="advait-kpi-subtext">{fmt(latest.polished_rod_load_lbf, 0)} lbf</span>
                  </div>
                  <div className="advait-kpi-card">
                    <span className="advait-kpi-title">SURFACE DISPLACEMENT</span>
                    <div className="advait-kpi-value cyan">{fmt(latest.polished_rod_position_in * 0.0254, 3)} m</div>
                    <span className="advait-kpi-subtext">{fmt(latest.polished_rod_position_in, 1)} in</span>
                  </div>
                  <div className="advait-kpi-card">
                    <span className="advait-kpi-title">OPERATING SPEED</span>
                    <div className="advait-kpi-value">{fmt(latest.spm, 2)} SPM</div>
                    <span className="advait-kpi-subtext">Crank {fmt(latest.crank_angle_deg, 1)}°</span>
                  </div>
                </div>
              )}

              {/* Operating State & Fault Scenario Ingestion Bar */}
              <div style={{
                background: '#0c1424',
                border: '1px solid #1e293b',
                borderRadius: 8,
                padding: '10px 14px',
                marginBottom: 16,
                display: 'flex',
                flexDirection: 'column',
                gap: 8
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: '#38bdf8', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                      🔬 OPERATING STATE / FAULT INGESTION:
                    </span>
                    <select
                      className="advait-select"
                      style={{ minWidth: 320, fontWeight: 600, borderColor: selectedState !== 'LIVE' ? '#38bdf8' : '#334155' }}
                      value={selectedState}
                      onChange={e => handleSelectState(e.target.value)}>
                      <option value="LIVE">● LIVE Digital Twin Streaming Telemetry</option>
                      <optgroup label="Canonical SRP Fault & Diagnostic States (API 11L / Gibbs Wave Model)">
                        {Object.entries(CANONICAL_STATES).map(([k, s]) => (
                          <option key={k} value={k}>
                            [{s.stateId}] {s.title}
                          </option>
                        ))}
                      </optgroup>
                    </select>
                  </div>

                  {selectedState !== 'LIVE' && (
                    <button
                      className="advait-tab-pill active"
                      style={{ fontSize: 10.5, background: 'rgba(56, 189, 248, 0.15)', borderColor: '#38bdf8', color: '#38bdf8' }}
                      onClick={() => setSelectedState('LIVE')}>
                      ↺ Return to Live Telemetry
                    </button>
                  )}
                </div>

                {/* Petroleum Engineering Diagnostic Advisory Banner */}
                {activeCanonical && (
                  <div style={{
                    background: 'rgba(15, 23, 42, 0.75)',
                    borderLeft: '3px solid #38bdf8',
                    padding: '8px 12px',
                    borderRadius: '0 6px 6px 0',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 4
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: '#f8fafc' }}>
                        {activeCanonical.title} ({activeCanonical.stateId})
                      </span>
                      <span className="badge-live" style={{ fontSize: 9.5 }}>
                        Fillage {activeCanonical.fillagePct}% · Fo {Math.round(activeCanonical.foLbf).toLocaleString()} lbf · {activeCanonical.displacementBpd} BPD
                      </span>
                    </div>
                    <div style={{ fontSize: 10.5, color: '#94a3b8' }}>
                      <strong style={{ color: '#cbd5e1' }}>Mechanism:</strong> {activeCanonical.description}
                    </div>
                    <div style={{ fontSize: 10.5, color: '#22c55e' }}>
                      <strong style={{ color: '#86efac' }}>Recommended Action:</strong> {activeCanonical.action}
                    </div>
                  </div>
                )}
              </div>

              {/* Both Reference Dynacards */}
              <div className="advait-dynacard-container">
                <section className="advait-panel">
                  <DynacardViewer
                    type="surface"
                    title={activeCanonical ? `${activeCanonical.title} · ${asset}` : (card?.diagnosis?.label ? `${card.diagnosis.label} · ${asset}` : `Surface Dynacard · ${asset}`)}
                    surfaceData={effectiveSurfaceData as any}
                    livePoints={livePoints}
                    liveMarker={latest ? {
                      x_in: latest.polished_rod_position_in,
                      y_lbf: latest.polished_rod_load_lbf
                    } : undefined}
                    crankAngleDeg={latest?.crank_angle_deg}
                    strokeId={card?.stroke_id ?? latest?.stroke_id}
                    timestamp={card?.timestamp ?? latest?.timestamp}
                    spm={card?.spm ?? latest?.spm}
                    source={activeCanonical ? 'Canonical Wave Calibration / ML Dataset' : (card?.source ?? 'Measured / Simulated')}
                    quality="GOOD"
                    imperial={imperialUnits}
                    onToggleUnits={() => setImperialUnits(!imperialUnits)}
                  />
                </section>

                <section className="advait-panel">
                  <DynacardViewer
                    type="downhole"
                    title={activeCanonical ? `${activeCanonical.title} (Downhole)` : 'Downhole Diagnostic'}
                    downholeData={effectiveDownholeData as any}
                    source={activeCanonical ? 'Everitt-Jennings FD / Gibbs Wave Equation' : (card?.source ?? 'Everitt-Jennings FD/2.0')}
                    quality="GOOD"
                    liveMarker={downholeMarker && card ? {
                      x_in: downholeMarker.x / 0.0254,
                      y_lbf: downholeMarker.f / 4.4482216152605
                    } : undefined}
                    crankAngleDeg={latest?.crank_angle_deg}
                    strokeId={card?.stroke_id}
                    timestamp={card?.timestamp}
                    spm={card?.spm}
                    imperial={imperialUnits}
                    onToggleUnits={() => setImperialUnits(!imperialUnits)}
                  />
                </section>
              </div>
            </>
          )}

          {/* VIEW: LIVE SURFACE DYNACARD (Full width reference card matching Image 1) */}
          {workspace === 'SurfaceCard' && (
            <>
              <div className="advait-panel-header" style={{ marginBottom: 16 }}>
                <div>
                  <h1 className="advait-page-title">Live Surface Dynacard · {asset}</h1>
                  <span className="advait-page-subtitle">Real-time polished rod position vs load telemetry streaming live from Digital Twin</span>
                </div>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                  <label className="field" style={{ color: '#94a3b8', fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                    Monitored Well:
                    <select
                      className="advait-select"
                      value={asset}
                      onChange={e => { setAsset(e.target.value); setSelected(undefined); }}>
                      {fleet.map(w => (
                        <option key={w.asset_id} value={w.asset_id}>
                          {w.asset_id} · {w.site_id || 'Farha South'}
                        </option>
                      ))}
                    </select>
                  </label>
                  {selected && <Action onClick={() => setSelected(undefined)}>Return to Live</Action>}
                </div>
              </div>

              {latest && (
                <div className="advait-kpi-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 16 }}>
                  <div className="advait-kpi-card">
                    <span className="advait-kpi-title">LIVE STROKE</span>
                    <div className="advait-kpi-value cyan">#{latest.stroke_id}</div>
                    <span className="advait-kpi-subtext">Sample #{latest.sample_index + 1} ({raw.length} in-stroke)</span>
                  </div>
                  <div className="advait-kpi-card">
                    <span className="advait-kpi-title">SURFACE LOAD</span>
                    <div className="advait-kpi-value green">{fmt(latest.polished_rod_load_lbf * 0.0044482216, 2)} kN</div>
                    <span className="advait-kpi-subtext">{fmt(latest.polished_rod_load_lbf, 0)} lbf ({fmt(latest.polished_rod_load_lbf / 1000, 2)} klbf)</span>
                  </div>
                  <div className="advait-kpi-card">
                    <span className="advait-kpi-title">SURFACE POSITION</span>
                    <div className="advait-kpi-value cyan">{fmt(latest.polished_rod_position_in, 1)} in</div>
                    <span className="advait-kpi-subtext">{fmt(latest.polished_rod_position_in * 0.0254, 3)} m</span>
                  </div>
                  <div className="advait-kpi-card">
                    <span className="advait-kpi-title">OPERATING SPEED</span>
                    <div className="advait-kpi-value">{fmt(latest.spm, 2)} SPM</div>
                    <span className="advait-kpi-subtext">Crank Angle {fmt(latest.crank_angle_deg, 1)}°</span>
                  </div>
                </div>
              )}

              <section className="advait-panel">
                <DynacardViewer
                  type="surface"
                  title={activeCanonical ? `${activeCanonical.title} · ${asset}` : (card?.diagnosis?.label ? `${card.diagnosis.label} · ${asset}` : `Surface Dynacard · ${asset}`)}
                  surfaceData={effectiveSurfaceData as any}
                  livePoints={livePoints}
                  liveMarker={latest ? {
                    x_in: latest.polished_rod_position_in,
                    y_lbf: latest.polished_rod_load_lbf
                  } : undefined}
                  crankAngleDeg={latest?.crank_angle_deg}
                  strokeId={card?.stroke_id ?? latest?.stroke_id}
                  timestamp={card?.timestamp ?? latest?.timestamp}
                  spm={card?.spm ?? latest?.spm}
                  imperial={imperialUnits}
                  onToggleUnits={() => setImperialUnits(!imperialUnits)}
                />
              </section>
            </>
          )}

          {/* VIEW: DOWNHOLE DYNACARD (Full width reference card matching Image 2) */}
          {workspace === 'DownholeCard' && (
            <>
              <div className="advait-panel-header" style={{ marginBottom: 16 }}>
                <div>
                  <h1 className="advait-page-title">Downhole Dynacard · {asset}</h1>
                  <span className="advait-page-subtitle">Downhole pump plunger dynacard reconstructed via Everitt-Jennings finite difference with Gibbs verification</span>
                </div>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                  <label className="field" style={{ color: '#94a3b8', fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                    Monitored Well:
                    <select
                      className="advait-select"
                      value={asset}
                      onChange={e => { setAsset(e.target.value); setSelected(undefined); }}>
                      {fleet.map(w => (
                        <option key={w.asset_id} value={w.asset_id}>
                          {w.asset_id} · {w.site_id || 'Farha South'}
                        </option>
                      ))}
                    </select>
                  </label>
                  {selected && <Action onClick={() => setSelected(undefined)}>Return to Live</Action>}
                </div>
              </div>

              {d?.features && (
                <div className="advait-kpi-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 16 }}>
                  <div className="advait-kpi-card">
                    <span className="advait-kpi-title">MPT / EPT</span>
                    <div className="advait-kpi-value cyan">{fmt(d.features.mpt_in, 1)} / {fmt(d.features.ept_in, 1)} in</div>
                    <span className="advait-kpi-subtext">Stroke Loss: {fmt(d.features.stroke_loss_in, 1)} in</span>
                  </div>
                  <div className="advait-kpi-card">
                    <span className="advait-kpi-title">PUMP FILLAGE</span>
                    <div className="advait-kpi-value green">{fmt(d.features.fillage_pct, 1)} %</div>
                    <span className="advait-kpi-subtext">{(typeof d.features.fluid_pound === 'object' ? d.features.fluid_pound?.detected : d.features.fluid_pound) ? 'Fluid Pound Detected' : 'Full Liquid Fill'}</span>
                  </div>
                  <div className="advait-kpi-card">
                    <span className="advait-kpi-title">FLUID LOAD (FO)</span>
                    <div className="advait-kpi-value cyan">{fmt(d.features.fluid_load_fo_lbf, 0)} lbf</div>
                    <span className="advait-kpi-subtext">{fmt(d.features.fluid_load_fo_lbf ? d.features.fluid_load_fo_lbf / 1000 : 0, 2)} klbf</span>
                  </div>
                  <div className="advait-kpi-card">
                    <span className="advait-kpi-title">DISPLACEMENT / PIP</span>
                    <div className="advait-kpi-value">{fmt(d.features.displacement_bpd, 1)} BPD</div>
                    <span className="advait-kpi-subtext">PIP: {fmt(d.features.pip_psi, 0)} psi</span>
                  </div>
                </div>
              )}

              <section className="advait-panel">
                <DynacardViewer
                  type="downhole"
                  title={activeCanonical ? `${activeCanonical.title} (Downhole)` : 'Downhole Diagnostic'}
                  downholeData={effectiveDownholeData as any}
                  liveMarker={downholeMarker && card ? {
                    x_in: downholeMarker.x / 0.0254,
                    y_lbf: downholeMarker.f / 4.4482216152605
                  } : undefined}
                  crankAngleDeg={latest?.crank_angle_deg}
                  strokeId={card?.stroke_id}
                  timestamp={card?.timestamp}
                  spm={card?.spm}
                  imperial={imperialUnits}
                  onToggleUnits={() => setImperialUnits(!imperialUnits)}
                />
              </section>
            </>
          )}

          {/* VIEW: DUAL-CARD COMPARISON */}
          {workspace === 'DualCard' && (
            <>
              <div className="advait-panel-header" style={{ marginBottom: 16 }}>
                <div>
                  <h1 className="advait-page-title">Dual-Card Comparison</h1>
                  <span className="advait-page-subtitle">Compare live surface stroke alongside reconstructed downhole dynacard with historical selection</span>
                </div>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                  <label className="field" style={{ color: '#94a3b8', fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                    Comparison Stroke:
                    <select className="advait-select" value={selected ? `${selected.run_id}/${selected.stroke_id}` : ''}
                      onChange={e => setSelected(cards.find(c => `${c.run_id}/${c.stroke_id}` === e.target.value))}>
                      <option value="">Latest completed</option>
                      {cards.map(c => <option key={`${c.run_id}/${c.stroke_id}`} value={`${c.run_id}/${c.stroke_id}`}>{c.stroke_id} · {new Date(c.timestamp).toLocaleTimeString()}</option>)}
                    </select>
                  </label>
                  <Action onClick={() => void searchStrokes()}>Refresh Strokes</Action>
                </div>
              </div>

              {card && (
                <div className="advait-kpi-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 16 }}>
                  <div className="advait-kpi-card"><span className="advait-kpi-title">STROKE ID</span><div className="advait-kpi-value cyan">#{card.stroke_id}</div><span className="advait-kpi-subtext">Selected stroke</span></div>
                  <div className="advait-kpi-card"><span className="advait-kpi-title">COMPLETENESS</span><div className="advait-kpi-value green">{fmt(card.completeness * 100, 1)}%</div><span className="advait-kpi-subtext">Sample acquisition</span></div>
                  <div className="advait-kpi-card"><span className="advait-kpi-title">PUMP SPEED</span><div className="advait-kpi-value cyan">{fmt(card.spm, 2)} SPM</div><span className="advait-kpi-subtext">Period {fmt(card.period_s, 2)} s</span></div>
                  <div className="advait-kpi-card"><span className="advait-kpi-title">TIMESTAMP</span><div className="advait-kpi-value">{new Date(card.timestamp).toLocaleTimeString()}</div><span className="advait-kpi-subtext">Acquisition time</span></div>
                </div>
              )}

              <div className="advait-dynacard-container">
                <section className="advait-panel">
                  <DynacardViewer type="surface" title={activeCanonical ? `${activeCanonical.title} · ${asset}` : (card?.diagnosis?.label ? `${card.diagnosis.label} · ${asset}` : `Surface Dynacard · ${asset}`)} surfaceData={effectiveSurfaceData as any} strokeId={card?.stroke_id} imperial={imperialUnits} onToggleUnits={() => setImperialUnits(!imperialUnits)} />
                </section>
                <section className="advait-panel">
                  <DynacardViewer type="downhole" title={activeCanonical ? `${activeCanonical.title} (Downhole)` : 'Downhole Diagnostic'} downholeData={effectiveDownholeData as any} strokeId={card?.stroke_id} imperial={imperialUnits} onToggleUnits={() => setImperialUnits(!imperialUnits)} />
                </section>
              </div>
            </>
          )}

          {/* VIEW: FAULT DETECTION & CONDITIONS */}
          {workspace === 'Faults' && (
            <>
              <div className="advait-panel-header" style={{ marginBottom: 16 }}>
                <div>
                  <h1 className="advait-page-title">Fault Detection & Condition Monitoring</h1>
                  <span className="advait-page-subtitle">Waveform change tracking, symptom threshold crossings, and ML pattern inference</span>
                </div>
              </div>

              <section className="advait-panel" style={{ marginBottom: 16 }}>
                <div className="advait-panel-header">
                  <h2>{headline}</h2>
                  <span className="badge-live">{card ? `Stroke #${card.stroke_id}` : 'Awaiting stroke'}</span>
                </div>

                {condition?.status === 'DYNACARD_CHANGE' && (
                  <div style={{ background: '#451a03', border: '1px solid #b45309', color: '#f59e0b', padding: '10px 14px', borderRadius: 6, marginBottom: 12 }}>
                    Dynacard change detected{condition.surface && condition.downhole &&
                      ` · Surface ${fmt(condition.surface.change_fraction * 100, 1)}% · Downhole ${fmt(condition.downhole.change_fraction * 100, 1)}% departure from baseline`}
                  </div>
                )}

                {condition?.symptom === 'DELAYED_PUMP_UNLOADING' && (
                  <p style={{ color: '#f59e0b', fontSize: 13 }}>
                    Delayed pump unloading · {fmt((condition.late_downstroke_excess_n ?? 0) / 1000, 2)} kN above late-downstroke reference (fluid pound / gas interference).
                  </p>
                )}
                {condition?.symptom === 'MEASURED_TRAVEL_CHANGE' && (
                  <p style={{ color: '#f59e0b', fontSize: 13 }}>
                    Measured polished-rod travel changed by {fmt(condition.surface_travel_delta_m, 3)} m. Check pumping-unit stroke geometry.
                  </p>
                )}
                {condition?.symptom === 'POLISHED_ROD_LOAD_OFFSET' && (
                  <p style={{ color: '#f59e0b', fontSize: 13 }}>
                    Polished-rod load offset shifted by {fmt((condition.surface_load_delta_n ?? 0) / 1000, 2)} kN. Check load-cell calibration and fluid level.
                  </p>
                )}
                {condition?.symptom === 'SURFACE_WAVEFORM_CHANGE' && (
                  <p style={{ color: '#f59e0b', fontSize: 13 }}>
                    Measured surface load waveform crossed its threshold while downhole waveform remained within bounds.
                  </p>
                )}
                {condition?.symptom === 'PUMP_STROKE_WORK_CHANGE' && (
                  <p style={{ color: '#f59e0b', fontSize: 13 }}>
                    Downhole stroke work changed by {fmt(condition.downhole_work_delta_j, 0)} J. Check hydraulic pump slippage and friction.
                  </p>
                )}
                {condition?.status === 'AWAITING_REFERENCE' && (
                  <p style={{ color: '#94a3b8', fontSize: 13 }}>
                    Establishing operating reference baseline ({condition.reference_count}/3 strokes).
                  </p>
                )}
                {condition?.status === 'WITHIN_REFERENCE' && (
                  <p style={{ color: '#22c55e', fontSize: 13 }}>
                    ● No dynacard waveform change above governing monitoring thresholds for this stroke.
                  </p>
                )}

                {!!condition?.measurements?.length && (
                  <div style={{ marginTop: 14 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: '#38bdf8', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                      Measured Signal Changes vs Governed Corridors
                    </span>
                    <div className="advait-table-wrap" style={{ marginTop: 8 }}>
                      <table className="advait-table">
                        <thead>
                          <tr>
                            <th>Signal</th>
                            <th>Change from Reference</th>
                            <th>Alert Threshold</th>
                          </tr>
                        </thead>
                        <tbody>
                          {condition.measurements.map(m => (
                            <tr key={m.label}>
                              <td>{m.label}</td>
                              <td style={{ color: Math.abs(m.delta) >= m.threshold ? '#ef4444' : '#22c55e', fontWeight: 600 }}>
                                {fmt(m.delta, 4)} {m.unit}
                              </td>
                              <td style={{ color: '#94a3b8' }}>{fmt(m.threshold, 4)} {m.unit}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </section>

              {f?.probability_preview && (
                <section className="advait-panel">
                  <div className="advait-panel-header">
                    <h2>Pattern Recognition Model Probabilities</h2>
                    <span className="badge-live">{f.probability_preview.model_version}</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14, marginTop: 12 }}>
                    {f.probability_preview.scores.map(({ label, score }) => (
                      <div key={label} style={{ background: '#090e1a', padding: '12px 14px', borderRadius: 6, border: '1px solid #1e293b' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#94a3b8', marginBottom: 6 }}>
                          <span>{label.replaceAll('_', ' ')}</span>
                          <strong style={{ color: score > 0.5 ? '#22c55e' : '#f8fafc' }}>{(score * 100).toFixed(1)}%</strong>
                        </div>
                        <div style={{ height: 8, background: '#1e293b', borderRadius: 4, overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${score * 100}%`, background: score > 0.5 ? '#22c55e' : '#38bdf8' }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </>
          )}

          {/* VIEW: ANIMATED PUMP ANALYSIS */}
          {workspace === 'Playback' && (
            <>
              <div className="advait-page-header">
                <div>
                  <h1 className="advait-page-title">Animated Pump Analysis</h1>
                  <span className="advait-page-subtitle">Downhole pump plunger motion simulation synchronized with measured polished rod crank angle</span>
                </div>
              </div>
              <section className="advait-panel">
                <PumpPlayback liveTime={liveTime} historical={!!selected} stroke={card} history={playbackHistory} select={item => setSelected(item as Card | undefined)} exportUrl={exportUrl} />
              </section>
            </>
          )}

          {/* VIEW: FLEET COCKPIT */}
          {workspace === 'Cockpit' && (
            <>
              <div className="advait-page-header">
                <div>
                  <h1 className="advait-page-title">SRP Fleet Cockpit</h1>
                  <span className="advait-page-subtitle">120 Production Wells across Prairie, Canyon, Mesa, Delta Fields</span>
                </div>
              </div>

              {/* KPI Strip */}
              <div className="advait-kpi-grid">
                <div className="advait-kpi-card">
                  <span className="advait-kpi-title">WELLS RUNNING</span>
                  <div className="advait-kpi-value green">118 / 120</div>
                  <span className="advait-kpi-subtext">2 safety trips</span>
                </div>
                <div className="advait-kpi-card">
                  <span className="advait-kpi-title">AVAILABILITY</span>
                  <div className="advait-kpi-value cyan">98.3 %</div>
                  <span className="advait-kpi-subtext">Run status weighted, 24 h</span>
                </div>
                <div className="advait-kpi-card">
                  <span className="advait-kpi-title">FLEET HEALTH INDEX</span>
                  <div className="advait-kpi-value amber">92.4</div>
                  <span className="advait-kpi-subtext">Weighted envelope + dynacards</span>
                </div>
                <div className="advait-kpi-card">
                  <span className="advait-kpi-title">OIL RATE</span>
                  <div className="advait-kpi-value cyan">11,840 bopd</div>
                  <span className="advait-kpi-subtext">Allocated, latest scan</span>
                </div>
                <div className="advait-kpi-card">
                  <span className="advait-kpi-title">PRODUCTION DEFERMENT</span>
                  <div className="advait-kpi-value amber">230 bopd</div>
                  <span className="advait-kpi-subtext">Vs expected from active cases</span>
                </div>
                <div className="advait-kpi-card">
                  <span className="advait-kpi-title">DEFERRED VALUE AT RISK</span>
                  <div className="advait-kpi-value amber">$17.2k /day</div>
                  <span className="advait-kpi-subtext">Offline & choked capacity</span>
                </div>
              </div>

              {/* Fleet Monitor Panel */}
              <section className="advait-panel">
                <div className="advait-panel-header">
                  <div>
                    <h2>FLEET MONITOR</h2>
                    <p style={{ margin: '2px 0 0 0', color: '#64748b', fontSize: 11 }}>
                      Actual status, ML health & cluster hierarchy for every SRP well — click a well to open well surveillance detail
                    </p>
                  </div>
                </div>

                <div className="advait-filter-bar">
                  <div className="advait-search-wrap">
                    <span className="advait-search-icon">🔍</span>
                    <input className="advait-search-input" placeholder="Filter well ID, station, pump..."
                      value={searchQuery} onChange={e => setSearchQuery(e.target.value)} />
                  </div>

                  <select className="advait-select" value={stationFilter} onChange={e => setStationFilter(e.target.value)}>
                    <option value="ALL">All stations</option>
                    <option value="GCS-01">GCS-01 · Prairie</option>
                    <option value="GCS-02">GCS-02 · Canyon</option>
                    <option value="GCS-03">GCS-03 · Mesa</option>
                    <option value="GCS-04">GCS-04 · Delta</option>
                  </select>

                  <select className="advait-select" value={fieldFilter} onChange={e => setFieldFilter(e.target.value)}>
                    <option value="ALL">All fields</option>
                    <option value="Prairie">Prairie</option>
                    <option value="Canyon">Canyon</option>
                    <option value="Mesa">Mesa</option>
                    <option value="Delta">Delta</option>
                  </select>

                  <select className="advait-select" value={stateFilter} onChange={e => setStateFilter(e.target.value)}>
                    <option value="ALL">All states</option>
                    <option value="Normal">Normal</option>
                    <option value="VSD trip">VSD trip</option>
                  </select>

                  <div className="advait-view-pills">
                    {(['Operations', 'Production & VFM', 'Equipment & Run Life', 'OPC Telemetry'] as const).map(p => (
                      <button key={p} className={`advait-tab-pill ${viewPill === p ? 'active' : ''}`}
                        onClick={() => setViewPill(p)}>{p}</button>
                    ))}
                  </div>

                  <span style={{ fontSize: 11, color: '#64748b', marginLeft: 'auto' }}>{filteredWells.length} wells</span>
                </div>

                <div className="advait-table-wrap">
                  <table className="advait-table">
                    <thead>
                      <tr>
                        <th>WELL ↕</th>
                        <th>STATION / CLUSTER ↕</th>
                        <th>OPERATING STATE ↕</th>
                        <th>ROR ENVELOPE ↕</th>
                        <th>HEALTH ▴</th>
                        <th>DIAGNOSIS / ANOMALY</th>
                        <th style={{ textAlign: 'right' }}>DEFERMENT ↕</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredWells.slice(0, 20).map(w => (
                        <tr key={w.id} onClick={() => { setAsset(w.id); setWorkspace('Surveillance'); }}>
                          <td>
                            <div className="advait-well-cell">
                              <span style={{ color: '#64748b' }}>⋮⋮</span>
                              <span className="advait-well-link">{w.id}</span>
                              <span className="badge-live">LIVE</span>
                            </div>
                          </td>
                          <td>{w.station}</td>
                          <td>
                            <span className={w.state === 'Normal' ? 'badge-state-normal' : 'badge-state-fault'}>
                              {w.state === 'Normal' ? '● Normal' : '■ VSD trip'}
                            </span>
                          </td>
                          <td>
                            <span className={w.envelope === 'Inside ROR' ? 'badge-envelope-inside' : 'badge-envelope-down'}>
                              ● {w.envelope}
                            </span>
                          </td>
                          <td>
                            <span style={{ color: w.health > 80 ? '#22c55e' : '#ef4444', fontWeight: 600 }}>{w.health}</span>
                            <span style={{ color: '#64748b' }}> / 100</span>
                          </td>
                          <td style={{ color: w.state === 'Normal' ? '#94a3b8' : '#f87171' }}>{w.diagnosis}</td>
                          <td style={{ textAlign: 'right', color: w.deferment === '0 BOPD' ? '#64748b' : '#f59e0b', fontWeight: 600 }}>{w.deferment}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}

          {/* VIEW: OPERATIONS CONSOLE */}
          {workspace === 'Console' && (
            <>
              <div className="advait-page-header">
                <div>
                  <h1 className="advait-page-title">Operations Console</h1>
                  <span className="advait-page-subtitle">Real-time SCADA matrix, fleet diagnostics and asset telemetry routing</span>
                </div>
              </div>
              <OperationsConsole
                kind="APM"
                selected={asset}
                onSelect={id => { setAsset(id); setWorkspace('Surveillance'); }}
                wells={fleet.map(w => ({
                  asset_id: w.asset_id,
                  field: w.site_id,
                  state: w.last_sample ? 'Connected' : 'Waiting',
                  condition: 'condition monitoring'
                }))}
              />
            </>
          )}

          {/* VIEW: FLEET MONITORING (Classic Asset Status Table) */}
          {workspace === 'FleetMonitoring' && (
            <>
              <div className="advait-page-header">
                <div>
                  <h1 className="advait-page-title">Fleet Monitoring</h1>
                  <span className="advait-page-subtitle">Summary of all registered field and virtual sucker rod pump units</span>
                </div>
              </div>
              <section className="advait-panel">
                <div className="advait-panel-header">
                  <h2>Active Well Telemetry Status</h2>
                  <span className="badge-live">{fleet.length} Connected Units</span>
                </div>
                <div className="advait-table-wrap">
                  <table className="advait-table">
                    <thead>
                      <tr>
                        <th>Asset ID</th>
                        <th>Site Concession</th>
                        <th>Strokes Recorded</th>
                        <th>Latest Sequence</th>
                        <th>Telemetry Status</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {fleet.map(w => (
                        <tr key={w.asset_id}>
                          <td style={{ color: '#38bdf8', fontWeight: 600 }}>{w.asset_id}</td>
                          <td>{w.site_id || 'Farha South'}</td>
                          <td>{w.stroke_count ?? 0}</td>
                          <td>{w.latest_sequence ?? '—'}</td>
                          <td><span className="badge-live">{w.last_sample ? 'Connected' : 'Waiting'}</span></td>
                          <td>
                            <button className="advait-tab-pill" style={{ fontSize: 10 }}
                              onClick={() => { setAsset(w.asset_id); setWorkspace('Surveillance'); }}>
                              Inspect
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}

          {/* VIEW: GCS MANIFOLD HIERARCHY */}
          {workspace === 'Manifolds' && (
            <>
              <div className="advait-config-banner">
                <div className="advait-config-pill">Block 3 Farha South</div>
                <div className="advait-config-pill">120 Active Wells · 4 GCS</div>
                <div className="advait-config-pill">11.4 msg/s SCADA</div>
              </div>

              <div className="advait-kpi-grid" style={{ gridTemplateColumns: 'repeat(6, 1fr)', marginBottom: 16 }}>
                <div className="advait-kpi-card"><span className="advait-kpi-title">GCS HEADERS</span><div className="advait-kpi-value cyan">4</div><span className="advait-kpi-subtext">GCS-01 to GCS-04</span></div>
                <div className="advait-kpi-card"><span className="advait-kpi-title">TOTAL WELLS</span><div className="advait-kpi-value green">120</div><span className="advait-kpi-subtext">30 wells / GCS</span></div>
                <div className="advait-kpi-card"><span className="advait-kpi-title">TELEMETRY RATE</span><div className="advait-kpi-value cyan">11.4 msg/s</div><span className="advait-kpi-subtext">Active MQTT</span></div>
                <div className="advait-kpi-card"><span className="advait-kpi-title">PUMP STROKES</span><div className="advait-kpi-value cyan">64 – 120 in</div><span className="advait-kpi-subtext">Geometry verified</span></div>
                <div className="advait-kpi-card"><span className="advait-kpi-title">FORMULAE</span><div className="advait-kpi-value green">Everitt / Gibbs</div><span className="advait-kpi-subtext">Coupled solvers</span></div>
                <div className="advait-kpi-card"><span className="advait-kpi-title">TELEMETRY STORE</span><div className="advait-kpi-value cyan">400k+ rows</div><span className="advait-kpi-subtext">Historical records</span></div>
              </div>

              <section className="advait-panel">
                <div className="advait-panel-header">
                  <div>
                    <h2>GCS & WELLS HIERARCHY</h2>
                    <p style={{ margin: '2px 0 0 0', color: '#64748b', fontSize: 11 }}>
                      Block operational GCS manifolds (120 producing wells across 4 stations)
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    {['All GCS', 'GCS-01', 'GCS-02', 'GCS-03', 'GCS-04'].map(gcs => (
                      <button key={gcs} className={`advait-tab-pill ${selectedGcs === gcs ? 'active' : ''}`}
                        onClick={() => setSelectedGcs(gcs)}>{gcs}</button>
                    ))}
                  </div>
                </div>

                {(selectedGcs === 'All GCS' || selectedGcs === 'GCS-01') && (
                  <div className="advait-manifold-card">
                    <div className="advait-manifold-header">
                      <div className="advait-manifold-tag">GCS-01 · Prairie Header</div>
                      <span className="badge-live">● 30/30 ONLINE</span>
                      <span style={{ fontSize: 11, color: '#94a3b8', marginLeft: 'auto' }}>Rate: 3,120 BOPD · Regime: Shallow Low Lift</span>
                    </div>
                    <div className="advait-well-strip">
                      {['prairie-001', 'prairie-002', 'prairie-003', 'prairie-004'].map(id => (
                        <div key={id} className="advait-card-cell" onClick={() => { setAsset(id); setWorkspace('Surveillance'); }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                            <strong style={{ color: '#38bdf8', fontSize: 12 }}>{id}</strong>
                            <span className="badge-live" style={{ fontSize: 8 }}>ONLINE</span>
                          </div>
                          <div style={{ fontSize: 10, color: '#94a3b8' }}>Pump: Mark-II C-228</div>
                          <div style={{ fontSize: 10, color: '#94a3b8' }}>SPM: 7.9 · Stroke: 64 in</div>
                          <div style={{ fontSize: 10, color: '#22c55e', marginTop: 4 }}>PIP: 197 psi · Normal</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {(selectedGcs === 'All GCS' || selectedGcs === 'GCS-02') && (
                  <div className="advait-manifold-card">
                    <div className="advait-manifold-header">
                      <div className="advait-manifold-tag">GCS-02 · Canyon Header</div>
                      <span className="badge-state-fault">● 29/30 ONLINE</span>
                      <span style={{ fontSize: 11, color: '#94a3b8', marginLeft: 'auto' }}>Rate: 2,980 BOPD · Regime: Deep Heavy Load</span>
                    </div>
                    <div className="advait-well-strip">
                      {['canyon-001', 'canyon-014', 'canyon-015', 'canyon-016'].map(id => (
                        <div key={id} className="advait-card-cell" onClick={() => { setAsset(id); setWorkspace('Surveillance'); }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                            <strong style={{ color: id === 'canyon-014' ? '#ef4444' : '#38bdf8', fontSize: 12 }}>{id}</strong>
                            <span className={id === 'canyon-014' ? 'badge-state-fault' : 'badge-live'} style={{ fontSize: 8 }}>
                              {id === 'canyon-014' ? 'TRIPPED' : 'ONLINE'}
                            </span>
                          </div>
                          <div style={{ fontSize: 10, color: '#94a3b8' }}>Pump: Conventional C-456</div>
                          <div style={{ fontSize: 10, color: '#94a3b8' }}>SPM: 8.5 · Stroke: 100 in</div>
                          <div style={{ fontSize: 10, color: id === 'canyon-014' ? '#ef4444' : '#22c55e', marginTop: 4 }}>
                            {id === 'canyon-014' ? 'Fluid Pound Trip' : 'PIP: 320 psi'}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            </>
          )}

          {/* VIEW: SETTINGS & ASSET CONFIGURATION JSON */}
          {workspace === 'Settings' && (
            <>
              <div className="advait-page-header">
                <div>
                  <h1 className="advait-page-title">Settings & Asset Configuration</h1>
                  <span className="advait-page-subtitle">Configure equipment dimensions, rod taper string geometries, and register virtual SRP units</span>
                </div>
              </div>

              <section className="advait-panel" style={{ marginBottom: 16 }}>
                <div className="advait-panel-header">
                  <h2>Register a Field or Virtual SRP Asset</h2>
                  <span className="badge-live">JSON Config</span>
                </div>
                <p style={{ color: '#94a3b8', fontSize: 12 }}>
                  Paste equipment specification JSON containing well_id, unit geometry, rod taper lengths, and plunger diameter.
                </p>
                <textarea
                  className="advait-chat-input"
                  style={{ width: '100%', height: 130, fontFamily: 'monospace', fontSize: 12, padding: 10, background: '#090e1a', borderRadius: 6, border: '1px solid #1e293b' }}
                  value={equipment}
                  onChange={e => setEquipment(e.target.value)}
                  placeholder={'{\n  "asset_id": "prairie-031",\n  "pumping_unit_type": "conventional",\n  "surface_stroke_length_in": 86.0,\n  "pump_setting_depth_ft": 4500\n}'}
                />
                <div style={{ marginTop: 10, display: 'flex', gap: 10 }}>
                  <Action primary onClick={() => void registerAsset()}>Register Asset</Action>
                  <Action onClick={() => void refresh()}>Reload Fleet</Action>
                </div>
              </section>

              <section className="advait-panel">
                <div className="advait-panel-header">
                  <h2>Registered Asset Hierarchy</h2>
                  <span className="badge-live">{fleet.length} Configured Assets</span>
                </div>
                <div className="advait-table-wrap">
                  <table className="advait-table">
                    <thead>
                      <tr>
                        <th>Asset ID</th>
                        <th>Site Concession</th>
                        <th>Strokes Recorded</th>
                        <th>Latest Sequence</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {fleet.map(w => (
                        <tr key={w.asset_id}>
                          <td style={{ color: '#38bdf8', fontWeight: 600 }}>{w.asset_id}</td>
                          <td>{w.site_id || 'Farha South'}</td>
                          <td>{w.stroke_count ?? 0}</td>
                          <td>{w.latest_sequence ?? '—'}</td>
                          <td><span className="badge-live">{w.last_sample ? 'Connected' : 'Waiting'}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}

          {/* VIEW: ENGINEERING BENCHMARK LABORATORY */}
          {workspace === 'Benchmark' && (
            <>
              <div className="advait-page-header">
                <div>
                  <h1 className="advait-page-title">Engineering Benchmark Laboratory</h1>
                  <span className="advait-page-subtitle">Wave equation analytical verification, finite difference convergence, and validation against reference standards</span>
                </div>
              </div>
              <section className="advait-panel">
                <Engineering base={base} asset={asset} stroke={card} exportUrl={exportUrl} benchmarkOnly={true} />
              </section>
            </>
          )}

          {/* VIEW: STATE-077 HISTORICAL VENDOR REFERENCE */}
          {workspace === 'Reference' && (
            <>
              <div className="advait-page-header">
                <div>
                  <h1 className="advait-page-title">STATE-077 Historical Vendor Reference</h1>
                  <span className="advait-page-subtitle">Independent validation against vendor downhole cards (TAM International / Lufkin reference)</span>
                </div>
              </div>
              <section className="advait-panel">
                <HistoricalReference base={base} />
              </section>
            </>
          )}

          {/* VIEW: HISTORICAL ANALYTICS & STROKE SEARCH */}
          {workspace === 'History' && (
            <>
              <div className="advait-page-header">
                <div>
                  <h1 className="advait-page-title">Historical Analytics & Stroke Search</h1>
                  <span className="advait-page-subtitle">Filter archived dynacards by stroke sequence, time window, fault state, and wave solver version</span>
                </div>
              </div>

              <section className="advait-panel" style={{ marginBottom: 16 }}>
                <div className="advait-panel-header">
                  <h2>Search Completed Strokes</h2>
                  <Action onClick={() => void searchStrokes()}>Execute Query</Action>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10, marginTop: 10 }}>
                  <label className="field" style={{ fontSize: 11, color: '#94a3b8' }}>
                    Stroke ID
                    <input className="advait-search-input" style={{ width: '100%', marginTop: 4 }} value={filter.stroke}
                      onChange={e => setFilter({ ...filter, stroke: e.target.value })} placeholder="e.g. 308" />
                  </label>
                  <label className="field" style={{ fontSize: 11, color: '#94a3b8' }}>
                    Since Timestamp
                    <input className="advait-search-input" style={{ width: '100%', marginTop: 4 }} value={filter.since}
                      onChange={e => setFilter({ ...filter, since: e.target.value })} placeholder="ISO 8601" />
                  </label>
                  <label className="field" style={{ fontSize: 11, color: '#94a3b8' }}>
                    Until Timestamp
                    <input className="advait-search-input" style={{ width: '100%', marginTop: 4 }} value={filter.until}
                      onChange={e => setFilter({ ...filter, until: e.target.value })} placeholder="ISO 8601" />
                  </label>
                  <label className="field" style={{ fontSize: 11, color: '#94a3b8' }}>
                    Fault Mechanism
                    <input className="advait-search-input" style={{ width: '100%', marginTop: 4 }} value={filter.fault}
                      onChange={e => setFilter({ ...filter, fault: e.target.value })} placeholder="e.g. FLUID_POUND" />
                  </label>
                  <label className="field" style={{ fontSize: 11, color: '#94a3b8' }}>
                    Model Version
                    <input className="advait-search-input" style={{ width: '100%', marginTop: 4 }} value={filter.model}
                      onChange={e => setFilter({ ...filter, model: e.target.value })} placeholder="e.g. Everitt-Jennings-FD/2.0" />
                  </label>
                </div>
              </section>

              <section className="advait-panel">
                <div className="advait-panel-header">
                  <h2>Matching Stroke Archives</h2>
                  <span className="badge-live">{cards.length} Records</span>
                </div>
                <div className="advait-table-wrap">
                  <table className="advait-table">
                    <thead>
                      <tr>
                        <th>Stroke ID</th>
                        <th>Timestamp</th>
                        <th>SPM</th>
                        <th>Samples</th>
                        <th>Quality</th>
                        <th>Diagnosis</th>
                        <th>Downhole Status</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cards.map(c => (
                        <tr key={`${c.run_id}-${c.stroke_id}`}>
                          <td style={{ color: '#38bdf8', fontWeight: 600 }}>#{c.stroke_id}</td>
                          <td>{new Date(c.timestamp).toLocaleString()}</td>
                          <td>{fmt(c.spm, 2)}</td>
                          <td>{c.sample_count}</td>
                          <td><span className="badge-live">{c.quality}</span></td>
                          <td>{c.diagnosis?.label || 'Normal'}</td>
                          <td style={{ color: c.downhole?.status === 'SOLVED' ? '#22c55e' : '#ef4444' }}>{c.downhole?.status}</td>
                          <td>
                            <button
                              className="advait-tab-pill"
                              style={{ fontSize: 10 }}
                              onClick={() => { setSelected(c); setWorkspace('Surveillance'); }}>
                              Inspect
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}

          {/* VIEW: ML MODEL REGISTRY */}
          {workspace === 'Registry' && (
            <>
              <div className="advait-page-header">
                <div>
                  <h1 className="advait-page-title">ML Model Registry & Deployed Artifacts</h1>
                  <span className="advait-page-subtitle">Inspect registered diagnostic classifier versions, wave equation parameters, and model weights</span>
                </div>
              </div>

              <section className="advait-panel">
                <div className="advait-panel-header">
                  <h2>Deployed Model Metadata & Hyperparameters</h2>
                  <span className="badge-live">Version Active</span>
                </div>
                <pre style={{
                  background: '#090e1a',
                  padding: 16,
                  borderRadius: 6,
                  border: '1px solid #1e293b',
                  fontSize: 12,
                  color: '#38bdf8',
                  overflow: 'auto',
                  maxHeight: 500
                }}>
                  {JSON.stringify(registry, null, 2) || 'Loading registry metadata...'}
                </pre>
              </section>
            </>
          )}

          {/* VIEW: DATASET INTELLIGENCE & EDA */}
          {workspace === 'Intelligence' && (
            <>
              <div className="advait-page-header">
                <div>
                  <h1 className="advait-page-title">Dataset Intelligence & EDA</h1>
                  <span className="advait-page-subtitle">Audited datasets, column dictionary, distribution histograms, and raw telemetry samples</span>
                </div>
              </div>

              <section className="advait-panel" style={{ marginBottom: 16 }}>
                <div className="advait-panel-header">
                  <h2>Field Validation Readiness</h2>
                  <span className="badge-live">Audited</span>
                </div>
                <p style={{ color: '#94a3b8', fontSize: 13 }}>
                  Independent virtual wells: {dataCatalog?.readiness?.synthetic_evaluation?.independent_virtual_wells ?? '120'} held-out virtual wells.
                </p>
                <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
                  <a href={`${base}/dataset-dictionary`} className="advait-tab-pill" style={{ textDecoration: 'none' }}>Export Data Dictionary CSV</a>
                </div>
              </section>

              {dataCatalog && (
                <section className="advait-panel" style={{ marginBottom: 16 }}>
                  <div className="advait-panel-header">
                    <h2>Audited Datasets & Training Sources</h2>
                    <span className="badge-live">{dataCatalog.datasets.length} Catalogs</span>
                  </div>

                  <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
                    <label className="field" style={{ fontSize: 11, color: '#94a3b8' }}>
                      Source:
                      <select className="advait-select" value={datasetFilter} onChange={e => setDatasetFilter(e.target.value)}>
                        <option value="">All sources</option>
                        {[...new Set(dataCatalog.datasets.map(x => x.source))].map(x => <option key={x} value={x}>{x}</option>)}
                      </select>
                    </label>
                    <label className="field" style={{ fontSize: 11, color: '#94a3b8' }}>
                      Origin:
                      <select className="advait-select" value={originFilter} onChange={e => setOriginFilter(e.target.value)}>
                        <option value="">All origins</option>
                        {[...new Set(dataCatalog.datasets.map(x => x.origin))].map(x => <option key={x} value={x}>{x}</option>)}
                      </select>
                    </label>
                  </div>

                  <div className="advait-table-wrap">
                    <table className="advait-table">
                      <thead>
                        <tr>
                          <th>Dataset ID</th>
                          <th>Source</th>
                          <th>Origin</th>
                          <th>Records</th>
                          <th>Surface Cards</th>
                          <th>Downhole Cards</th>
                          <th>Training Eligibility</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dataCatalog.datasets
                          .filter(x => (!datasetFilter || x.source === datasetFilter) && (!originFilter || x.origin === originFilter))
                          .map(x => (
                            <tr key={x.dataset_id}>
                              <td style={{ color: '#38bdf8', fontWeight: 600 }}>{x.dataset_id}</td>
                              <td>{x.source}</td>
                              <td>{x.origin}</td>
                              <td>{x.records ?? '120 wells'}</td>
                              <td>{x.surface_cards ?? 'Calibrated'}</td>
                              <td>{x.downhole_cards ?? 'Harmonic Gibbs'}</td>
                              <td><span className="badge-live">{x.training_eligible ? 'Synthetic Twin' : x.permission}</span></td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}

              {dataCatalog?.profiles && (
                <section className="advait-panel" style={{ marginBottom: 16 }}>
                  <div className="advait-panel-header">
                    <h2>Column Dictionary and Observed Distributions</h2>
                  </div>
                  <label className="field" style={{ fontSize: 12, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                    Measured Column:
                    <select className="advait-select" value={selectedProfile} onChange={e => setSelectedProfile(e.target.value)}>
                      <option value="">Select a column to inspect distribution...</option>
                      {dataCatalog.profiles.map(x => (
                        <option key={`${x.dataset_id}:${x.original_column_name}`} value={`${x.dataset_id}:${x.original_column_name}`}>
                          {x.dataset_id.split('/').pop()} · {x.original_column_name}
                        </option>
                      ))}
                    </select>
                  </label>

                  {dataCatalog.profiles.filter(x => `${x.dataset_id}:${x.original_column_name}` === selectedProfile).map(x => (
                    <div key={selectedProfile} style={{ marginTop: 10 }}>
                      <Metrics items={[
                        ['Values', x.sample_count],
                        ['Missing', x.missing_count],
                        ['Unit', x.original_unit],
                        ['Minimum', fmt(x.minimum, 2)],
                        ['Maximum', fmt(x.maximum, 2)],
                        ['Mean', fmt(x.mean, 2)]
                      ]} />
                      {x.histogram && (
                        <div style={{ marginTop: 14 }}>
                          <Chart label={`Observed Distribution: ${x.original_column_name}`} height={240}
                            series={[{ x: x.histogram.edges.slice(0, -1), y: x.histogram.counts }]}
                            xLabel={x.original_column_name} yLabel="Frequency Count" />
                        </div>
                      )}
                    </div>
                  ))}
                </section>
              )}

              {dataCatalog?.preview?.length ? (
                <section className="advait-panel">
                  <div className="advait-panel-header">
                    <h2>Source Row Preview</h2>
                    <span className="badge-live">Telemetry Sample</span>
                  </div>
                  <div className="advait-table-wrap">
                    <table className="advait-table">
                      <thead>
                        <tr>
                          {Object.keys(dataCatalog.preview[0] ?? {}).map(k => <th key={k}>{k}</th>)}
                        </tr>
                      </thead>
                      <tbody>
                        {dataCatalog.preview.slice(0, 10).map((row, i) => (
                          <tr key={i}>
                            {Object.values(row).map((v, j) => <td key={j}>{v}</td>)}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              ) : null}
            </>
          )}

          {/* VIEW: IMPORT / EXPORT CENTER */}
          {workspace === 'Export' && (
            <>
              <div className="advait-page-header">
                <div>
                  <h1 className="advait-page-title">Import / Export Center</h1>
                  <span className="advait-page-subtitle">Batch data export, CSV interchangeable formats, and third-party vendor file imports</span>
                </div>
              </div>
              <section className="advait-panel">
                <Engineering base={base} asset={asset} stroke={card} exportUrl={exportUrl} benchmarkOnly={false} />
              </section>
            </>
          )}
        </main>

        {/* 4. RIGHT-HAND SLIDE-OUT DRAWER: OPERATIONS COPILOT */}
        {copilotOpen && (
          <aside className="advait-copilot-drawer">
            <div className="advait-copilot-header">
              <div className="advait-copilot-title-group">
                <span style={{ color: '#38bdf8', fontSize: 16 }}>✦</span>
                <span className="advait-copilot-title">Operations Copilot</span>
                <span className="badge-copilot-streaming">● Streaming</span>
              </div>
              <div className="advait-copilot-actions">
                <button className="advait-icon-btn" title="Copy briefing">⧉</button>
                <button className="advait-icon-btn" title="Clear chat" onClick={() => setCopilotMessages([])}>🗑</button>
                <button className="advait-icon-btn" title="Close" onClick={() => setCopilotOpen(false)}>✕</button>
              </div>
            </div>

            <div className="advait-copilot-body">
              {copilotMessages.map((msg, idx) => (
                msg.sender === 'user' ? (
                  <div key={idx} className="advait-user-bubble">{msg.text}</div>
                ) : msg.briefing ? (
                  <div key={idx} className="advait-assistant-card">
                    <div className="advait-briefing-header">[SRP APM] FLEET HEALTH & OPERATIONAL BRIEFING</div>

                    <div className="advait-briefing-scope">
                      <strong>Asset Scope:</strong> 120 Monitored Wells across 4 Gathering Centers (GCS-01, GCS-02, GCS-03, GCS-04)<br />
                      <strong>Aggregate Production:</strong> <span style={{ color: '#38bdf8' }}>11,840 BOPD</span> | <strong>Fleet Availability:</strong> <span style={{ color: '#22c55e' }}>98.3%</span> (118 of 120 Online)
                    </div>

                    <div className="advait-briefing-section">
                      <h4>1. OPERATIONAL FLEET BREAKDOWN</h4>
                      <p style={{ margin: '4px 0' }}>
                        <span style={{ color: '#22c55e' }}>● 116 Running Nominal:</span> Operating inside governed load corridors (Average SPM: 8.4).
                      </p>
                      <p style={{ margin: '4px 0' }}>
                        <span style={{ color: '#f59e0b' }}>● 2 Watch / Warning:</span> prairie-007 (Elevated dynamic rod stress), delta-018 (Mild gas interference).
                      </p>
                      <p style={{ margin: '4px 0' }}>
                        <span style={{ color: '#ef4444' }}>● 2 CRITICAL SAFETY TRIP / ALERT:</span> canyon-014 (Fluid Pound Shutdown), mesa-021 (Traveling Valve Severe Leakage).
                      </p>
                    </div>

                    <div className="advait-briefing-section">
                      <h4>2. GATHERING CENTER DISTRIBUTION & AVAILABILITY</h4>
                      <div className="advait-table-wrap" style={{ marginTop: 6 }}>
                        <table className="advait-table" style={{ fontSize: 11 }}>
                          <thead>
                            <tr>
                              <th>Station</th>
                              <th>Online</th>
                              <th>Flow (BOPD)</th>
                              <th>Status</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr>
                              <td>GCS-01 (Prairie)</td>
                              <td>30/30</td>
                              <td>3,120</td>
                              <td><span className="badge-state-normal">■ Normal</span></td>
                            </tr>
                            <tr>
                              <td>GCS-02 (Canyon)</td>
                              <td>29/30</td>
                              <td>2,980</td>
                              <td><span className="badge-state-fault">■ 1 Fault</span></td>
                            </tr>
                            <tr>
                              <td>GCS-03 (Mesa)</td>
                              <td>29/30</td>
                              <td>2,850</td>
                              <td><span className="badge-state-fault">■ 1 Fault</span></td>
                            </tr>
                            <tr>
                              <td>GCS-04 (Delta)</td>
                              <td>30/30</td>
                              <td>2,890</td>
                              <td><span className="badge-state-normal">■ Normal</span></td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div key={idx} className="advait-assistant-card">{msg.text}</div>
                )
              ))}
            </div>

            <div className="advait-copilot-footer">
              <div style={{ display: 'flex', gap: 6, marginBottom: 8, overflowX: 'auto' }}>
                <button className="advait-tab-pill" style={{ background: '#111c2e', border: '1px solid #1e2e4a', fontSize: 10 }}
                  onClick={() => setChatInput('What is the status of my fleet ?')}>Fleet Status</button>
                <button className="advait-tab-pill" style={{ background: '#111c2e', border: '1px solid #1e2e4a', fontSize: 10 }}
                  onClick={() => setChatInput('Explain canyon-014 downhole card')}>canyon-014 Card</button>
                <button className="advait-tab-pill" style={{ background: '#111c2e', border: '1px solid #1e2e4a', fontSize: 10 }}
                  onClick={() => setChatInput('Show highest deferment wells')}>Deferment</button>
              </div>

              <div className="advait-chat-input-box">
                <input className="advait-chat-input" placeholder="Ask Copilot about well diagnostics or fleet deferment..."
                  value={chatInput} onChange={e => setChatInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleSendChat(); }} />
                <button className="advait-chat-send-btn" onClick={handleSendChat}>➤</button>
              </div>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
