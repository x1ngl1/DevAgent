import React, { useState } from 'react';
import { Modal, Button, Input, Space, Typography, Tag } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, EditOutlined } from '@ant-design/icons';
import useWorkerStore from '../../stores/workerStore';
import useTaskStore from '../../stores/taskStore';

const { TextArea } = Input;
const { Text } = Typography;

const INTERVENTION_LABELS = {
  pm_retry: { title: 'PM审核未通过', description: 'PM审核评分低于阈值，请决定下一步操作：' },
  code_review: { title: 'Code Review', description: 'Code has been written. Review and decide next step.' },
  test_report: { title: 'Test Report', description: 'Tests completed. Review the test results.' },
};

export default function 干预请求Panel() {
  const { interventionRequest, clear干预请求Request } = useWorkerStore();
  const { send干预请求 } = useTaskStore();
  const [feedback, setFeedback] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!interventionRequest) return null;

  const { request_id, type, context } = interventionRequest;
  const meta = INTERVENTION_LABELS[type] || { title: '需要您的决策', description: '请选择下一步操作：' };

  const handleDecision = async (decision) => {
    setSubmitting(true);
    try {
      await send干预请求(request_id, decision, feedback);
      clear干预请求Request();
      setFeedback('');
    } catch (e) {
      console.error('干预请求 submit failed:', e);
    } finally {
      setSubmitting(false);
    }
  };

  const isPMRetry = type === 'pm_retry';

  return (
    <Modal
      title={
        <Space>
          <span style={{ fontSize: 16 }}>🤔</span>
          <span>{meta.title}</span>
          <Tag color="warning">干预请求</Tag>
        </Space>
      }
      open={true}
      onCancel={() => handleDecision('approve')}
      footer={null}
      width={520}
      closable={false}
      maskClosable={false}
      destroyOnClose
    >
      <div style={{ marginBottom: 16 }}>
        <Text type="secondary">{meta.description}</Text>
      </div>

      {isPMRetry && context && (
        <div style={{ background: '#FEF3C7', padding: '12px 16px', borderRadius: 8, marginBottom: 16 }}>
          <div style={{ marginBottom: 4 }}><Text strong>评分：</Text> <Tag color={context.score >= 60 ? 'green' : 'red'}>{context.score}/100</Tag></div>
          {context.feedback && <div style={{ marginBottom: 4 }}><Text strong>反馈：</Text> <Text>{context.feedback}</Text></div>}
          <div><Text strong>已重试：</Text> <Text>{context.retry_count}/{context.max_retries}</Text></div>
        </div>
      )}

      <div style={{ marginBottom: 16 }}>
        <Text strong>您的反馈（可选）：</Text>
        <TextArea
          rows={3}
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder="请输入意见或修改说明..."
          style={{ marginTop: 8 }}
        />
      </div>

      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        {isPMRetry && (
          <Button
            icon={<CloseCircleOutlined />}
            onClick={() => handleDecision('reject')}
            loading={submitting}
            danger
          >
            退回修改
          </Button>
        )}
        <Button
          type="primary"
          icon={<CheckCircleOutlined />}
          onClick={() => handleDecision('approve')}
          loading={submitting}
        >
          通过
        </Button>
        <Button
          icon={<EditOutlined />}
          onClick={() => handleDecision('modify')}
          loading={submitting}
        >
          我来修改
        </Button>
      </div>
    </Modal>
  );
}