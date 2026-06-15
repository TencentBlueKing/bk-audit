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
  <bk-select
    ref="tableSelectRef"
    v-model="selectedTableNodes"
    :auto-height="false"
    collapse-tags
    custom-content
    display-key="label"
    id-key="value"
    :min-height="400"
    multiple
    multiple-mode="tag"
    :placeholder="t('请选择')"
    :popover-options="{
      extCls: 'scene-table-select-popover',
      width: 660,
    }"
    :scroll-height="600"
    @clear="handleClearTable"
    @tag-remove="handleRemoveTableTag"
    @toggle="(val: boolean) => { if (val) tableSearchKey = '' }">
    <div
      class="table-select-panel"
      @click.stop>
      <div class="table-select-tabs">
        <div
          v-for="item in allConfigTypeTable"
          :key="item.value"
          class="table-select-tab"
          :class="{ 'is-active': activeTableType === item.value }"
          @click.stop="handleTableTypeChange(item.value)">
          {{ item.label }}
        </div>
      </div>
      <div class="table-select-search">
        <audit-icon
          class="search-icon"
          type="search1" />
        <bk-input
          v-model.trim="tableSearchKey"
          behavior="simplicity"
          :placeholder="t('请输入关键字搜索')"
          size="small" />
      </div>
      <div
        class="table-select-all-data"
        :class="{ 'is-active': isSelectAllTableData }"
        @click.stop="handleToggleAllTableData">
        <span class="all-data-icon">ALL</span>
        <span>{{ t('全部数据') }}</span>
      </div>
      <div
        class="table-tree-wrapper"
        :class="{ 'is-disabled': isSelectAllTableData }">
        <bk-tree
          v-if="currentTableTreeData.length"
          :key="activeTableType"
          ref="tableTreeRef"
          children="children"
          :data="currentTableTreeData"
          :empty-text="t('数据搜索为空')"
          :expand-all="!!tableSearchKey"
          label="label"
          :node-content-action="['click']"
          node-key="value"
          :search="tableSearchKey"
          show-checkbox
          :show-node-type-icon="false"
          @node-checked="handleTableTreeChecked">
          <template #default="{ data: nodeData }: { data: ConfigTypeTableNode }">
            <span class="table-tree-node">
              {{ nodeData.label }}
            </span>
          </template>
        </bk-tree>
        <bk-exception
          v-else
          scene="part"
          type="empty" />
      </div>
    </div>
  </bk-select>
</template>

