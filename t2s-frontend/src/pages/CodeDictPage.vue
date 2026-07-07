<template>
  <section class="code-dict-page">
    <div class="page-header">
      <div>
        <h2>码值字典导入</h2>
      </div>
    </div>

    <div v-if="notice" class="notice" :class="noticeType">{{ notice }}</div>

    <div class="upload-grid">
      <section class="upload-panel">
        <div class="panel-head">
          <h3>码值字典</h3>
          <span>写入取值层</span>
        </div>

        <label class="file-picker">
          <span>Excel 文件</span>
          <input ref="dictInputRef" type="file" accept=".xlsx,.xlsm" multiple @change="handleFileChange('dict', $event)" />
        </label>

        <table class="format-table">
          <thead>
            <tr>
              <th>必要列</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><code>category_key</code>、<code>code</code>、<code>name</code></td>
            </tr>
          </tbody>
        </table>

        <div class="actions">
          <button class="btn-primary" @click="upload('dict')" :disabled="panels.dict.loading">
            {{ panels.dict.loading ? "导入中" : "导入码值字典" }}
          </button>
          <span v-if="panels.dict.files.length" class="file-name">已选 {{ panels.dict.files.length }} 个文件</span>
        </div>

        <ul v-if="panels.dict.files.length" class="file-list">
          <li v-for="file in panels.dict.files" :key="`${file.name}-${file.lastModified}`">{{ file.name }}</li>
        </ul>

        <div v-if="panels.dict.result" class="result-inline">
          <div class="stats">
            <span>码值 {{ panels.dict.result.value.value_count }}</span>
            <span>类目 {{ panels.dict.result.value.category_count }}</span>
            <span>写入 {{ panels.dict.result.value.written }}</span>
            <span v-if="panels.dict.result.value.skipped_rows">跳过行 {{ panels.dict.result.value.skipped_rows }}</span>
          </div>
          <p v-if="panels.dict.result.ignored_files?.length" class="hint">
            未导入文件：{{ panels.dict.result.ignored_files.join("、") }}
          </p>
        </div>
      </section>

      <section class="upload-panel">
        <div class="panel-head">
          <h3>字段码值绑定</h3>
          <span>写入绑定层</span>
        </div>

        <label class="file-picker">
          <span>Excel 文件</span>
          <input ref="bindingInputRef" type="file" accept=".xlsx,.xlsm" multiple @change="handleFileChange('binding', $event)" />
        </label>

        <table class="format-table">
          <thead>
            <tr>
              <th>必要列</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><code>table_name</code>、<code>column_name</code>、<code>category_key</code></td>
            </tr>
          </tbody>
        </table>

        <div class="actions">
          <button class="btn-primary" @click="upload('binding')" :disabled="panels.binding.loading">
            {{ panels.binding.loading ? "导入中" : "导入字段绑定" }}
          </button>
          <span v-if="panels.binding.files.length" class="file-name">已选 {{ panels.binding.files.length }} 个文件</span>
        </div>

        <ul v-if="panels.binding.files.length" class="file-list">
          <li v-for="file in panels.binding.files" :key="`${file.name}-${file.lastModified}`">{{ file.name }}</li>
        </ul>

        <div v-if="panels.binding.result" class="result-inline">
          <div class="stats">
            <span>绑定 {{ panels.binding.result.binding.binding_count }}</span>
            <span>写入 {{ panels.binding.result.binding.written }}</span>
            <span v-if="panels.binding.result.binding.skipped_rows">跳过行 {{ panels.binding.result.binding.skipped_rows }}</span>
          </div>
          <p v-if="panels.binding.result.ignored_files?.length" class="hint">
            未导入文件：{{ panels.binding.result.ignored_files.join("、") }}
          </p>
        </div>
      </section>
    </div>

    <div v-if="panels.dict.result || panels.binding.result" class="result-panel">
      <div class="section-title">最近导入</div>
      <div class="stats">
        <span v-if="panels.dict.result">码值写入 {{ panels.dict.result.value.written }}</span>
        <span v-if="panels.binding.result">绑定写入 {{ panels.binding.result.binding.written }}</span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from "vue";
