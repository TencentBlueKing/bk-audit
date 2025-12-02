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
        id-key="id"
        multiple
        multiple-mode="tag">
        <bk-tree
          ref="treeRef"
          :check-strictly="false"
          children="children"
          :data="treeData"
          label="name"
          style="color: #63656e">
          <template #nodeType="node">
            <span v-if="node.isChild && node.children.length === 0">
              <bk-checkbox
                v-model="node.isChecked"
                style="padding-right: 5px;"
                @change="(val) => handelCheckoxChange(val, node)" />
            </span>
          </template>
        </bk-tree>
      </bk-select>
    </div>
    <div class="content-item">
      <div class="content-lable">
        {{ t('设置展示字段') }}
      </div>
      <!-- <div
        v-for="item in selectedItems"
        :key="item.id">
        <component
          :is="modelComMap[item.type]"
          ref="comRef"
          :data="item" />
      </div> -->
      <vuedraggable
        :group="{
          name: 'field',
          pull: false,
          push: true
        }"
        item-key="id"
        :list="selectedItems">
        <template #item="{ element }">
          <component
            :is="modelComMap[element.type]"
            ref="comRef"
            :data="element" />
        </template>
      </vuedraggable>
    </div>
  </div>
</template>
<script setup lang='ts'>
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import Vuedraggable from 'vuedraggable';

  import listModel from './list-table.vue';
  import objectModel from './object-table.vue';

  interface Props {
    resultData: any,
  }

  const props = defineProps<Props>();
  const { t } = useI18n();
  const modelComMap: Record<string, any> = {
    object: objectModel,
    list: listModel,
  };
  const selectValue = ref([
    'results',
    'num_pages',
    'addd',
    'total',
  ]);
  const selectedId = ref([
    'frontend-data-3-4',
    'frontend-data-3-2',
    'frontend-data-3-5',
    'frontend-data-3-3',
  ]);
  const selectedItems = ref([
    {
      name: 'results',
      id: 'frontend-data-3-4',
      isChecked: true,
      isChild: true,
      children: [],
      list: [
        {
          name: 'risk_id',
          id: 'frontend-data-3-4-1',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'event_content',
          id: 'frontend-data-3-4-2',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'strategy_id',
          id: 'frontend-data-3-4-3',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'event_time',
          id: 'frontend-data-3-4-4',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'event_end_time',
          id: 'frontend-data-3-4-5',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'operator',
          id: 'frontend-data-3-4-6',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'status',
          id: 'frontend-data-3-4-7',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'current_operator',
          id: 'frontend-data-3-4-8',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'notice_users',
          id: 'frontend-data-3-4-9',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'event_data',
          id: 'frontend-data-3-4-10',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'tags',
          id: 'frontend-data-3-4-11',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'risk_label',
          id: 'frontend-data-3-4-12',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'experiences',
          id: 'frontend-data-3-4-13',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'last_operate_time',
          id: 'frontend-data-3-4-14',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'title',
          id: 'frontend-data-3-4-15',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'permission',
          id: 'frontend-data-3-4-16',
          isChecked: false,
          isChild: true,
          children: [
            {
              name: 'edit_risk_v2',
              id: 'frontend-data-3-4-16-1',
              isChecked: false,
              isChild: true,
              children: [],
              list: [],
              type: 'object',
            },
          ],
          list: [],
          type: 'list',
        },
      ],
      type: 'list',
    },
    {
      name: 'num_pages',
      id: 'frontend-data-3-2',
      isChecked: true,
      isChild: true,
      children: [],
      list: [],
      type: 'object',
    },
    {
      name: 'addd',
      id: 'frontend-data-3-5',
      isChecked: true,
      isChild: true,
      children: [],
      list: [
        {
          name: 'risk_id',
          id: 'frontend-data-3-5-1',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'event_content',
          id: 'frontend-data-3-5-2',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'strategy_id',
          id: 'frontend-data-3-5-3',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'event_time',
          id: 'frontend-data-3-5-4',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'event_end_time',
          id: 'frontend-data-3-5-5',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'operator',
          id: 'frontend-data-3-5-6',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'status',
          id: 'frontend-data-3-5-7',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'current_operator',
          id: 'frontend-data-3-5-8',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'notice_users',
          id: 'frontend-data-3-5-9',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'event_data',
          id: 'frontend-data-3-5-10',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'tags',
          id: 'frontend-data-3-5-11',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'risk_label',
          id: 'frontend-data-3-5-12',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'experiences',
          id: 'frontend-data-3-5-13',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'last_operate_time',
          id: 'frontend-data-3-5-14',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'title',
          id: 'frontend-data-3-5-15',
          isChecked: false,
          isChild: true,
          children: [],
          list: [],
          type: 'list',
        },
        {
          name: 'permission',
          id: 'frontend-data-3-5-16',
          isChecked: false,
          isChild: true,
          children: [
            {
              name: 'edit_risk_v2',
              id: 'frontend-data-3-5-16-1',
              isChecked: false,
              isChild: true,
              children: [],
              list: [],
              type: 'object',
            },
          ],
          list: [],
          type: 'list',
        },
      ],
      type: 'list',
    },
    {
      name: 'total',
      id: 'frontend-data-3-3',
      isChecked: true,
      isChild: true,
      children: [],
      list: [],
      type: 'object',
    },
  ]);

  const treeData = computed(() => buildTree(props.resultData));
  const buildTree = (obj, parentId = '', path = [], isChild = false, type = 'object')  => {
    const result = [];

    // 如果是对象，我们递归它的每个键值对
    if (typeof obj === 'object' && obj !== null) {
      const keys = Object.keys(obj);
      keys.forEach((key, index) => {
        const currentPath = [...path, key];
        const currentId = parentId
          ? `${parentId}-${index + 1}`
          : `frontend-data-${index + 1}`;

        const node = {
          name: key,
          id: currentId,
          isChecked: false,
          isChild,
          children: [],
          list: [],
          type,
        };
        if (typeof obj[key] === 'object' && obj[key] !== null && !Array.isArray(obj[key])) {
          // 如果值是对象且不是数组，递归
          node.children = buildTree(obj[key], currentId, currentPath, true, 'object', '');
        } else if (Array.isArray(obj[key]) && obj[key].length > 0) { // 如果值是数组 代表list
          // 递归它的第一个元素
          node.type = 'list';
          const childNodes = buildTree(obj[key][0], currentId, currentPath, true, 'list', key);
          node.list = childNodes;
        }

        result.push(node);
      });
    }
    return result;
  };

  console.log('buildTree>>', buildTree(props.resultData));

  const handelCheckoxChange = (val, node) => {
    console.log('val>>', val, node, treeData.value);
    if (val) {
      // 选中时添加name到selectValue
      if (!selectedId.value.includes(node.id)) {
        selectedId.value.push(node.id);
        selectValue.value.push(node.name);
        selectedItems.value.push(node);
      }
    } else {
      // 取消选中时从selectValue中删除name
      const index = selectedId.value.indexOf(node.id);
      if (index > -1) {
        selectedId.value.splice(index, 1);
        selectValue.value.splice(index, 1);
        selectedItems.value.splice(index, 1);
      }
    }
    console.log('selectValue.value', selectValue.value);
    console.log('selectedId.value>', selectedId.value);

    console.log('selectedItems', selectedItems.value);
  };
</script>

<style lang="postcss" scoped>
.result-content {
  padding-top: 10px;
}

.content-item {
  padding-top: 10px;

  .content-lable {
    margin-top: 10px;
    font-size: 14px;
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
