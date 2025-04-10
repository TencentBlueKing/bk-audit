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
  <div class="customize-resource-data-wrap">
    <bk-form-item
      class="no-label"
      label-width="0"
      property="configs.data_source.rt_id">
      <bk-cascader
        v-slot="{node,data}"
        v-model="dataSource.rt_id"
        filterable
        id-key="value"
        :list="filterTableData"
        name-key="label"
        trigger="hover"
        @change="handleTableIdChange">
        <p
          v-bk-tooltips="{
            disabled: (node.children && node.children.length) || !data.leaf,
            content: sourceType === 'BuildIn'
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
  import { InfoBox } from 'bkui-vue';
  import {
    computed,
    h,
    ref,
    watch  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';

  interface Emits {
    (e: 'resetConfig'): void;
  }
  interface Expose {
    setConfigs: (config: Record<string, any>) => void;
  }
  interface Props {
    tableData: Array<{
      label: string;
      value: string;
      children: Array<{
        label: string;
        value: string;
      }>
    }>;
    sourceType: string;
    hasData: boolean;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const dataSource = defineModel<{
    rt_id: Array<string>;
  }>('dataSource', {
    required: true,
  });

  const { t } = useI18n();

  const prevValue = ref<Array<string>>([]);

  const filterTableData = computed(() => props.tableData.map(item => ({
    ...item,
    leaf: true,
    disabled: !(item.children && item.children.length),
  })));

  const createInfoBoxConfig = (overrides: {
    onConfirm: () => void
    onClose: () => void
  }): any => ({
    type: 'warning',
    title: t('切换数据源请注意'),
    subTitle: () => h(
      'div',
      {
        style: {
          color: '#4D4F56',
          backgroundColor: '#f5f6fa',
          padding: '12px 16px',
          borderRadius: '2px',
          fontSize: '14px',
          textAlign: 'left',
        },
      },
      t('切换后，已配置的数据将被清空。是否继续？'),
    ),
    confirmText: t('继续切换'),
    cancelText: t('取消'),
    headerAlign: 'center',
    contentAlign: 'center',
    footerAlign: 'center',
    ...overrides,
  });


  const handleTableIdChange = () => {
    if (!prevValue.value.length || !props.hasData) {
      prevValue.value = [...dataSource.value.rt_id];
      return;
    }
    InfoBox(createInfoBoxConfig({
      onConfirm() {
        prevValue.value = [...dataSource.value.rt_id];
        emit('resetConfig');
      },
      onClose() {
        // 恢复到之前的值
        dataSource.value.rt_id = [...prevValue.value];
      },
    }));
  };

  watch(() => props.tableData, (data) => {
    if (data) {
      data.sort((a, b) => {
        if (a.children && a.children.length) return -1;
        if (b.children && b.children.length) return 1;
        return 0;
      });
    }
  });

  defineExpose<Expose>({
    setConfigs(config: Record<string, any>) {
      if (Array.isArray(config.data_source.rt_id)) {
        dataSource.value.rt_id = config.data_source.rt_id;
        return;
      }
      // 对tableid转换
      props.tableData.forEach((item) => {
        if (item.children && item.children.length) {
          item.children.forEach((cItem) => {
            if (cItem.value === config.data_source.rt_id) {
              dataSource.value.rt_id = [item.value, config.data_source.rt_id];
            }
          });
        }
      });
    },
  });
</script>

<style lang="postcss" scoped>
.strategy-aiops-resource-data-wrap {
  .flex-center {
    display: flex;
    align-items: center;
  }
}
</style>
