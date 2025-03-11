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
      <div class="mb16">
        <bk-input
          v-model="searckKey"
          :placeholder="t('请输入 应用名称、应用 ID 进行搜索')"
          style="width: 480px;"
          @change="handleSearch" />
      </div>
      <render-list
        ref="listRef"
        :columns="tableColumn"
        :data-source="dataSource"
        :reverse-sort-fields="['system_id','status']"
        @clear-search="handleClearSearch"
        @column-filter="handleColumnFilter"
        @row-click="handleRowClick" />
    </div>
  </skeleton-loading>
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

  import type SyetemModel from '@model/meta/system';

  import EditTag from '@components/edit-box/tag.vue';

  enum FullEnum {
    FULL = 'full',
    FUZZY = 'fuzzy'
  }
  enum SortScope {
    CURRENT = 'current',
    ALL = 'all'
  }
  const { t } = useI18n();
  const tableColumn = [
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
        const to = {
          name: 'systemDetail',
          params: {
            id: data.system_id,
          },
        };
        return (
          <auth-router-link
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
      field: () => 'system_id',
      width: '180px',
    },
    {
      label: () => t('系统负责人'),
      render: ({ data }: {data: SyetemModel}) => <EditTag data={data.managers} key={data.id}/>,
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
  ] as Column[];

  const listRef = ref();
  const dataSource = MetaManageService.fetchSystemList;

  const searckKey = ref('');
  const isLoading = computed(() => (listRef.value ? listRef.value.loading : true));

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

  onMounted(() => {
    listRef.value.fetchData();
  });

</script>
<style lang="postcss">
  .system-list-page {
    padding: 24px;
    background: #fff;

    .audit-render-list {
      td {
        cursor: pointer;
      }
    }
  }
</style>
