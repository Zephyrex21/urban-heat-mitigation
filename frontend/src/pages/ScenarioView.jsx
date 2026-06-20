import { useState, useEffect, useCallback } from 'react';
import DeckGL from '@deck.gl/react';
import { GeoJsonLayer } from '@deck.gl/layers';
import Map from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { API_BASE } from '../api';
import './ScenarioView.css';

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

const INTERVENTIONS = [
  { id: 'tree_cover', label: 'Tree Cover', icon: '🌳', maxImpact: 'High' },
  { id: 'cool_roofs', label: 'Cool Roofs', icon: '🏢', maxImpact: 'Medium' },
  { id: 'green_roofs', label: 'Green Roofs', icon: '🌿', maxImpact: 'Medium' },
  { id: 'water_bodies', label: 'Water Bodies', icon: '💧', maxImpact: 'Low' },
  { id: 'albedo_improvement', label: 'Albedo', icon: '⬜', maxImpact: 'High' }
];

const EMPTY_INTENSITIES = {
  tree_cover: 0, cool_roofs: 0, green_roofs: 0, water_bodies: 0, albedo_improvement: 0
};

const TIER_COLORS = {
  critical: [255, 23, 68],
  high: [255, 145, 0],
  moderate: [255, 214, 0],
  normal: [0, 200, 83],
  cool: [41, 121, 255]
};

