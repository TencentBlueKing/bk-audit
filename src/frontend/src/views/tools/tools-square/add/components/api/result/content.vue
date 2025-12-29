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
  <div class="result-content">
    <div class="content-item">
      <div class="content-lable">
        {{ t('选择展示字段') }}
      </div>
      <bk-select
        ref="selectRef"
        v-model="selectValue"
        :auto-height="false"
        collapse-tags
        custom-content
        display-key="name"
        filterable
        id-key="json_path"
        multiple
        multiple-mode="tag"
        :popover-options="{
          placement: 'top',
        }"
        @search-change="handleTreeSearchChange"
        @tag-remove="handelTagRemove">
        <bk-tree
          ref="treeRef"
          :check-strictly="false"
          children="children"
          :data="treeData"
          expand-all
          label="name"
          style="color: #63656e;">
          <template #operations="node">
            <span v-if="node.children.length === 0 ">
              <bk-checkbox
                v-model="node.isChecked"
                style="padding-right: 5px;"
                @change="(val: any) => handleCheckboxChange(val, node)" />
            </span>
          </template>
          <template #nodeType="node">
            <span v-if="node.children.length === 0 ">
              <bk-checkbox
                v-model="node.isChecked"
                style="padding-right: 5px;"
                @change="(val: any) => handleCheckboxChange(val, node)" />
            </span>
          </template>
        </bk-tree>
      </bk-select>
    </div>
    <div
      v-if="selectValue.length > 0"
      class="content-item">
      <div class="content-lable">
        {{ t('设置展示字段') }}
      </div>
      <vuedraggable
        :group="{
          name: 'field',
          pull: false,
          push: true
        }"
        item-key="json_path"
        :list="selectedItems">
        <template #item="{ element }">
          <component
            :is="modelComMap(element)"
            ref="comRef"
            :data="element"
            :is-edit-mode="isEditMode"
            :is-grouping="isGrouping"
            :list-data="selectedItems"
            :output-fields="outputFields"
            :tree-data="treeData"
            @close="handleClose"
            @config-change="(...args: unknown[]) => handleConfigChange(args[0] as any, args[1] as string)"
            @list-config-change="(...args: unknown[]) =>
              handleListConfigChange(args[0] as any, args[1] as string, args[2] as any)" />
        </template>
      </vuedraggable>
    </div>
  </div>
