import { X, Flame, Map, BarChart2, Layers, Sparkles } from 'lucide-react';
import './LstExplainerModal.css';
import './AboutModal.css';

export default function AboutModal({ onClose }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-card modal-card--large glass-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <button className="modal-close" onClick={onClose} aria-label="Close">
          <X size={18} />
        </button>

        <div className="modal-icon about-icon">
          <Flame size={22} />
        </div>

        <h2>What is Urban Heat?</h2>
        <p className="modal-intro">
          Cities get hotter than the countryside around them — concrete,
          asphalt, and packed buildings trap heat that green, open land
          would otherwise release. This is called the{' '}
          <strong>urban heat island effect</strong>, and it makes some
          neighborhoods genuinely more dangerous in a heatwave than others
          just a few kilometers away.
        </p>
        <p className="modal-intro">
          This tool maps that effect, block by block, across major Indian
          cities — and lets you test what would actually cool things down.
        </p>

        <h3 className="section-heading">How to use it — 3 steps</h3>

        <div className="steps-grid">
          <div className="step-card">
            <div className="step-number">1</div>
            <div className="step-icon">
              <Map size={18} />
            </div>
            <h4>Heat Map</h4>
            <p>
              Pick a city from the sidebar. Each colored block on the map is
              a real area of the city — red/pink means dangerously hot,
              green means normal, blue means cooler than average.
            </p>
          </div>

          <div className="step-card">
            <div className="step-number">2</div>
            <div className="step-icon">
              <BarChart2 size={18} />
            </div>
            <h4>Heat Drivers</h4>
            <p>
              See <em>why</em> an area is hot — too much concrete, too few
              trees, far from water, dense buildings — ranked by how much
              each factor actually contributes.
            </p>
          </div>

          <div className="step-card">
            <div className="step-number">3</div>
            <div className="step-icon">
              <Layers size={18} />
            </div>
            <h4>Scenarios</h4>
            <p>
              Try fixes — adding trees, cool roofs, more water bodies — and
              see a live before/after comparison, plus an estimated cost to
              actually do it.
            </p>
          </div>
        </div>

        <div className="about-footnote">
          <Sparkles size={14} />
          <p>
            Wondering what the temperature numbers actually mean? Click the
            (ⓘ) icon next to a city name on the Heat Map or Scenarios page
            for that explanation.
          </p>
        </div>
      </div>
    </div>
  );
}
