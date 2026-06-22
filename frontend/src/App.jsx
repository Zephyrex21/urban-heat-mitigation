import { useState, useEffect } from 'react';
import { Routes, Route, NavLink } from 'react-router-dom';
import { Map, BarChart2, Layers, ChevronDown, Sun, Moon, Info, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import './App.css';
import { API_BASE } from './api';
import { useTheme } from './ThemeContext';
import AboutModal from './components/AboutModal';
import ServerWakingNotice from './components/ServerWakingNotice';

import MapView from './pages/MapView';
import DriversView from './pages/DriversView';
import ScenarioView from './pages/ScenarioView';

function App() {
  const { theme, toggleTheme } = useTheme();
  const [showAbout, setShowAbout] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => localStorage.getItem('urban-heat-sidebar-collapsed') === 'true'
  );

  const toggleSidebar = () => {
    setSidebarCollapsed((c) => {
      localStorage.setItem('urban-heat-sidebar-collapsed', String(!c));
      return !c;
    });
  };

  const [cities, setCities] = useState([]);
  const [selectedCity, setSelectedCity] = useState(null);
  const [loadingCities, setLoadingCities] = useState(true);
  const [citiesError, setCitiesError] = useState(null);

  const fetchCities = () => {
    setLoadingCities(true);
    setCitiesError(null);
    fetch(`${API_BASE}/api/v1/cities`)
      .then((res) => res.json())
      .then((data) => {
        setCities(data.cities || []);
        setSelectedCity(data.default_city || (data.cities[0] && data.cities[0].id));
      })
      .catch((err) => {
        console.error('Failed to load city list:', err);
        setCitiesError(err.message || 'Could not reach the server.');
      })
      .finally(() => setLoadingCities(false));
  };

  useEffect(() => {
    fetchCities();
  }, []);

  const activeCity = cities.find((c) => c.id === selectedCity);

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <aside className={`sidebar glass-panel${sidebarCollapsed ? ' collapsed' : ''}`}>
        <div className="sidebar-header">
          <div className="logo-icon">🔥</div>
          <div className="logo-text">
            <h2>Urban Heat</h2>
            <p>Urban Heat Island Tracker</p>
          </div>
          <button
            className="sidebar-collapse-btn"
            onClick={toggleSidebar}
            aria-label="Collapse sidebar"
          >
            <PanelLeftClose size={16} />
          </button>
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
          <button className="instructions-row" onClick={() => setShowAbout(true)}>
            <span className="instructions-label">Instructions</span>
            <span className="info-trigger">
              <Info size={12} />
            </span>
          </button>

          <div className="theme-toggle-row">
            <span className="theme-toggle-label">
              {theme === 'light' ? <Sun size={14} /> : <Moon size={14} />}
              {theme === 'light' ? 'Light' : 'Dark'} mode
            </span>
            <button
              className={`theme-toggle-btn${theme === 'light' ? ' is-light' : ''}`}
              onClick={toggleTheme}
              aria-label="Toggle light and dark theme"
            >
              <span className="toggle-thumb">
                {theme === 'light' ? <Sun size={11} /> : <Moon size={11} />}
              </span>
            </button>
          </div>
        </div>
      </aside>

      {sidebarCollapsed && (
        <button
          className="sidebar-restore-btn"
          onClick={toggleSidebar}
          aria-label="Expand sidebar"
        >
          <PanelLeftOpen size={18} />
        </button>
      )}

      {/* Main Content Area */}
      <main className="main-content">
        {selectedCity && (
          <Routes>
            <Route path="/" element={<MapView key={selectedCity} city={selectedCity} cityInfo={activeCity} />} />
            <Route path="/drivers" element={<DriversView key={selectedCity} city={selectedCity} cityInfo={activeCity} />} />
            <Route path="/scenarios" element={<ScenarioView key={selectedCity} city={selectedCity} cityInfo={activeCity} />} />
          </Routes>
        )}

        {!selectedCity && (
          <ServerWakingNotice onRetry={fetchCities} error={citiesError} />
        )}
      </main>

      {showAbout && <AboutModal onClose={() => setShowAbout(false)} />}
    </div>
  );
}

export default App;
