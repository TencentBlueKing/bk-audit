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
    v-if="Array.isArray(modelValue.rt_id)"
    class="strategy-customize-eventlog-wrap">
    <bk-form-item
      class="no-label"
      label-width="0"
      property="configs.data_source.data_sheet_id"
      style="margin-bottom: 8px;">
      <bk-cascader
        v-slot="{node}"
        v-model="modelValue.rt_id"
        filterable
        id-key="value"
        :list="filterTableData"
        :loading="loading"
        name-key="label"
        trigger="hover">
        <p>
          {{ node.name }}
        </p>
      </bk-cascader>
    </bk-form-item>
  </div>
</template>

<script setup lang='ts'>
  import { computed, inject, onMounted, type Ref, ref, watch } from 'vue';

  import StrategyManageService from '@service/strategy-manage';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';

  import useRequest from '@hooks/use-request';

  type ModelValue = LinkDataDetailModel['config']['links'][0]['left_table'] | LinkDataDetailModel['config']['links'][0]['right_table']

  interface Props {
    links: LinkDataDetailModel['config']['links'],
    type: 'left' | 'right',
    linkIndex: number
  }

  const props = defineProps<Props>();
  const modelValue = defineModel<ModelValue>({
    required: true,
  });
  const isEditMode = inject<Ref<boolean>>('isEditMode', ref(false));
  const AllOtherRtIds = ref<Array<string>>([]);

  // 所有关联中选中的BizRt
  watch(() => props.links, (data) => {
    AllOtherRtIds.value = [];
    if (props.linkIndex === 0) return;

    // 遍历所有的关联
    data.forEach((link) => {
      const leftTable = link.left_table;
      const rightTable = link.right_table;

      // 检查 left_table 是否为 BizRt 类型
      if (leftTable.table_type === 'BizRt') {
        // 如果 rt_id 是数组，获取最后一个元素；如果是字符串，直接添加
        if (Array.isArray(leftTable.rt_id)) {
          AllOtherRtIds.value.push(leftTable.rt_id[leftTable.rt_id.length - 1]);
        } else {
          AllOtherRtIds.value.push(leftTable.rt_id);
        }
      }

      // 检查 right_table 是否为 BizRt 类型
      if (rightTable.table_type === 'BizRt') {
        // 如果 rt_id 是数组，获取最后一个元素；如果是字符串，直接添加
        if (Array.isArray(rightTable.rt_id)) {
          AllOtherRtIds.value.push(rightTable.rt_id[rightTable.rt_id.length - 1]);
        } else {
          AllOtherRtIds.value.push(rightTable.rt_id);
        }
      }
    });
  }, {
    deep: true,
    immediate: true,
  });

  const changeData = (data: Array<{
    label: string;
    value: string;
    children: Array<{
      label: string;
      value: string;
    }>
  }>) => {
    data.forEach((item) => {
      if (item.children && item.children.length) {
        item.children.forEach((cItem) => {
          if (cItem.value === modelValue.value.rt_id) {
            modelValue.value.rt_id = [item.value, modelValue.value.rt_id];
          }
        });
      }
    });
  };

  // 不能选择已选的表
  const getRightTableData = () => tableData.value.map(item => ({
    ...item,
    leaf: true,
    disabled: !(item.children && item.children.length),
    children: item.children.map(child => ({
      ...child,
      disabled: AllOtherRtIds.value.length ? AllOtherRtIds.value.includes(child.value) : false,
    })),
  }));

  // 只能选择前面关联已有的表
  const getLeftTableData = () => tableData.value.map((item) => {
    // 默认选中第一个
    if (AllOtherRtIds.value.length) {
      // eslint-disable-next-line prefer-destructuring
      modelValue.value.rt_id = AllOtherRtIds.value[0];
      changeData(tableData.value);
    }
    return {
      ...item,
      leaf: true,
      disabled: !(item.children && item.children.length),
      children: item.children.map(child => ({
        ...child,
        disabled: AllOtherRtIds.value.length ? !AllOtherRtIds.value.includes(child.value) : false,
      })),
    };
  });


  const filterTableData = computed(() => {
    if (props.type === 'right') {
      return getRightTableData();
    }
    return getLeftTableData();
  });

  // 获取rt_id
  const {
    data: tableData,
    run: fetchTable,
    loading,
  } = useRequest(StrategyManageService.fetchTable, {
    defaultValue: [],
    onSuccess: (data) => {
      if (!modelValue.value.rt_id) {
        modelValue.value.rt_id = [];
      }
      if (data) {
        data.sort((a, b) => {
          if (a.children && a.children.length) return -1;
          if (b.children && b.children.length) return 1;
          return 0;
        });
      }
      if (isEditMode.value) {
        // 对tableid转换
        data.forEach((item) => {
          if (item.children && item.children.length) {
            item.children.forEach((cItem) => {
              if (cItem.value === modelValue.value.rt_id) {
                modelValue.value.rt_id = [item.value, modelValue.value.rt_id];
              }
            });
          }
        });
      }
    },
  });

  onMounted(() => {
    fetchTable({
      table_type: 'BizRt',
    });
  });
</script>
