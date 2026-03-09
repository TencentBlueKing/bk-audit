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
  <bk-popover
    ref="popoverRef"
    :arrow="false"
    :is-show="isShow"
    placement="bottom-start"
    theme="light nl-tag-popover"
    trigger="manual"
    @after-hidden="handlePopoverHidden">
    <div
      ref="tagRef"
      class="condition-tag-item"
      :class="{ 'is-editing': isShow }"
      @click="handleToggle">
      <span class="tag-label">{{ t(tag.label) }}：</span>
      <span
        v-bk-tooltips="{
          content: fullDisplayValue,
          disabled: !isOverflow,
        }"
        class="tag-value-wrapper">
        <span class="tag-value">{{ displayValue }}</span>
      </span>
      <audit-icon
        class="tag-remove-btn"
        type="close"
        @click.stop="$emit('remove', tag.fieldName)" />
    </div>
    <template #content>
      <div
        class="nl-tag-editor-popover nl-tag-select-popover"
        @click.stop
        @mousedown.stop>
        <div class="nl-tag-search-input">
          <audit-icon
            class="nl-tag-search-icon"
            type="search1" />
          <input
            v-model="searchKey"
            class="nl-tag-search-inner"
            :placeholder="t('搜索')"
            type="text">
        </div>
        <bk-loading :loading="loading">
          <div class="nl-tag-select-list">
            <div
              v-for="item in filteredOptions"
              :key="valName ? item[valName] : item.id"
              class="nl-tag-select-item"
              :class="{
                'is-selected': isOptionSelected(item),
              }"
              @click="handleToggleOption(item)">
              <span>{{ item[labelName] }}</span>
              <audit-icon
                v-if="isOptionSelected(item)"
                style="color: #3a84ff;"
                type="check-line" />
            </div>
            <div
              v-if="filteredOptions.length === 0"
              class="nl-tag-select-empty">
              {{ t('无匹配项') }}
            </div>
          </div>
        </bk-loading>
      </div>
    </template>
  </bk-popover>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import {
    computed,
    onBeforeUnmount,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { IConditionTag } from '../../types';

  interface Props {
    tag: IConditionTag;
    // eslint-disable-next-line vue/no-unused-properties
    searchModel: Record<string, any>;
    isEditing: boolean;
    optionsCache: Record<string, Array<Record<string, any>>>;
  }
  interface Emits {
    (e: 'startEdit', fieldName: string): void;
    (e: 'update', fieldName: string, value: any): void;
    (e: 'remove', fieldName: string): void;
    (e: 'finishEdit'): void;
    (e: 'updateCache', fieldName: string, options: Array<Record<string, any>>): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();

  const MAX_MULTI_LEN = 10;

  const isShow = ref(props.isEditing);
  const localValue = ref<any[]>([]);
  const options = ref<Array<Record<string, any>>>([]);
  const loading = ref(false);
  const searchKey = ref('');
  const tagRef = ref<HTMLElement>();
  const popoverRef = ref();

  const valName = computed(() => props.tag.config.valName || 'id');
  const labelName = computed(() => props.tag.config.labelName || 'name');

  // 过滤后的选项
  const filteredOptions = computed(() => {
    const keyword = searchKey.value.trim().toLowerCase();
    if (!keyword) return options.value;
    return options.value.filter(item => String(item[labelName.value]).toLowerCase()
      .includes(keyword)
      || String(item[valName.value]).toLowerCase()
        .includes(keyword));
  });

  // 获取label列表
  const getLabels = (values: any[]): string[] => {
    const cached = props.optionsCache[props.tag.fieldName] || options.value;
    if (!cached || cached.length === 0) return values.map(String);
    return values.map((val) => {
      const found = cached.find(item => String(item[valName.value]) === String(val));
      return found ? found[labelName.value] : String(val);
    });
  };

  const fullDisplayValue = computed(() => {
    const { value } = props.tag;
    if (!Array.isArray(value) || value.length === 0) return '--';
    return getLabels(value).join('，');
  });

  const displayValue = computed(() => {
    const { value } = props.tag;
    if (!Array.isArray(value) || value.length === 0) return '--';
    const labels = getLabels(value);
    let displayText = '';
    let visibleCount = 0;
    for (const label of labels) {
      const nextText = visibleCount === 0 ? label : `${displayText}，${label}`;
      if (nextText.length > MAX_MULTI_LEN && visibleCount > 0) break;
      displayText = nextText;
      visibleCount += 1;
    }
    const remaining = labels.length - visibleCount;
    return remaining > 0 ? `${displayText}，+${remaining}` : displayText;
  });

  const isOverflow = computed(() => {
    const { value } = props.tag;
    if (!Array.isArray(value)) return false;
    const labels = getLabels(value);
    return labels.join('，').length > MAX_MULTI_LEN;
  });

  // 判断选项是否被选中
  const isOptionSelected = (item: Record<string, any>) => {
    const val = item[valName.value];
    if (Array.isArray(localValue.value)) {
      return localValue.value.includes(val) || localValue.value.includes(String(val));
    }
    return false;
  };

  // 切换编辑态
  const handleToggle = () => {
    if (isShow.value) {
      emit('finishEdit');
    } else {
      emit('startEdit', props.tag.fieldName);
    }
  };

  // 点击外部区域关闭下拉框
  // 注意：popover 内容区域已通过 @click.stop 阻止冒泡，不会触发此处理函数
  const handleDocumentClick = (e: MouseEvent) => {
    if (!isShow.value) return;
    const target = e.target as HTMLElement;
    // 点击标签自身内部 → 由 handleToggle 处理
    if (tagRef.value?.contains(target)) return;
    // 兜底：检查点击是否在 tippy-box 弹出层内（如 bk-input 的 clearable 图标等可能冒泡的元素）
    const closestTippy = (target as Element)?.closest?.('.tippy-box[data-theme~="nl-tag-popover"]');
    if (closestTippy) return;
    // 其他区域 → 关闭
    emit('finishEdit');
  };

  // 选项勾选切换
  const handleToggleOption = (item: Record<string, any>) => {
    const val = item[valName.value];
    if (!Array.isArray(localValue.value)) {
      localValue.value = [];
    }
    const index = localValue.value.findIndex((v: any) => String(v) === String(val));
    if (index >= 0) {
      localValue.value.splice(index, 1);
    } else {
      localValue.value.push(val);
    }
    emit('update', props.tag.fieldName, [...localValue.value]);
  };

  const handlePopoverHidden = () => {
    // 不在此处调用 finishEdit，完全由外部点击和 handleToggle 控制关闭
    // 避免选择选项更新 searchModel 时 popover 意外关闭
  };

  // 加载选项数据
  const loadOptions = async () => {
    if (!props.tag.config.service) return;
    if (props.optionsCache[props.tag.fieldName]) {
      options.value = props.optionsCache[props.tag.fieldName];
      return;
    }
    loading.value = true;
    try {
      const data = await props.tag.config.service(props.tag.config.defaultParams || {});
      if (props.tag.config.filterList) {
        options.value = data.filter(item => !props.tag.config.filterList?.includes(item[valName.value]));
      } else {
        options.value = data;
      }
      emit('updateCache', props.tag.fieldName, options.value);
    } catch {
      options.value = [];
    } finally {
      loading.value = false;
    }
  };

  // 监听编辑态切换，管理 document 点击事件和 popover 显示
  watch(() => props.isEditing, (val) => {
    isShow.value = val;
    if (val) {
      localValue.value = _.cloneDeep(props.tag.value) || [];
      searchKey.value = '';
      loadOptions();
      // 使用 setTimeout 确保当前点击事件处理完毕后再绑定，避免立即触发关闭
      setTimeout(() => {
        document.addEventListener('click', handleDocumentClick);
      });
    } else {
      document.removeEventListener('click', handleDocumentClick);
    }
  });

  onBeforeUnmount(() => {
    document.removeEventListener('click', handleDocumentClick);
  });
</script>
<style lang="postcss" scoped>
  .nl-tag-select-popover {
    width: 240px;
    padding: 8px;

    .nl-tag-search-input {
      display: flex;
      align-items: center;
      padding: 4px 0;
      margin-bottom: 4px;
      border-bottom: 1px solid #dcdee5;

      .nl-tag-search-icon {
        margin-right: 6px;
        font-size: 15px;
        color: #979ba5;
        flex-shrink: 0;
      }

      .nl-tag-search-inner {
        width: 100%;
        height: 24px;
        padding: 0;
        font-size: 12px;
        color: #63656e;
        background: transparent;
        border: none;
        outline: none;
        flex: 1;

        &::placeholder {
          color: #c4c6cc;
        }
      }
    }

    .nl-tag-select-list {
      max-height: 200px;
      overflow-y: auto;

      .nl-tag-select-item {
        display: flex;
        height: 32px;
        padding: 0 8px;
        font-size: 12px;
        color: #63656e;
        cursor: pointer;
        align-items: center;
        justify-content: space-between;
        transition: background .15s;

        &:hover {
          background: #f5f7fa;
        }

        &.is-selected {
          color: #3a84ff;
        }
      }

      .nl-tag-select-empty {
        padding: 16px 0;
        font-size: 12px;
        color: #c4c6cc;
        text-align: center;
      }
    }
  }
</style>
