import { useState } from 'react';
import { Satellite, ChevronDown, ChevronUp } from 'lucide-react';
import './ValidationBadge.css';

export default function ValidationBadge({ validation }) {
  const [expanded, setExpanded] = useState(false);

  if (!validation || !validation.available) return null;

  const { validation: stats, scene_datetime, cloud_cover_pct, platform, cells_covered, total_cells } = validation;
  const coveragePct = total_cells ? Math.round((cells_covered / total_cells) * 100) : null;
  const sceneDate = scene_datetime ? new Date(scene_datetime).toLocaleDateString('en-IN', {
    year: 'numeric', month: 'short', day: 'numeric',
  }) : null;

  return (
    <div className={`validation-badge${expanded ? ' expanded' : ''}`}>
      <button className="validation-badge-trigger" onClick={() => setExpanded((e) => !e)}>
        <Satellite size={13} />
        <span>Verified against real Landsat data</span>
        {stats && <span className="validation-rmse">±{stats.rmse_c}°C</span>}
        {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
      </button>

      {expanded && (
        <div className="validation-detail">
          <div className="validation-row">
            <span>Satellite</span>
            <strong>{platform === 'landsat-9' ? 'Landsat 9' : platform === 'landsat-8' ? 'Landsat 8' : platform}</strong>
          </div>
          <div className="validation-row">
            <span>Scene date</span>
            <strong>{sceneDate}</strong>
          </div>
          <div className="validation-row">
            <span>Cloud cover</span>
            <strong>{cloud_cover_pct}%</strong>
          </div>
          <div className="validation-row">
            <span>Grid coverage</span>
            <strong>{coveragePct}% of cells</strong>
          </div>
          {stats && (
            <>
              <div className="validation-divider" />
              <div className="validation-row">
                <span>Mean error (RMSE)</span>
                <strong>{stats.rmse_c}°C</strong>
              </div>
              <div className="validation-row">
                <span>Correlation</span>
                <strong>{stats.correlation}</strong>
              </div>
            </>
          )}
          <p className="validation-note">
            This city's synthetic temperature estimate was checked cell-by-cell
            against a real Landsat thermal measurement — the numbers above show
            how close they came.
          </p>
        </div>
      )}
    </div>
  );
}
