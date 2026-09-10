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
  <div class="json-field-preview">
    <div
      v-if="jsonObject"
      class="json-field-preview-popover-host">
      <bk-popover
        arrow
        boundary="body"
        ext-cls="sec-chat-json-preview-popover"
        hide-ignore-reference
        :is-show="popoverVisible"
        placement="bottom-start"
        theme="light"
        trigger="manual"
        :width="600"
        @clickoutside="popoverVisible = false"
        @update:is-show="onPopoverShowChange">
        <div
          class="json-field-preview-trigger"
          @click.stop="openPopover">
          {{ previewText }}
        </div>
        <template #content>
          <div
            class="json-field-preview-panel"
            @click.stop>
            <button
              class="json-copy-btn"
              title="复制"
              type="button"
              @click="handleCopy">
              <audit-icon type="copy" />
            </button>
            <div class="json-field-preview-scroll">
              <!-- eslint-disable vue/no-v-html -->
              <!-- highlightHtml 由 getJsonHighlightHtml 生成，内容已 escapeHtml 转义 -->
              <pre
                class="json-field-preview-code"
                v-html="highlightHtml" />
              <!-- eslint-enable vue/no-v-html -->
            </div>
          </div>
        </template>
      </bk-popover>
    </div>
    <show-tooltips-text
      v-else
      class="json-field-preview-fallback"
      :data="fallbackText"
      :max-width="tooltipMaxWidth"
      :tooltip-content-class="tooltipContentClass"
      :tooltip-max-height="tooltipMaxHeight" />
  </div>
</template>

<script lang="ts" setup>
  import { computed, ref, watch } from 'vue';

  import ShowTooltipsText from '@components/show-tooltips-text/index.vue';
  import useMessage from '@hooks/use-message';

  import {
    getJsonFirstPairPreview,
    getJsonHighlightHtml,
    getJsonPrettyText,
    tryParseJsonObject,
  } from '../utils/json-field-preview';

  const props = withDefaults(defineProps<{
    /** 原始值（对象优先） */
    value?: unknown;
    /** 非 JSON 时的展示文案 */
    text?: string;
    tooltipMaxWidth?: string | number;
    tooltipMaxHeight?: string;
    tooltipContentClass?: string;
  }>(), {
    value: undefined,
    text: '',
    tooltipMaxWidth: 480,
    tooltipMaxHeight: '400px',
    tooltipContentClass: 'show-tooltips-text-popup',
  });

  const { messageSuccess, messageError } = useMessage();
  const popoverVisible = ref(false);

  const jsonObject = computed(() => (
    tryParseJsonObject(props.value) || tryParseJsonObject(props.text)
  ));

  const previewText = computed(() => {
    if (!jsonObject.value) return '';
    return getJsonFirstPairPreview(jsonObject.value);
  });

  const highlightHtml = computed(() => (
    jsonObject.value ? getJsonHighlightHtml(jsonObject.value) : ''
  ));

  const prettyText = computed(() => (
    jsonObject.value ? getJsonPrettyText(jsonObject.value) : ''
  ));

  const fallbackText = computed(() => {
    if (props.text !== undefined && props.text !== null && String(props.text) !== '') {
      return String(props.text);
    }
    if (props.value === undefined || props.value === null || props.value === '') {
      return '';
    }
    return String(props.value);
  });

  watch(jsonObject, () => {
    popoverVisible.value = false;
  });

  const openPopover = () => {
    popoverVisible.value = !popoverVisible.value;
  };

  const onPopoverShowChange = (visible: boolean) => {
    popoverVisible.value = visible;
  };

  const handleCopy = async () => {
    if (!prettyText.value) return;
    try {
      await navigator.clipboard.writeText(prettyText.value);
      messageSuccess('复制成功');
    } catch {
      messageError('复制失败');
    }
  };
</script>

<style lang="postcss" scoped>
  .json-field-preview {
    display: block;
    width: 100%;
    max-width: 100%;
    min-width: 0;
    overflow: hidden;
    line-height: inherit;
    box-sizing: border-box;
  }

  .json-field-preview-popover-host {
    display: block;
    width: 100%;
    max-width: 100%;
    min-width: 0;
    overflow: hidden;
  }

  /* bk-popover 默认 reference 为 inline，会被超长文本撑开，导致 tip 错位、邻列无法点击 */
  .json-field-preview-popover-host :deep(> .bk-popover-reference),
  .json-field-preview-popover-host :deep(> .bk-popover-trigger),
  .json-field-preview-popover-host :deep(> span) {
    display: block !important;
    width: 100% !important;
    max-width: 100% !important;
    min-width: 0 !important;
    overflow: hidden;
    box-sizing: border-box;
  }

  .json-field-preview-trigger {
    display: block;
    width: 100%;
    max-width: 100%;
    min-width: 0;
    overflow: hidden;
    font-size: inherit;
    line-height: inherit;
    color: inherit;
    text-overflow: ellipsis;
    white-space: nowrap;
    cursor: pointer;
    box-sizing: border-box;
  }

  .json-field-preview-fallback {
    display: block;
    width: 100%;
    max-width: 100%;
    min-width: 0;
    overflow: hidden;
  }
</style>

<style lang="postcss">
  .sec-chat-json-preview-popover {
    z-index: 9999 !important;

    .bk-pop2-content,
    .bk-popover-content {
      padding: 0;
      overflow: hidden;
      background: #fff;
      border: 1px solid #dcdee5;
      border-radius: 8px;
      box-shadow: 0 4px 16px rgb(0 0 0 / 12%);
      box-sizing: border-box;
    }
  }

  .json-field-preview-panel {
    position: relative;
    box-sizing: border-box;
    width: 100%;
    max-width: 100%;
    overflow: hidden;
  }

  .json-field-preview-scroll {
    max-height: min(400px, 70vh);
    padding: 16px 40px 16px 16px;
    overflow-x: hidden;
    overflow-y: auto;
    box-sizing: border-box;
    scrollbar-width: thin;
    scrollbar-color: #dcdee5 transparent;

    &::-webkit-scrollbar {
      width: 4px;
      height: 4px;
    }

    &::-webkit-scrollbar-thumb {
      background: #dcdee5;
      border-radius: 2px;
    }
  }

  .json-copy-btn {
    position: absolute;
    top: 10px;
    /* 滚动条约 4px 在最右侧，图标在其内侧 */
    right: 14px;
    z-index: 1;
    display: inline-flex;
    width: 24px;
    height: 24px;
    padding: 0;
    color: #3a84ff;
    cursor: pointer;
    background: #fff;
    border: none;
    border-radius: 4px;
    align-items: center;
    justify-content: center;

    &:hover {
      background: #f0f5ff;
    }

    .audit-icon {
      font-size: 16px;
    }
  }

  .json-field-preview-code {
    margin: 0;
    font-family: Consolas, Menlo, Monaco, 'Courier New', monospace;
    font-size: 12px;
    line-height: 20px;
    color: #313238;
    word-break: break-all;
    white-space: pre-wrap;

    .json-key {
      color: #3a84ff;
    }

    .json-string,
    .json-literal {
      color: #313238;
    }
  }
</style>
