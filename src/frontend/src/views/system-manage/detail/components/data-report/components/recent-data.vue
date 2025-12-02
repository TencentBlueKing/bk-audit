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
  <skeleton-loading
    ref="rootRef"
    class="recent-data-card"
    :loading="loading"
    name="systemDetailRecentData"
    :once="false"
    style="height: 546px;">
    <apply-permission-catch :key="data.id">
      <div ref="tableWrapperRef">
        <bk-table
          v-if="data.type !== 'bkbase'"
          :border="['outer', 'row']"
          :columns="tableColumn"
          :data="tableData"
          :max-height="530">
          <template #empty>
            <bk-exception
              scene="part"
              style="padding-top: 130px;color: #63656e;"
              type="empty">
              {{ t('暂无数据') }}
            </bk-exception>
          </template>
        </bk-table>
        <bk-table
          v-else
          :border="['outer', 'row']"
          :columns="dataIdTableColumn"
          :data="dataIdTableData"
          :max-height="530">
          <template #empty>
            <bk-exception
              scene="part"
              style="padding-top: 130px;color: #63656e;"
              type="empty">
              {{ t('暂无数据') }}
            </bk-exception>
          </template>
        </bk-table>
      </div>
    </apply-permission-catch>
    <div
      class="fold-button"
      style=" margin-top: 8px;text-align: right;">
      <bk-button
        style="font-size: 12px;"
        text
        theme="primary"
        @click="handleFold">
        {{ t('收起') }}
      </bk-button>
    </div>
  </skeleton-loading>
