import React from 'react';
import { Tooltip } from 'antd';
import { BookOutlined } from '@ant-design/icons';
import useRagStore from '../../stores/ragStore';

export default function RAGButton() {
  const { togglePanel, panelOpen } = useRagStore();

  return (
    <Tooltip title="知识问答 (RAG)" placement="left">
      <div
        onClick={togglePanel}
        style={{
          position: 'fixed',
          bottom: 48,
          right: panelOpen ? 396 : 16,
          width: 36,
          height: 36,
          borderRadius: '50%',
          background: panelOpen ? 'rgba(255,255,255,0.08)' : '#DDFF28',
          color: panelOpen ? '#7A7D85' : '#111F26',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          boxShadow: panelOpen ? 'none' : '0 2px 12px rgba(0,122,204,0.4)',
          transition: 'all 0.2s ease',
          zIndex: 1060,
          border: '1px solid',
          borderColor: panelOpen ? 'rgba(255,255,255,0.08)' : 'transparent',
          fontSize: 16,
        }}
        onMouseEnter={e => {
          if (!panelOpen) {
            e.currentTarget.style.transform = 'scale(1.1)';
            e.currentTarget.style.boxShadow = '0 4px 12px rgba(8,145,178,0.4)';
          }
        }}
        onMouseLeave={e => {
          if (!panelOpen) {
            e.currentTarget.style.transform = 'scale(1)';
            e.currentTarget.style.boxShadow = '0 2px 8px rgba(8,145,178,0.3)';
          }
        }}
      >
        <BookOutlined />
      </div>
    </Tooltip>
  );
}
