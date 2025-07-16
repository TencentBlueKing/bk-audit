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
    fullscreen
    :loading="isLoading"
    name="systemList">
    <div class="system-list-page">
      <div class="mb16 action-header">
        <auth-button
          action-id="create_system"
          class="mr8"
          :permission="permissionCheckData"
          theme="primary"
          @click="handleCreate">
          <audit-icon
            style="margin-right: 8px;font-size: 14px;"
            type="add" />
          {{ t('接入系统') }}
        </auth-button>
        <bk-input
          v-model="searckKey"
          :placeholder="t('请输入 应用名称、应用 ID 进行搜索')"
          style="width: 480px;"
          @change="handleSearch" />
      </div>
      <render-list
        ref="listRef"
        class="audit-highlight-table"
        :columns="tableColumn"
        :data-source="dataSource"
        :reverse-sort-fields="['system_id','status']"
        :settings="settings"
        @clear-search="handleClearSearch"
        @column-filter="handleColumnFilter"
        @request-success="handleRequestSuccess"
        @row-click="handleRowClick" />
    </div>
  </skeleton-loading>
</template>
<script setup lang="tsx">
  import {
    computed,
    onMounted,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import IamManageService from '@service/iam-manage';
  import MetaManageService from '@service/meta-manage';

  import type SyetemModel from '@model/meta/system';

  import EditTag from '@components/edit-box/tag.vue';

  import getAssetsFile from '@utils/getAssetsFile';

  import useRequest from '@/hooks/use-request';

  // import useRequest from '@/hooks/use-request';

  interface Syetem {
    page: number;
    num_pages: number;
    total: number;
    results: Array<SyetemModel>
  }

  enum FullEnum {
    FULL = 'full',
    FUZZY = 'fuzzy'
  }
  enum SortScope {
    CURRENT = 'current',
    ALL = 'all'
  }
  const { t } = useI18n();
  const router = useRouter();
  const tableColumn = ref([
    {
      label: () => '',
      width: '65px',
      render: ({ data }: {data: SyetemModel}) => (
        <img
        src={data.logo_url}
        style="width: 24px; height: 24px; vertical-align: middle;" />
      ),
    },
    {
      label: () => t('系统名称'),
      sort: 'custom',
      field: () => 'name',
      render: ({ data }: {data: SyetemModel}) => {
        const isNew = isNewData(data);
        const to = {
          name: 'systemDetail',
          params: {
            id: data.system_id,
          },
          query: {
            type: data.permission_type,
          },
        };
        return (isNew
          ? <div style='display: flex;align-items: center;'>
            <auth-router-link
              id={`systemDetailLink${data.system_id}`}
              permission={data.permission.view_system}
              actionId='view_system'
              resource={data.system_id}
              resourceTypeId="system"
              to={to}>
              {data.name}
            </auth-router-link>
            <img
              class='table-new-tip'
              src={getAssetsFile('new-tip.png')}/>
          </div>
          : <auth-router-link
            id={`systemDetailLink${data.system_id}`}
            permission={data.permission.view_system}
            actionId='view_system'
            resource={data.system_id}
            resourceTypeId="system"
            to={to}>
            {data.name}
          </auth-router-link>
        );
      },
    },
    {
      label: () => t('系统 ID'),
      sort: 'custom',
      field: () => 'instance_id',
      width: '180px',
    },
    {
      label: () => t('系统负责人'),
      render: ({ data }: {data: SyetemModel}) => <EditTag data={data.managers} key={data.id}/>,
    },
    {
      label: () => t('系统来源'),
      sort: 'custom',
      filter: {
        list: [
          {
            text: t('权限中心V3'),
            value: 'iam_v3',
          },
          {
            text: t('权限中心V4'),
            value: 'iam_v4',
          },
          {
            text: t('审计中心'),
            value: 'bk_audit',
          },
        ],
        filterScope: SortScope.ALL,
        match: FullEnum.FUZZY,
        btnSave: t('确定'),
        btnReset: t('重置'),
      },
      field: () => 'source_type',
      render: ({ data }: {data: SyetemModel}) => (GlobalChoices.value.meta_system_source_type.find(item => item.id === data.source_type)?.name || '--'),
    },
    {
      label: () => t('权限模型'),
      render: ({ data }: {data: SyetemModel}) => <>{
        (!data.resource_type_count && !data.action_count)
          ? <bk-tag theme="warning">{t('未配置')}</bk-tag>
          : <div>
            <bk-tag
              style="margin-right: 4px"
              theme="info"
              v-bk-tooltips={t('已配置资源', { count: data.resource_type_count })}>
              { data.resource_type_count }
            </bk-tag>
            <bk-tag
              theme="info"
              v-bk-tooltips={t('已配置操作', { count: data.action_count })}>
              { data.action_count }
            </bk-tag>
          </div>
      }</>,
    },
    {
      label: () => t('数据上报状态'),
      sort: 'custom',
      width: '200px',
      filter: {
        list: [
          {
            text: t('正常'),
            value: 'normal',
          },
          {
            text: t('未配置'),
            value: 'unset',
          },
          {
            text: t('无数据'),
            value: 'nodata',
          },
        ],
        filterScope: SortScope.ALL,
        match: FullEnum.FUZZY,
        btnSave: t('确定'),
        btnReset: t('重置'),
      },
      field: () => 'status',
      render: ({ data }: {data: SyetemModel}) => {
        if (!data.status_msg) {
          return '--';
        }
        return (
          <>
            <audit-icon type={data.statusIcon} svg class='mr8' />
            <span>{ data.status_msg }</span>
          </>
        );
      },
    },
    {
      label: () => t('最近数据时间'),
      sort: 'custom',
      field: () => 'last_time',
      width: '180px',
      render: ({ data }: {data: SyetemModel}) => data.last_time || '--',
    },
    {
      label: () => t('应用ID'),
      sort: 'custom',
      field: () => 'clients',
      width: '180px',
      render: ({ data }: {data: SyetemModel}) => data.clients.join(',') || '--',
    },
    {
      label: () => t('系统域名'),
      sort: 'custom',
      field: () => 'system_url',
      width: '180px',
    },
    {
      label: () => t('创建时间'),
      field: () => 'created_at',
      width: 170,
      render: ({ data }: {data: SyetemModel}) => data.created_at || '--',
    },
    {
      label: () => t('创建人'),
      field: () => 'created_by',
      width: 140,
      render: ({ data }: {data: SyetemModel}) => data.created_by || '--',
    },
  ] as any[]);

  const listRef = ref();
  const dataSource = MetaManageService.fetchSystemList;

  const searckKey = ref('');
  const isLoading = computed(() => (listRef.value ? listRef.value.loading : true));

  const permissionCheckData = ref();

  const disabledMap: Record<string, string> = {
    name: 'name',
    system_id: 'system_id',
    managers: 'managers',
    id: 'id', // 权限模型
    status: 'status',
    last_time: 'last_time',
  };
  console.log('tableColumn', tableColumn);

  const initSettings = () => ({
    fields: tableColumn.value.reduce((res, item) => {
      if (item.field) {
        res.push({
          label: item.label(),
          field: item.field(),
          disabled: !!disabledMap[item.field()],
        });
      }
      return res;
    }, [] as Array<{
      label: string, field: string, disabled: boolean,
    }>),
    checked: ['name', 'system_id', 'managers', 'id', 'status', 'status', 'last_time'],
    showLineHeight: false,
  });
  const settings = computed(() => {
    const jsonStr = localStorage.getItem('audit-strategy-manage-list-setting');
    if (jsonStr) {
      const jsonSetting = JSON.parse(jsonStr);
      jsonSetting.showLineHeight = false;
      return jsonSetting;
    }
    return initSettings();
  });

  // 获取策略新建权限
  useRequest(IamManageService.check, {
    defaultParams: {
      action_ids: 'create_system',
    },
    defaultValue: {},
    manual: true,
    onSuccess: (data) => {
      permissionCheckData.value = data.create_strategy;
    },
  });

  const {
    data: GlobalChoices,
  } = useRequest(MetaManageService.fetchGlobalChoices, {
    defaultValue: {},
    manual: true,
  });

  // 搜索
  const handleSearch = (keyword: string|number) => {
    listRef.value.fetchData({
      keyword,
    });
  };

  // 点击整行
  const handleRowClick = (event: Event, row: any) => {
    (document.querySelector(`#systemDetailLink${row.system_id}`) as HTMLElement)?.click();
  };
  // 清空搜索
  const handleClearSearch = () => {
    searckKey.value = '';
    listRef.value.fetchData({ keyword: '' });
  };
  // 筛选过滤
  const handleColumnFilter = (checkedObj: Record<string, any>) => {
    const checkField = checkedObj.column.field();
    const value = checkedObj.checked.join(',');
    listRef.value.fetchData({
      [checkField]: value,
    });
  };

  const handleCreate = () => {
    const route = router.resolve({
      name: 'systemAccess',
    });
    window.open(route.href, '_blank');
  };

  // 判断是否是新建数据
  const isNewData = (data: SyetemModel) => {
    if (!data.created_at) {
      return false;
    }
    const time = new Date(data.created_at).getTime();
    const now = new Date().getTime();
    const diff = Math.abs(now - time);
    const isNew = diff < (5 * 60 * 1000);
    return isNew;
  };

  // 将新建的tr高亮
  const setNewCreateTrHighlight = (index: number, isNew : boolean) => {
    const domList = document.querySelectorAll(`.audit-highlight-table .bk-table-body tbody tr:nth-child(${index + 1}) td`);
    if (domList) {
      domList.forEach((dom) => {
        const el = dom as HTMLElement;
        el.style.background = isNew ? '#f2fff4' : '#fff';
      });
    }
  };

  const handleRequestSuccess = (data: Syetem) => {
    setTimeout(() => {
      data.results.forEach((item, index) => {
        const isNew = isNewData(item);
        setNewCreateTrHighlight(index, isNew);
      });
    }, 1000);
  };

  onMounted(() => {
    listRef.value.fetchData();
  });

</script>
<style lang="postcss">
  .system-list-page {
    padding: 24px;
    background: #fff;

    .action-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .audit-render-list {
      td {
        cursor: pointer;
      }

      .table-new-tip {
        height: 14px;
        margin-left: 8px;
      }
    }
  }
</style>
