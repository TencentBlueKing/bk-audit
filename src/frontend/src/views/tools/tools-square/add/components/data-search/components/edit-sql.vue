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
    :quick-close="false"
    show-footer-slot
    :title="t('编辑sql')"
    width="820"
    @update:is-show="updateIsShow">
    <div
      class="tip-button"
      @click="openSqlTip">
      {{ t('SQL 变量占位符使用指引 >>') }}
    </div>
    <div class="edit-container">
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
              type="copy"
              @click.stop="handleCopy" />
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
          :loading="btnLoading || editBtnLoading"
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
  <sql-tip ref="sqlTipRef" />
</template>
<script setup lang="ts">
  import * as monaco from 'monaco-editor';
  import { nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import ToolManageService from '@service/tool-manage';

  import ParseSqlModel from '@model/tool/parse-sql';

  import { execCopy } from '@utils/assist';

  import SqlTip from './edit-sql-tip.vue';

  import useFullScreen from '@/hooks/use-full-screen';
  import useRequest from '@/hooks/use-request';

  interface Emits {
    (e: 'UpdateParseSql', value: ParseSqlModel): void;
  }

  const emits = defineEmits<Emits>();
  const showEditSql = defineModel<boolean>('showEditSql', {
    required: !true,
  });

  let editor: monaco.editor.IStandaloneCodeEditor;

  const { t } = useI18n();
  const rootRef = ref();
  const uploadRef = ref();
  const { showExit, handleScreenfull } = useFullScreen(
    () => editor,
    () => rootRef.value,
  );
  const sqlTipRef = ref();
  const route = useRoute();
  const isEditMode = ref(false);
  const filename = ref('');
  const uid = ref('');
  const formData = ref({
    sql: '',
    dialect: 'mysql',
    with_permission: true,
  });

  const updateIsShow = () => {
    formData.value.sql = '';
  };

  const openSqlTip = () => {
    if (sqlTipRef.value) {
      sqlTipRef.value.openDialog();
    }
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

  // 解析sql
  const {
    loading: editBtnLoading,
    run: editModelParseSql,
  } = useRequest(ToolManageService.editModelParseSql, {
    defaultValue: new ParseSqlModel(),
    onSuccess: (data) => {
      emits('UpdateParseSql', data);
      handleCancle();
    },
  });

  // 保存并解析
  const handleConfirm = () => {
    nextTick(() => {
      if (route.name === 'toolsAdd' || !isEditMode.value) {
        parseSql(formData.value);
      } else {
        editModelParseSql({
          ...formData.value,
          uid: uid.value,
        });
      }
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

  const handleCopy = () => {
    execCopy(formData.value.sql, t('复制成功'));
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
      value: formData.value.sql,
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
    setEditorValue(value: string, id: string) {
      formData.value.sql = value;
      uid.value = id;
      isEditMode.value = true;
    },
  });
</script>
<style scoped lang="postcss">
.tip-button {
  width: 211px;
  padding: 5px;
  margin-top: 10px;
  margin-left: 32px;
  font-size: 14px;
  letter-spacing: 0;
  color: #3a84ff;
  text-align: center;
  cursor: pointer;
  background: #fff;
  border: 1px solid #3a84ff;
  border-radius: 2px;
}

.edit-container {
  padding: 16px 40px;

  .sql-editor {
    height: 75vh;
    min-width: 550px;
    padding-bottom: 5px;
    margin-top: 16px;
    line-height: 40px;

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