</template>
<script setup lang="tsx">
  import type { Column } from 'bkui-vue/lib/table/props';
  import {
    nextTick,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';
  import DataIdManageService from '@service/dataid-manage';

  import type CollectorTailLogModel from '@model/collector/collector-tail-log';

  import useRequest from '@hooks/use-request';

  import {
    execCopy,
  } from '@utils/assist';

  import type DataIdTopicLogModel from '@/domain/model/dataid/dataid-tail';

  interface Props {
    data: {
      id: number|string;
      name: string;
      type?:string
    };
  }

  interface Emits {
    (e: 'fold'): void
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const route = useRoute();
  const { t } = useI18n();
  const tableColumn = [
    {
      label: () => t('上报信息'),
      width: '180px',
      render: ({ data }: {data: CollectorTailLogModel}) => (
        <span style="display:block; font-size:12px; font-weight:bold; color:#63656E;">
          {data.origin.datetime}
        </span>
      ),
    },
    {
      label: () => t('原始日志'),
      render: ({ data }: {data: CollectorTailLogModel}) => (
        <bk-popover
          placement="top-end"
          width={ poverWidth.value || 1200 }
          id="log-cell">
          {{
            default: () => (
              <span class="log-cell" style={{  width: poverWidth.value }}>
                {data.originData}
              </span>
            ),
            content: () => (
              <div  style={{  width: poverWidth.value || 1200, 'word-break': 'break-all' }}>
                {data.originData}
              </div>
            ),
          }}
        </bk-popover>
        ),
    },
    {
      label: () => t('操作'),
      width: 60,
      render: ({ data }: {data: CollectorTailLogModel}) => (
        <span
          style="cursor: pointer;width: 25px; height:25px;display:inline-block"
          onClick={() => handleCopyData(data)}>
          <audit-icon
            v-bk-tooltips={t('复制')}
            type="copy"/>
        </span>
      ),
    },
  ] as Column[];
  const dataIdTableColumn = [
    {
      label: () => t('上报信息'),
      width: '180px',
      render: ({ data }: {data: DataIdTopicLogModel}) => (
        <span style="display:block; font-size:12px; font-weight:bold; color:#63656E;">
          {data.topic}
        </span>
      ),
    },
    {
      label: () => t('原始日志'),
      render: ({ data }: {data:DataIdTopicLogModel}) => (
        <bk-popover
          placement="top-end"
          width={poverWidth.value || 1200}
          id="log-cell">
          {{
            default: () => (
              <span class="log-cell" style={{  width: poverWidth.value }}>
                {data.value}
              </span>
            ),
            content: () => (
              <div  style={{  width: poverWidth.value || 1200, 'word-break': 'break-all' }}>
                {data.value}
              </div>
            ),
          }}
        </bk-popover>
        ),
    },
    {
      label: () => t('操作'),
      width: 60,
      render: ({ data }: {data: DataIdTopicLogModel}) => (
        <span
          style="cursor: pointer;width: 25px; height:25px;display:inline-block"
          onClick={() => handleCopyDataIdData(data)}>
          <audit-icon
            v-bk-tooltips={t('复制')}
            type="copy"/>
        </span>
      ),
    },
  ] as Column[];
  const rootRef = ref();
  const poverWidth = ref();
  const loading = ref(false);
  const tableData = ref<CollectorTailLogModel[]>([]);
  const dataIdTableData = ref<Array<{
    topic: string;
    value: string;
  }>>([]);
  const {
    run: fetchTailLog,
  // eslint-disable-next-line vue/no-setup-props-destructure
  } = useRequest(CollectorManageService.fetchTailLog, {
    defaultParams: {
      collector_config_id: props.data.id,
    },
    defaultValue: [],
    onSuccess: (data) => {
      tableData.value = data;
      nextTick(() => {
        const node = document.getElementById('log-cell')?.parentElement;
        poverWidth.value = node?.clientWidth || 999;
        poverWidth.value = poverWidth.value  - 30;
      });
    },
  });
  const {
    run: fetchDataIdTail,
  } = useRequest(DataIdManageService.fetchTail, {
    defaultValue: [],
    onSuccess(data) {
      dataIdTableData.value = data;
    },
  });
  const {
    run: fetchApiPushTailLog,
  // eslint-disable-next-line vue/no-setup-props-destructure
  } = useRequest(CollectorManageService.fetchApiPushTailLog, {
    defaultParams: {
      system_id: props.data.id,
    },
    defaultValue: [],
    onSuccess: (data) => {
      tableData.value = data;
      nextTick(() => {
        const node = document.getElementById('log-cell')?.parentElement;
        poverWidth.value = node?.clientWidth || 999;
        poverWidth.value = poverWidth.value  - 30;
      });
    },
  });

  watch(() => props.data.id, (id) => {
    loading.value = true;
    if (id === 'api') {
      fetchApiPushTailLog({
        system_id: route.params.id,
      }).finally(() => {
        loading.value = false;
      });
    } else if (props.data.type !== 'bkbase') {
      fetchTailLog({
        collector_config_id: id,
      }).finally(() => {
        loading.value = false;
      });
    } else {
      fetchDataIdTail({
        bk_data_id: id,
      }).finally(() => {
        loading.value = false;
      });
    }
  }, {
    immediate: true,
  });

  const handleCopyDataIdData = (data: DataIdTopicLogModel) => {
    execCopy(data.value, t('复制成功'));
  };
  const handleCopyData = (data:CollectorTailLogModel) => {
    execCopy(data.originData, t('复制成功'));
  };

  const handleFold = () => {
    emit('fold');
  };

</script>
<style lang="postcss">
  .recent-data-card {
    /* padding: 16px 24px;
    overflow: hidden;
    background-color: #fff;
    border-radius: 2px;
    box-shadow: 0 1px 2px 0 rgb(0 0 0 / 16%); */

    .title {
      display: flex;
      margin-bottom: 16px;
      font-size: 14px;
      line-height: 22px;
      color: #313238;

      .refresh-btn {
        width: 22px;
        margin-left: auto;
        color: #979ba5;
        text-align: right;
        cursor: pointer;

        &:hover {
          color: #3a84ff;
        }
      }
    }

    .bk-table .bk-table-body table td {
      padding: 8px 0 !important;
      border-bottom: 1px solid #dcdee5;
    }

    /* .bk-table.bordered-row td .cell {
      border-bottom: none !important;
    } */

    .bk-table .bk-table-body table td .cell {
      height: auto !important;
      min-height: 40px !important;
      padding: 0 15px !important;
      overflow: hidden !important;
      font-size: 12px;
      line-height: 20px !important;
      color: #63656e !important;
      text-align: left !important;
      text-overflow: ellipsis !important;
      white-space: unset !important;

      .log-cell {
        /* stylelint-disable-next-line value-no-vendor-prefix */
        display: -webkit-box;
        overflow: hidden;
        font-size: 12px;
        text-overflow: ellipsis;
        word-break: break-all;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 3;
      }

      .bk-popover-content {
        z-index: 999 !important;
      }
    }

    .copy-textarea {
      height: 0;
      opacity: 0%;
    }
  }
</style>
