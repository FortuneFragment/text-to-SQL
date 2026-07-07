<template>
  <section class="annotation-page">
    <article class="annotation-card">
      <header class="annotation-titlebar">
        <span class="title-icon" aria-hidden="true">注</span>
        <div>
          <h2>字段注释导入</h2>
          <p>批量导入字段注释，完善数据资产元信息，辅助智慧校园数据治理。</p>
        </div>
      </header>

      <div v-if="notice" class="notice" :class="noticeType">{{ notice }}</div>

      <section class="upload-section">
        <h3>导入文件</h3>
        <label class="file-drop" :class="{ 'has-file': selectedFile }">
          <input ref="fileInputRef" class="file-input" type="file" accept=".xlsx,.xlsm,.xls,.csv,.tsv,.json" @change="handleFileChange" />
          <span class="upload-mark" aria-hidden="true">↑</span>
          <span class="file-copy">
            <strong>{{ selectedFile ? selectedFile.name : "点击选择文件，或将文件拖拽到此处" }}</strong>
            <small>支持 .xlsx、.xls、.csv、.tsv、.json 格式，文件大小不超过 50 MB</small>
          </span>
          <span class="choose-button">选择文件</span>
          <span class="file-state">{{ selectedFile ? "已选择文件" : "未选择任何文件" }}</span>
        </label>
        <p class="upload-hint">请按下方支持列名准备文件，系统会在导入前完成安全校验。</p>
      </section>

      <section class="template-panel">
        <h3>支持列名说明</h3>
        <div class="table-frame">
          <table>
            <thead>
              <tr>
                <th>列名</th>
                <th>是否必填</th>
                <th>填写说明</th>
                <th>示例</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><code>table_name</code></td>
                <td><span class="badge required">是</span></td>
                <td>表名</td>
                <td><code>T_STUDENT</code></td>
              </tr>
              <tr>
                <td><code>column_name</code></td>
                <td><span class="badge required">是</span></td>
                <td>字段名</td>
                <td><code>GENDER_ID</code></td>
              </tr>
              <tr>
                <td><code>column_comment</code></td>
                <td><span class="badge suggested">建议填写</span></td>
                <td>字段注释说明</td>
                <td>性别</td>
              </tr>
              <tr>
                <td><code>table_comment</code></td>
                <td><span class="badge optional">可选</span></td>
                <td>表注释说明</td>
                <td>学生信息</td>
              </tr>
              <tr>
                <td><code>aliases</code></td>
                <td><span class="badge optional">可选</span></td>
                <td>别名，如性别编码、男女</td>
                <td>性别编码,男女</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <footer class="actions">
        <button class="btn-primary" @click="upload" :disabled="loading">
          {{ loading ? "导入中" : "导入字段注释" }}
        </button>
        <span class="security-note">数据导入安全校验，保障数据质量与安全</span>
      </footer>
    </article>

    <article v-if="result" class="result-panel">
      <header class="result-header">
        <h3>导入结果</h3>
        <div class="stats">
          <span>解析 {{ result.parsed }}</span>
          <span>写入 {{ result.upserted }}</span>
          <span>跳过 {{ result.skipped }}</span>
        </div>
      </header>
      <div v-if="result.sample?.length" class="table-frame">
        <table>
          <thead>
            <tr>
              <th>表</th>
              <th>字段</th>
              <th>字段注释</th>
              <th>别名</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in result.sample" :key="`${item.table_name}.${item.column_name}`">
              <td><code>{{ item.table_name }}</code></td>
              <td><code>{{ item.column_name }}</code></td>
              <td>{{ item.column_comment || "-" }}</td>
              <td>{{ (item.aliases || []).join(", ") || "-" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  </section>
</template>

<script setup>
import { ref } from "vue";
import { apiRequest } from "../api/client";

const selectedFile = ref(null);
const fileInputRef = ref(null);
const loading = ref(false);
const notice = ref("");
const noticeType = ref("info");
const result = ref(null);

function setNotice(message, type = "info") {
  notice.value = message;
  noticeType.value = type;
}

function handleFileChange(event) {
  selectedFile.value = event.target.files?.[0] || null;
  result.value = null;
  if (selectedFile.value) setNotice(`已选择 ${selectedFile.value.name}`, "info");
}

async function upload() {
  if (!selectedFile.value) {
    fileInputRef.value?.click();
    return;
  }
  loading.value = true;
  result.value = null;
  try {
    const form = new FormData();
    form.append("file", selectedFile.value);
    const data = await apiRequest("/text2sql/schema-annotation/import", {
      method: "POST",
      body: form,
    });
    result.value = data;
    setNotice(`导入完成：写入 ${data.upserted} 条字段注释。`, "success");
  } catch (error) {
    setNotice(`导入失败：${error.message}`, "error");
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.annotation-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 1260px;
  margin: 0 auto;
}

.annotation-card,
.result-panel {
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow);
  padding: clamp(18px, 2vw, 24px);
}

.annotation-titlebar {
  display: flex;
  align-items: flex-start;
  gap: 18px;
  margin-bottom: 22px;
}

.title-icon {
  display: inline-grid;
  place-items: center;
  width: 46px;
  height: 46px;
  flex: 0 0 auto;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--accent), #e24549);
  color: #fff8f8;
  box-shadow: 0 12px 24px rgba(var(--accent-rgb), 0.18);
  font-size: 18px;
  font-weight: 760;
}

h2,
h3 {
  margin: 0;
  color: var(--text-main);
}

h2 {
  font-size: clamp(26px, 2.8vw, 38px);
  line-height: 1.1;
  letter-spacing: 0;
}

.annotation-titlebar p {
  margin: 8px 0 0;
  color: var(--text-muted);
  font-size: 15px;
  line-height: 1.6;
}

h3 {
  font-size: 16px;
  font-weight: 730;
}

.upload-section,
.template-panel {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.74);
  padding: 16px;
}

