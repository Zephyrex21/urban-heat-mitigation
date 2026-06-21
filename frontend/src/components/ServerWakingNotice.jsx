import { useState, useEffect } from 'react';
import { Flame, RotateCw } from 'lucide-react';
import './ServerWakingNotice.css';

/**
 * Shown whenever we're waiting on the backend. The free Render tier spins
 * down after ~15 minutes idle, so the very first request after a quiet
 * period can take 30-60s to respond instead of the usual instant. Rather
 * than leaving the screen blank (which looks broken), this escalates the
 * message over time so it's clear the app is alive and working, not stuck.
 */
export default function ServerWakingNotice({ onRetry, error = null, compact = false }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(t);
  }, []);

  let message = 'Loading…';
  let sub = null;

  if (error) {
    message = 'Could not reach the server';
    sub = error;
  } else if (elapsed >= 4 && elapsed < 10) {
    message = 'Connecting to the server…';
  } else if (elapsed >= 10 && elapsed < 50) {
    message = 'Waking up the backend…';
    sub = 'This app runs on free hosting that sleeps after inactivity. First load can take up to a minute — thanks for waiting.';
  } else if (elapsed >= 50) {
    message = 'Still waking up…';
    sub = "This is taking longer than usual. It should still come through — or tap retry.";
  }

  const showRetry = onRetry && (error || elapsed >= 50);

  return (
    <div className={`server-waking${compact ? ' compact' : ''}`}>
      <div className="server-waking-icon">
        <Flame size={compact ? 20 : 28} />
      </div>
      {!error && <div className="spinner" />}
      <p className="server-waking-message">{message}</p>
      {sub && <p className="server-waking-sub">{sub}</p>}
      {showRetry && (
        <button className="server-waking-retry" onClick={onRetry}>
          <RotateCw size={14} />
          Retry
        </button>
      )}
    </div>
  );
}
