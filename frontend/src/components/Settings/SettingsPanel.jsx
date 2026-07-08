import React, { useState, useEffect } from 'react';
import { Modal, Form, Input, InputNumber, Select, Button, message, Tabs, Space, Tag } from 'antd';
import { CloseOutlined, SaveOutlined, ReloadOutlined } from '@ant-design/icons';
import useWorkerStore from '../../stores/workerStore';

const { Option } = Select;

const WORKER_LABELS = {
  leader: 'Leader (任务调度)',
  coder: 'Coder (代码编写)',
  pm: 'PM (质量审核)',
  tester: 'Tester (测试执行)',
};

const LLM_PROVIDERS = [
  {
    key: 'deepseek',
    label: 'DeepSeek',
    baseUrl: 'https://api.deepseek.com/v1',
    models: ['deepseek-chat', 'deepseek-coder', 'deepseek-v2'],
  },
  {
    key: 'openai',
    label: 'OpenAI',
    baseUrl: 'https://api.openai.com/v1',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
  },
  {
    key: 'qwen',
    label: '通义千问',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    models: ['qwen-plus', 'qwen-turbo', 'qwen-max'],
  },
  {
    key: 'custom',
    label: '自定义',
    baseUrl: '',
    models: [],
  },
];

export default function SettingsPanel({ open, onClose }) {
  const { configs, loadConfigs, saveConfig, resetConfigs } = useWorkerStore();
  const [forms] = useState({});
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('leader');

  useEffect(() => {
    if (open) {
      loadConfigs();
    }
  }, [open, loadConfigs]);

  const handleSave = async (workerId) => {
    const form = forms[workerId];
    if (!form) return;

    try {
      const values = await form.validateFields();
      setSaving(true);

      // 如果选择了预设提供商，自动填充 baseUrl
      const provider = LLM_PROVIDERS.find(p => p.key === values.provider);
      if (provider && values.provider !== 'custom') {
        values.api_base_url = provider.baseUrl;
      }

      const success = await saveConfig(workerId, values);
      if (success) {
        message.success(`${WORKER_LABELS[workerId]} 配置已保存`);
      } else {
        message.error('保存失败');
      }
    } catch (error) {
      console.error('验证失败:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleResetAll = async () => {
    Modal.confirm({
      title: '确认重置',
      content: '确定要重置所有 Worker 配置为默认值吗？这将清除所有自定义的 API Key 和参数设置。',
      okText: '确认重置',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        const success = await resetConfigs();
        if (success) {
          message.success('所有配置已重置为默认值');
          loadConfigs();
        } else {
          message.error('重置失败');
        }
      },
    });
  };

  const handleProviderChange = (workerId, providerKey) => {
    const provider = LLM_PROVIDERS.find(p => p.key === providerKey);
    const form = forms[workerId];
    if (form && provider) {
      form.setFieldsValue({
        api_base_url: provider.baseUrl,
        model_name: provider.models[0] || '',
      });
    }
  };

  const renderWorkerForm = (workerId) => {
    const config = configs[workerId] || {};

    return (
      <Form
        layout="vertical"
        initialValues={{
          provider: config.provider || 'deepseek',
          model_name: config.model_name || 'deepseek-chat',
          api_base_url: config.api_base_url || 'https://api.deepseek.com/v1',
          api_key: config.api_key || '',
          temperature: config.temperature || 0.7,
          max_tokens: config.max_tokens || 4096,
          timeout: config.timeout || 30,
        }}
        ref={(ref) => { forms[workerId] = ref; }}
      >
        <Form.Item
          label="LLM 提供商"
          name="provider"
          rules={[{ required: true, message: '请选择提供商' }]}
        >
          <Select onChange={(val) => handleProviderChange(workerId, val)}>
            {LLM_PROVIDERS.map(p => (
              <Option key={p.key} value={p.key}>{p.label}</Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item
          label="模型名称"
          name="model_name"
          rules={[{ required: true, message: '请输入模型名称' }]}
          extra="例如：deepseek-chat, gpt-4o, qwen-plus"
        >
          <Input placeholder="输入模型名称" />
        </Form.Item>

        <Form.Item
          label="API Base URL"
          name="api_base_url"
          rules={[{ required: true, message: '请输入 API 地址' }]}
        >
          <Input placeholder="https://api.deepseek.com/v1" />
        </Form.Item>

        <Form.Item
          label="API Key"
          name="api_key"
          extra="你的 API Key 将加密存储，不会明文显示"
        >
          <Input.Password placeholder="输入 API Key（可选，留空使用默认）" />
        </Form.Item>

        <Form.Item
          label="Temperature"
          name="temperature"
          rules={[{ required: true, message: '请输入温度值' }]}
          extra="控制输出的随机性，0-1 之间，值越高输出越随机"
        >
          <InputNumber min={0} max={1} step={0.1} style={{ width: '100%' }} />
        </Form.Item>

        <Form.Item
          label="Max Tokens"
          name="max_tokens"
          rules={[{ required: true, message: '请输入最大 Token 数' }]}
        >
          <InputNumber min={100} max={32000} step={100} style={{ width: '100%' }} />
        </Form.Item>

        <Form.Item
          label="超时时间 (秒)"
          name="timeout"
          rules={[{ required: true, message: '请输入超时时间' }]}
        >
          <InputNumber min={5} max={300} step={5} style={{ width: '100%' }} />
        </Form.Item>

        <Button
          type="primary"
          icon={<SaveOutlined />}
          onClick={() => handleSave(workerId)}
          loading={saving}
          block
        >
          保存配置
        </Button>
      </Form>
    );
  };

  const tabItems = Object.entries(WORKER_LABELS).map(([key, label]) => ({
    key,
    label: (
      <span>
        {label}
        {configs[key] && <Tag color="green" style={{ marginLeft: 8 }}>已配置</Tag>}
      </span>
    ),
    children: renderWorkerForm(key),
  }));

  return (
    <Modal
      title={
        <Space>
          <span>Worker 配置</span>
          <Tag color="blue">多 Agent 设置</Tag>
        </Space>
      }
      open={open}
      onCancel={onClose}
      width={700}
      footer={[
        <Button key="reset" danger icon={<ReloadOutlined />} onClick={handleResetAll}>
          重置所有配置
        </Button>,
        <Button key="close" onClick={onClose}>
          关闭
        </Button>,
      ]}
    >
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={tabItems}
        type="card"
      />
    </Modal>
  );
}