import { apiRequest } from "../api/client";

const notice = ref("");
const noticeType = ref("info");
const dictInputRef = ref(null);
const bindingInputRef = ref(null);

const panels = reactive({
  dict: {
    files: [],
    loading: false,
    result: null,
  },
  binding: {
    files: [],
    loading: false,
    result: null,
  },
});

const uploadConfig = {
  dict: {
    label: "码值字典",
    endpoint: "/text2sql/code-dict/import/value",
  },
  binding: {
    label: "字段绑定",
    endpoint: "/text2sql/code-dict/import/binding",
  },
};

function setNotice(message, type = "info") {
  notice.value = message;
  noticeType.value = type;
}

function handleFileChange(type, event) {
  const panel = panels[type];
  const config = uploadConfig[type];
  if (!panel || !config) return;

  panel.files = Array.from(event.target.files || []);
  panel.result = null;
  if (panel.files.length) setNotice(`已选择 ${config.label}文件 ${panel.files.length} 个`, "info");
}

async function upload(type) {
  const panel = panels[type];
  const config = uploadConfig[type];
  if (!panel || !config) return;
  if (!panel.files.length) {
    const inputRef = type === "dict" ? dictInputRef : bindingInputRef;
    inputRef.value?.click();
    return;
  }

  panel.loading = true;
  panel.result = null;
  try {
    const form = new FormData();
    for (const file of panel.files) form.append("files", file);
    const data = await apiRequest(config.endpoint, {
      method: "POST",
      body: form,
    });
    panel.result = data;
    const written = type === "dict" ? data.value.written : data.binding.written;
    setNotice(`${config.label}导入完成：写入 ${written} 条。`, "success");
  } catch (error) {
    setNotice(`${config.label}导入失败：${error.message}`, "error");
  } finally {
    panel.loading = false;
  }
}
</script>

<style scoped>
.code-dict-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 1120px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

h2 {
  margin: 0;
  font-size: clamp(24px, 2.7vw, 34px);
  line-height: 1.1;
}

.upload-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.upload-panel,
.result-panel {
  background: rgba(255, 255, 255, 0.58);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.panel-head h3 {
  margin: 0;
  font-size: 18px;
  line-height: 1.2;
}

.panel-head span {
  color: var(--text-muted);
  font-size: 12px;
  white-space: nowrap;
}

.file-picker {
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 13px;
  font-weight: 620;
  color: var(--text-muted);
}

input[type="file"] {
  padding: 12px;
}

.section-title {
  font-weight: 690;
  margin-bottom: 10px;
}

.section-title {
  margin-top: 18px;
}

table {
  width: 100%;
  border-collapse: collapse;
}

.format-table {
  margin-top: 16px;
}

th,
td {
  border-bottom: 1px solid var(--line);
  padding: 11px 10px;
  text-align: left;
}

th {
  color: var(--text-muted);
  font-size: 13px;
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

.file-name {
  color: var(--text-muted);
}

.file-list {
  margin: 12px 0 0;
  padding-left: 18px;
  color: var(--text-muted);
  font-size: 13px;
}

.result-inline {
  margin-top: 18px;
}

.stats {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.stats span {
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: 7px;
  padding: 6px 12px;
  font-weight: 620;
}

.stats span.ok {
  background: #ecfdf5;
  color: #065f46;
  border-color: #a7f3d0;
}

.stats span.warn {
  background: #fffbeb;
  color: #92400e;
  border-color: #fde68a;
}

.hint {
  color: var(--text-muted);
  font-size: 13px;
  margin: 0 0 8px;
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

@media (max-width: 720px) {
  .page-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .upload-grid {
    grid-template-columns: 1fr;
  }
}
</style>
