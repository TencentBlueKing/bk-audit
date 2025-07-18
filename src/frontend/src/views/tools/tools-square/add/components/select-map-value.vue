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
  <div
    ref="rootRef"
    class="reference-select-map-value"
    :class="{
      'is-focused': isShowPop,
      'is-errored': isError
    }">
    <vuedraggable
      class="draggable-box"
      :group="{
        name: 'field',
        pull: false,
        push: true
      }"
      item-key="key"
      :list="localValue"
      @change="handelValueDragChange">
      <template #item="{element}">
        <div class="select-result-text">
          <span>{{ element }}</span>
        </div>
      </template>
    </vuedraggable>
    <audit-icon
      v-if="localValue.length > 0"
      class="remove-btn"
      type="delete-fill"
      @click.self="handleRemove" />
    <audit-icon
      v-if="localValue.length < 1"
      class="focused-flag"
      type="angle-line-down" />
    <audit-icon
      v-if="isError"
      v-bk-tooltips="t('必填项')"
      class="error-flag"
      type="remind-fill" />
  </div>
  <div style="display: none;">
    <div ref="popRef">
      <div
        v-if="searchKey || renderFieldList.length > 0"
        class="search-input-box">
        <bk-input
          v-model="searchKey"
          behavior="simplicity"
          :placeholder="t('请输入字段名搜索')">
          <template #prefix>
            <span style="font-size: 14px; color: #979ba5;">
              <audit-icon type="search1" />
            </span>
          </template>
        </bk-input>
      </div>
      <div class="field-list">
        <div
          v-for="fieldItem in renderFieldList"
          :key="fieldItem.raw_name"
          class="field-item"
          @click="handleAlternativeFieldSelect(fieldItem)">
          <span>{{ fieldItem.raw_name }}</span>
        </div>
      </div>
      <div
        v-if="renderFieldList.length < 1"
        style="color: #63656e; text-align: center;">
        {{ t('数据为空') }}
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import tippy, {
    type Instance,
    type SingleTarget,
  } from 'tippy.js';
  import {
    computed,
    onBeforeUnmount,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import Vuedraggable from 'vuedraggable';

  import useDebouncedRef from '@hooks/use-debounced-ref';

  import { encodeRegexp } from '@/utils/assist';

  interface LocalOutputField {
    raw_name: string;
    display_name: string;
    description: string;
    [key: string]: string;
  }

  interface Props {
    value: string,
    alternativeFieldList: Array<LocalOutputField>,
  }
  interface Emits {
    (e: 'change', value: Array<LocalOutputField>): void
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  let tippyIns: Instance;

  const localValue = ref<Array<string>>([]);
  const isShowPop = ref(false);
  const isError = ref(false);
  const rootRef = ref();
  const popRef = ref();

  const searchKey = useDebouncedRef('');

  const renderFieldList = computed(() => props.alternativeFieldList.reduce((result, item) => {
    const reg = new RegExp(encodeRegexp(searchKey.value), 'i');
    if (reg.test(item.raw_name) || reg.test(item.description)) {
      result.push(item);
    }
    return result;
  }, [] as Array<LocalOutputField>));

  watch(() => props.value, (value) => {
    localValue.value = [value];
  }, {
    immediate: true,
  });
  // 拖拽
  const handelValueDragChange = (dragEvent: any) => {
    isError.value = false;
    if (dragEvent.added && dragEvent.added.element) {
      emits('change', [dragEvent.added.element]);
    }
  };
  // 用户选择
  const handleAlternativeFieldSelect = (field: LocalOutputField) => {
    emits('change', [field]);
    tippyIns.hide();
  };
  // 删除值
  const handleRemove = () => {
    emits('change', []);
  };

  onMounted(() => {
    tippyIns = tippy(rootRef.value as SingleTarget, {
      content: popRef.value,
      placement: 'bottom',
      appendTo: () => document.body,
      theme: 'alternative-field-pop-menu light',
      maxWidth: 'none',
      trigger: 'click',
      interactive: true,
      arrow: false,
      offset: [0, 8],
      onShow: () => {
        const { width } = rootRef.value.getBoundingClientRect();
        Object.assign(popRef.value.style, {
          width: `${width}px`,
        });
        isShowPop.value = true;
        isError.value = false;
      },
      onHide: () => {
        isShowPop.value = false;
        searchKey.value = '';
      },
    });
  });

  onBeforeUnmount(() => {
    tippyIns.hide();
    tippyIns.unmount();
    tippyIns.destroy();
  });
</script>
<style lang="postcss">
  .reference-select-map-value {
    position: relative;
    display: flex;
    height: 30px;
    overflow: hidden;
    cursor: pointer;
    border: 1px solid transparent;
    transition: all .15s;
    align-items: center;

    &:hover {
      background-color: #fafbfd;
    }

    &.is-focused {
      border: 1px solid #3a84ff;

      .focused-flag {
        transform: rotateZ(-90deg);
      }
    }

    &.is-errored {
      background: rgb(255 221 221 / 20%);
      outline: 1px solid #dcdee5;
    }

    .draggable-box {
      position: relative;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background-color: #fff;

      .sortable-ghost {
        position: absolute;
        inset: 0;
        z-index: 1;
        border: 1px solid #3a84ff;
      }
    }

    .select-result-text {
      display: flex;
      padding: 0 10px;
    }

    .select-result-text-value {
      overflow: hidden;
      color: #979ba5;
      text-overflow: ellipsis;
      word-break: keep-all;
      white-space: nowrap;
    }

    .focused-flag {
      position: absolute;
      right: 8px;
      font-size: 12px;
      transition: all .15s;
    }

    .remove-btn {
      position: absolute;
      right: 8px;
      z-index: 1;
      font-size: 12px;
      color: #c4c6cc;
      transition: all .15s;

      &:hover {
        color: #979ba5;
      }
    }

    .error-flag {
      position: absolute;
      right: 27px;
      font-size: 14px;
      color: #ea3636;
    }
  }

  .tippy-box[data-theme~='alternative-field-pop-menu'] {
    .tippy-content {
      padding: 10px 0;
      font-size: 12px;
      line-height: 32px;
      color: #26323d;
      background-color: #fff;
      border: 1px solid #dcdee5;
      border-radius: 2px;
      user-select: none;

      .search-input-box {
        padding: 0 12px;

        .bk-input--text {
          background-color: #fff;
        }
      }

      .field-list {
        max-height: 300px;
        overflow-y: auto;
      }

      .field-item {
        display: flex;
        height: 32px;
        align-items: center;
        padding: 0 12px;

        &:hover {
          color: #3a84ff;
          cursor: pointer;
          background-color: #f5f7fa;
        }

        &.active {
          color: #3a84ff;
        }

        &.disabled {
          color: #c4c6cc;
          cursor: not-allowed;
          background-color: transparent;
        }
      }

      .field-item-value {
        padding-left: 8px;
        overflow: hidden;
        color: #979ba5;
        text-overflow: ellipsis;
        word-break: keep-all;
        white-space: nowrap;
      }
    }
  }
</style>
