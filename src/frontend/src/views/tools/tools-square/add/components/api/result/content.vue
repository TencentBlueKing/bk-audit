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
        id-key="json_path"
        multiple
        multiple-mode="tag"
        :popover-options="{
          placement: 'top',
        }"
        @tag-remove="handelTagRemove">
        <bk-tree
          ref="treeRef"
          :check-strictly="false"
          children="children"
          :data="treeData"
          label="name"
          style="color: #63656e;">
          <template #nodeType="node">
            <span v-if="node.isChild && node.children.length === 0">
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
            :output-fields="outputFields"
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
  import { nextTick, onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import Vuedraggable from 'vuedraggable';

  import { buildTree } from './build-tree';
  import listModel from './list-table.vue';
  import objectModel from './object-table.vue';


  interface Props {
    resultData: any,
    groupKey?: string,
    // isEditMode: boolean,
    groupOutputFields?: any,
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
  const modelComMap = (item: Record<string, any>) => (item.type === 'kv' ? objectModel : listModel);
  const selectValue = ref<string[]>([]);
  const selectedId = ref<string[]>([]);
  const selectedItems = ref<any[]>([]);
  const comRef = ref();
  const treeData = ref<any[]>([]);
  const outputFields = ref<any[]>([]);


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
        node.list = data;
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

      treeData.value = updateTreeCheckedState(treeData.value, newVal);
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

  // 分组时的复现
  watch(() => props.groupOutputFields, (newVal) => {
    if (newVal) {
      newVal?.forEach((item: any) => {
        // 递归查找匹配的节点
        const findAndCheckNode = (nodes: any[]) => {
          for (const node of nodes) {
            // 如果当前节点匹配
            if (node.json_path === item.json_path) {
              handleCheckboxChange(true, node);
              return true; // 找到并处理，返回true
            }

            // 如果节点有子节点，递归查找
            if (node.children && node.children.length > 0) {
              const found = findAndCheckNode(node.children);
              if (found) return true; // 如果在子节点中找到，提前返回
            }
          }
          return false; // 未找到
        };
        // 从 treeData.value 开始查找
        findAndCheckNode(treeData.value);
      });
      outputFields.value = newVal;
    }
  }, {
    deep: true,
    immediate: true,
  });

  watch(() => props.resultData, (newVal) => {
    if (newVal) {
      treeData.value = Array.isArray(JSON.parse(newVal)) ? JSON.parse(newVal) : buildTree(JSON.parse(newVal));
    }
  }, {
    deep: true,
    immediate: true,
  });
  onMounted(() => {
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
    // 不分组
    setConfigs(data: any) {
      nextTick(() => {
        data[0].output_fields?.forEach((item: any) => {
          // 当 item.json_path 与节点的json_path相同时 执行  handleCheckboxChange(true, node: any) node为节点
          // 递归查找匹配的节点
          const findAndCheckNode = (nodes: any[]) => {
            for (const node of nodes) {
              // 如果当前节点匹配
              if (node.json_path === item.json_path) {
                handleCheckboxChange(true, node);
                return true; // 找到并处理，返回true
              }

              // 如果节点有子节点，递归查找
              if (node.children && node.children.length > 0) {
                const found = findAndCheckNode(node.children);
                if (found) return true; // 如果在子节点中找到，提前返回
              }
            }
            return false; // 未找到
          };
          // 从 treeData.value 开始查找
          findAndCheckNode(treeData.value);
        });
        outputFields.value = data[0].output_fields || [];
      });
    },
  });
</script>

<style lang="postcss" scoped>
.result-content {
  padding-top: 10px;
}

.content-item {
  padding-bottom: 10px;

  .content-lable {
    padding-bottom: 10px;
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
