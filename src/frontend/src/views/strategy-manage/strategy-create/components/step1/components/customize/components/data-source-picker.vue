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
      <span
        class="dsp-trigger-text"
        :title="displayLabel || undefined">
        {{ displayLabel || t('点击选择数据表') }}
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
              :placeholder="leftSearchPlaceholder"
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
              :placeholder="rightSearchPlaceholder"
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
                <template v-if="isEventLogTab">
                  <div
                    class="dsp-list-item"
                    :class="{ 'is-active': isAllSystemsSelected }"
                    @click="handleToggleAllSystems">
                    <span class="dsp-list-item-label">{{ t('全部系统') }}</span>
                    <audit-icon
                      v-if="isAllSystemsSelected"
                      class="dsp-list-item-check"
                      type="check-line" />
                  </div>
                  <div
                    v-for="item in filteredRightList"
                    :key="item.value"
                    class="dsp-list-item"
                    :class="{ 'is-active': isEventLogSystemSelected(item) }"
                    @click="handleToggleEventLogSystem(item)">
                    <span class="dsp-list-item-label">{{ formatEventLogSystemLabel(item) }}</span>
                    <audit-icon
                      v-if="isEventLogSystemSelected(item)"
                      class="dsp-list-item-check"
                      type="check-line" />
                  </div>
                </template>
                <template v-else>
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
                </template>
                <div
                  v-if="filteredRightList.length === 0 && !rightLoading"
                  class="dsp-list-empty">
                  {{ t('暂无数据') }}
                </div>
              </template>
              <div
                v-else
                class="dsp-list-empty">
                {{ rightEmptyHint }}
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
    /** 操作日志已选系统（多选） */
    systemIds?: string[];
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
    (e: 'update:systemIds', value: string[]): void;
    (e: 'changeSystemIds', value: string[]): void;
    (e: 'eventLogCommit', payload: { path: string[]; systemIds: string[] }): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    systemIds: () => [],
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
  const selectedSystemIds = ref<string[]>([]);

  const decodeId = (tableType: string, value: string | number) => {
    if (props.decodeTypeBizId) {
      return props.decodeTypeBizId(tableType, value);
    }
    return String(value);
  };

  const activeTypeItem = computed(() => (
    props.list.find(item => item.value === activeTab.value)
  ));

  const leftSearchPlaceholder = computed(() => {
    if (activeTab.value === 'EventLog') {
      return t('搜索插件名称');
    }
    if (activeTab.value === 'LinkTable') {
      return t('搜索 联表数据名称');
    }
    // 资产数据后端枚举值为 BuildIn
    if (activeTab.value === 'BuildIn') {
      return t('搜索 系统名称、系统ID');
    }
    return t('搜索 业务名称、业务ID');
  });

  const rightSearchPlaceholder = computed(() => {
    if (activeTab.value === 'EventLog') {
      return t('搜索 系统名称、系统ID');
    }
    if (activeTab.value === 'BuildIn') {
      return t('搜索 资产名称');
    }
    return t('搜索 数据表名称');
  });

  const rightEmptyHint = computed(() => (
    activeTab.value === 'EventLog'
      ? t('请先选择左侧插件')
      : t('请先选择左侧业务')
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

  const isEventLogTab = computed(() => activeTab.value === 'EventLog');

  const isLeafNode = (item?: PickerNode | null) => {
    if (!item) return false;
    // 操作日志插件需点选后再拉系统，不当叶子
    if (isEventLogTab.value) return false;
    if (item.leaf) return true;
    return !(item.children && item.children.length > 0)
      && !needsLazyLoad(item);
  };

  const needsLazyLoad = (item?: PickerNode | null) => {
    if (!item || !activeTab.value) return false;
    // 操作日志 / 我的授权结果表：点左侧后再懒加载右侧
    if (isEventLogTab.value) {
      if (item.children && item.children.length > 0) return false;
      return true;
    }
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

  // 操作日志、我的授权结果表等：始终展示右栏；联表等纯叶子类型仅单列
  const hasThirdLevel = computed(() => {
    if (isEventLogTab.value || activeTab.value === props.mineBizRtType) {
      return true;
    }
    return leftList.value.some(item => !isLeafNode(item) || needsLazyLoad(item));
  });

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

  const formatNodeNameId = (label: string, id: string) => {
    const name = label || '';
    const realId = id || '';
    if (!realId) return name;
    if (!name) return realId;
    if (name.includes(`(${realId})`)) return name;
    return `${name}(${realId})`;
  };

  const joinDisplayPath = (parts: Array<string | undefined>) => parts
    .map(part => (part || '').trim())
    .filter(Boolean)
    .join(' / ');

  const displayLabel = computed(() => {
    const path = props.modelValue || [];
    // 面板打开时操作日志用本地草稿回显，关闭提交后再用 modelValue
    const useEventLogDraft = panelVisible.value
      && isEventLogTab.value
      && selectedLeftValue.value;
    const eventLogPath = useEventLogDraft
      ? ['EventLog', selectedLeftValue.value]
      : path;
    const eventLogSystemIds = useEventLogDraft
      ? selectedSystemIds.value
      : ((props.systemIds?.length ? props.systemIds : selectedSystemIds.value) || []);

    if (eventLogPath[0] === 'EventLog' && eventLogPath.length >= 2) {
      const typeItem = props.list.find(item => item.value === 'EventLog');
      if (!typeItem) return '';
      const plugin = typeItem.children?.find(item => item.value === eventLogPath[1]);
      const pluginLabel = plugin?.label || String(eventLogPath[1] || '');
      if (!eventLogSystemIds.length) {
        return joinDisplayPath([typeItem.label, pluginLabel]);
      }
      const systems = lazyChildrenMap.value[`EventLog_${eventLogPath[1]}`] || [];
      const allSelected = systems.length > 0
        && systems.every(item => eventLogSystemIds.includes(item.value));
      if (allSelected) {
        return joinDisplayPath([typeItem.label, pluginLabel, t('全部系统')]);
      }
      const systemLabels = eventLogSystemIds.map((id) => {
        const sys = systems.find(item => item.value === id);
        return formatNodeNameId(sys?.label || id, id);
      }).join('、');
      return joinDisplayPath([typeItem.label, pluginLabel, systemLabels]);
    }

    if (path.length < 2) return '';
    const typeItem = props.list.find(item => item.value === path[0]);
    if (!typeItem) return '';
    const tabLabel = typeItem.label;

    // 两级：联表等 → 联表数据 / 名称
    if (path.length === 2) {
      const leaf = typeItem.children?.find(item => item.value === path[1]);
      return joinDisplayPath([tabLabel, leaf?.label || String(path[1] || '')]);
    }

    // 三级：资产数据 / 系统(id) / 资产；其他数据 / 业务(id) / 表 …
    const left = typeItem.children?.find(item => item.value === path[1]);
    if (!left) {
      return joinDisplayPath([tabLabel, String(path[1] || '')]);
    }
    const leftId = decodeId(path[0], left.value);
    const leftLabel = formatNodeNameId(left.label, leftId);
    const right = left.children?.find(item => item.value === path[2])
      || lazyChildrenMap.value[`${path[0]}_${path[1]}`]?.find(item => item.value === path[2]);
    const rightLabel = right?.label || String(path[2] || '');
    return joinDisplayPath([tabLabel, leftLabel, rightLabel]);
  });

  const formatLeftLabel = (item: PickerNode) => {
    const realId = decodeId(activeTab.value, item.value);
    // 业务名后展示 ID，贴近图二「SaaS测试 ( 1000003 )」
    if (activeTab.value !== 'LinkTable' && activeTab.value !== 'EventLog' && realId && realId !== item.label) {
      const maybeBizId = realId.includes('_') ? realId.split('_')[0] : realId;
      if (/^\d+$/.test(maybeBizId) && !String(item.label).includes(maybeBizId)) {
        return `${item.label} ( ${maybeBizId} )`;
      }
      // 资产数据等：系统名称(系统ID)
      if (activeTab.value === 'BuildIn') {
        return formatNodeNameId(item.label, realId);
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
        || activeTab.value === 'BuildIn'
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

  const formatEventLogSystemLabel = (item: PickerNode) => (
    formatNodeNameId(item.label || '', item.value || '')
  );

  const isEventLogSystemSelected = (item: PickerNode) => (
    selectedSystemIds.value.includes(item.value)
  );

  const isAllSystemsSelected = computed(() => {
    if (!rightList.value.length) return false;
    return rightList.value.every(item => selectedSystemIds.value.includes(item.value));
  });

  const setLocalSystemIds = (ids: string[]) => {
    selectedSystemIds.value = [...ids];
  };

  const emitPath = (path: string[], options?: { keepOpen?: boolean }) => {
    if (!options?.keepOpen) {
      panelVisible.value = false;
    }
    emit('update:modelValue', path);
    emit('change', path);
  };

  /** 关闭面板时提交操作日志：插件 + 系统多选一次性生效 */
  const commitEventLogSelection = () => {
    if (activeTab.value !== 'EventLog') {
      return false;
    }
    if (!selectedLeftValue.value || selectedSystemIds.value.length === 0) {
      return false;
    }
    emit('eventLogCommit', {
      path: ['EventLog', selectedLeftValue.value],
      systemIds: [...selectedSystemIds.value],
    });
    return true;
  };

  const closePanel = () => {
    if (!panelVisible.value) return;
    panelVisible.value = false;
    const committed = commitEventLogSelection();
    if (!committed && isEventLogTab.value) {
      // 未选完系统则回滚本地草稿
      selectedSystemIds.value = [...(props.systemIds || [])];
      syncFromModelValue();
    }
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
    if (tabValue === 'EventLog') {
      selectedSystemIds.value = [...(props.systemIds || [])];
    } else {
      selectedSystemIds.value = [];
    }
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
    const pluginChanged = selectedLeftValue.value !== item.value;
    selectedLeftValue.value = item.value;
    rightKeyword.value = '';
    if (isLeafNode(item)) {
      emitPath([activeTab.value, item.value]);
      return;
    }
    await ensureLazyChildren(item);
    // 操作日志：仅本地选中插件并加载系统，关闭面板时再统一提交
    if (isEventLogTab.value && pluginChanged) {
      setLocalSystemIds([]);
    }
  };

  const handleSelectRight = (item: PickerNode) => {
    if (item.disabled) return;
    if (!selectedLeftValue.value || !activeTab.value) return;
    emitPath([activeTab.value, selectedLeftValue.value, item.value]);
  };

  const handleToggleEventLogSystem = (item: PickerNode) => {
    if (!selectedLeftValue.value) return;
    const next = selectedSystemIds.value.includes(item.value)
      ? selectedSystemIds.value.filter(id => id !== item.value)
      : [...selectedSystemIds.value, item.value];
    setLocalSystemIds(next);
  };

  const handleToggleAllSystems = () => {
    if (!selectedLeftValue.value || !rightList.value.length) return;
    if (isAllSystemsSelected.value) {
      setLocalSystemIds([]);
      return;
    }
    setLocalSystemIds(rightList.value.map(item => item.value));
  };

  const togglePanel = () => {
    if (panelVisible.value) {
      closePanel();
      return;
    }
    panelVisible.value = true;
  };

  const syncFromModelValue = async () => {
    const path = props.modelValue || [];
    selectedSystemIds.value = [...(props.systemIds || [])];
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
    // InfoBox 确认框点击不关闭提交（节点可能在 body 下）
    const targetEl = target as HTMLElement;
    if (targetEl?.closest?.('.bk-modal, .bk-dialog, .bk-info-wrapper, .bk-message')) {
      return;
    }
    closePanel();
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

  watch(() => props.systemIds, (ids) => {
    selectedSystemIds.value = [...(ids || [])];
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
  min-height: 0;
  grid-template-columns: 1fr 1fr;

  &.is-single-column {
    grid-template-columns: 1fr;
  }
}

.dsp-column {
  display: flex;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  flex-direction: column;
  border-right: 1px solid #dcdee5;

  &:last-child {
    border-right: none;
  }
}

.dsp-right-loading {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  flex-direction: column;

  :deep(.bk-loading-wrapper),
  :deep(.bk-nested-loading),
  :deep(.bk-loading) {
    display: flex;
    flex: 1;
    min-height: 0;
    overflow: hidden;
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
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #c4c6cc transparent;

  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-thumb {
    background: #c4c6cc;
    border-radius: 2px;
  }

  &::-webkit-scrollbar-thumb:hover {
    background: #979ba5;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-button {
    display: none;
    width: 0;
    height: 0;
  }
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

.dsp-list-item-check {
  margin-left: 8px;
  font-size: 16px;
  color: #3a84ff;
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
