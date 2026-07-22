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
    class="data-source-picker">
    <div
      class="dsp-trigger"
      :class="{ 'is-active': panelVisible, 'is-empty': !displayLabel }"
      @click="togglePanel">
      <span class="dsp-trigger-text">
        {{ displayLabel || t('搜索数据名称、别名、数据ID等') }}
      </span>
      <audit-icon
        class="dsp-trigger-arrow"
        :class="{ 'is-open': panelVisible }"
        type="angle-line-down" />
    </div>

    <div
      v-show="panelVisible"
      class="dsp-panel">
      <div
        v-if="list.length"
        class="dsp-tabs">
        <span
          v-for="tab in list"
          :key="tab.value"
          class="dsp-tab-item"
          :class="{ 'is-active': activeTab === tab.value }"
          @click="handleTabChange(tab.value)">
          {{ tab.label }}
        </span>
      </div>

      <div
        class="dsp-body"
        :class="{ 'is-single-column': !hasThirdLevel }">
        <div class="dsp-column dsp-column-left">
          <div class="dsp-search">
            <audit-icon
              class="dsp-search-icon"
              type="search1" />
            <input
              v-model="leftKeyword"
              class="dsp-search-input"
              :placeholder="t('搜索 业务名称、业务ID')"
              type="text"
              @click.stop>
          </div>
          <div class="dsp-list">
            <div
              v-for="item in filteredLeftList"
              :key="item.value"
              v-bk-tooltips="getItemTooltip(item, true)"
              class="dsp-list-item"
              :class="{
                'is-active': selectedLeftValue === item.value,
                'is-disabled': item.disabled,
              }"
              @click="handleSelectLeft(item)">
              <span class="dsp-list-item-label">{{ formatLeftLabel(item) }}</span>
              <span
                v-if="!isLeafNode(item)"
                class="dsp-list-item-meta">
                <bk-tag
                  v-if="getChildCount(item) > 0"
                  class="dsp-list-item-count"
                  radius="8px">
                  {{ getChildCount(item) }}
                </bk-tag>
                <audit-icon
                  class="dsp-list-item-arrow"
                  type="angle-line-down" />
              </span>
            </div>
            <div
              v-if="filteredLeftList.length === 0"
              class="dsp-list-empty">
              {{ t('暂无数据') }}
            </div>
          </div>
        </div>

        <div
          v-if="hasThirdLevel"
          class="dsp-column dsp-column-right">
          <div class="dsp-search">
            <audit-icon
              class="dsp-search-icon"
              type="search1" />
            <input
              v-model="rightKeyword"
              class="dsp-search-input"
              :placeholder="t('搜索 数据表名称')"
              type="text"
              @click.stop>
          </div>
          <bk-loading
            class="dsp-right-loading"
            :loading="rightLoading"
            mode="spin"
            size="small">
            <div class="dsp-list">
              <template v-if="showRightPane">
                <div
                  v-for="item in filteredRightList"
                  :key="item.value"
                  v-bk-tooltips="getItemTooltip(item, false)"
                  class="dsp-list-item"
                  :class="{
                    'is-active': isRightSelected(item),
                    'is-disabled': item.disabled,
                  }"
                  @click="handleSelectRight(item)">
                  <span class="dsp-list-item-label">{{ item.label }}</span>
                </div>
                <div
                  v-if="filteredRightList.length === 0 && !rightLoading"
                  class="dsp-list-empty">
                  {{ t('暂无数据') }}
                </div>
              </template>
              <div
                v-else
                class="dsp-list-empty">
                {{ t('请先选择左侧业务') }}
              </div>
            </div>
          </bk-loading>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import {
    computed,
    nextTick,
    onBeforeUnmount,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface PickerNode {
    label: string;
    value: string;
    version?: number;
    leaf?: boolean;
    disabled?: boolean;
    children?: Array<{
      label: string;
      value: string;
      leaf?: boolean;
      disabled?: boolean;
    }>;
  }

  interface ConfigTypeTableItem {
    label: string;
    value: string;
    children: PickerNode[];
  }

  interface Props {
    list: ConfigTypeTableItem[];
    modelValue: string[];
    mineBizRtType?: string;
    loadChildren?: (tableType: string, bizId: string) => Promise<Array<{
      label: string;
      value: string;
      leaf: boolean;
    }>>;
    decodeTypeBizId?: (tableType: string, value: string | number) => string;
  }

  interface Emits {
    (e: 'update:modelValue', value: string[]): void;
    (e: 'change', value: string[]): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    mineBizRtType: 'MineBizRt',
    loadChildren: undefined,
    decodeTypeBizId: undefined,
  });
  const emit = defineEmits<Emits>();
  const { t } = useI18n();

  const rootRef = ref<HTMLElement>();
  const panelVisible = ref(false);
  const activeTab = ref('');
  const selectedLeftValue = ref('');
  const leftKeyword = ref('');
  const rightKeyword = ref('');
  const rightLoading = ref(false);
  const lazyChildrenMap = ref<Record<string, PickerNode[]>>({});

  const decodeId = (tableType: string, value: string | number) => {
    if (props.decodeTypeBizId) {
      return props.decodeTypeBizId(tableType, value);
    }
    return String(value);
  };

  const activeTypeItem = computed(() => (
    props.list.find(item => item.value === activeTab.value)
  ));

  const leftList = computed(() => activeTypeItem.value?.children || []);

  const filteredLeftList = computed(() => {
    const keyword = leftKeyword.value.trim().toLowerCase();
    if (!keyword) {
      return leftList.value;
    }
    return leftList.value.filter((item) => {
      const label = String(item.label || '').toLowerCase();
      const value = decodeId(activeTab.value, item.value).toLowerCase();
      return label.includes(keyword) || value.includes(keyword);
    });
  });

  const selectedLeftNode = computed(() => (
    leftList.value.find(item => item.value === selectedLeftValue.value)
  ));

  const isLeafNode = (item?: PickerNode | null) => {
    if (!item) return false;
    if (item.leaf) return true;
    return !(item.children && item.children.length > 0)
      && !needsLazyLoad(item);
  };

  const needsLazyLoad = (item?: PickerNode | null) => {
    if (!item || !activeTab.value) return false;
    if (activeTab.value !== props.mineBizRtType) return false;
    if (item.leaf) return false;
    if (item.children && item.children.length > 0) return false;
    return true;
  };

  const getChildCount = (item: PickerNode) => {
    if (item.children?.length) {
      return item.children.length;
    }
    const cached = lazyChildrenMap.value[`${activeTab.value}_${item.value}`];
    return cached?.length || 0;
  };

  const rightList = computed(() => {
    const left = selectedLeftNode.value;
    if (!left || isLeafNode(left)) {
      return [];
    }
    if (left.children?.length) {
      return left.children;
    }
    return lazyChildrenMap.value[`${activeTab.value}_${left.value}`] || [];
  });

  const showRightPane = computed(() => {
    const left = selectedLeftNode.value;
    if (!left) return false;
    return !isLeafNode(left) || needsLazyLoad(left) || rightList.value.length > 0;
  });

  // 两级叶子类型（联表等）无第三列，不展示右栏
  const hasThirdLevel = computed(() => (
    leftList.value.some(item => !isLeafNode(item) || needsLazyLoad(item))
  ));

  const filteredRightList = computed(() => {
    const keyword = rightKeyword.value.trim().toLowerCase();
    if (!keyword) {
      return rightList.value;
    }
    return rightList.value.filter((item) => {
      const label = String(item.label || '').toLowerCase();
      const value = decodeId(activeTab.value, item.value).toLowerCase();
      return label.includes(keyword) || value.includes(keyword);
    });
  });

  const displayLabel = computed(() => {
    const path = props.modelValue || [];
    if (path.length < 2) return '';
    const typeItem = props.list.find(item => item.value === path[0]);
    if (!typeItem) return '';

    if (path.length === 2) {
      const leaf = typeItem.children?.find(item => item.value === path[1]);
      return leaf?.label || '';
    }

    const left = typeItem.children?.find(item => item.value === path[1]);
    if (!left) return '';
    const right = left.children?.find(item => item.value === path[2])
      || lazyChildrenMap.value[`${path[0]}_${path[1]}`]?.find(item => item.value === path[2]);
    return right?.label || left.label || '';
  });

  const formatLeftLabel = (item: PickerNode) => {
    const realId = decodeId(activeTab.value, item.value);
    // 业务名后展示 ID，贴近图二「SaaS测试 ( 1000003 )」
    if (activeTab.value !== 'LinkTable' && activeTab.value !== 'EventLog' && realId && realId !== item.label) {
      const maybeBizId = realId.includes('_') ? realId.split('_')[0] : realId;
      if (/^\d+$/.test(maybeBizId) && !String(item.label).includes(maybeBizId)) {
        return `${item.label} ( ${maybeBizId} )`;
      }
    }
    return item.label;
  };

  const getItemTooltip = (item: PickerNode, isLeft: boolean) => {
    const disabled = Boolean(item.disabled);
    const isLeaf = isLeft ? isLeafNode(item) : true;
    return {
      disabled: !disabled || !isLeaf,
      content: activeTab.value === 'Asset'
        || (props.list.find(tab => tab.value === activeTab.value)?.label === t('资产数据'))
        ? t('该系统暂未上报资源数据')
        : t('审计无权限，请前往BKBase申请授权'),
      delay: 400,
    };
  };

  const isRightSelected = (item: PickerNode) => {
    const path = props.modelValue || [];
    return path.length >= 3
      && path[1] === selectedLeftValue.value
      && path[2] === item.value;
  };

  const emitPath = (path: string[]) => {
    panelVisible.value = false;
    emit('update:modelValue', path);
    emit('change', path);
  };

  const ensureLazyChildren = async (leftItem: PickerNode) => {
    if (!needsLazyLoad(leftItem) || !props.loadChildren) {
      return;
    }
    const cacheKey = `${activeTab.value}_${leftItem.value}`;
    if (Object.prototype.hasOwnProperty.call(lazyChildrenMap.value, cacheKey)) {
      return;
    }
    rightLoading.value = true;
    try {
      const bizId = decodeId(activeTab.value, leftItem.value);
      const children = await props.loadChildren(activeTab.value, bizId);
      lazyChildrenMap.value = {
        ...lazyChildrenMap.value,
        [cacheKey]: children.map(child => ({
          ...child,
          leaf: true,
        })),
      };
    } finally {
      rightLoading.value = false;
    }
  };

  const handleTabChange = (tabValue: string) => {
    if (activeTab.value === tabValue) return;
    activeTab.value = tabValue;
    selectedLeftValue.value = '';
    leftKeyword.value = '';
    rightKeyword.value = '';
    const first = leftList.value[0];
    if (first && !isLeafNode(first)) {
      selectedLeftValue.value = first.value;
      ensureLazyChildren(first);
    }
  };

  const handleSelectLeft = async (item: PickerNode) => {
    if (item.disabled && isLeafNode(item)) {
      return;
    }
    selectedLeftValue.value = item.value;
    rightKeyword.value = '';
    if (isLeafNode(item)) {
      emitPath([activeTab.value, item.value]);
      return;
    }
    await ensureLazyChildren(item);
  };

  const handleSelectRight = (item: PickerNode) => {
    if (item.disabled) return;
    if (!selectedLeftValue.value || !activeTab.value) return;
    emitPath([activeTab.value, selectedLeftValue.value, item.value]);
  };

  const togglePanel = () => {
    panelVisible.value = !panelVisible.value;
  };

  const syncFromModelValue = async () => {
    const path = props.modelValue || [];
    if (!path.length) {
      if (!activeTab.value && props.list.length) {
        activeTab.value = props.list[0].value;
      }
      return;
    }
    const [tabValue, leftValue] = path;
    activeTab.value = tabValue;
    if (path.length >= 2) {
      selectedLeftValue.value = leftValue;
      const left = leftList.value.find(item => item.value === leftValue);
      if (left && !isLeafNode(left)) {
        await ensureLazyChildren(left);
      }
    }
  };

  const handleDocumentClick = (event: MouseEvent) => {
    if (!panelVisible.value) return;
    const target = event.target as Node;
    if (rootRef.value?.contains(target)) return;
    panelVisible.value = false;
  };

  watch(() => props.list, (list) => {
    if (!list.length) return;
    if (!activeTab.value || !list.some(item => item.value === activeTab.value)) {
      activeTab.value = list[0].value;
    }
    // 面板打开时用户正在浏览，list 懒加载变更不要强制回写选中态
    if (!panelVisible.value) {
      syncFromModelValue();
    }
  }, { immediate: true, deep: true });

  watch(() => props.modelValue, () => {
    if (!panelVisible.value) {
      syncFromModelValue();
    }
  }, { deep: true });

  watch(panelVisible, async (visible) => {
    if (!visible) return;
    await nextTick();
    await syncFromModelValue();
  });

  onMounted(() => {
    document.addEventListener('mousedown', handleDocumentClick, true);
  });

  onBeforeUnmount(() => {
    document.removeEventListener('mousedown', handleDocumentClick, true);
  });
