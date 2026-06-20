import { useState, useEffect } from 'react';
import { Routes, Route, NavLink } from 'react-router-dom';
import { Map, BarChart2, Layers, ChevronDown } from 'lucide-react';
import './App.css';
import { API_BASE } from './api';

import MapView from './pages/MapView';
import DriversView from './pages/DriversView';
import ScenarioView from './pages/ScenarioView';

function App() {
  const [cities, setCities] = useState([]);
  const [selectedCity, setSelectedCity] = useState(null);
  const [loadingCities, setLoadingCities] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/cities`)
      .then((res) => res.json())
      .then((data) => {
        setCities(data.cities || []);
        setSelectedCity(data.default_city || (data.cities[0] && data.cities[0].id));
      })
      .catch((err) => {
        console.error('Failed to load city list:', err);
      })
      .finally(() => setLoadingCities(false));
  }, []);

  const activeCity = cities.find((c) => c.id === selectedCity);

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <aside className="sidebar glass-panel">
        <div className="sidebar-header">
          <div className="logo-icon">🔥</div>
          <div className="logo-text">
            <h2>Urban Heat</h2>
            <p>India + Demo Cities</p>
          </div>
        </div>

        <div className="city-selector-wrap">
          <label htmlFor="city-select" className="city-selector-label">City</label>
          <div className="city-selector">
            <select
              id="city-select"
              value={selectedCity || ''}
              onChange={(e) => setSelectedCity(e.target.value)}
              disabled={loadingCities || cities.length === 0}
            >
              {loadingCities && <option>Loading cities…</option>}
              {!loadingCities && cities.length === 0 && <option>No cities available</option>}
              {cities.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}{c.country === 'India' ? '' : `, ${c.country}`}
                </option>
              ))}
            </select>
            <ChevronDown size={16} className="city-selector-chevron" />
          </div>
        </div>

        <nav className="sidebar-nav">
          <NavLink to="/" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'} end>
            <Map size={20} />
            <span>Heat Map</span>
          </NavLink>

          <NavLink to="/drivers" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            <BarChart2 size={20} />
            <span>Heat Drivers</span>
          </NavLink>

          <NavLink to="/scenarios" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            <Layers size={20} />
            <span>Scenarios</span>
          </NavLink>
        </nav>

        <div className="sidebar-footer">
          <div className="status-indicator">
            <span className="dot pulse"></span>
            Live Data
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        {selectedCity && (
          <Routes>
            <Route path="/" element={<MapView key={selectedCity} city={selectedCity} cityInfo={activeCity} />} />
            <Route path="/drivers" element={<DriversView key={selectedCity} city={selectedCity} cityInfo={activeCity} />} />
            <Route path="/scenarios" element={<ScenarioView key={selectedCity} city={selectedCity} cityInfo={activeCity} />} />
          </Routes>
        )}
      </main>
    </div>
  );
}

export default App;