<script setup lang="ts">
  import {
    computed,
    nextTick,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';
  import CommonDataModel from '@model/strategy/common-data';

  import useRequest from '@/hooks/use-request';

  interface ConfigTypeTableNode {
    label: string;
    value: string;
    leaf?: boolean;
    disabled?: boolean;
    children?: ConfigTypeTableNode[];
  }

  interface ConfigTypeTableItem {
    label: string;
    value: string;
    children: ConfigTypeTableNode[];
  }

  interface SelectedTableNode {
    label: string;
    value: string;
  }

  interface Props {
    /** 选中的数据表 ID 列表 */
    modelValue: string[];
    /** 是否编辑模式 */
    isEditMode?: boolean;
    /** 编辑模式下场景 ID */
    sceneId?: string | number;
  }

  interface Emits {
    (e: 'update:modelValue', value: string[]): void;
    (e: 'change', value: string[]): void;
    (e: 'loaded'): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    isEditMode: false,
    sceneId: undefined,
  });
  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  // refs
  const tableSelectRef = ref();
  const tableTreeRef = ref();

  // 数据源状态
  const typeTableLoading = ref(false);
  const allConfigTypeTable = ref<Array<ConfigTypeTableItem>>([]);
  const selectedTableNodes = ref<SelectedTableNode[]>([]);
  const activeTableType = ref('');
  const tableSearchKey = ref('');
  const isSyncingTableTree = ref(false);

  // 全部数据选择模式：按类型独立，key 为类型 value
  const tableSelectModeMap = ref<Record<string, 'all' | 'system'>>({});
  // 系统级选择时，选中的系统 value 列表（按类型）
  const selectedTableSystemsMap = ref<Record<string, string[]>>({});

  // ========== 计算属性 ==========

  const currentTableType = computed(() => allConfigTypeTable.value.find(item => item.value === activeTableType.value)
    || allConfigTypeTable.value[0]);

  const isTableLeafNode = (node: ConfigTypeTableNode) => !node.children || node.children.length === 0;

  const isSelectableTableNode = (node: ConfigTypeTableNode) => isTableLeafNode(node) && !node.disabled;

  const isSelectAllTableData = computed(() => tableSelectModeMap.value[activeTableType.value] === 'all');

  const currentTableTreeData = computed(() => {
    const children = currentTableType.value?.children || [];
    // 过滤掉所有禁用叶子节点
    const filterDisabled = (nodes: ConfigTypeTableNode[]): ConfigTypeTableNode[] => nodes
      .filter(node => !node.disabled || !isTableLeafNode(node))
      .map(node => ({
        ...node,
        children: node.children ? filterDisabled(node.children) : undefined,
      }));
    return filterDisabled(children);
  });

  // ========== 工具方法 ==========

  const getTableLeafNodes = (nodes: ConfigTypeTableNode[]) => nodes.reduce<ConfigTypeTableNode[]>((result, node) => {
    if (isTableLeafNode(node)) {
      result.push(node);
      return result;
    }
    result.push(...getTableLeafNodes(node.children || []));
    return result;
  }, []);

  /** 发送值变更事件 */
  const emitValueChange = (value: string[]) => {
    emits('update:modelValue', value);
    emits('change', value);
  };

  // ========== 同步方法 ==========

  const syncSelectedTableNodes = () => {
    const result: SelectedTableNode[] = [];
    const selectedIdSet = new Set(props.modelValue);

    // 遍历所有类型
    for (const typeItem of allConfigTypeTable.value) {
      const typeValue = typeItem.value;
      const isTypeAll = tableSelectModeMap.value[typeValue] === 'all';

      if (isTypeAll) {
        // 当前类型为全选模式
        result.push({
          value: `__all__${typeValue}`,
          label: `${typeItem.label}：全部`,
        });
      } else {
        const systems = typeItem.children || [];
        for (const sysNode of systems) {
          const sysLeaves = getTableLeafNodes(sysNode.children || []);
          const selectableLeaves = sysLeaves.filter(leaf => !leaf.disabled);
          const selectedInSys = selectableLeaves.filter(leaf => selectedIdSet.has(leaf.value));

          if (selectableLeaves.length > 0 && selectedInSys.length === selectableLeaves.length) {
            result.push({
              value: `__system__${sysNode.value}`,
              label: `${typeItem.label}：${sysNode.label}`,
            });
          } else if (selectedInSys.length > 0) {
            for (const leaf of selectedInSys) {
              result.push({
                value: leaf.value,
                label: `${typeItem.label}/${sysNode.label}/${leaf.label}`,
              });
            }
          }
        }
      }
    }

    selectedTableNodes.value = result;
    nextTick(() => {
      if (tableSelectRef.value) {
        tableSelectRef.value.selected = selectedTableNodes.value.map(item => ({
          value: item.value,
          label: item.label,
        }));
      }
    });
  };

  const syncCurrentTreeChecked = () => {
    nextTick(() => {
      if (!tableTreeRef.value) return;
      const selectedIdSet = new Set(props.modelValue);
      const treeData = currentTableTreeData.value;
      const allLeaves = getTableLeafNodes(treeData);
      const treeSystems = treeData;
      isSyncingTableTree.value = true;

      // 先取消全部
      allLeaves.forEach((node) => {
        tableTreeRef.value.setChecked(node, false);
      });
      treeSystems.forEach((sysNode) => {
        tableTreeRef.value.setChecked(sysNode, false);
      });

      nextTick(() => {
        if (isSelectAllTableData.value) {
          allLeaves.forEach((node) => {
            tableTreeRef.value.setChecked(node, true);
          });
          treeSystems.forEach((sysNode) => {
            tableTreeRef.value.setChecked(sysNode, true);
          });
        } else {
          allLeaves.forEach((node) => {
            if (selectedIdSet.has(node.value)) {
              tableTreeRef.value.setChecked(node, true);
            }
          });
          for (const sysNode of treeSystems) {
            const sysLeaves = getTableLeafNodes(sysNode.children || []);
            const selectableLeaves = sysLeaves.filter(leaf => !leaf.disabled);
            if (selectableLeaves.length > 0 && selectableLeaves.every(leaf => selectedIdSet.has(leaf.value))) {
              tableTreeRef.value.setChecked(sysNode, true);
            }
          }
        }
        nextTick(() => {
          isSyncingTableTree.value = false;
        });
      });
    });
  };

  // ========== 事件处理 ==========

  const handleToggleAllTableData = () => {
    const typeValue = activeTableType.value;
    if (isSelectAllTableData.value) {
      // 取消当前类型的全选：移除当前类型的所有叶子节点
      delete tableSelectModeMap.value[typeValue];
      delete selectedTableSystemsMap.value[typeValue];
      const currentLeaves = getTableLeafNodes(currentTableType.value?.children || [])
        .filter(leaf => !leaf.disabled);
      const currentLeafIds = new Set(currentLeaves.map(leaf => leaf.value));
      const newIds = props.modelValue.filter(id => !currentLeafIds.has(id));
      emitValueChange(newIds);
    } else {
      // 选中当前类型全部数据
      tableSelectModeMap.value[typeValue] = 'all';
      selectedTableSystemsMap.value[typeValue] = [];
      const currentLeaves = getTableLeafNodes(currentTableType.value?.children || [])
        .filter(leaf => !leaf.disabled);
      const currentLeafIds = new Set(currentLeaves.map(leaf => leaf.value));
      // 并集：保留其他类型 + 当前类型全部
      const otherIds = props.modelValue.filter(id => !currentLeafIds.has(id));
      const newIds = [...otherIds, ...currentLeaves.map(leaf => leaf.value)]
        .filter((id, index, list) => list.indexOf(id) === index);
      emitValueChange(newIds);
    }
    syncSelectedTableNodes();
    syncCurrentTreeChecked();
  };

  const handleTableTypeChange = (value: string) => {
    activeTableType.value = value;
    tableSearchKey.value = '';
    syncCurrentTreeChecked();
  };

  const handleTableTreeChecked = (nodes: ConfigTypeTableNode[]) => {
    if (isSyncingTableTree.value) return;
    if (isSelectAllTableData.value) return;

    const typeValue = activeTableType.value;
    const allCurrentPageLeaves = getTableLeafNodes(currentTableType.value?.children || [])
      .filter(leaf => !leaf.disabled);
    const currentPageLeafIds = new Set(allCurrentPageLeaves.map(leaf => leaf.value));

    const checkedLeaves = nodes.filter(isSelectableTableNode);
    const checkedIds = new Set(checkedLeaves.map(leaf => leaf.value));

    const systems = currentTableType.value?.children || [];
    const fullSelectedSystems: string[] = [];
    const currentPageSelectedLeaves: string[] = [];

    for (const sysNode of systems) {
      const sysLeaves = getTableLeafNodes(sysNode.children || []);
      const selectableLeaves = sysLeaves.filter(leaf => !leaf.disabled);
      const selectedInSys = selectableLeaves.filter(leaf => checkedIds.has(leaf.value));

      if (selectableLeaves.length > 0 && selectedInSys.length === selectableLeaves.length && selectedInSys.length > 0) {
        fullSelectedSystems.push(sysNode.value);
        currentPageSelectedLeaves.push(...selectableLeaves.map(leaf => leaf.value));
      } else if (selectedInSys.length > 0) {
        currentPageSelectedLeaves.push(...selectedInSys.map(leaf => leaf.value));
      }
    }

    // 并集：保留其他页 + 当页新选
    let resultTableIds = props.modelValue.filter(id => !currentPageLeafIds.has(id));
    resultTableIds = [...resultTableIds, ...currentPageSelectedLeaves]
      .filter((id, index, list) => list.indexOf(id) === index);

    if (fullSelectedSystems.length > 0 && currentPageSelectedLeaves.length === fullSelectedSystems.flatMap((s) => {
      const sys = systems.find(item => item.value === s);
      return sys ? getTableLeafNodes(sys.children || []) : [];
    }).length) {
      tableSelectModeMap.value[typeValue] = 'system';
      selectedTableSystemsMap.value[typeValue] = fullSelectedSystems;
      emitValueChange(resultTableIds);
    } else if (fullSelectedSystems.length > 0) {
      tableSelectModeMap.value[typeValue] = 'system';
      selectedTableSystemsMap.value[typeValue] = fullSelectedSystems;
      emitValueChange(resultTableIds);
    } else {
      delete tableSelectModeMap.value[typeValue];
      delete selectedTableSystemsMap.value[typeValue];
      emitValueChange(resultTableIds);
    }
    syncSelectedTableNodes();
  };

  const handleRemoveTableTag = (value: string | SelectedTableNode) => {
    const id = typeof value === 'string' ? value : value.value;
    let newTableIds = [...props.modelValue];

    if (id.startsWith('__all__')) {
      // 移除某个类型的全选
      const typeValue = id.replace('__all__', '');
      delete tableSelectModeMap.value[typeValue];
      delete selectedTableSystemsMap.value[typeValue];
      // 找到该类型并移除其所有叶子节点
      const typeItem = allConfigTypeTable.value.find(item => item.value === typeValue);
      if (typeItem) {
        const leaves = getTableLeafNodes(typeItem.children || []).map(leaf => leaf.value);
        newTableIds = newTableIds.filter(tableId => !leaves.includes(tableId));
      }
    } else if (id.startsWith('__system__')) {
      const sysId = id.replace('__system__', '');
      const typeValue = activeTableType.value;
      if (selectedTableSystemsMap.value[typeValue]) {
        selectedTableSystemsMap.value[typeValue] = selectedTableSystemsMap.value[typeValue].filter(s => s !== sysId);
        if (selectedTableSystemsMap.value[typeValue].length === 0) {
          delete tableSelectModeMap.value[typeValue];
          delete selectedTableSystemsMap.value[typeValue];
        }
      }
      // 需要在所有类型中查找该系统
      for (const typeItem of allConfigTypeTable.value) {
        const sysNode = typeItem.children?.find(item => item.value === sysId);
        if (sysNode) {
          const sysLeaves = getTableLeafNodes(sysNode.children || []).map(leaf => leaf.value);
          newTableIds = newTableIds.filter(tableId => !sysLeaves.includes(tableId));
          break;
        }
      }
    } else {
      newTableIds = newTableIds.filter(item => item !== id);
      if (newTableIds.length === 0) {
        // 清空所有类型的选择模式
        tableSelectModeMap.value = {};
        selectedTableSystemsMap.value = {};
      }
    }
    emitValueChange(newTableIds);
    syncSelectedTableNodes();
  };

  const handleClearTable = () => {
    tableSelectModeMap.value = {};
    selectedTableSystemsMap.value = {};
    emitValueChange([]);
    syncSelectedTableNodes();
  };

  // ========== 检测选择模式 ==========

  const detectAndSetSelectMode = () => {
    if (!props.modelValue || props.modelValue.length === 0) {
      tableSelectModeMap.value = {};
      selectedTableSystemsMap.value = {};
      return;
    }
    const selectedIdSet = new Set(props.modelValue);
    // 检测每个类型是否全选
    const newModeMap: Record<string, 'all'> = {};
    for (const typeItem of allConfigTypeTable.value) {
      const leaves = getTableLeafNodes(typeItem.children || []).filter(leaf => !leaf.disabled);
      if (leaves.length > 0 && leaves.every(leaf => selectedIdSet.has(leaf.value))) {
        newModeMap[typeItem.value] = 'all';
      }
    }
    tableSelectModeMap.value = newModeMap;
  };

  // ========== 数据加载 ==========

  const {
    run: fetchTable,
  } = useRequest(StrategyManageService.fetchTable, {
    defaultValue: [],
  });

  const {
    run: fetchStrategyCommon,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
    onSuccess: (data) => {
      type ConfigTypeItem = { label: string; value: string };
      // eslint-disable-next-line max-len
      const targetTypes = (data.rule_audit_config_type as ConfigTypeItem[]).filter(item => item.value !== 'EventLog' && item.value !== 'LinkTable' && item.value !== 'MineBizRt');
      const requests = targetTypes.map((item: ConfigTypeItem) => {
        const req = fetchTable({ table_type: item.value, scene_id: props.isEditMode ? props.sceneId : '' });
        return req.then((tableData: any[]) => ({
          label: item.label,
          value: item.value,
          children: tableData.map((tableItem: any) => ({
            label: tableItem.label || tableItem.table_name || '',
            value: tableItem.value || tableItem.table_id || '',
            children: tableItem.children || [],
            leaf: true,
            disabled: !(tableItem.children && tableItem.children.length),
          })),
        }));
      });
      Promise.all(requests).then((results) => {
        allConfigTypeTable.value = results;
        if (!activeTableType.value && results.length) {
          activeTableType.value = results[0].value;
        }
        typeTableLoading.value = false;
        detectAndSetSelectMode();
        syncSelectedTableNodes();
        syncCurrentTreeChecked();
        emits('loaded');
      });
    },
  });

  /** 对外暴露：加载数据 */
  const loadData = () => {
    typeTableLoading.value = true;
    fetchStrategyCommon();
  };

  /** 对外暴露：重置状态 */
  const resetState = () => {
    selectedTableNodes.value = [];
    tableSearchKey.value = '';
    tableSelectModeMap.value = {};
    selectedTableSystemsMap.value = {};
    syncCurrentTreeChecked();
  };

  // ========== 监听器 ==========

  watch(() => props.modelValue, () => {
    if (!isSyncingTableTree.value) {
      detectAndSetSelectMode();
      syncSelectedTableNodes();
    }
  }, { deep: true });

  watch(currentTableTreeData, () => {
    syncCurrentTreeChecked();
  }, { deep: true });

  // ========== 暴露方法 ==========
  defineExpose({
    loadData,
    resetState,
  });
