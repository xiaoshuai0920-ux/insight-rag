<template>
  <div class="terms-page">
    <div class="terms-card">
      <h1>服务协议与隐私政策</h1>
      <p class="muted">这是演示项目的占位页面。InsightRAG 为 NexaTech 虚构企业知识场景的毕业设计级 Demo。</p>
      <h2>服务协议（占位）</h2>
      <p>1. 本平台仅用于企业内部知识检索与问答演示，所有内容均为虚构演示数据。</p>
      <p>2. 回答内容由 AI 基于知识库资料生成，具体执行以制度原文及企业审批流程为准。</p>
      <h2>隐私政策（占位）</h2>
      <p>1. 上传的文档仅存储于本地部署环境中，用于构建检索索引。</p>
      <p>2. 平台不会将您的文档或对话数据用于模型训练。</p>
      <router-link to="/login" class="btn-primary back-link">返回登录</router-link>
    </div>
  </div>
</template>

<style scoped>
.terms-page {
  min-height: 100vh;
  background: var(--bg);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 48px 24px;
}
.terms-card {
  width: 640px;
  max-width: 100%;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: 32px 36px;
}
.terms-card h1 {
  font-size: 20px;
  margin: 0 0 6px;
}
.terms-card h2 {
  font-size: 15px;
  margin: 20px 0 8px;
}
.muted {
  color: var(--text-secondary);
}
.back-link {
  display: inline-block;
  margin-top: 24px;
  text-decoration: none;
}
</style>
