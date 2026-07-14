import React, { useState, useEffect } from 'react';
import { Input, Button, message, Tag, Spin } from 'antd';
import { StarFilled, StarOutlined, SaveOutlined, CloseOutlined, TrophyOutlined } from '@ant-design/icons';
import useExperienceStore from '../../stores/experienceStore';
import useTaskStore from '../../stores/taskStore';

const { TextArea } = Input;

const STAR_LABELS = ['', '很差', '较差', '一般', '不错', '优秀'];

export default function TaskRating() {
  const {
    currentTaskId, rating, tags, notes, savedExp, saving,
    setRating, setTags, setNotes, save, reset, fetchStats,
  } = useExperienceStore();
  const { currentTask, subtasks } = useTaskStore();
  const [dismissed, setDismissed] = useState(false);

  // Reset when task changes
  useEffect(() => {
    reset();
    setDismissed(false);
  }, [currentTask?.id]);

  // Auto-populate currentTaskId
  useEffect(() => {
    if (currentTask?.id && !currentTaskId) {
      useExperienceStore.setState({ currentTaskId: currentTask.id });
    }
  }, [currentTask?.id, currentTaskId]);

  // Check if task is done
  const taskDone = currentTask?.status === 'done';

  if (!taskDone || dismissed || savedExp) return null;

  const handleSave = async () => {
    if (rating === 0) {
      message.warning('请先评分再保存');
      return;
    }
    const totalDuration = subtasks.reduce((sum, st) => sum + (st.duration || 0), 0);
    try {
      await save({
        task_id: currentTask?.id,
        user_input: currentTask?.input || '',
        summary: subtasks.map(s => s.output || s.description || '').filter(Boolean).join('\n').slice(0, 500),
        task_status: 'done',
        subtask_count: subtasks.length,
        total_duration: totalDuration,
      });
      message.success('经验已保存到知识库');
      fetchStats();
    } catch (e) {
      message.error('保存失败');
    }
  };

  const commonTags = ['前端', '后端', 'API', '数据库', 'UI', '测试', '配置', '部署', '算法', '优化'];

  return (
    <div style={{
      background: 'rgba(245,158,11,0.08)',
      border: '1px solid rgba(245,158,11,0.2)',
      borderRadius: 8,
      padding: '10px 14px',
      marginBottom: 8,
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: 8,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <TrophyOutlined style={{ color: '#D97706', fontSize: 14 }} />
          <span style={{ fontSize: 12, fontWeight: 600, color: '#92400E' }}>
            任务完成 - 保存经验?
          </span>
        </div>
        <Button type="text" size="small" icon={<CloseOutlined />}
          onClick={() => setDismissed(true)}
          style={{ color: '#A16207', fontSize: 10 }} />
      </div>

      {/* Star rating */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <span style={{ fontSize: 10, color: '#92400E', minWidth: 28 }}>评分:</span>
        {[1, 2, 3, 4, 5].map((star) => (
          <span
            key={star}
            onClick={() => setRating(star)}
            style={{
              cursor: 'pointer', fontSize: 18, lineHeight: 1,
              color: star <= rating ? '#F59E0B' : '#D1D5DB',
              transition: 'color 0.1s',
            }}
            onMouseEnter={e => { e.currentTarget.style.color = '#F59E0B'; }}
            onMouseLeave={e => { if (star > rating) e.currentTarget.style.color = '#D1D5DB'; }}
          >
            {star <= rating ? <StarFilled /> : <StarOutlined />}
          </span>
        ))}
        {rating > 0 && (
          <span style={{ fontSize: 10, color: '#A16207', marginLeft: 4 }}>
            {STAR_LABELS[rating]}
          </span>
        )}
      </div>

      {/* Tags */}
      <div style={{ marginBottom: 8 }}>
        <span style={{ fontSize: 10, color: '#92400E', marginRight: 6 }}>标签:</span>
        {commonTags.map(tag => {
          const tagList = tags.split(',').map(t => t.trim()).filter(Boolean);
          const active = tagList.includes(tag);
          return (
            <Tag
              key={tag}
              style={{
                cursor: 'pointer', fontSize: 10, lineHeight: '18px', marginBottom: 2,
                background: active ? 'rgba(245,158,11,0.2)' : 'rgba(245,158,11,0.08)',
                borderColor: active ? 'rgba(245,158,11,0.5)' : 'rgba(245,158,11,0.2)',
                color: active ? '#FBBF24' : '#F59E0B',
              }}
              onClick={() => {
                const newTags = active
                  ? tagList.filter(t => t !== tag).join(',')
                  : [...tagList, tag].join(',');
                setTags(newTags);
              }}
            >
              {tag}
            </Tag>
          );
        })}
        <Input
          size="small"
          placeholder="自定义标签..."
          value={tags}
          onChange={e => setTags(e.target.value)}
          style={{
            width: 120, fontSize: 10, height: 22, marginTop: 2,
            background: 'rgba(245,158,11,0.12)', borderColor: 'rgba(245,158,11,0.25)',
          }}
        />
      </div>

      {/* Notes */}
      <TextArea
        placeholder="备注（什么做得好？什么可以改进？）"
        value={notes}
        onChange={e => setNotes(e.target.value)}
        autoSize={{ minRows: 1, maxRows: 2 }}
        style={{
          fontSize: 11, marginBottom: 8,
          background: 'rgba(245,158,11,0.12)', borderColor: 'rgba(245,158,11,0.25)',
        }}
      />

      {/* Actions */}
      <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
        <Button size="small" onClick={() => setDismissed(true)}
          style={{ fontSize: 10, color: '#92400E', borderColor: '#FDE68A' }}>
          跳过
        </Button>
        <Button
          type="primary" size="small"
          icon={saving ? <Spin size="small" /> : <SaveOutlined />}
          onClick={handleSave}
          disabled={rating === 0 || saving}
          style={{
            fontSize: 10, background: '#D97706', borderColor: '#D97706',
          }}
        >
          {saving ? '保存中...' : '保存经验'}
        </Button>
      </div>
    </div>
  );
}
