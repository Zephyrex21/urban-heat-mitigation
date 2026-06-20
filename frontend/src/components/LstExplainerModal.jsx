import { X, Thermometer, Sun, Wind } from 'lucide-react';
import './LstExplainerModal.css';

export default function LstExplainerModal({ onClose }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card glass-panel" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Close">
          <X size={18} />
        </button>

        <div className="modal-icon">
          <Thermometer size={22} />
        </div>

        <h2>What does "temperature" mean here?</h2>
        <p className="modal-intro">
          This map shows <strong>Land Surface Temperature (LST)</strong> — not
          the air temperature you'd see on a weather app. They're measured
          completely differently, which is why the numbers here look higher
          than what's reported for the same city today.
        </p>

        <div className="modal-compare">
          <div className="compare-card">
            <div className="compare-head">
              <Sun size={16} />
              <span>Land Surface Temperature</span>
            </div>
            <p>
              The actual skin temperature of roads, rooftops, and bare soil,
              measured by satellite. Surfaces in direct sun — especially
              asphalt and concrete — heat up far more than the air around
              them.
            </p>
            <span className="compare-tag">What this map shows</span>
          </div>

          <div className="compare-card">
            <div className="compare-head">
              <Wind size={16} />
              <span>Air Temperature</span>
            </div>
            <p>
              The temperature reported by weather apps and news — measured
              in shaded air, about 1.5–2m above the ground. This is the
              number you "feel."
            </p>
            <span className="compare-tag muted">Not what this map shows</span>
          </div>
        </div>

        <p className="modal-footnote">
          It's normal for LST to run <strong>10–20°C hotter</strong> than air
          temperature on a sunny afternoon over dense, paved areas — that gap
          is exactly what drives the urban heat island effect this tool is
          built to find and reduce.
        </p>
      </div>
    </div>
  );
}