</script>

<style lang="postcss" scoped>
.data-source-picker {
  position: relative;
  width: 100%;
  max-width: 640px;
}

.dsp-trigger {
  display: flex;
  width: 100%;
  height: 32px;
  padding: 0 10px;
  font-size: 12px;
  color: #63656e;
  cursor: pointer;
  background: #fff;
  border: 1px solid #c4c6cc;
  border-radius: 2px;
  box-sizing: border-box;
  align-items: center;
  justify-content: space-between;

  &.is-empty {
    color: #c4c6cc;
  }

  &.is-active,
  &:hover {
    border-color: #3a84ff;
  }
}

.dsp-trigger-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.dsp-trigger-arrow {
  margin-left: 8px;
  color: #979ba5;
  transition: transform .15s;
  flex-shrink: 0;

  &.is-open {
    transform: rotate(180deg);
  }
}

.dsp-panel {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 100;
  width: 640px;
  overflow: hidden;
  background: #fff;
  border: 1px solid #dcdee5;
  border-radius: 2px;
  box-shadow: 0 2px 10px rgb(0 0 0 / 10%);
}

.dsp-tabs {
  display: flex;
  gap: 4px;
  padding: 4px;
  overflow-x: auto;
  background: #f0f1f5;
}

.dsp-tab-item {
  display: inline-flex;
  height: 28px;
  padding: 0 12px;
  font-size: 12px;
  color: #63656e;
  white-space: nowrap;
  cursor: pointer;
  background: transparent;
  border-radius: 2px;
  transition: all .15s;
  align-items: center;
  justify-content: center;
  flex: 1 0 auto;

  &.is-active {
    color: #3a84ff;
    background: #fff;
  }
}