export default function ScenarioView({ city, cityInfo }) {
  const [gridData, setGridData] = useState(null);
  const [presets, setPresets] = useState([]);
  const [intensities, setIntensities] = useState(EMPTY_INTENSITIES);
  const [simulationResult, setSimulationResult] = useState(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [activePresetId, setActivePresetId] = useState(null);
  // Feedback for cases that previously failed silently: no sliders
  // moved, or the API call itself failing.
  const [statusMessage, setStatusMessage] = useState(null);

  useEffect(() => {
    if (!city) return;

    // Fetch grid geometry
    fetch(`${API_BASE}/api/v1/grid?city=${city}`)
      .then(res => res.json())
      .then(data => setGridData(data))
      .catch(err => {
        console.error('Failed to load grid', err);
        setStatusMessage({ type: 'error', text: 'Could not load the map for this city.' });
      });

    // Fetch presets
    fetch(`${API_BASE}/api/v1/scenarios/presets?city=${city}`)
      .then(res => res.json())
      .then(data => setPresets(data))
      .catch(err => console.error('Failed to load presets', err));
  }, [city]);

  const handleSliderChange = (id, value) => {
    setIntensities(prev => ({ ...prev, [id]: parseFloat(value) }));
    setActivePresetId(null);
  };

  // Shared simulation runner — used by both the manual "Run Simulation"
  // button (current slider state) and preset buttons (a fixed
  // intervention set), so both paths behave identically and both
  // actually update the After map.
  const runInterventions = useCallback(async (interventionDict) => {
    const activeInterventions = Object.entries(interventionDict)
      .filter(([, intensity]) => intensity > 0)
      .map(([type, intensity]) => ({ type, intensity }));

    if (activeInterventions.length === 0) {
      // Previously this just silently did nothing, which looked
      // exactly like a broken button. Now it says so.
      setSimulationResult(null);
      setStatusMessage({ type: 'info', text: 'Move at least one slider above zero, or pick a preset, before running a simulation.' });
      return;
    }

    setIsSimulating(true);
    setStatusMessage(null);

    try {
      const res = await fetch(`${API_BASE}/api/v1/scenarios/simulate?city=${city}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ interventions: activeInterventions })
      });

      if (res.ok) {
        const data = await res.json();
        setSimulationResult(data);
      } else {
        const errBody = await res.json().catch(() => ({}));
        setStatusMessage({ type: 'error', text: errBody.detail || 'Simulation failed. Please try again.' });
      }
    } catch (err) {
      console.error(err);
      setStatusMessage({ type: 'error', text: 'Could not reach the server. Is the backend running?' });
    } finally {
      setIsSimulating(false);
    }
  }, [city]);

  const runSimulation = () => {
    setActivePresetId(null);
    runInterventions(intensities);
  };

  const loadPreset = (preset) => {
    const newIntensities = { ...EMPTY_INTENSITIES };
    Object.entries(preset.interventions).forEach(([k, v]) => {
      newIntensities[k] = v;
    });
    setIntensities(newIntensities);
    setActivePresetId(preset.scenario_id);

    if (Object.keys(preset.interventions).length === 0) {
      // The "Baseline" preset has no interventions by design.
      setSimulationResult(null);
      setStatusMessage({ type: 'info', text: 'Baseline has no interventions applied — this is the current, unmodified city.' });
      return;
    }

    // Run the preset's interventions through the live simulator so the
    // After map and the summary numbers are guaranteed consistent with
    // each other (previously, presets only showed static precomputed
    // stats and the After map never changed at all).
    runInterventions(preset.interventions);
  };

  // Merge simulation results back into grid data for the "After" map
  const getAfterGrid = () => {
    if (!gridData || !simulationResult || !simulationResult.cell_results || simulationResult.cell_results.length === 0) {
      return gridData;
    }

    const resultDict = {};
    simulationResult.cell_results.forEach(r => {
      resultDict[r.grid_id] = r;
    });

    return {
      ...gridData,
      features: gridData.features.map(f => {
        const sim = resultDict[f.properties.grid_id];
        if (sim) {
          return {
            ...f,
            properties: { ...f.properties, tier: sim.tier_after, lst_mean: sim.lst_after }
          };
        }
        return f;
      })
    };
  };

  const beforeLayer = new GeoJsonLayer({
    id: 'before-layer',
    data: gridData,
    pickable: true,
    stroked: false,
    filled: true,
    getFillColor: d => {
      const color = TIER_COLORS[d.properties.tier] || [128, 128, 128];
      return [...color, 180];
    }
  });

  const afterLayer = new GeoJsonLayer({
    id: 'after-layer',
    data: getAfterGrid(),
    pickable: true,
    stroked: false,
    filled: true,
    getFillColor: d => {
      const color = TIER_COLORS[d.properties.tier] || [128, 128, 128];
      return [...color, 180];
    },
    transitions: { getFillColor: 1000 }
  });

  const [centerLon, centerLat] = cityInfo?.center || [77.20, 28.61];
  const initialViewState = {
    longitude: centerLon,
    latitude: centerLat,
    zoom: 10,
    pitch: 0,
    bearing: 0
  };

  const hasActiveIntervention = Object.values(intensities).some(v => v > 0);

  return (
    <div className="page-container animate-fade-in">
      <div className="scenario-layout">

        {/* Left Panel: Builder */}
        <div className="builder-panel glass-panel">
          <div className="panel-header">
            <h2>Interventions</h2>
            <p>Adjust intensity to simulate cooling{cityInfo ? ` in ${cityInfo.name}` : ''}.</p>
          </div>

          <div className="sliders-container">
            {INTERVENTIONS.map(inv => (
              <div key={inv.id} className="slider-group">
                <div className="slider-label">
                  <span className="icon">{inv.icon}</span>
                  <span className="name">{inv.label}</span>
                  <span className="value">{(intensities[inv.id] * 100).toFixed(0)}%</span>
                </div>
                <input
                  type="range"
                  min="0" max="1" step="0.05"
                  value={intensities[inv.id]}
                  onChange={(e) => handleSliderChange(inv.id, e.target.value)}
                  className="range-slider"
                />
              </div>
            ))}
          </div>

          <button
            className="btn-simulate"
            onClick={runSimulation}
            disabled={isSimulating || !hasActiveIntervention}
            title={!hasActiveIntervention ? 'Move at least one slider first' : undefined}
          >
            {isSimulating ? 'Simulating...' : '▶ Run Simulation'}
          </button>

          {statusMessage && (
            <div className={`status-message status-${statusMessage.type}`}>
              {statusMessage.text}
            </div>
          )}

          <div className="presets-section">
            <h3>Presets</h3>
            <div className="preset-buttons">
              {presets.map(p => (
                <button
                  key={p.scenario_id}
                  onClick={() => loadPreset(p)}
                  className={`btn-preset${activePresetId === p.scenario_id ? ' active' : ''}`}
                  disabled={isSimulating}
                >
                  {p.name}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right Panel: Maps & Results */}
        <div className="results-panel">
          <div className="split-maps">
            <div className="map-half">
              <div className="map-label">Before</div>
              <DeckGL key={`before-${city}`} initialViewState={initialViewState} controller={true} layers={[beforeLayer]}>
                <Map mapStyle={MAP_STYLE} />
              </DeckGL>
            </div>
            <div className="map-half">
              <div className="map-label">After</div>
              <DeckGL key={`after-${city}`} initialViewState={initialViewState} controller={true} layers={[afterLayer]}>
                <Map mapStyle={MAP_STYLE} />
              </DeckGL>
            </div>
          </div>

          {simulationResult && simulationResult.summary && (
            <div className="results-summary glass-panel animate-fade-in">
              <div className="result-metric">
                <span className="metric-label">Mean Cooling</span>
                <span className="metric-value text-success">{simulationResult.summary.mean_cooling_c.toFixed(2)}°C</span>
              </div>
              <div className="result-metric">
                <span className="metric-label">Hotspot Reduction</span>
                <span className="metric-value text-success">{simulationResult.summary.hotspot_reduction_pct.toFixed(1)}%</span>
              </div>
              <div className="result-metric">
                <span className="metric-label">Remaining Hotspots</span>
                <span className="metric-value">{simulationResult.summary.hotspots_after} cells</span>
              </div>
              <div className="result-metric">
                <span className="metric-label">Est. Cost</span>
                <span className="metric-value text-warning">${simulationResult.summary.cost_estimate_m.toFixed(1)}M</span>
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