</script>

<style lang="postcss" scoped>
.table-select-panel {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-height: 480px;
  background: #fff;
  border-radius: 2px;
  box-sizing: border-box;
}

.table-select-tabs {
  display: flex;
  flex-shrink: 0;
  height: 52px;
  border-bottom: 1px solid #dcdee5;
}

.table-select-tab {
  position: relative;
  display: flex;
  flex: 1;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: #63656e;
  cursor: pointer;

  &.is-active {
    color: #3a84ff;

    &::after {
      position: absolute;
      right: 12px;
      bottom: -1px;
      left: 12px;
      height: 2px;
      background: #3a84ff;
      border-radius: 1px;
      content: '';
    }
  }
}

.table-select-search {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  height: 38px;
  padding: 0 12px;
  border-bottom: 1px solid #dcdee5;

  .search-icon {
    margin-right: 8px;
    font-size: 16px;
    color: #979ba5;
  }

  :deep(.bk-input) {
    flex: 1;
  }
}

.table-select-all-data {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  height: 44px;
  padding: 0 16px;
  font-size: 14px;
  color: #63656e;
  cursor: pointer;

  &.is-active {
    color: #3a84ff;

    .all-data-icon {
      background: #3a84ff1f;
    }
  }

  &:hover {
    color: #3a84ff;
  }
}

.all-data-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 18px;
  margin-right: 8px;
  font-size: 12px;
  font-weight: 700;
  color: #a3a7b1;
  background: #f0f1f5;
  border-radius: 2px;
}

.table-tree-wrapper {
  padding: 8px 12px 12px;
  overflow: hidden auto;
  flex: 1;

  &.is-disabled {
    /* 只禁用复选框，保留展开箭头可用 */
    :deep(.bk-checkbox) {
      pointer-events: none;
      opacity: 50%;
    }
  }
}

.table-tree-node {
  width: 100%;
  padding-left: 8px;
  margin: 0;
  overflow: hidden;
  line-height: 32px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

<style lang="postcss">
/* 全局样式：popover 宽度控制 */
.scene-table-select-popover {
  left: 0 !important;
  padding: 0 !important;

  .bk-popover-content {
    width: 708px;
    padding: 0 !important;
    box-sizing: border-box;
  }
}
</style>
