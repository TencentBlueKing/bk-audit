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
    class="customize-resource-data-wrap">
    <bk-form-item
      class="no-label"
      label-width="0"
      property="rt_id"
      style="margin-bottom: 8px;">
      <bk-cascader
        v-slot="{node,data}"
        v-model="modelValue.rt_id"
        filterable
        id-key="value"
        :list="filterTableData"
        :loading="loading"
        name-key="label"
        trigger="hover">
        <p
          v-bk-tooltips="{
            disabled: (node.children && node.children.length) || !data.leaf,
            content: modelValue.table_type === 'BuildIn'
              ? t('该系统暂未上报资源数据')
              : t('审计中心暂未获得该业务数据的使用授权，请联系系统管理员到BKBASE上申请权限'),
            delay: 400,
          }">
          {{ node.name }}
        </p>
      </bk-cascader>
    </bk-form-item>
  </div>
</template>

<script setup lang='ts'>
  import {
    computed,
    inject,
    onMounted,
    type Ref,
    ref,
    watch,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';

  import useRequest from '@/hooks/use-request';

  type ModelValue = LinkDataDetailModel['config']['links'][0]['left_table'] | LinkDataDetailModel['config']['links'][0]['right_table']

  type TableData = Array<{
    label: string;
    value: string;
    children: Array<{
      label: string;
      value: string;
    }>
  }>

  interface Props {
    links: LinkDataDetailModel['config']['links'],
    type: 'left' | 'right',
    linkIndex: number,
    tableTableMap: Record<'BuildIn' | 'BizRt' | 'EventLog', TableData>
  }

  interface Emits {
    (e: 'updateTableData', value: typeof tableData.value, type: 'BuildIn'): void,
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const modelValue = defineModel<ModelValue>({
    required: true,
  });
  const { t } = useI18n();
  const isEditMode = inject<Ref<boolean>>('isEditMode', ref(false));
  const AllReSourceDataRtIds = ref<Array<string>>([]);

  watch(() => props.links, (data) => {
    AllReSourceDataRtIds.value = [];

    // 遍历所有的关联
    data.forEach((link) => {
      const leftTable = link.left_table;
      const rightTable = link.right_table;

      // 检查 left_table 是否为 BuildIn 类型
      if (leftTable.table_type === 'BuildIn') {
        // 如果 rt_id 是数组，获取最后一个元素；如果是字符串，直接添加
        if (Array.isArray(leftTable.rt_id)) {
          AllReSourceDataRtIds.value.push(leftTable.rt_id[leftTable.rt_id.length - 1]);
        } else {
          AllReSourceDataRtIds.value.push(leftTable.rt_id);
        }
      }

      // 检查 right_table 是否为 BuildIn 类型
      if (rightTable.table_type === 'BuildIn') {
        // 如果 rt_id 是数组，获取最后一个元素；如果是字符串，直接添加
        if (Array.isArray(rightTable.rt_id)) {
          AllReSourceDataRtIds.value.push(rightTable.rt_id[rightTable.rt_id.length - 1]);
        } else {
          AllReSourceDataRtIds.value.push(rightTable.rt_id);
        }
      }
    });
  }, {
    immediate: true,
    deep: true,
  });

  const changeData = (data: TableData) => {
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

  const getDisabled = (child: {
    label: string,
    value: string
  }) => {
    if (props.linkIndex === 0 && props.type === 'left') return false;
    // 不能选择已选的表
    if (props.type === 'right') {
      return AllReSourceDataRtIds.value.length ? AllReSourceDataRtIds.value.includes(child.value) : false;
    }
    // 只能选择前面关联已有的表
    return AllReSourceDataRtIds.value.length ? !AllReSourceDataRtIds.value.includes(child.value) : false;
  };

  const getTableData = () => tableData.value.map(item => ({
    ...item,
    leaf: true,
    disabled: !(item.children && item.children.length),
    children: item.children.map(child => ({
      ...child,
      disabled: getDisabled(child),
    })),
  }));

  const filterTableData = computed(() => getTableData());

  const processData = (data: TableData) => {
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
      changeData(data);
    }
  };

  // 获取rt_id
  const {
    data: tableData,
    run: fetchTable,
    loading,
  } = useRequest(StrategyManageService.fetchTable, {
    defaultValue: [],
    onSuccess: (data) => {
      emits('updateTableData', data, 'BuildIn');
      processData(data);
    },
  });

  onMounted(() => {
    if (props.tableTableMap.BuildIn.length) {
      const data = props.tableTableMap.BuildIn;
      tableData.value = data;
      processData(data);
      return;
    }
    fetchTable({
      table_type: 'BuildIn',
    });
  });
</script>
<style  lang="postcss" scoped>
.strategy-aiops-resource-data-wrap {
  .flex-center {
    display: flex;
    align-items: center;
  }
}
</style>
