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
  <div class="add-search-tree">
    <bk-select
      ref="selectRef"
      v-model="selectedItems"
      :auto-height="false"
      collapse-tags
      custom-content
      display-key="name"
      id-key="id"
      multiple
      :popover-options="{
        'width': 'auto',
        extCls: 'add-search-tree-pop',
      }"
      @search-change="handleSearch">
      <template #trigger>
        <span
          style="color: #3884ff; cursor: pointer;">
          <audit-icon
            style="margin-right: 5px;"
            type="add" />
          <span>{{ t('添加其他条件') }}</span>
        </span>
      </template>
      <bk-tree
        ref="treeRef"
        :check-strictly="false"
        children="children"
        :data="localData"
        :empty-text="t('数据搜索为空')"
        label="raw_name"
        :node-content-action="['click']"
        show-checkbox
        :show-node-type-icon="false"
        @node-checked="handleNodeChecked">
        <template #default="{ data: nodeData }: { data: CascaderItem }">
          <template v-if="!nodeData.isEdit">
            <span> {{ nodeData.name }}</span>
            <div :class="[nodeData.disabled ? 'disabled-row' : '']">
              <span
                class="category-type"
                :style="categoryStyleMap[nodeData.category as keyof typeof categoryStyleMap]">
                {{ categoryMap[nodeData.category as keyof typeof categoryMap] }}
              </span>
              <!-- 添加子字段 -->
              <!-- <div style="width: 14px; height: 14px;"> -->
              <span style="display: inline-block; width: 14px; height: 14px;">
                <audit-icon
                  v-if="nodeData.dynamic_content"
                  style="margin-left: 5px;
                    font-size: 14px;
                    color: #3a84ff"
                  type="plus-circle"
                  @click.stop="handleAddNode(nodeData)" />
              </span>
              <!-- </div> -->
            </div>
          </template>
          <div
            v-else
            style="display: flex; align-items: center;">
            <span>{{ nodeData.name }}</span>
            <span style="margin: 0 5px;">/</span>
            <!-- 多级字段输入 -->
            <template
              v-for="(item, index) in fieldTypeValue[nodeData.id]"
              :key="index">
              <bk-input
                v-model="item.field"
                autofocus
                :placeholder="t('请输入')"
                style="width: 115px;" />
              <audit-icon
                v-if="index === fieldTypeValue[nodeData.id].length - 1"
                v-bk-tooltips="t('添加下级字段')"
                class="add-icon"
                :class="[!item.field ? 'disabled-add-icon' : '']"
                type="add-fill"
                @click="() => item.field && fieldTypeValue[nodeData.id].push({ field: '' })" />
              <span
                v-else
                style="margin: 0 5px;">/</span>
            </template>
            <div class="field-edit-right">
              <audit-icon
                v-bk-tooltips="t('确认')"
                :class="[fieldTypeValue[nodeData.id] && fieldTypeValue[nodeData.id].
                  some(field => !field.field) ? 'disabled-submit-icon' : 'submit-icon']"
                svg
                type="check-line"
                @click.stop="handleAddFieldSubmit(nodeData)" />
              <audit-icon
                v-bk-tooltips="t('取消添加')"
                style="margin-right: 4px;
                  font-size: 18px;
                  color: #c1c3c9;"
                svg
                type="close"
                @click.stop="handleAddFieldClose(nodeData)" />
            </div>
          </div>
        </template>
      </bk-tree>
    </bk-select>
  </div>
</template>

