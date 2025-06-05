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
    <div class="resource-list-header">
      <h3 style="margin-bottom: 16px; line-height: 22px;">
        {{ t('资源') }}
      </h3>
      <span style=" margin-left: 25px;line-height: 22px; color: #979ba5;">
        {{ t('资源回调地址') }}:
        <a
          class="cursor"
          href="xxx"
          target="_blank">{{ 1111 }}</a>
      </span>
    </div>
    <div class="resource-list-action-header">
      <div class="btns-wrap">
        <bk-button
          class="mr8"
          theme="primary"
          @click="handleCreate">
          <audit-icon
            style="margin-right: 8px;font-size: 14px;"
            type="add" />
          {{ t('新建资源类型') }}
        </bk-button>
        <bk-button>
          {{ t('批量新增') }}
        </bk-button>
      </div>
      <bk-search-select
        v-model="searchKey"
        class="search-input"
        clearable
        :condition="[]"
        :data="searchData"
        :defaut-using-item="{ inputHtml: t('请选择') }"
        :placeholder="t('搜索资源类型、资源名称、资源操作、启停状态、敏感等级、资源状态')"
        style="width: 480px;"
        unique-select
        value-split-code=","
        @update:model-value="handleSearch" />
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
  import _ from 'lodash';
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

  interface SearchKey {
    id: string,
    name: string,
    values: [
      {
        id: string,
        name: string
      }
    ]
  }
  interface SearchData{
    name: string;
    id: string;
    children?: Array<SearchData>;
    placeholder?: string;
    multiple?: boolean;
    onlyRecommendChildren?: boolean,
  }

  const { t, locale } = useI18n();
  const route = useRoute();

  const baseTableColumn = [
    {
      label: () => t('资源类型'),
      field: () => 'resource_type_id',
      width: '250px',
    },
    {
      label: () => t('资源名称'),
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
      label: () => t('资源操作'),
      field: () => 'resource_action',
      width: '250px',
    },
    {
      label: () => t('敏感等级'),
      render: ({ data }: {data: SystemResourceTypeModel}) => (
        <render-sensitivity-level value={data.sensitivity} />
      ),
    },
    {
      label: () => t('数据更新方式'),
      render: ({ data }: {data: SystemResourceTypeModel}) => (
        <DataUpdateTag
          data={data}
          type={snapShotStatusList.value[data.resource_type_id]?.pull_type}
          status={snapShotStatusList.value[data.resource_type_id]?.status}
          onChangeStatus={() => handleDataStatus()} />
      ),
    },
    {
      label: () => t('资源状态'),
      render: ({ data }: {data: SystemResourceTypeModel}) => (
        <StatusTag
          status={snapShotStatusList.value[data.resource_type_id]?.status}
          statusMsg={snapShotStatusList.value[data.resource_type_id]?.status_msg} />
      ),
    },
  ];
  const searchData: SearchData[] = [
    {
      name: t('资源类型'),
      id: 'resource_type_id',
      placeholder: t('请输入资源类型'),
    },
    {
      name: t('资源名称'),
      id: 'name',
      placeholder: t('请输入资源名称'),
    },
    {
      name: t('资源操作'),
      id: 'resource_action',
      placeholder: t('请输入资源操作'),
    },
    {
      name: t('敏感等级'),
      id: 'sensitivity',
      placeholder: t('请输入敏感等级'),
    },
    {
      name: t('资源状态'),
      id: 'status',
      placeholder: t('请输入资源状态'),
    },
  ];

  const isShowJobPlan = ref(false);
  const controlsPermission = ref(false);
  const rowData = ref({
    resource_type_id: '',
  });
  const searchKey = ref<Array<SearchKey>>([]);

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
        render: ({ data }: {data: SystemResourceTypeModel}) => <>
          <div style="display: flex">
            <bk-button
              theme='primary'
              class='mr16'
              onClick={() => handleEdit(data)}
              text>
              {t('编辑')}
            </bk-button>
            <TaskSwitch
              data={data}
              bkbaseUrl={snapShotStatusList.value[data.resource_type_id]?.bkbase_url}
              status={snapShotStatusList.value[data.resource_type_id]?.status}
              onChangeStatus={() => handleDataStatus()}/>
            <bk-dropdown
              trigger="click"
              style="margin-left: 8px">
              {{
                default: () => <bk-button text>
                  <audit-icon type="more" />
                </bk-button>,
                content: () => (
                  <bk-dropdown-menu>
                    <bk-dropdown-item>
                      <bk-button
                        text
                        onClick={() => handleViewData(data)}
                        v-bk-tooltips={t('点击跳转到bkbase，地址为')}>
                        {t('数据详情')}
                      </bk-button>
                    </bk-dropdown-item>
                    <bk-dropdown-item>
                      <bk-button
                        onClick={() => handleDelete(data)}
                        text>
                        {t('删除')}
                      </bk-button>
                    </bk-dropdown-item>
                  </bk-dropdown-menu>
                ),
              }}
            </bk-dropdown>
          </div>
        </>,
      },
    ];
  });

  const handleSearch = (keyword: Array<any>) => {
    const search = {
      resource_type_id: '',
      name: '',
      resource_action: '',
      sensitivity: '',
      status: '',
      id: route.params.id,
    } as Record<string, any>;

    keyword.forEach((item: SearchKey, index) => {
      if (item.values) {
        const value = item.values.map(item => item.id).join(',');
        const list = search[item.id].split(',').filter((item: string) => !!item);
        list.push(value);
        _.uniq(list);
        search[item.id] = list.join(',');
      } else {
        // 默认输入字段后匹配规则名称
        const list = search.name.split(',').filter((item: string) => !!item);
        list.push(item.id);
        _.uniq(list);
        search.name = list.join(',');
        searchKey.value[index] = ({ id: 'name', name: t('资源名称'), values: [{ id: item.id, name: item.id }] });
      }
    });
    fetchSysetemResourceTypeList(search);
  };

  /* 有相关权限才显示操作列
    1. 拥有 manage_global_setting 权限
    2. 拥有特性开关enabled为true
  */
  const checkPermission = async () => {
    const { manage_global_setting: manageGlobalSetting = false } = await IamManageService.check({ action_ids: 'manage_global_setting' });
    const { enabled = false } = await MetaManageService.fetchFeature({
      feature_id: 'bkbase_aiops',
    });
    controlsPermission.value =  manageGlobalSetting && enabled;
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

  // const handleJobPlan = (data: SystemResourceTypeModel) => {
  //   isShowJobPlan.value = true;
  //   rowData.value = data;
  // };

  const handleEdit = (data: SystemResourceTypeModel) => {
    console.log(data);
  };

  const handleViewData = (data: SystemResourceTypeModel) => {
    console.log(data);
  };

  const handleDelete = (data: SystemResourceTypeModel) => {
    console.log(data);
  };

  const handleCreate = () => {
    console.log('新建');
  };

  onMounted(() => {
    checkPermission();
  });
</script>
<style lang="postcss">
  .access-model-resource-list {
    padding: 6px 24px;
    color: #313238;
    background-color: #fff;

    .resource-list-header {
      display: flex;
    }

    .resource-list-action-header {
      display: flex;
      margin-bottom: 14px;
      align-items: center;
      justify-content: space-between;
    }

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
