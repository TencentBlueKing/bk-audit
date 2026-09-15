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
    <bk-loading
      class="structure-preview-loading"
      :loading="loadingRtMeta">
      <div class="structure-preview">
        <div
          class="title"
          style="margin-bottom: 16px;">
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
        <div class="title-head">
          <div class="title">
            {{ t('资源数据结构') }}
          </div>
          <bk-button
            class="ml10"
            outline
            theme="primary"
            @click="handleViewMore">
            {{ t('更多信息') }}
            <audit-icon
              style="margin-left: 5px; transform: rotate(-90deg);"
              type="angle-line-down" />
          </bk-button>
        </div>
        <div
          ref="tableWrapRef"
          class="table-wrap">
          <bk-table
            ref="tableRef"
            :border="['outer']"
            :columns="columns"
            :data="rtMeta.formatted_fields"
            :max-height="tableHeight" />
        </div>
      </div>
    </bk-loading>
  </audit-sideslider>
</template>
<script setup lang="ts">
  import type { Table } from 'bkui-vue';
  import {
    computed,
    h,
    nextTick,
    onBeforeUnmount,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RootManageService from '@service/root-manage';
  import StrategyManageService from '@service/strategy-manage';

  import ConfigModel from '@model/root/config';
  import RtMetaModel from '@model/strategy/rt-meta';

  import Tooltips from '@components/show-tooltips-text/index.vue';

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

  const tableWrapRef = ref<HTMLElement>();
  const tableHeight = ref(480);
  const TABLE_BOTTOM_GAP = 24;

  const updateTableHeight = () => {
    const el = tableWrapRef.value;
    if (!el) {
      return;
    }
    const { top } = el.getBoundingClientRect();
    if (top <= 0) {
      return;
    }
    const next = Math.floor(window.innerHeight - top - TABLE_BOTTOM_GAP);
    if (next > 0) {
      tableHeight.value = next;
    }
  };

  const formatLastDataValue = (value: unknown) => {
    if (value === undefined || value === null || value === '') {
      return '--';
    }
    if (typeof value === 'object') {
      try {
        return JSON.stringify(value);
      } catch {
        return '--';
      }
    }
    return String(value);
  };

  const getLastDataRecord = () => {
    const payload = rtLastData.value as { last_data?: unknown } | unknown[];
    if (Array.isArray(payload)) {
      return payload[0] as Record<string, any> | undefined;
    }
    const lastData = payload?.last_data;
    if (Array.isArray(lastData)) {
      return lastData[0] as Record<string, any> | undefined;
    }
    if (lastData && typeof lastData === 'object') {
      return lastData as Record<string, any>;
    }
    return undefined;
  };

  const getRecordFieldValue = (record: Record<string, any> | undefined, fieldName: string) => {
    if (!record || !fieldName) {
      return undefined;
    }
    if (Object.prototype.hasOwnProperty.call(record, fieldName)) {
      return record[fieldName];
    }
    const target = fieldName.toLowerCase();
    if (Object.prototype.hasOwnProperty.call(record, target)) {
      return record[target];
    }
    const matchedKey = Object.keys(record).find(key => key.toLowerCase() === target);
    return matchedKey !== undefined ? record[matchedKey] : undefined;
  };

  const {
    data: configData,
  } =  useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });

  const handleViewMore = () => {
    const rtId = Array.isArray(props.rtId) ? props.rtId[props.rtId.length - 1] : props.rtId;
    const prefix = rtId.split('_')[0];

    window.open(`${configData.value.third_party_system.bkbase_web_url}#/data-mart/data-dictionary/detail?dataType=result_table&result_table_id=${props.rtId}&bk_biz_id=${prefix}`);
  };

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
    run: fetchTableRtLastData,
  } = useRequest(StrategyManageService.fetchTableRtLastData, {
    defaultValue: {
      last_data: [],
    },
  });

  const columns = computed(() => {
    const lastRecord = getLastDataRecord();
    return [
      {
        label: () => t('序号'),
        width: 60,
        type: 'index',
      },
      {
        label: () => t('字段名'),
        field: () => 'value',
        width: 180,
      },
      {
        label: () => t('字段中文名'),
        field: () => 'label',
        width: 140,
      },
      {
        label: () => t('类型'),
        width: 90,
        field: () => 'spec_field_type',
      },
      {
        label: () => t('最新一条数据'),
        field: () => '',
        minWidth: 320,
        render: ({ data }: {data: Record<string, any>}) => h(Tooltips, {
          data: formatLastDataValue(getRecordFieldValue(lastRecord, data.value)),
          maxWidth: 480,
        }),
      },
    ] as InstanceType<typeof Table>['$props']['columns'];
  });

  watch(
    [() => props.rtId, showStructure],
    ([rtId, visible]) => {
      if (!visible || !rtId) {
        return;
      }
      fetchTableRtMeta({
        table_id: rtId,
      });
      fetchTableRtLastData({
        table_id: rtId,
      });
    },
  );

  watch(
    [showStructure, () => loadingRtMeta.value],
    async ([visible]) => {
      window.removeEventListener('resize', updateTableHeight);
      if (!visible) {
        return;
      }
      await nextTick();
      requestAnimationFrame(updateTableHeight);
      window.addEventListener('resize', updateTableHeight);
    },
    {
      flush: 'post',
    },
  );

  onBeforeUnmount(() => {
    window.removeEventListener('resize', updateTableHeight);
  });
</script>
<style scoped lang="postcss">
.structure-preview-loading {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;

  :deep(.bk-loading-wrapper) {
    display: flex;
    height: 100%;
    min-height: 0;
    flex-direction: column;
  }
}

.structure-preview {
  display: flex;
  height: 100%;
  min-height: 0;
  padding: 20px 40px;
  overflow: hidden;
  flex-direction: column;
  box-sizing: border-box;

  .title-head {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .title {
    flex-shrink: 0;
    font-size: 14px;
    font-weight: 700;
  }

  .base-info {
    flex-shrink: 0;
  }

  .info-block {
    display: grid;
    margin-bottom: 12px;
    grid-template-columns: repeat(3, 1fr);
  }

  .table-wrap {
    min-height: 0;
    flex: 1;
  }

  :deep(.bk-table) {
    width: 100%;

    .bk-table-body,
    .bk-table-body-wrapper {
      overflow-x: hidden !important;
    }

    td .cell,
    th .cell {
      overflow: hidden;
    }

    .show-tooltips-text {
      max-width: 100%;
    }
  }
}
</style>
