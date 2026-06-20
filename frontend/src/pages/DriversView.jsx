import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { API_BASE } from '../api';
import './DriversView.css';

export default function DriversView({ city, cityInfo }) {
  const [driversData, setDriversData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!city) return;

    let cancelled = false;

    const fetchDrivers = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/v1/drivers?city=${city}`);
        if (cancelled) return;
        if (res.ok) {
          const data = await res.json();
          setDriversData(data.global_importance);
        } else {
          setError('Could not load driver data for this city.');
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Failed to fetch drivers data', err);
          setError('Could not reach the server. Is the backend running?');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchDrivers();
    return () => { cancelled = true; };
  }, [city]);

  // Format feature names for display
  const formatFeatureName = (name) => {
    return name
      .replace('frac_', '')
      .replace('_mean', '')
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  if (loading) {
    return (
      <div className="page-container">
        <div className="loading-spinner">Loading Driver Analysis...</div>
      </div>
    );
  }

  return (
    <div className="page-container animate-fade-in">
      <div className="page-content">
        <div className="page-header">
          <h1>Heat Drivers Analysis{cityInfo ? ` — ${cityInfo.name}` : ''}</h1>
          <p>Global feature importance based on SHAP values. Understand what physical factors drive the Urban Heat Island effect.</p>
        </div>

        {error && <div className="empty-state" style={{ marginBottom: 16 }}>{error}</div>}

        <div className="drivers-layout">
          {/* Main Chart Card */}
          <div className="chart-card glass-panel">
            <h3>Global Feature Importance</h3>
            <p className="subtitle">Average impact on predicted LST (°C)</p>

            <div className="chart-container">
              {driversData && driversData.length > 0 ? (
                <ResponsiveContainer width="100%" height={400}>
                  <BarChart
                    data={driversData.slice(0, 10)}
                    layout="vertical"
                    margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                  >
                    <XAxis type="number" hide />
                    <YAxis
                      type="category"
                      dataKey="feature"
                      tickFormatter={formatFeatureName}
                      width={150}
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                    />
                    <Tooltip
                      cursor={{fill: 'rgba(255, 255, 255, 0.05)'}}
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div className="custom-tooltip glass-panel">
                              <p className="tt-label">{formatFeatureName(data.feature)}</p>
                              <p className="tt-value">Impact: <span>{data.importance.toFixed(3)} °C</span></p>
                              <p className="tt-dir">
                                Effect: {data.direction === 'positive' ?
                                  <span className="text-danger">Increases Heat</span> :
                                  <span className="text-success">Provides Cooling</span>
                                }
                              </p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Bar dataKey="importance" radius={[0, 4, 4, 0]} barSize={24}>
                      {driversData.slice(0, 10).map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.direction === 'positive' ? 'var(--tier-critical)' : 'var(--tier-cool)'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="empty-state">No driver data available. Train the model first.</div>
              )}
            </div>
          </div>

          {/* Side Panels */}
          <div className="side-panels">
            <div className="info-card glass-panel">
              <h3>Interpretation</h3>
              <div className="insight-item">
                <div className="insight-icon heating">↑</div>
                <div>
                  <strong>Heating Factors</strong>
                  <p>Features like Impervious Surfaces and Building Density trap heat and raise temperatures.</p>
                </div>
              </div>
              <div className="insight-item">
                <div className="insight-icon cooling">↓</div>
                <div>
                  <strong>Cooling Factors</strong>
                  <p>Vegetation (NDVI) and Water Bodies act as natural heat sinks, lowering local temperatures.</p>
                </div>
              </div>
            </div>

            <div className="action-card glass-panel">
              <h3>Next Steps</h3>
              <p>Use these insights in the Scenario Simulator to target the most impactful factors for mitigation.</p>
              <button className="btn-primary" onClick={() => navigate('/scenarios')}>
                Go to Scenarios →
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
