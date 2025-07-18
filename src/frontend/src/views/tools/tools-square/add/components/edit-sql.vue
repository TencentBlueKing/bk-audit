<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on
  an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
  either express or implied. See the License for the
  specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
-->
<template>
  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="showEditSql"
    show-footer-slot
    :title="t('编辑sql')"
    width="820"
    @update:is-show="updateIsShow">
    <div class="edit-container">
      <bk-alert
        v-if="isEditMode"
        closable
        theme="warning">
        {{ t('编辑后，已渲染的内容有可能会重新修改') }}
      </bk-alert>
      <div class="sql-editor">
        <div class="title">
          <span style="margin-left: auto;">
            <input
              ref="uploadRef"
              accept=".sql"
              name="avatar"
              style="display: none;"
              type="file"
              @change="handleChangSql">
            <audit-icon
              v-bk-tooltips="t('上传')"
              class="icon"
              type="upload"
              @click="handleUpload" />
            <audit-icon
              v-bk-tooltips="t('复制')"
              class="ml16 icon"
              type="copy" />
            <audit-icon
              v-bk-tooltips="t('全屏')"
              class="ml16 icon"
              type="full-screen"
              @click.stop="handleToggleFullScreen" />
          </span>
        </div>
        <div
          ref="rootRef"
          class="sql-container"
          :style="{height: '100%', width: '100%'}">
          <audit-icon
            v-if="showExit"
            v-bk-tooltips="t('退出全屏')"
            class="ml16 exit-icon"
            type="un-full-screen-2"
            @click="handleExitFullScreen" />
        </div>
      </div>
    </div>
    <template #footer>
      <div style="padding-left: 16px;">
        <bk-button
          class="mr8"
          :loading="btnLoading"
          style="width: 102px;"
          theme="primary"
          @click="handleConfirm">
          {{ t('保存并解析') }}
        </bk-button>
        <bk-button
          style="min-width: 64px;"
          @click="handleCancle">
          {{ t('取消') }}
        </bk-button>
      </div>
    </template>
  </audit-sideslider>
