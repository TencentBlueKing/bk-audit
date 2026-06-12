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
  <div class="pagination-field-tree">
    <div
      v-for="node in filteredNodes"
      :key="node.path"
      class="tree-node">
      <div
        v-bk-tooltips="{
          content: getDisabledReason(node),
          disabled: isNodeSelectable(node) || !getDisabledReason(node),
          placement: 'top',
          theme: 'dark',
        }"
        class="node-item"
        :class="[{
          'is-selectable': isNodeSelectable(node),
          'is-disabled': !isNodeSelectable(node),
        }]"
        :style="{ paddingLeft: `${level * 16}px` }"
        @click="handleNodeClick(node)">
        <audit-icon
          v-if="node.children && node.children.length > 0"
          class="expand-icon"
          :class="[{ 'is-expanded': expandedNodes.includes(node.path) }]"
          type="angle-fill-rignt"
          @click.stop="toggleExpand(node)" />
        <span
          v-else
          class="expand-icon-placeholder" />
        <span class="node-label">{{ node.name }}({{ node.path }})</span>
        <span class="node-type">{{ getTypeLabel(node.type) }}</span>
      </div>
      <div
        v-if="node.children && node.children.length > 0 && expandedNodes.includes(node.path)">
        <pagination-field-tree
          :filter-text="filterText"
          :level="level + 1"
          :nodes="node.children"
          :selected-fields="selectedFields"
          :type="type"
          @select="(n: any) => emit('select', n)" />
      </div>
    </div>
    <div
      v-if="filteredNodes.length === 0"
      class="empty-tip">
      {{ t('暂无可选字段') }}
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface TreeNode {
    name: string;
    path: string;
    type: string;
    selectable: boolean;
    children: TreeNode[];
  }

  interface Props {
    nodes: TreeNode[];
    type: 'array' | 'number';
    filterText?: string;
    level?: number;
    selectedFields?: string[]; // 已选字段路径列表，用于跨行重复选择校验
  }

  const props = withDefaults(defineProps<Props>(), {
    filterText: '',
    level: 0,
    selectedFields: () => [],
  });

  // eslint-disable-next-line func-call-spacing
  const emit = defineEmits<{
    (e: 'select', node: TreeNode): void;
  }>();

  const { t } = useI18n();
  const expandedNodes = ref<string[]>([]);

  const filteredNodes = computed(() => {
    if (!props.filterText) return props.nodes;
    return filterTree(props.nodes, props.filterText.toLowerCase());
  });

  const filterTree = (nodes: TreeNode[], text: string): TreeNode[] => {
    const result: TreeNode[] = [];
    nodes.forEach((node) => {
      const nameMatch = node.name.toLowerCase().includes(text);
      const pathMatch = node.path.toLowerCase().includes(text);
      const displayMatch = `${node.name}(${node.path})`.toLowerCase().includes(text);

      if (nameMatch || pathMatch || displayMatch) {
        result.push(node);
      } else if (node.children && node.children.length > 0) {
        const filteredChildren = filterTree(node.children, text);
        if (filteredChildren.length > 0) {
          result.push({
            ...node,
            children: filteredChildren,
          });
          // 搜索时自动展开
          if (!expandedNodes.value.includes(node.path)) {
            expandedNodes.value.push(node.path);
          }
        }
      }
    });
    return result;
  };

  const toggleExpand = (node: TreeNode) => {
    const index = expandedNodes.value.indexOf(node.path);
    if (index > -1) {
      expandedNodes.value.splice(index, 1);
    } else {
      expandedNodes.value.push(node.path);
    }
  };

  // 检查节点是否可选择
  const isNodeSelectable = (node: TreeNode): boolean => {
    if (!node.selectable) return false;

    // 检查是否已被其他行选择
    if (props.selectedFields.includes(node.path)) {
      return false;
    }

    return true;
  };

  const handleNodeClick = (node: TreeNode) => {
    const hasChildren = !!(node.children && node.children.length > 0);

    // 父节点：整行点击切换展开/收起
    if (hasChildren) {
      toggleExpand(node);
      // 父节点本身可选时，仍触发选择
      if (isNodeSelectable(node)) {
        emit('select', node);
      }
      return;
    }

    // 叶子节点：可选则触发选择
    if (isNodeSelectable(node)) {
      emit('select', node);
    }
  };

  const getTypeLabel = (type: string) => {
    const map: Record<string, string> = {
      array: 'array',
      number: 'number',
      object: 'object',
      string: 'string',
    };
    return map[type] || type;
  };

  // 获取节点禁用原因
  const getDisabledReason = (node: TreeNode): string => {
    // 跨行重复选择优先级最高
    if (node.selectable && props.selectedFields.includes(node.path)) {
      return t('该字段已配置过分页');
    }
    if (!node.selectable) {
      return props.type === 'array' ? t('仅支持选择数组字段') : t('仅支持选择数值字段');
    }
    return '';
  };
</script>

<style lang="postcss" scoped>
.pagination-field-tree {
  font-size: 12px;
}

.tree-node {
  .node-item {
    display: flex;
    align-items: center;
    height: 32px;
    padding-right: 8px;
    cursor: pointer;
    border-radius: 2px;

    &:hover {
      background: #f0f1f5;
    }

    &.is-selectable {
      cursor: pointer;

      &:hover {
        background: #e1ecff;
      }
    }

    &.is-disabled {
      .node-label {
        color: #c4c6cc;
      }

      .node-type {
        color: #c4c6cc;
      }

      &:hover {
        background: transparent;
      }
    }

    .expand-icon {
      display: inline-block;
      width: 16px;
      margin-right: 4px;
      font-size: 12px;
      color: #979ba5;
      text-align: center;
      transition: transform .2s;

      &.is-expanded {
        transform: rotate(90deg);
      }
    }

    .expand-icon-placeholder {
      display: inline-block;
      width: 16px;
      margin-right: 4px;
    }

    .node-label {
      flex: 1;
      margin-left: 4px;
      overflow: hidden;
      color: #63656e;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .node-type {
      padding: 0 4px;
      margin-left: 8px;
      font-size: 10px;
      color: #979ba5;
      background: #f0f1f5;
      border-radius: 2px;
    }
  }
}

.empty-tip {
  padding: 16px;
  font-size: 12px;
  color: #979ba5;
  text-align: center;
}
</style>
