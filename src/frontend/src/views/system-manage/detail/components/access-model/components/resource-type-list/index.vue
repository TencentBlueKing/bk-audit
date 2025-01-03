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
  <div class="access-model-resource-list">
    <div style="margin-bottom: 16px; font-size: 14px;">
      {{ t('资源') }}
    </div>
    <bk-loading :loading="loading || isSystemDataLoading">
      <bk-table
        :border="['outer']"
        :columns="renderTableColumn"
        :data="resourceTypeList" />
    </bk-loading>
  </div>
  <audit-sideslider
    v-model:is-show="isShowJobPlan"
    :show-footer="false"
    :title="rowData.resource_type_id"
    :width="640">
    <job-plan :data="rowData" />
  </audit-sideslider>
</template>
<script setup lang="tsx">
  import {
    computed,
    onMounted,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';
  import IamManageService from '@service/iam-manage';
  import MetaManageService from '@service/meta-manage';

  import SystemModel from '@model/meta/system';
  import type SystemResourceTypeModel from '@model/meta/system-resource-type';

  import useRequest from '@hooks/use-request';

  import DataUpdateTag from './components/data-update-tag.vue';
  import JobPlan from './components/job-plan.vue';
  import StatusTag from './components/status-tag.vue';
  import TaskSwitch from './components/task-switch.vue';

  const { t, locale } = useI18n();
  const rowData = ref({
    resource_type_id: '',
  });

  const baseTableColumn = [
    {
      label: () => t('资源类型'),
      field: () => 'resource_type_id',
      width: '250px',
    },
    {
      label: () => t('资源名称'),
      width: '200px',
      render: ({ data }: {data: SystemResourceTypeModel}) => (
        data.description ? (
        <span
          class="tips"
          v-bk-tooltips={ t(data.description) }>
          {data.name}
        </span>)
          : (<span>{data.name}</span>)
      ),
    },
    {
      label: () => t('敏感等级'),
      width: '200px',
      render: ({ data }: {data: SystemResourceTypeModel}) => (
        <render-sensitivity-level value={data.sensitivity} />
      ),
    },
    {
      label: () => t('资源实例 URL'),
      minWidth: 200,
      showOverflowTooltip: true,
      render: ({ data }: {data: SystemResourceTypeModel}) => (
        `${systemDetailData.value.provider_config.host}${data.provider_config.path} `
      ),
    },
    {
      label: () => t('数据结构'),
      width: '150px',
      render: ({ data }: {data: SystemResourceTypeModel}) => (
          <div
            onClick={() => handleJobPlan(data)}
            style="color:#3a84ff"
            class="cursor"
            >
            <audit-icon
              class="mr8 schema-icon"
              svg
              type="schema"
            />
            <span class="ml5">schema</span>
          </div>
      ),
    },
    {
      label: () => t('数据更新方式'),
      width: '150px',
      render: ({ data }: {data: SystemResourceTypeModel}) => (
        <DataUpdateTag
          data={data}
          type={snapShotStatusList.value[data.resource_type_id]?.pull_type}
          status={snapShotStatusList.value[data.resource_type_id]?.hdfs_status}
          onChangeStatus={() => handleDataStatus()} />
      ),
    },
    {
      label: () => t('资源状态'),
      width: '150px',
      render: ({ data }: {data: SystemResourceTypeModel}) => (
        <StatusTag
          status={snapShotStatusList.value[data.resource_type_id]?.hdfs_status}
          statusMsg={snapShotStatusList.value[data.resource_type_id]?.status_msg} />
      ),
    },
  ];

  const route = useRoute();
  const isShowJobPlan = ref(false);
  const controlsPermission = ref(false);
  const renderTableColumn = computed(() => {
    if (!controlsPermission.value) {
      return baseTableColumn;
    }
    return [
      ...baseTableColumn,
      {
        label: () => t('操作'),
        width: locale.value === 'en-US' ? 200 : 120,
        fixed: 'right',
        render: ({ data }: {data: SystemResourceTypeModel}) => <TaskSwitch
          data={data}
          bkbaseUrl={snapShotStatusList.value[data.resource_type_id]?.bkbase_url}
          status={snapShotStatusList.value[data.resource_type_id]?.hdfs_status}
          onChangeStatus={() => handleDataStatus()}/>,
      },
    ];
  });

  /* 有相关权限才显示操作列
    1. 拥有 access_global_setting 权限
    2. 拥有特性开关enabled为true
  */
  const checkPermission = async () => {
    const { access_global_setting: accessGlobalSetting = false } = await IamManageService.check({ action_ids: 'access_global_setting' });
    const { enabled = false } = await MetaManageService.fetchFeature({
      feature_id: 'bkbase_aiops',
    });
    controlsPermission.value =  accessGlobalSetting && enabled;
  };

  // 获取系统详情
  const {
    loading: isSystemDataLoading,
    run: fetchSystemDetail,
    data: systemDetailData,
  } = useRequest(MetaManageService.fetchSystemDetail, {
    defaultParams: {
      id: route.params.id,
    },
    defaultValue: new SystemModel(),
    // manual: true,
  });

  // 获取列表数据
  const {
    loading,
    run: fetchSysetemResourceTypeList,
    data: resourceTypeList,
  }  = useRequest(MetaManageService.fetchSysetemResourceTypeList, {
    defaultParams: {
      id: route.params.id,
    },
    defaultValue: [],
    // manual: true,
  });

  const {
    data: snapShotStatusList,
    run: fetchSnapShotStatus,
  } = useRequest(CollectorManageService.fetchSnapShotStatus, {
    defaultValue: {},
  });

  const getSnapShotStatus = () => {
    const resourceIds = resourceTypeList.value.map(item => item.resource_type_id).join(',');
    fetchSnapShotStatus({
      system_id: systemDetailData.value.system_id,
      resource_type_ids: resourceIds,
    });
  };

  Promise.all([fetchSystemDetail({
    id: route.params.id,
  }), fetchSysetemResourceTypeList({
    id: route.params.id,
  })]).then(() => {
    // 获取资源快照状态
    getSnapShotStatus();
  });

  // 更新资源快照状态
  const handleDataStatus = () => {
    getSnapShotStatus();
  };

  const handleJobPlan = (data: SystemResourceTypeModel) => {
    isShowJobPlan.value = true;
    rowData.value = data;
  };

  onMounted(() => {
    checkPermission();
  });
</script>
<style lang="postcss">
  .access-model-resource-list {
    padding: 16px 24px;
    margin-top: 24px;
    color: #313238;
    background-color: #fff;
    border-radius: 2px;
    box-shadow: 0 1px 2px 0 rgb(0 0 0 / 16%);

    .schema-icon {
      font-size: 14px;
      vertical-align: sub;
    }

    .bk-table {
      .hover-highlight {
        &:hover {
          td:not(.empty-cell) {
            .type-edit {
              display: block;
            }
          }
        }
      }
    }
  }
</style>