<script setup lang="ts">
  import _ from 'lodash';
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { IFieldConfig } from '../render-field-config/config';

  interface CascaderItem {
    allow_operators: string[]
    category?: string
    children: CascaderItem[]
    disabled: boolean
    dynamic_content: boolean
    id: string
    isJson: boolean
    level: number
    name: string
    isEdit: boolean
    isOpen: boolean;
  }

  interface Emits {
    (e: 'select', value: CascaderItem[]): void;
  }

  interface Props {
    data: CascaderItem[];
    modelValue?:  CascaderItem[];
    filedConfig: Record<string, IFieldConfig>
    deleteFieldName: string;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const treeRef = ref();

  const categoryMap = {
    system: t('系统'),
    standard: t('标准'),
    snapshot: t('快照'),
  };

  const categoryStyleMap = {
    system: {
      backgroundColor: '#E1ECFF',
      color: '#1768EF',
    },
    standard: {
      backgroundColor: '#DAF6E5',
      color: '#299E56',
    },
    snapshot: {
      backgroundColor: '#FCE5C0',
      color: '#E38B02',
    },
  };

  const isSearching = ref(false);

  const localData = ref<CascaderItem[]>([]);
  // 保存原始数据，用于在搜索关键词为空时恢复
  const originalData = ref<CascaderItem[]>([]);

  const selectedItems = ref<Array<CascaderItem>>([]);
  const fieldTypeValue = ref<Record<string, Record<string, any>[]>>({});

  const handleSearch = (keyword: string) => {
    isSearching.value = !!keyword;

    if (!keyword) {
      // 如果关键词为空，恢复原始数据
      localData.value = [...originalData.value];
      return;
    }

    // 递归搜索匹配项
    const filterNodes = (nodes: CascaderItem[]): CascaderItem[] => nodes.filter((node) => {
      // 检查当前节点名称是否包含关键词
      const isMatch = node.name.toLowerCase().includes(keyword.toLowerCase());

      // 如果有子节点，递归搜索
      if (node.children && node.children.length) {
        const filteredChildren = filterNodes(node.children);
        // 更新子节点为过滤后的结果
        // eslint-disable-next-line no-param-reassign
        node.children = filteredChildren;
        // 如果子节点中有匹配项，或当前节点匹配，则保留该节点
        return filteredChildren.length > 0 || isMatch;
      }

      // 如果是叶子节点，根据是否匹配决定是否保留
      return isMatch;
    });

    // 对数据进行过滤
    localData.value = filterNodes([...originalData.value]);
  };

  const handleNodeChecked = (data: Array<CascaderItem>) => {
    const { schema } = treeRef.value.getData();
    // 过滤掉 __is_indeterminate 为 true 的项
    selectedItems.value = data.filter((item) => {
      const schemaItem = schema.get(item);
      // eslint-disable-next-line no-underscore-dangle
      return !schemaItem?.__is_indeterminate;
    });
    // 触发选择事件
    emit('select', selectedItems.value);
  };

  // const handleNodeClick = (data: Array<CascaderItem>) => {
  //   //
  // };

  const handleAddNode = (node: CascaderItem) => {
    if (fieldTypeValue.value[node.id]) {
      return;
    }
    fieldTypeValue.value[node.id] = [{ field: '' }];
    node.children.push({
      allow_operators: [],
      children: [],
      disabled: false,
      dynamic_content: false,
      id: node.id,
      isJson: false,
      level: node.level + 1,
      name: node.name,
      isOpen: false,
      isEdit: true,
    });
    // eslint-disable-next-line no-param-reassign
    node.isOpen = true;
    originalData.value = _.cloneDeep(localData.value);
  };

  const handleAddFieldSubmit = (node: CascaderItem) => {
    const customFields =  fieldTypeValue.value[node.id];
    const parentId = node.id;
    if (!customFields || customFields.length === 0) {
      return;
    }
    if (customFields.some(field => !field.field)) {
      return;
    }
    const newIdArray = [node.id, ...customFields.map(item => item.field)];
    const newNameStr = `${node.name}/${customFields.map(item => item.field).join('/')}`;
    // eslint-disable-next-line no-param-reassign
    node.id = JSON.stringify(newIdArray);
    // eslint-disable-next-line no-param-reassign
    node.name = newNameStr;
    // eslint-disable-next-line no-param-reassign
    node.isEdit = false;
    // 清空customFields
    delete fieldTypeValue.value[parentId];
  };

  const handleAddFieldClose = (node: CascaderItem) => {
    delete fieldTypeValue.value[node.id];
    const nodeId = node.id;
    const parentNode = localData.value.find(item => item.id === nodeId);
    if (parentNode) {
      parentNode.children.pop();
    }
  };

  watch(() => props.deleteFieldName, (newVal) => {
    // 根据id在selectedItems中找到对应的节点
    const nodeToRemove = selectedItems.value.find(node => node.id === newVal);
    if (nodeToRemove) {
      // 从selectedItems中移除该节点
      selectedItems.value = selectedItems.value.filter(node => node !== nodeToRemove);
      treeRef.value.setChecked(nodeToRemove, false);
    }
  });

  // 同步外部值的改动
  watch(() => props.modelValue, (newVal) => {
    selectedItems.value = newVal || [];
  }, {
    immediate: true,
  });

  // 设置disabled
  watch(
    () => props.data,
    (newVal) => {
      const processedData = newVal.map(item => ({
        ...item,
        disabled: Object.keys(props.filedConfig).includes(item.id),
      }));

      localData.value = processedData;
      // 保存原始数据副本
      originalData.value = _.cloneDeep(processedData);
    },
  );
</script>
<style lang="postcss">
  .add-search-tree-pop {
    .bk-node-row {
      font-size: 12px;

      .bk-node-action {
        width: 14px;
        height: 32px;
      }

      .bk-node-content {
        > span:first-child {
          display: flex;
          align-items: center;
        }

        .bk-node-text {
          display: flex;
          min-width: 240px;
          padding-right: 8px;;
          margin-left: 8px;
          align-items: center;
          justify-content: space-between;

          .category-type {
            width: 28px;
            height: 16px;
            font-size: 10px;
            line-height: 16px;
            text-align: center;
            border-radius: 2px;
          }
        }

        .add-icon {
          margin-left: 5px;
          color: #c4c6cc;

          &:hover {
            color: #3a84ff;
          }
        }

        .disabled-add-icon {
          color: #dcdee5;
          cursor: not-allowed;
          user-select: none
        }

        .field-edit-right {
          display: flex;
          align-items: center;
          margin-left: 5px;

          .submit-icon {
            margin-right: 4px;
            font-size: 18px;
            color: #7bbe8a;
          }

          .disabled-submit-icon {
            font-size: 18px;
            color: #dcdee5;
            cursor: not-allowed;
            user-select: none
          }
        }
      }

      .bk-node-content:has(.disabled-row) {
        cursor: not-allowed;

        > span:first-child {
          .bk-checkbox {
            pointer-events: none;
            cursor: not-allowed;
            opacity: 60%;
          }
        }

        .bk-node-text:has(.disabled-row) {
          color: #dcdee5;
          cursor: not-allowed;
          user-select: none
        }
      }
    }
  }
</style>