.dsp-body {
  display: grid;
  height: 280px;
  grid-template-columns: 1fr 1fr;

  &.is-single-column {
    grid-template-columns: 1fr;
  }
}

.dsp-column {
  display: flex;
  min-width: 0;
  flex-direction: column;
  border-right: 1px solid #dcdee5;

  &:last-child {
    border-right: none;
  }
}

.dsp-right-loading {
  flex: 1;
  min-height: 0;

  :deep(.bk-loading-wrapper),
  :deep(.bk-nested-loading) {
    display: flex;
    height: 100%;
    flex-direction: column;
  }

  :deep(.bk-loading-indicator) {
    z-index: 2;
  }
}

.dsp-search {
  display: flex;
  height: 40px;
  padding: 0 12px;
  border-bottom: 1px solid #dcdee5;
  align-items: center;
  flex-shrink: 0;
}

.dsp-search-icon {
  margin-right: 6px;
  font-size: 14px;
  color: #979ba5;
  flex-shrink: 0;
}

.dsp-search-input {
  width: 100%;
  height: 28px;
  font-size: 12px;
  color: #63656e;
  background: transparent;
  border: none;
  outline: none;

  &::placeholder {
    color: #c4c6cc;
  }
}

.dsp-list {
  flex: 1;
  overflow: auto;
}

.dsp-list-item {
  display: flex;
  min-height: 36px;
  padding: 8px 16px;
  font-size: 12px;
  color: #63656e;
  cursor: pointer;
  align-items: center;
  justify-content: space-between;
  box-sizing: border-box;

  &:hover {
    background: #f5f7fa;
  }

  &.is-active {
    color: #3a84ff;
    background: #e1ecff;
  }

  &.is-disabled {
    color: #c4c6cc;
    cursor: not-allowed;
  }
}

.dsp-list-item-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.dsp-list-item-meta {
  display: inline-flex;
  margin-left: 8px;
  color: #979ba5;
  align-items: center;
  flex-shrink: 0;
}

.dsp-list-item-count {
  height: 16px;
  padding: 0 6px;
  margin-right: 4px;
  font-size: 12px;
  line-height: 16px;
  border-radius: 8px !important;
  flex-shrink: 0;
}

.dsp-list-item-arrow {
  transform: rotate(-90deg);
}

.dsp-list-empty {
  padding: 24px 16px;
  font-size: 12px;
  color: #979ba5;
  text-align: center;
}
</style>
