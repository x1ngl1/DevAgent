import React, { useState, useEffect } from 'react';
import { Button } from 'antd';
import './WelcomeModal.css';

const MODULES = [
  {
    title: '终端对话',
    subtitle: 'TERMINAL',
    desc: '核心交互区，上传代码文件或粘贴代码内容，向 AI 测试团队下达测试指令。支持文件上传、流式输出、消息筛选，实时查看测试生成过程。',
  },
  {
    title: '多 Agent 测试团队',
    subtitle: 'TEST TEAM',
    desc: '四个专业角色协作：Leader（代码分析与测试规划）、测试生成（单元测试编写）、PM（硬指标+软指标混合评分）、测试执行（覆盖率与报告）。',
  },
  {
    title: '覆盖率监控',
    subtitle: 'COVERAGE',
    desc: '右侧面板实时展示测试执行进度、函数覆盖率、各 Agent 工作状态。可视化进度条与覆盖率指标，让测试质量一目了然。',
  },
  {
    title: '历史记录',
    subtitle: 'HISTORY',
    desc: '侧滑面板管理所有历史测试任务，支持查看详情、展开子任务、批量删除和下载测试报告。',
  },
  {
    title: '灵活配置',
    subtitle: 'SETTINGS',
    desc: '支持为每个 Agent 独立配置 LLM 提供商（DeepSeek / OpenAI / Anthropic / 通义千问）、模型、API 密钥及运行参数。',
  },
];

const FEATURES = [
  { label: '智能代码分析', desc: '自动识别函数、构建依赖图' },
  { label: '多模型支持', desc: '兼容主流 LLM 提供商' },
  { label: '实时可见', desc: '每一步测试执行都尽在掌握' },
];

export default function WelcomeModal() {
  const [visible, setVisible] = useState(false);
  const [closing, setClosing] = useState(false);

  useEffect(() => {
    const shown = sessionStorage.getItem('welcome_shown');
    if (!shown) {
      const timer = setTimeout(() => setVisible(true), 400);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleClose = () => {
    setClosing(true);
    setTimeout(() => {
      setVisible(false);
      setClosing(false);
      sessionStorage.setItem('welcome_shown', 'true');
    }, 280);
  };

  if (!visible) return null;

  return (
    <div className={`welcome-overlay ${closing ? 'welcome-fade-out' : ''}`} onClick={handleClose}>
      <div
        className={`welcome-modal ${closing ? 'welcome-scale-out' : ''}`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* 头部 */}
        <div className="welcome-header">
          <div className="welcome-brand">
            <span className="welcome-logo">◆</span>
            <span className="welcome-title">AI TEAM</span>
          </div>
          <h1 className="welcome-heading">AI 测试团队</h1>
          <p className="welcome-subtitle">
            一个由多 Agent 协作的智能测试系统 — 上传代码，AI 团队自动分析并生成单元测试与覆盖率报告
          </p>
        </div>

        {/* 模块列表 */}
        <div className="welcome-modules">
          {MODULES.map((mod, i) => (
            <div key={i} className="welcome-module" style={{ animationDelay: `${i * 60}ms` }}>
              <div className="welcome-module-body">
                <div className="welcome-module-subtitle">{mod.subtitle}</div>
                <div className="welcome-module-title">{mod.title}</div>
                <div className="welcome-module-desc">{mod.desc}</div>
              </div>
            </div>
          ))}
        </div>

        {/* 特性标签 */}
        <div className="welcome-features">
          {FEATURES.map((f, i) => (
            <div key={i} className="welcome-feature-tag">
              <span className="welcome-feature-dot" />
              <span className="welcome-feature-label">{f.label}</span>
              <span className="welcome-feature-desc">{f.desc}</span>
            </div>
          ))}
        </div>

        {/* 确定按钮 */}
        <div className="welcome-footer">
          <Button type="primary" size="large" onClick={handleClose} className="welcome-btn">
            开始使用
          </Button>
        </div>
      </div>
    </div>
  );
}
