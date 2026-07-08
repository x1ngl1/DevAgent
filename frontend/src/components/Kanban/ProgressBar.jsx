import React from 'react';

export default function ProgressBar({ percent, text }) {
  return (
    <div className="monitor-progress">
      <div className="mp-bar">
        <div
          className="mp-fill"
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>
      <div className="mp-text">{text || `${percent}%`}</div>
    </div>
  );
}
