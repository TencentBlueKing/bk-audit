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
  <div class="diff-content">
    <bk-table
      ref="resultTable"
      :border="['outer']"
      :columns="tableColumn"
      :data="diffData" />
  </div>
</template>
<script setup lang="tsx">
  import type { Column } from 'bkui-vue/lib/table/props';
  import {
    computed,
    onMounted,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';

  import type ResourceTypeSchemaModel from '@model/meta/resource-type-schema';

  import useRequest from '@hooks/use-request';

  import Tooltips from '@components/show-tooltips-text/index.vue';

  interface Props{
    data: Record<string, any>;
  }
  const props = defineProps<Props>();
  interface DataType {
    update_field: string,
    update_before: string,
    update_after: string,
    is_diff: boolean,
  }

  const { t } = useI18n();
  // eslint-disable-next-line vue/no-setup-props-destructure
  const updateFields = Object.keys(props.data.instance_data);
  const updateBeforeValues = computed(() => props.data.instance_origin_data);
  const updateAfterValues = computed(() => props.data.instance_data);
  const diffData = ref<Array<DataType>>([]);
  const tableColumn = [
    {
      label: () => t('变更字段'),
      render: ({ data }: {data: DataType}) => <div class={data.is_diff ? 'is-diff' : ''}>{data.update_field}</div>,
    },
    {
      label: () => t('变更前'),
      showOverflowTooltip: true,
      render: ({ data }: {data: DataType}) => <div class={data.is_diff ? 'is-diff active-color' : ''}><Tooltips data={data.update_before}/></div>,
    },
    {
      label: () => t('变更后'),
      showOverflowTooltip: true,
      render: ({ data }: { data: DataType }) => <div class={data.is_diff ? 'is-diff active-color' : ''}><Tooltips data={data.update_after} /> </div>,
    },
  ] as  Column[];

  // eslint-disable-next-line vue/no-setup-props-destructure
  useRequest(MetaManageService.fetchResourceTypeSchemaSearch, {
    defaultParams: {
      system_id: props.data.system_id,
      id: props.data.resource_type_id,
      resource_type_id: props.data.resource_type_id,
    },
    defaultValue: [],
    manual: true,
    onSuccess: (result) => {
      const tmpSchemaResult = result.reduce((result, item) => ({
        // eslint-disable-next-line no-param-reassign
        ...result,
        [item.id]: item,
      }), {} as Record<string, ResourceTypeSchemaModel>);
      const data = updateFields.map((item: string) => ({
        update_field: (tmpSchemaResult[item]
          && tmpSchemaResult[item].description)
          || item,
      }));
      diffData.value = diffData.value.map((item, index) => ({ ...item, ...data[index] }));
    },
  });

  onMounted(() => {
    diffData.value = updateFields.map((item: string) => ({
      update_field: item,
      update_before: JSON.stringify(updateBeforeValues.value[item as keyof typeof updateBeforeValues]) || '--',
      update_after: JSON.stringify(updateAfterValues.value[item as keyof typeof updateAfterValues]) || '--',
      is_diff: JSON.stringify(updateBeforeValues.value[item as keyof typeof updateBeforeValues])
        !== JSON.stringify(updateAfterValues.value[item as keyof typeof updateAfterValues]),
    }));
  });
</script>
<style lang="postcss">
.diff-content {
  padding: 28px 40px;

  .is-diff {
    padding: 0 20px;
    margin: 0 -20px;
    background-color: rgb(255 232 195 / 20%);
  }

  .is-diff.active-color {
    color: #ff9c01;
  }
}

</style>
