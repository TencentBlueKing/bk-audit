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
    :show-footer="false"
    :title="t('编辑sql')"
    width="996">
    <div class="edit-container">
      <bk-alert
        closable
        theme="warning">
        {{ t('编辑后，已渲染的内容有可能会重新修改') }}
      </bk-alert>
      <div class="sql-editor">
        <div class="title">
          <span style="margin-left: auto;">
            <audit-icon
              v-bk-tooltips="t('复制')"
              class="icon"
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
          :style="{height: '680px', width: '100%'}">
          <audit-icon
            v-if="showExit"
            v-bk-tooltips="t('退出全屏')"
            class="ml16 exit-icon"
            type="un-full-screen-2"
            @click="handleExitFullScreen" />
        </div>
      </div>
    </div>
  </audit-sideslider>
</template>
<script setup lang="ts">
  import * as monaco from 'monaco-editor';
  import { nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  let editor: monaco.editor.IStandaloneCodeEditor;

  const { t } = useI18n();
  const rootRef = ref();

  const showEditSql = defineModel<boolean>('showEditSql', {
    required: true,
  });

  const showExit = ref(false);

  // 实现全屏
  const handleToggleFullScreen = () => {
    console.log('toggle full screen');
  };

  const handleExitFullScreen = () => {
    console.log('exit full screen');
  };

  const handleReize = () => {
    editor.layout();
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
        'scrollbarSlider.background': '#373a44', // 滚动条背景
        'editor.foreground': '#0d0b09', // 基础字体颜色
        'editor.background': '#00090B', // 背景颜色
        'editorCursor.foreground': '#d4b886', // 焦点颜色
        'editor.lineHighlightBackground': '#6492a520', // 焦点所在的一行的背景颜色
        'editorLineNumber.foreground': '#008800', // 行号字体颜色
      },
    });

    monaco.editor.setTheme('sqlEdit');
  };

  const initEditor = () => {
    editor = monaco.editor.create(rootRef.value, {
      language: 'sql',
      theme: 'vs-dark',
      minimap: {
        enabled: true,
      },
      automaticLayout: true,
      wordWrap: 'bounded',
    });
    editor.layout();
    window.addEventListener('resize', handleReize);
  };

  watch(() => showEditSql.value, (val) => {
    if (val) {
      nextTick(() => {
        initEditor();
        defineTheme();
      });
    }
  });
</script>
<style scoped lang="postcss">
.edit-container {
  padding: 16px 40px;

  .sql-editor {
    min-width: 800px;
    margin-top: 16px;
    line-height: 40px;

    .title {
      display: flex;
      height: 40px;
      padding: 0 25px;
      font-size: 14px;
      color: #c4c6cc;
      background: #1e1e1e;

      .icon {
        font-size: 16px;
        cursor: pointer;
      }
    }

    .sql-container {
      position: relative;
    }
  }
}
</style>
