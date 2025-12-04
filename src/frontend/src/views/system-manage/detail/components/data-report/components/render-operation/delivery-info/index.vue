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
  <div class="collection-delivery-info">
    <p class="title">
      {{ t('采集状态') }}
      <span class="title-info">{{ t('每 15 分钟按照 CMDB 最新拓扑自动部署或取消采集') }}</span>
    </p>
    <div class="collector-status">
      <div
        class="status-operation">
        <bk-loading :loading="loading">
          <div
            class="status-operation-box">
            <status-tab
              v-model="listType"
              :data="collectorTaskStatus" />
            <bk-button
              :disabled="collectorTaskStatus.failedList.length < 1"
              :loading="isRetryTaskLoading"
              style="margin-left: auto;"
              @click="handleRetryFaildTask">
              {{ t('失败批量重试') }}
            </bk-button>
          </div>
          <bk-table
            :border="['outer']"
            :columns="tableColumn"
            :data="renderList" />
        </bk-loading>
      </div>
      <audit-sideslider
        v-model:is-show="isShowDetail"
        :show-footer="false"
        :title="t('部署详情')"
        :width="640">
        <deploy-log
          v-if="isShowDetail"
          :collector-config-id="data.collector_config_id"
          :instance-id="instanceId" />
      </audit-sideslider>
    </div>
  </div>
</template>
<script setup lang="tsx">
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import CollectorManageService from '@service/collector-manage';

  import { BcsContent, BcsContentChild } from '@model/collector/bcs-task-status';
  import type CollectorModel from '@model/collector/collector';
  import { Content, ContentChild } from '@model/collector/task-status';

  import useRequest from '@hooks/use-request';

  import DeployLog from './components/deploy-log.vue';
  import StatusTab from './components/status-tab.vue';

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  interface Props {
    data: CollectorModel;
    environment: string|null;
  }
  interface Emits {
    (e: 'getStatus', value: Content|BcsContent): void
  }

  const { t } = useI18n();
  const loading = ref(true);
  const tableColumn = ref([] as any);

  const column = [
    {
      label: () => t('目标'),
      field: 'ip',
    },
    {
      label: () => t('状态'),
      field: 'status',
      render: ({ data }: {data: ContentChild}) => (
          <>
            <audit-icon svg type={data.statusIconType} />
            <span>{ t(data.statusText) }</span>
          </>
        ),
    },
    {
      label: () => t('更新时间'),
      field: 'create_time',
    },
    {
      label: () => t('操作'),
      width: 120,
      render: ({ data }: {data: ContentChild}) => (
        <bk-button
         text
          theme="primary"
          onClick={() => handleShowLog(data)}>
          { t('部署详情') }
        </bk-button>
      ),
    },
  ];

  const bcsColumn = [
    {
      label: 'ID',
      field: 'container_collector_config_id',
    },
    {
      label: () => t('名称'),
      field: 'name',
    },
    {
      label: () => t('状态'),
      field: 'status',
      render: ({ data }: {data: BcsContentChild}) => (
          <>
            <audit-icon svg type={data.statusIconType} />
            <span>{ t(data.statusText) }</span>
          </>
        ),
    },
  ];
  const listType = ref('all');
  const isShowDetail = ref(false);
  const instanceId = ref('');

  // table 数据
  const renderList = computed(() => {
    if (listType.value === 'success') {
      return collectorTaskStatus.value.successList;
    } if (listType.value === 'failed') {
      return collectorTaskStatus.value.failedList;
    } if (listType.value === 'running') {
      return collectorTaskStatus.value.runningList;
    }
    return collectorTaskStatus.value.allList;
  });

  const collectorTaskStatus = computed(() => (props.environment === 'container' ? bcsData.value : statusData.value));
  const {
    data: statusData,
    run: fetchStatus,
  // eslint-disable-next-line vue/no-setup-props-destructure
  } = useRequest(CollectorManageService.fetchCollectorSubscriptionStatus, {
    defaultParams: {
      collector_config_id: props.data.collector_config_id,
    },
    defaultValue: new Content(),
    onSuccess: (result) => {
      emits('getStatus', result);
    },
  });

  const {
    data: bcsData,
    run: fetchBcsStatus,
  // eslint-disable-next-line vue/no-setup-props-destructure
  } = useRequest(CollectorManageService.fetchBcsTaskStatus, {
    defaultParams: {
      collector_config_id: props.data.collector_config_id,
      task_id_list: [],
    },
    defaultValue: new BcsContent(),
    onSuccess: (result) => {
      emits('getStatus', result);
    },
  });

  // 失败重试
  const {
    loading: isRetryTaskLoading,
    run: retryStask,
  } = useRequest(CollectorManageService.retryStask);

  // 失败批量重试
  const handleRetryFaildTask = () => {
    if (props.environment === 'container') {
      const targetNodes = bcsData.value.failedList.map(item => item.container_collector_config_id);
      const params = {
        instance_id_list: targetNodes,
        id: props.data.collector_config_id,
      };
      retryStask(params);
      return;
    }
    const targetNodes = statusData.value.failedList.map(item => ({
      bk_cloud_id: item.bk_cloud_id,
      bk_supplier_id: item.bk_supplier_id,
      ip: item.ip,
    }));
    const params = {
      id: props.data.collector_config_id,
      target_nodes: targetNodes,
    };
    retryStask(params);
  };

  // 部署详情
  const handleShowLog = (data: ContentChild) => {
    isShowDetail.value = true;
    instanceId.value = data.instance_id;
  };

  watch(() => props.environment, (data) => {
    if (data === 'container') {
      tableColumn.value = bcsColumn;
      fetchBcsStatus({
        task_id_list: [],
        collector_config_id: props.data.collector_config_id,
      }).finally(() => {
        loading.value = false;
      });
    } else {
      tableColumn.value = column;
      fetchStatus({
        collector_config_id: props.data.collector_config_id,
      }).finally(() => {
        loading.value = false;
      });
    }
  }, {
    deep: true,
  });
</script>
<style lang="postcss">
  .collection-delivery-info {
    background: #fff;

    .title {
      padding-bottom: 16px;
      font-size: 14px;
      font-weight: bold;
      color: #313238;

      .title-info {
        font-size: 12px;
        font-weight: 500;
        font-weight: normal;
        color: #979ba5;
      }
    }

    .status-operation-box {
      display: flex;
      margin: 16px 0;
      user-select: none;
    }

    .status-tab {
      display: flex;
      padding: 3px;
      font-size: 12px;
      color: #63656e;
      background: #f0f1f5;
      border-radius: 2px;
    }

    .status-tab-item {
      display: flex;
      height: 26px;
      padding: 0 8px;
      cursor: pointer;
      border-radius: 2px;
      align-items: center;
      justify-content: center;
      transition: all .15s;

      &.active {
        background: #fff;
        box-shadow: 0 1px 2px 0 rgb(0 0 0 / 8%);
      }
    }
  }
</style>
