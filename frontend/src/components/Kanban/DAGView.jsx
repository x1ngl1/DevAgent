import React, { useMemo, useState } from 'react';
import { api } from '../../services/api';
import useTaskStore from '../../stores/taskStore';

const ROLE_LABELS = { coder: 'C', pm: 'PM', tester: 'T', leader: 'L' };
const ROLE_COLORS = {
  coder: { bg: 'rgba(0,229,255,0.12)', border: 'rgba(0,229,255,0.4)', text: '#00E5FF' },
  pm: { bg: 'rgba(255,110,199,0.12)', border: 'rgba(255,110,199,0.4)', text: '#FF6EC7' },
  tester: { bg: 'rgba(123,97,255,0.12)', border: 'rgba(123,97,255,0.4)', text: '#7B61FF' },
  leader: { bg: 'rgba(221,255,40,0.15)', border: 'rgba(221,255,40,0.4)', text: '#111F26' },
};
const STATUS_NODE_COLORS = {
  pending: { border: 'rgba(122,125,133,0.12)', bg: 'rgba(122,125,133,0.04)', text: '#7A7D85' },
  running: { border: 'rgba(221,255,40,0.5)', bg: 'rgba(221,255,40,0.15)', text: '#111F26' },
  done: { border: 'rgba(34,197,94,0.5)', bg: 'rgba(34,197,94,0.12)', text: '#22C55E' },
  failed: { border: 'rgba(239,68,68,0.5)', bg: 'rgba(239,68,68,0.12)', text: '#EF4444' },
  skipped: { border: 'rgba(122,125,133,0.08)', bg: 'rgba(122,125,133,0.02)', text: '#5A5E65' },
};

function topoSort(subtasks) {
  if (!subtasks || subtasks.length === 0) return [];
  const map = {};
  subtasks.forEach(s => { map[s.id] = { ...s, depends_on: s.depends_on || [] }; });

  const inDegree = {};
  const adjList = {};
  subtasks.forEach(s => {
    inDegree[s.id] = 0;
    adjList[s.id] = [];
  });

  // Normalize depends_on to array
  subtasks.forEach(s => {
    const deps = Array.isArray(s.depends_on)
      ? s.depends_on.filter(Boolean)
      : (s.depends_on ? [s.depends_on] : []);
    deps.forEach(d => {
      if (adjList[d]) {
        adjList[d].push(s.id);
        inDegree[s.id] = (inDegree[s.id] || 0) + 1;
      }
    });
  });

  // Kahn's algorithm
  const levels = [];
  let queue = Object.keys(inDegree).filter(id => inDegree[id] === 0);
  while (queue.length > 0) {
    levels.push(queue);
    const next = [];
    queue.forEach(id => {
      adjList[id]?.forEach(nb => {
        inDegree[nb]--;
        if (inDegree[nb] === 0) next.push(nb);
      });
    });
    queue = next;
  }
  return levels;
}

export default function DAGView({ subtasks, onNodeClick }) {
  const levels = useMemo(() => topoSort(subtasks), [subtasks]);

  if (!subtasks || subtasks.length === 0) return null;

  const nodeMap = {};
  subtasks.forEach(s => { nodeMap[s.id] = s; });

  return (
    <div style={{
      padding: '8px 4px',
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
    }}>
      <div style={{
        fontSize: 10, fontWeight: 600, color: '#A8ABB0',
        textTransform: 'uppercase', letterSpacing: '0.5px',
        marginBottom: 2,
      }}>
        任务依赖图 ({subtasks.length} 个子任务)
      </div>

      {levels.map((level, li) => (
        <div key={li} style={{
          display: 'flex',
          gap: 8,
          justifyContent: level.length > 1 ? 'flex-start' : 'flex-start',
          flexWrap: 'wrap',
          position: 'relative',
        }}>
          {level.map((nodeId, ni) => {
            const st = nodeMap[nodeId];
            if (!st) return null;
            return (
              <DAGNode
                key={st.id}
                subtask={st}
                onClick={() => onNodeClick?.(st.id)}
              />
            );
          })}
        </div>
      ))}

      {/* Legend */}
      <div style={{
        display: 'flex', gap: 8, flexWrap: 'wrap',
        marginTop: 4, paddingTop: 8,
        borderTop: '1px solid rgba(255,255,255,0.08)',
      }}>
        {Object.entries(STATUS_NODE_COLORS).map(([key, val]) => (
          <div key={key} style={{
            display: 'flex', alignItems: 'center', gap: 4,
            fontSize: 9, color: '#7A7D85',
          }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%',
              background: val.border,
            }} />
            {key === 'pending' ? '待执行' : key === 'running' ? '执行中' : key === 'done' ? '完成' : key === 'failed' ? '失败' : '跳过'}
          </div>
        ))}
      </div>
    </div>
  );
}

function DAGNode({ subtask, onClick }) {
  const st = subtask;
  const statusColor = STATUS_NODE_COLORS[st.status] || STATUS_NODE_COLORS.pending;
  const roleColor = ROLE_COLORS[st.role] || ROLE_COLORS.coder;
  const roleLabel = ROLE_LABELS[st.role] || st.role?.charAt(0)?.toUpperCase() || '?';

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '5px 8px',
        borderRadius: 6,
        border: `1.5px solid ${statusColor.border}`,
        background: statusColor.bg,
        cursor: 'pointer',
        transition: 'all 0.15s ease',
        fontSize: 11,
        minWidth: 0,
        maxWidth: 220,
      }}
      onMouseEnter={e => { e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
      onMouseLeave={e => { e.currentTarget.style.boxShadow = 'none'; e.currentTarget.style.transform = 'none'; }}
    >
      {/* Role badge */}
      <span style={{
        fontSize: 8, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace",
        color: roleColor.text, background: roleColor.bg,
        padding: '1px 4px', borderRadius: 3,
        border: `1px solid ${roleColor.border}`,
        flexShrink: 0, lineHeight: '14px',
      }}>
        {roleLabel}
      </span>

      {/* Description */}
      <span style={{
        flex: 1, minWidth: 0,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        color: statusColor.text, fontSize: 10,
        lineHeight: 1.4,
      }}>
        {st.description || st.role || '-'}
      </span>

      {/* Duration if done */}
      {st.duration > 0 && (
        <span style={{
          fontSize: 8, color: '#7A7D85',
          fontFamily: "'JetBrains Mono', monospace",
          flexShrink: 0,
        }}>
          {st.duration}s
        </span>
      )}
    </div>
  );
}
