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
  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="showStructure"
    :show-footer="false"
    :title="t('数据结构预览')"
    :width="960">
    <bk-loading :loading="loadingRtMeta || loadingRtLastData">
      <div class="structure-preview">
        <div class="title">
          {{ t('基础信息') }}
        </div>
        <div class="base-info">
          <render-info-block class="info-block">
            <render-info-item
              :label="t('数据名称')"
              style="width: 250px;">
              {{ rtMeta.result_table_name || '--' }}
            </render-info-item>
            <render-info-item
              :label="t('数据ID')"
              style="width: 250px;">
              {{ rtMeta.result_table_id || '--' }}
            </render-info-item>
            <render-info-item
              :label="t('中文名称')"
              style="width: 250px;">
              {{ rtMeta.result_table_name_alias || '--' }}
            </render-info-item>
          </render-info-block>
          <render-info-block class="info-block">
            <render-info-item
              :label="t('数据表别名')"
              style="width: 250px;">
              --
            </render-info-item>
            <render-info-item
              :label="t('数据管理员')"
              style="width: 250px;">
              {{ rtMeta.managers?.join('，') || '--' }}
            </render-info-item>
            <render-info-item
              :label="t('业务运维人员')"
              style="width: 250px;">
              {{ rtMeta.sensitivity_info?.biz_role_memebers?.join(',') || '--' }}
            </render-info-item>
          </render-info-block>
          <render-info-block>
            <render-info-item
              :label="t('表类型')"
              style="width: 250px;">
              {{ rtMeta.processing_type || '--' }}
            </render-info-item>
          </render-info-block>
        </div>
        <div class="title">
          {{ t('资源数据结构') }}
        </div>
        <bk-table
          ref="tableRef"
          :border="['outer']"
          :columns="columns"
          :data="rtMeta.formatted_fields"
          :max-height="650" />
      </div>
    </bk-loading>
  </audit-sideslider>
</template>
<script setup lang="ts">
  import { watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import RtMetaModel from '@model/strategy/rt-meta';

  import RenderInfoBlock from '@views/strategy-manage/list/components/render-info-block.vue';
  import RenderInfoItem from '@views/strategy-manage/list/components/render-info-item.vue';

  import useRequest from '@/hooks/use-request';

  interface Props {
    rtId: string;
  }
  const props = defineProps<Props>();

  const { t } = useI18n();

  const showStructure = defineModel<boolean>('showStructure', {
    required: true,
  });

  const columns = [
    {
      label: () => t('序号'),
      width: 60,
      type: 'index',
    },
    {
      label: () => t('字段名'),
      field: () => 'value',
    },
    {
      label: () => t('字段中文名'),
      field: () => 'label',
    },
    {
      label: () => t('类型'),
      width: 60,
      field: () => 'spec_field_type',
    },
    {
      label: () => t('最新一条数据'),
      field: () => '',
      render: ({ data }: {data: Record<string, any>}) => rtLastData.value.last_data?.[data.value] || '--',
    },
  ];

  // 获取表格信息
  const {
    data: rtMeta,
    loading: loadingRtMeta,
    run: fetchTableRtMeta,
  } = useRequest(StrategyManageService.fetchTableRtMeta, {
    defaultValue: new RtMetaModel(),
  });

  // 获取表格最后一条数据
  const {
    data: rtLastData,
    loading: loadingRtLastData,
    run: fetchTableRtLastData,
  } = useRequest(StrategyManageService.fetchTableRtLastData, {
    defaultValue: {
      last_data: [],
    },
  });

  watch(() => props.rtId, () => {
    fetchTableRtMeta({
      table_id: props.rtId,
    });
    fetchTableRtLastData({
      table_id: props.rtId,
    });
  });
</script>
<style scoped lang="postcss">
.structure-preview {
  padding: 20px 40px;

  .title {
    margin-bottom: 16px;
    font-size: 14px;
    font-weight: 700;
  }

  .info-block {
    display: grid;
    margin-bottom: 12px;
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>