</template>
<script setup lang='ts'>
  import { nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import Vuedraggable from 'vuedraggable';

  import resultDataModel from '@model/tool/api';

  import { buildTree } from './build-tree';
  import listModel from './list-table.vue';
  import objectModel from './object-table.vue';

  interface Props {
    resultData: Array<resultDataModel> | string,
    groupKey?: string,
    isEditMode: boolean,
    groupOutputFields?: any,
    isGrouping: boolean
  }

  interface Exposes {
    handleGetResultConfig: () => void;
    handleGetGroupResultConfig: () => void;
    setConfigs: (data: any) => void;
  }
  interface Emits {
    (e: 'groupContentChange', data: any, id: string | number): void
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const modelComMap = (item: Record<string, any>) => (item.type === 'table' ?  listModel : objectModel);
  const selectValue = ref<string[]>([]);
  const selectedId = ref<string[]>([]);
  const selectedItems = ref<any[]>([]);
  const treeData = ref<any[]>([]);
  const outputFields = ref<any[]>([]);
  const initTreeDatas = ref<any[]>([]);

  // 递归查找节点并勾选（公共函数）
  const findAndCheckNode = (nodes: any[], targetJsonPath: string): boolean => {
    for (const node of nodes) {
      if (node.json_path === targetJsonPath) {
        handleCheckboxChange(true, node);
        return true;
      }
      if (node.children?.length > 0 && findAndCheckNode(node.children, targetJsonPath)) {
        return true;
      }
    }
    return false;
  };

  // 批量恢复选中状态
  const restoreCheckedNodes = (outputFieldsData: any[]) => {
    outputFieldsData?.forEach((item: any) => {
      findAndCheckNode(treeData.value, item.json_path);
    });
  };

  // 搜索
  const handleTreeSearchChange = (val: any) => {
    if (!val) {
      treeData.value = initTreeDatas.value;
      return;
    }

    // 递归搜索树形结构
    const searchTree = (nodes: any[]) => nodes.filter((node: any) => {
      // 检查当前节点是否匹配
      const currentMatch = node.name.includes(val);

      // 递归搜索子节点
      let childrenMatch = false;
      if (node.children && node.children.length > 0) {
        const filteredChildren = searchTree(node.children);
        if (filteredChildren.length > 0) {
          childrenMatch = true;
          // 保留匹配的子节点
          // eslint-disable-next-line no-param-reassign
          node.children = filteredChildren;
        }
      }

      // 如果当前节点匹配或有匹配的子节点，则保留该节点
      return currentMatch || childrenMatch;
    });

    treeData.value = searchTree(JSON.parse(JSON.stringify(initTreeDatas.value)));
  };
  const handelTagRemove = (val: any) => {
    if (val) {
      // selectedItems中找出name与val相同的节点
      const node = selectedItems.value.find(item => item.name === val);
      if (node) {
        const index = selectedId.value.indexOf(node.json_path);
        if (index > -1) {
          selectedId.value.splice(index, 1);
          selectedItems.value.splice(index, 1);
        }
      }
    }
  };

  const handleCheckboxChange = (val: any, node: any) => {
    if (val) {
      // 选中时添加name到selectValue
      if (!selectedId.value.includes(node.json_path)) {
        selectedId.value.push(node.json_path);
        selectValue.value.push(node.name);
        selectedItems.value.push(node);
      }
    } else {
      // 取消选中时从selectValue中删除name
      const index = selectedId.value.indexOf(node.json_path);
      if (index > -1) {
        selectedId.value.splice(index, 1);
        selectValue.value.splice(index, 1);
        selectedItems.value.splice(index, 1);
      }
    }
  };

  // 关闭
  const handleClose = (item: any) => {
    // 删除对应的item treeData中的isChecked 改为false
    const index = selectedId.value.indexOf(item.json_path);
    if (index > -1) {
      selectedId.value.splice(index, 1);
      selectValue.value.splice(index, 1);
      selectedItems.value.splice(index, 1);
    }
  };
  // kv组件配置更新
  const handleConfigChange = (data: any, jsonPath: string) => {
    if (data) {
      // 更新对应的item treeData中的isChecked 改为false
      const node = selectedItems.value.find(item => item.json_path === jsonPath);
      if (node) {
        node.config = data;
      }
    }
  };
  // list组件配置更新
  const handleListConfigChange = (data: any, jsonPath: string, listInfo: any) => {
    if (data) {
      // 更新对应的item treeData中的isChecked 改为false
      const node = selectedItems.value.find(item => item.json_path === jsonPath);
      if (node) {
        node.list = JSON.parse(JSON.stringify(data));
        node.listDescription = listInfo.desc;
        node.listName = listInfo.name;
      }
    }
  };

  watch(
    () => selectedId.value, (newVal) => {
      // 递归更新树中所有节点的isChecked状态
      const updateTreeCheckedState = (nodes: any[], selectedIds: string[]) => nodes.map((node: any) => {
        // 更新当前节点的选中状态
        // eslint-disable-next-line no-param-reassign
        node.isChecked = selectedIds?.includes(node.json_path);

        // 递归更新子节点
        if (node.children && node.children.length > 0) {
          // eslint-disable-next-line no-param-reassign
          node.children = updateTreeCheckedState(node.children, selectedIds);
        }

        // 递归更新list中的子节点
        if (node.list && node.list.length > 0) {
          // eslint-disable-next-line no-param-reassign
          node.list = updateTreeCheckedState(node.list, selectedIds);
        }

        return node;
      }, {
        deep: true,
      });

      treeData.value = updateTreeCheckedState(JSON.parse(JSON.stringify(treeData.value)), newVal);
    },
    {
      immediate: true,
      deep: true,
    },
  );
  watch(
    () => selectedItems.value, (newVal) => {
      emits('groupContentChange', newVal, props?.groupKey || '');
    },
    {
      immediate: true,
      deep: true,
    },
  );

  watch(() => props.resultData, (newVal: any) => {
    if (newVal) {
      initTreeDatas.value = Array.isArray(JSON.parse(newVal)) ? JSON.parse(newVal) : buildTree(JSON.parse(newVal));
      treeData.value = initTreeDatas.value;

      // 分组模式：恢复选中状态
      if (props.groupOutputFields?.length > 0) {
        restoreCheckedNodes(props.groupOutputFields);
        outputFields.value = props.groupOutputFields;
      }
    }
  }, {
    deep: true,
    immediate: true,
  });

  defineExpose<Exposes>({
    // 提交获取内容
    handleGetResultConfig() {
      return selectedItems.value;
    },
    handleGetGroupResultConfig() {
      return  {
        groupKey: props.groupKey,
        items: selectedItems.value,
      };
    },
    // 非分组模式：恢复配置
    setConfigs(data: any) {
      nextTick(() => {
        const fields = data[0].output_fields || [];
        restoreCheckedNodes(fields);
        outputFields.value = fields;
      });
    },
  });
</script>

<style lang="postcss" scoped>

.content-item {
  margin-top: 24px;

  .content-lable {
    font-size: 12px;
    color: #4d4f56;
  }
}

.underline-dashed {
  text-decoration: underline;
  text-decoration-style: dashed;
  text-decoration-color: #c4c6cc;
  text-underline-offset: 2px;
}

</style>
<style lang="postcss">
.api-tree-ref {
  .bk-node-row.is-selected {
    background-color: #fff !important;
  }
}
</style>
