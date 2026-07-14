import React, { useEffect } from "react";
import { Drawer, Spin, Tag, Typography, Divider, Empty } from "antd";
import {
  BookOutlined, LinkOutlined, CodeOutlined,
  FileTextOutlined, ApiOutlined, ExceptionOutlined,
  ThunderboltOutlined, PercentageOutlined,
} from "@ant-design/icons";
import useRagStore from "../../stores/ragStore";

const { Text, Paragraph } = Typography;

export default function RAGContextDrawer({ open, taskId, subtaskId, onClose }) {
  const {
    subtaskContext, subtaskContextLoading, subtaskContextError,
    fetchSubtaskContext, clearSubtaskContext,
  } = useRagStore();

  useEffect(() => {
    if (open && taskId && subtaskId) {
      fetchSubtaskContext(taskId, subtaskId);
    }
    if (!open) {
      clearSubtaskContext();
    }
  }, [open, taskId, subtaskId]);

  const data = subtaskContext;

  return (
    <Drawer
      title={
        <span style={{ fontSize: 14, fontWeight: 600 }}>
          <BookOutlined style={{ marginRight: 8, color: "#DDFF28" }} />
          生成上下文证据
          {data?.function_name && (
            <Tag color="cyan" style={{ marginLeft: 8, fontSize: 11 }}>
              <CodeOutlined /> {data.function_name}
            </Tag>
          )}
        </span>
      }
      placement="right"
      width={420}
      open={open}
      onClose={onClose}
      destroyOnClose
      styles={{ body: { padding: "16px 20px" } }}
    >
      {subtaskContextLoading ? (
        <div style={{ textAlign: "center", padding: "60px 0" }}>
          <Spin size="large" />
          <div style={{ marginTop: 12, color: "#7A7D85", fontSize: 13 }}>
            检索生成上下文...
          </div>
        </div>
      ) : subtaskContextError ? (
        <div style={{
          padding: 16, background: "rgba(239,68,68,0.12)", borderRadius: 8,
          color: "#DC2626", fontSize: 13,
        }}>
          <ExceptionOutlined style={{ marginRight: 6 }} />
          {subtaskContextError}
        </div>
      ) : data ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

          {/* ── 参考上下文 ── */}
          <Section
            icon={<FileTextOutlined />}
            title="参考上下文"
            subtitle="本次生成时检索到的 Top 3 相似代码片段"
          >
            {data.reference_context?.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {data.reference_context.map((ctx, i) => (
                  <div key={i} style={{
                    background: "rgba(255,255,255,0.04)",
                    border: "1px solid #E2E8F0",
                    borderRadius: 8,
                    padding: 10,
                  }}>
                    <div style={{
                      display: "flex", justifyContent: "space-between",
                      alignItems: "center", marginBottom: 6,
                    }}>
                      <Tag color="blue" style={{ fontSize: 10, margin: 0 }}>
                        #{i + 1} {ctx.metadata?.task_id ? `任务 ${ctx.metadata.task_id}` : "知识库"}
                      </Tag>
                      <Tag style={{ fontSize: 9, margin: 0 }} color={
                        ctx.relevance >= 0.85 ? "success"
                          : ctx.relevance >= 0.7 ? "warning"
                          : "default"
                      }>
                        <PercentageOutlined /> 相似度 {(ctx.relevance * 100).toFixed(0)}%
                      </Tag>
                    </div>
                    <Text code style={{
                      fontSize: 11, lineHeight: 1.6,
                      display: "block", whiteSpace: "pre-wrap",
                      wordBreak: "break-word", fontFamily: "'JetBrains Mono', monospace",
                      color: "#A8ABB0",
                    }}>
                      {ctx.text?.length > 300 ? ctx.text.slice(0, 300) + "..." : ctx.text || "（无代码内容）"}
                    </Text>
                    {ctx.source && (
                      <div style={{ marginTop: 4, fontSize: 10, color: "#7A7D85" }}>
                        <LinkOutlined style={{ marginRight: 3 }} />
                        来源: {ctx.source}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={<span style={{ fontSize: 12, color: "#7A7D85" }}>暂未检索到相似代码</span>}
              />
            )}
          </Section>

          <Divider style={{ margin: "4px 0" }} />

          {/* ── 依赖文档 ── */}
          <Section
            icon={<ApiOutlined />}
            title="依赖文档"
            subtitle="本次用到的第三方库及官方文档摘要"
          >
            {data.dependency_docs?.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {data.dependency_docs.map((dep, i) => (
                  <div key={i} style={{
                    display: "flex", alignItems: "flex-start", gap: 8,
                    padding: "6px 10px",
                    background: "rgba(0,229,255,0.08)",
                    borderRadius: 6,
                    border: "1px solid #E0F2FE",
                  }}>
                    <ThunderboltOutlined style={{ color: "#DDFF28", marginTop: 2 }} />
                    <div>
                      <Tag color="cyan" style={{ fontSize: 10, marginBottom: 2 }}>
                        {dep.library}
                      </Tag>
                      <div style={{ fontSize: 11, color: "#A8ABB0", lineHeight: 1.5 }}>
                        {dep.usage}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={<span style={{ fontSize: 12, color: "#7A7D85" }}>未检测到第三方库依赖</span>}
              />
            )}
          </Section>

          <Divider style={{ margin: "4px 0" }} />

          {/* ── 风格特征 ── */}
          <Section
            icon={<CodeOutlined />}
            title="风格特征"
            subtitle="从老代码中提取的编码规范与模式"
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <StyleRow
                label="命名规范"
                value={data.style_features?.naming_convention || "snake_case"}
                color="#DDFF28"
              />
              <StyleRow
                label="异常类型"
                value={data.style_features?.exceptions?.length > 0
                  ? data.style_features.exceptions.join(", ")
                  : "无自定义异常"}
                color={data.style_features?.exceptions?.length > 0 ? "#DC2626" : "#7A7D85"}
              />
              <StyleRow
                label="装饰器"
                value={data.style_features?.decorators?.length > 0
                  ? data.style_features.decorators.join(", ")
                  : "无装饰器"}
                color={data.style_features?.decorators?.length > 0 ? "#7C3AED" : "#7A7D85"}
              />
              <StyleRow
                label="导入模块"
                value={data.style_features?.imports?.length > 0
                  ? data.style_features.imports.join(", ")
                  : "无导入"}
                color={data.style_features?.imports?.length > 0 ? "#059669" : "#7A7D85"}
              />
            </div>
          </Section>

        </div>
      ) : null}
    </Drawer>
  );
}

/* ── 子组件 ── */

function Section({ icon, title, subtitle, children }) {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
        <span style={{ fontSize: 15, color: "#DDFF28" }}>{icon}</span>
        <span style={{ fontSize: 13, fontWeight: 600, color: "#F7F7F5" }}>{title}</span>
      </div>
      {subtitle && (
        <div style={{ fontSize: 11, color: "#7A7D85", marginBottom: 10 }}>
          {subtitle}
        </div>
      )}
      {children}
    </div>
  );
}

function StyleRow({ label, value, color }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8,
      padding: "6px 10px",
      background: "rgba(255,255,255,0.04)",
      borderRadius: 6,
      border: "1px solid rgba(255,255,255,0.08)",
    }}>
      <span style={{ fontSize: 11, color: "#A8ABB0", minWidth: 60, flexShrink: 0 }}>
        {label}
      </span>
      <span style={{
        fontSize: 12,
        color: color || "#A8ABB0",
        fontWeight: 500,
        fontFamily: color === "#DC2626" ? "'JetBrains Mono', monospace" : undefined,
      }}>
        {value}
      </span>
    </div>
  );
}