.upload-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 12px;
}

.file-drop {
  display: grid;
  grid-template-columns: 74px minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 16px;
  min-height: 94px;
  padding: 16px 20px;
  border: 1px dashed rgba(var(--accent-rgb), 0.58);
  border-radius: 8px;
  background: linear-gradient(180deg, #fffefe, #fff7f7);
  cursor: pointer;
}

.file-drop:hover,
.file-drop.has-file {
  border-color: var(--accent);
  background: var(--accent-light);
}

.file-input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.upload-mark {
  display: inline-grid;
  place-items: center;
  width: 56px;
  height: 46px;
  border: 2px solid rgba(var(--accent-rgb), 0.72);
  border-radius: 22px 22px 10px 10px;
  color: var(--accent);
  font-size: 30px;
  font-weight: 700;
  line-height: 1;
}

.file-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 6px;
}

.file-copy strong {
  overflow: hidden;
  color: var(--text-main);
  font-size: 15px;
  font-weight: 720;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-copy small,
.upload-hint,
.security-note {
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.45;
}

.choose-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 38px;
  padding: 0 18px;
  border: 1px solid var(--accent);
  border-radius: 7px;
  color: var(--accent);
  background: #ffffff;
  font-size: 14px;
  font-weight: 680;
  white-space: nowrap;
}

.file-state {
  color: var(--text-muted);
  font-size: 14px;
  white-space: nowrap;
}

.upload-hint {
  margin: 0;
}

.template-panel h3 {
  margin-bottom: 12px;
}

.table-frame {
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
}

table {
  width: 100%;
  border-collapse: collapse;
  background: rgba(255, 255, 255, 0.72);
}

th,
td {
  border-bottom: 1px solid var(--line);
  padding: 11px 18px;
  text-align: left;
  vertical-align: middle;
  font-size: 14px;
}

th {
  background: rgba(247, 242, 243, 0.72);
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 700;
}

tbody tr:last-child td {
  border-bottom: none;
}

tbody tr:hover td {
  background: rgba(var(--accent-rgb), 0.035);
}

code {
  color: #1f2937;
  font-weight: 680;
}

.badge {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.badge.required {
  background: #ffe4e6;
  color: var(--accent);
}

.badge.suggested {
  background: #fff7ed;
  color: #c2410c;
}

.badge.optional {
  background: #f2f4f8;
  color: var(--text-muted);
}

.actions {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 20px;
  flex-wrap: wrap;
}

button {
  padding: 12px 20px;
  font-weight: 620;
  cursor: pointer;
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.stats {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.stats span {
  background: #fff5f5;
  border: 1px solid rgba(var(--accent-rgb), 0.1);
  border-radius: 7px;
  padding: 6px 12px;
  font-weight: 620;
  color: var(--accent);
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.notice {
  border-radius: 8px;
  padding: 12px 16px;
  font-size: 13px;
  font-weight: 560;
}

.notice.success { background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }
.notice.error { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
.notice.info { background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; }

@media (max-width: 860px) {
  .file-drop {
    grid-template-columns: 56px minmax(0, 1fr);
  }

  .choose-button,
  .file-state {
    grid-column: 2;
    justify-self: start;
  }
}

@media (max-width: 640px) {
  .annotation-titlebar {
    flex-direction: column;
  }

  .file-drop {
    grid-template-columns: 1fr;
    justify-items: start;
  }

  .choose-button,
  .file-state {
    grid-column: auto;
  }

  .file-copy strong {
    white-space: normal;
  }
}
</style>