</template>
<script setup lang="ts">
  import * as monaco from 'monaco-editor';
  import { nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolManageService from '@service/tool-manage';

  import ParseSqlModel from '@model/tool/parse-sql';

  import useFullScreen from '@/hooks/use-full-screen';
  import useRequest from '@/hooks/use-request';

  interface Emits {
    (e: 'UpdateParseSql', value: ParseSqlModel): void;
  }

  const emits = defineEmits<Emits>();
  const showEditSql = defineModel<boolean>('showEditSql', {
    required: true,
  });

  let editor: monaco.editor.IStandaloneCodeEditor;

  const { t } = useI18n();
  const rootRef = ref();
  const uploadRef = ref();
  const { showExit, handleScreenfull } = useFullScreen(
    () => editor,
    () => rootRef.value,
  );

  const isEditMode = ref(false);
  const filename = ref('');
  const sqlDec = ref(`/*
──────────────────────────────────────────────────────────────────────────────
SQL 变量占位符使用指引
──────────────────────────────────────────────────────────────────────────────
1. 在SQL 模式中，如需让终端用户自行填写某字段，请使用 :key 形式
   声明变量。执行时系统会弹出输入框并安全绑定，杜绝 SQL 注入风险。
2. 同一变量可在多处复用，只需保持变量名一致（如 :thedate）。
──────────────────────────────────────────────────────────────────────────────
不同前端类型变量的渲染指引

- 输入框/字符串：
    SQL写法：WHERE username = :username
    用户输入：字符串，最终渲染为 WHERE username = 'xxx'

- 数字输入框：
    SQL写法：WHERE age = :age
    用户输入：数字，最终渲染为 WHERE age = 18

- 时间选择器：
    SQL写法：WHERE created_at = :created_at
    用户输入：'2023-01-01 12:00:00'，最终渲染为 WHERE created_at = 1672545600000
    （系统自动转为毫秒时间戳）

- 时间范围选择器：
    SQL写法：WHERE event_time = :time_range
    用户输入：['2023-01-01 00:00:00', '2023-01-02 00:00:00']
    最终渲染为 WHERE event_time BETWEEN 1672502400000 AND 1672588800000

- 人员选择器：
    SQL写法：WHERE operator IN :user_list
    用户输入：['user1', 'user2']
    最终渲染为 WHERE operator IN ('user1','user2')
──────────────────────────────────────────────────────────────────────────────
*/
 `);
  const formData = ref({
    sql: '',
    dialect: 'mysql',
  });

  const updateIsShow = () => {
    formData.value.sql = '';
  };
  // 解析sql
  const {
    loading: btnLoading,
    run: parseSql,
  } = useRequest(ToolManageService.parseSql, {
    defaultValue: new ParseSqlModel(),
    onSuccess: (data) => {
      emits('UpdateParseSql', data);
      handleCancle();
    },
  });

  // 保存并解析
  const handleConfirm = () => {
    nextTick(() => {
      parseSql(formData.value);
    });
  };

  const handleCancle = () => {
    formData.value.sql = '';
    showEditSql.value = false;
    isEditMode.value = false;
  };

  // 实现全屏
  const handleToggleFullScreen = () => {
    handleScreenfull();
  };

  // 退出全屏
  const handleExitFullScreen = () => {
    handleScreenfull();
  };

  const handleUpload = () => {
    uploadRef.value.click();
  };

  const handleChangSql = (e: any) => {
    const reader = new FileReader();
    filename.value = uploadRef.value.files[0].name;
    reader.readAsText((uploadRef.value.files[0]));
    reader.onload = (e: Event) => {
      const target = e.target as FileReader;
      formData.value.sql = target.result as string;
      const model = monaco.editor.createModel(formData.value.sql, 'sql');
      editor.setModel(model);
    };
    e.target.value = '';
  };

  const defineTheme = () => {
    monaco.editor.defineTheme('sqlEdit', {
      base: 'vs', // 以哪个默认主题为基础："vs" | "vs-dark" | "hc-black" | "hc-light"
      inherit: true,
      rules: [
        { token: 'identifier', foreground: '#d06733' },
        { token: 'number', foreground: '#6bbeeb', fontStyle: 'italic' },
        { token: 'keyword', foreground: '#05a4d5' },
      ],
      colors: {
        'scrollbarSlider.background': '#eeeff2', // 滚动条背景
        'editor.foreground': '#0d0b09', // 基础字体颜色
        'editor.background': '#fbfbfc', // 背景颜色
        'editorCursor.foreground': '#d4b886', // 焦点颜色
        'editor.lineHighlightBackground': '#6492a520', // 焦点所在的一行的背景颜色
        'editorLineNumber.foreground': '#008800', // 行号字体颜色
      },
    });

    monaco.editor.setTheme('sqlEdit');
  };
  // 删除注释
  const removeComments = (inputSql: string) => {
    let result = inputSql;
    // 删除单行注释 (-- 或 #)
    result = result.replace(/--.*$|#.*$/gm, '');
    // 删除多行注释 (/* */)
    result = result.replace(/\/\*[\s\S]*?\*\//g, '');
    return result.trim();
  };
  const initEditor = () => {
    editor = monaco.editor.create(rootRef.value, {
      value: formData.value.sql || sqlDec.value,
      language: 'sql',
      theme: 'vs-dark',
      minimap: {
        enabled: true,
      },
      automaticLayout: true,
      wordWrap: 'bounded',
    });
    editor.layout();
    editor.onDidBlurEditorText(() => {
      formData.value.sql = removeComments(editor.getValue());
    });
  };

  watch(() => showEditSql.value, (val) => {
    if (val) {
      nextTick(() => {
        initEditor();
        defineTheme();
      });
    }
  });

  defineExpose({
    setEditorValue(value: string) {
      formData.value.sql = value;
      isEditMode.value = true;
    },
  });
</script>
<style scoped lang="postcss">
.edit-container {
  padding: 16px 40px;

  .sql-editor {
    height: 75vh;
    min-width: 550px;
    padding-bottom: 5px;
    margin-top: 16px;
    line-height: 40px;
    background-color: aqua;

    .title {
      display: flex;
      height: 40px;
      padding: 0 25px;
      font-size: 14px;
      color: #c4c6cc;
      background: #fbfbfc;

      .icon {
        font-size: 16px;
        cursor: pointer;
      }
    }

    .sql-container {
      position: relative;

      .exit-icon {
        position: absolute;
        top: 10px;
        right: 20px;
        z-index: 11111;
        font-size: 20px;
        color: #c4c6cc;
        cursor: pointer;
      }
    }
  }
}
</style>
