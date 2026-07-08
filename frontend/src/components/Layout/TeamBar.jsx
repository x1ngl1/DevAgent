import React, { useState } from 'react';
import { Tooltip, Modal, Form, Input, Slider, Switch, Button, App, InputNumber } from 'antd';
import { SaveOutlined, UndoOutlined, SettingOutlined } from '@ant-design/icons';
import useWorkerStore from '../../stores/workerStore';
import { WORKER_ROLES, LLM_PROVIDERS } from '../../utils/constants';

export default function TeamBar({ onWorkerClick }) {
  const { workers, configs, loadConfigs, saveConfig, resetConfigs } = useWorkerStore();
  const { message } = App.useApp();
  const [configOpen, setConfigOpen] = useState(null);
  const [saving, setSaving] = useState(false);
  // 跟踪用户是否修改了 API Key（为空时表示保留已有key）
  const [apiKeyDirty, setApiKeyDirty] = useState({});

  React.useEffect(() => {
    loadConfigs();
  }, [loadConfigs]);

  const handleSave = async (workerId) => {
    setSaving(true);
    try {
      const cfg = configs[workerId];
      if (!cfg) return;

      // 组装发送数据
      const payload = {
        provider: cfg.provider,
        model_name: cfg.model_name,
        api_base_url: cfg.api_base_url,
        // 仅当用户修改过API Key时才发送，留空表示保留已有key
        api_key: apiKeyDirty[workerId] ? (cfg.api_key || '') : '',
        temperature: cfg.temperature ?? 0.3,
        max_tokens: cfg.max_tokens ?? 4096,
        timeout: cfg.timeout ?? 30,
        is_enabled: cfg.is_enabled !== false,
      };

      // 清除dirty标记
      setApiKeyDirty(prev => ({ ...prev, [workerId]: false }));

      const success = await saveConfig(workerId, payload);
      if (success) {
        message.success(`${WORKER_ROLES[workerId]?.label} 配置已保存`);
        // 重新加载配置确认状态
        await loadConfigs();
      } else {
        message.error(`保存 ${WORKER_ROLES[workerId]?.label} 配置失败`);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    const success = await resetConfigs();
    if (success) {
      message.success('已恢复默认配置');
      await loadConfigs();
    }
  };

  const updateConfig = (workerId, field, value) => {
    useWorkerStore.setState((state) => ({
      configs: {
        ...state.configs,
        [workerId]: {
          ...state.configs[workerId],
          [field]: value,
          _dirty: true,
        },
      },
    }));
  };

  const handleItemClick = (id) => {
    // 切换弹窗：如果点击的是同一个，关闭；否则打开新的
    const opening = configOpen !== id;
    setConfigOpen(prev => prev === id ? null : id);
    // 重置该worker的API Key脏标记
    setApiKeyDirty(prev => ({ ...prev, [id]: false }));
    if (opening) {
      // 打开弹窗时重新加载配置，确保显示最新数据
      loadConfigs();
    }
    if (onWorkerClick) onWorkerClick(id);
  };

  const renderConfigForm = (id) => {
    const info = WORKER_ROLES[id];
    const cfg = configs[id] || {};
    // 查找 provider：精确匹配 key，或通过 _aliases 兼容旧数据
    const provider = LLM_PROVIDERS.find(p => p.key === cfg.provider) ||
                     LLM_PROVIDERS.find(p => p._aliases?.includes(cfg.provider)) ||
                     LLM_PROVIDERS[0];
    const models = provider.models || [];
    const hasKey = cfg.api_key_configured || !!cfg.api_key;

    return (
      <Form layout="vertical" size="small">
        {/* 提供商 — 可直接输入 */}
        <Form.Item label="LLM 提供商" style={{ marginBottom: 8 }}>
          <Input
            size="small"
            value={cfg.provider || ''}
            onChange={(e) => {
              updateConfig(id, 'provider', e.target.value);
              // 匹配预设提供商时自动填充 base URL
              const p = LLM_PROVIDERS.find(x => x.key === e.target.value);
              if (p) updateConfig(id, 'api_base_url', p.baseUrl);
            }}
            placeholder="deepseek / openai / anthropic / aliyun / custom"
          />
        </Form.Item>

        {/* 模型名称 — 可直接输入 */}
        <Form.Item label="模型名称" style={{ marginBottom: 8 }}>
          <Input
            size="small"
            value={cfg.model_name || ''}
            onChange={(e) => updateConfig(id, 'model_name', e.target.value)}
            placeholder="如 qwen-plus、deepseek-v4-flash、gpt-4o"
          />
        </Form.Item>

        {/* API Base URL */}
        <Form.Item label="API Base URL" style={{ marginBottom: 8 }}>
          <Input
            size="small"
            value={cfg.api_base_url || ''}
            onChange={(e) => updateConfig(id, 'api_base_url', e.target.value)}
            placeholder="https://api.example.com/v1"
          />
        </Form.Item>

        {/* API Key */}
        <Form.Item
          label="API Key"
          style={{ marginBottom: 8 }}
          extra={hasKey ? '已有密钥，留空则保留原值' : '输入 API Key'}
        >
          <Input.Password
            size="small"
            value={cfg.api_key || ''}
            onChange={(e) => {
              updateConfig(id, 'api_key', e.target.value);
              setApiKeyDirty(prev => ({ ...prev, [id]: true }));
            }}
            placeholder={hasKey ? '留空则保留已有密钥' : '输入 API Key'}
            visibilityToggle={false}
          />
        </Form.Item>

        {/* Temperature */}
        <Form.Item label={`Temperature: ${cfg.temperature ?? 0.3}`} style={{ marginBottom: 8 }}>
          <Slider
            min={0}
            max={1}
            step={0.1}
            value={cfg.temperature ?? 0.3}
            onChange={(v) => updateConfig(id, 'temperature', v)}
          />
        </Form.Item>

        {/* Max Tokens */}
        <Form.Item label="Max Tokens" style={{ marginBottom: 8 }}>
          <InputNumber
            size="small"
            min={100}
            max={128000}
            step={100}
            value={cfg.max_tokens ?? 4096}
            onChange={(v) => updateConfig(id, 'max_tokens', v ?? 4096)}
            style={{ width: '100%' }}
          />
        </Form.Item>

        {/* Timeout */}
        <Form.Item label="超时时间 (秒)" style={{ marginBottom: 8 }}>
          <InputNumber
            size="small"
            min={5}
            max={300}
            step={5}
            value={cfg.timeout ?? 30}
            onChange={(v) => updateConfig(id, 'timeout', v ?? 30)}
            style={{ width: '100%' }}
          />
        </Form.Item>

        {/* 启用开关 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <span style={{ fontSize: 12, color: '#94A3B8', flexShrink: 0 }}>启用</span>
          <Switch
            checked={cfg.is_enabled !== false}
            onChange={(v) => updateConfig(id, 'is_enabled', v)}
            size="small"
            checkedChildren="开"
            unCheckedChildren="关"
          />
          {hasKey && (
            <span style={{ fontSize: 11, color: '#22C55E', marginLeft: 'auto' }}>
              ● 已配置密钥
            </span>
          )}
        </div>

        {/* 按钮组 */}
        <div style={{ display: 'flex', gap: 6 }}>
          <Button
            type="primary"
            size="small"
            icon={<SaveOutlined />}
            onClick={() => handleSave(id)}
            loading={saving}
            style={{ flex: 1 }}
          >
            保存
          </Button>
          <Button
            size="small"
            icon={<UndoOutlined />}
            onClick={handleReset}
            style={{ flex: 1 }}
          >
            重置
          </Button>
        </div>
      </Form>
    );
  };

  return (
    <>
      <div className="team-bar">
        {Object.entries(WORKER_ROLES).map(([id, info]) => {
          const state = workers[id] || { status: 'idle' };
          const cfg = configs[id] || {};
          const hasKey = cfg.api_key_configured || !!cfg.api_key;
          return (
            <Tooltip key={id} title={
              <div style={{ textAlign: 'center' }}>
                <div>{info.label}</div>
                <div style={{ fontSize: 11, opacity: 0.7 }}>
                  {cfg.model_name || '未配置'}
                  {hasKey ? ' 🔑' : ''}
                </div>
              </div>
            } placement="right" mouseEnterDelay={0.3}>
              <button
                className={`team-bar-item ${configOpen === id ? 'active' : ''}`}
                onClick={() => handleItemClick(id)}
              >
                <div className="team-avatar-wrap">
                  <img
                    className="team-avatar"
                    src={info.icon}
                    alt={info.label}
                  />
                  <span className={`team-dot tdot-${state.status}`} />
                </div>
              </button>
            </Tooltip>
          );
        })}
      </div>

      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <SettingOutlined />
            <span>{configOpen ? WORKER_ROLES[configOpen]?.label : ''} 配置</span>
            {configOpen && configs[configOpen]?.model_name && (
              <span style={{ fontSize: 12, color: '#94A3B8', fontWeight: 400 }}>
                {configs[configOpen].model_name}
              </span>
            )}
          </div>
        }
        open={!!configOpen}
        onCancel={() => setConfigOpen(null)}
        footer={null}
        width={440}
        destroyOnClose
        maskClosable={false}
        style={{ top: 40, left: 20 }}
      >
        {configOpen && renderConfigForm(configOpen)}
      </Modal>
    </>
  );
}
