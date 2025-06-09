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
    name="noticeGroup">
    <div
      class="notice-group-list">
      <div class="action-header">
        <auth-button
          action-id="create_notice_group"
          style="width: 88px;"
          theme="primary"
          @click="handleCreate">
          {{ t('新建') }}
        </auth-button>
        <bk-input
          v-model="searchKey"
          class="search-input"
          :placeholder="t('ID、通知组名称')"
          @change="handleSearch" />
      </div>
      <render-list
        ref="listRef"
        :columns="tableColumn"
        :data-source="dataSource"
        :reverse-sort-fields="['name']"
        @clear-search="handleClearSearch"
        @request-success="handleRequestSuccess" />
    </div>
  </skeleton-loading>
  <create-group
    ref="createRef"
    @update="handleCreateUpdate" />
  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="showDetail"
    :show-footer="false"
    title="通知组详情"
    :width="960">
    <div>
      <detail :data="groupItem" />
    </div>
  </audit-sideslider>
</template>
<script setup lang="tsx">
  import {
    onMounted,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import IamManageService from '@service/iam-manage';
  import NoticeManageService from '@service/notice-group';

  import type NoticeGroupsModel from '@model/notice/notice-group';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import Tooltips from '@components/show-tooltips-text/index.vue';

  import CreateGroup from '../notice-group-create/index.vue';

  import Detail from './components/detail.vue';

  interface Groups {
    page: number;
    num_pages: number;
    total: number;
    results: Array<NoticeGroupsModel>;
  }
  const {
    getSearchParams,
  } = useUrlSearch();
  const createRef = ref();
  const { messageSuccess } = useMessage();
  const { t } = useI18n();
  const isLoading = ref(false);
  const listRef = ref();
  const searchKey = ref('');
  const showDetail = ref(false);
  const dataSource = NoticeManageService.fetchGroupList;
  const groupItem = ref({} as NoticeGroupsModel);
  const isNeedShowDetail = ref(false);
  const tableColumn = [
    {
      label: () => 'ID',
      width: 120,
      sort: 'custom',
      field: () => 'group_id',
      render: ({ data }:{data: NoticeGroupsModel}) =>  `#${data.group_id}`,
    },
    {
      label: () => t('通知组名称'),
      sort: 'custom',
      width: 300,
      field: () => 'group_name',
      render: ({ data }:{data: NoticeGroupsModel}) => (
        <a
          onClick={() => handleDetail(data)}>
          <Tooltips data={data.group_name} />
        </a>
      ),
    },
    {
      label: () => t('说明'),
      showOverflowTooltip: true,
      // width: 300,
      // render: ({ data }:{data: NoticeGroupsModel}) => <Tooltips data = {data.description} />,
      render: ({ data }:{data: NoticeGroupsModel}) => data.description || '--',
    },
    {
      label: () => t('最近更新人'),
      // width: 180,
      sort: 'custom',
      field: () => 'updated_by',
    },
    {
      label: () => t('最近更新时间'),
      width: 300,
      sort: 'custom',
      field: () => 'updated_at',
    },
    {
      label: () => t('操作'),
      width: '160px',
      fixed: 'right',
      render: ({ data }: {data: NoticeGroupsModel}) => (
      <>
        <auth-button
          action-id="edit_notice_group_v2"
          theme="primary"
          resource={data.group_id}
          text
          permission={!!data.permission.edit_notice_group_v2}
          onClick={() => handleEdit(data.group_id)}>
          {t('编辑')}
        </auth-button>
        <audit-popconfirm
          content={t('删除后将不可找回')}
          title={t('确认删除通知组？')}
          confirmHandler={() => handleRemove(data.group_id)}>
          <auth-button
            action-id="delete_notice_group_v2"
            class="ml8"
            resource={data.group_id}
            permission={!!data.permission.delete_notice_group_v2}
            theme="primary"
            text>
            {t('删除')}
          </auth-button>
        </audit-popconfirm>
      </>
      ),
    },
  ];

  // 获取权限
  useRequest(IamManageService.check, {
    defaultParams: {
      action_ids: 'create_notice_group',
    },
    defaultValue: {},
    manual: true,
  });
  // 删除
  const {
    run: remove,
  } = useRequest(NoticeManageService.deleteGroup, {
    defaultValue: {},
    onSuccess: () => {
      listRef.value.refreshList();
      messageSuccess(t('删除成功'));
    },
  });
  // 搜索
  const handleSearch = (keyword: string|number) => {
    listRef.value.fetchData({
      keyword,
    });
  };
  // 新建
  const handleCreate = () => {
    createRef.value.show();
  };
  const handleCreateUpdate = () => {
    listRef.value.fetchData({ keyword: searchKey.value });
  };
  // 编辑
  const handleEdit = (id: number) => {
    createRef.value.show(id);
  };
  // 清空搜索
  const handleClearSearch = () => {
    searchKey.value = '';
    listRef.value.fetchData({ keyword: '' });
  };
  // 删除
  const handleRemove = (id: number) => {
    remove({
      group_id: id,
    });
  };
  const handleDetail = (data: NoticeGroupsModel) => {
    groupItem.value = data;
    showDetail.value = true;
  };
  const handleRequestSuccess = (data: Groups) => {
    const { keyword } = getSearchParams();
    if (keyword && isNeedShowDetail.value) {
      handleDetail(data.results[0]);
      isNeedShowDetail.value = false;
    }
  };
  onMounted(() => {
    const { keyword, create } = getSearchParams();
    if (keyword) {
      searchKey.value = keyword;
      isNeedShowDetail.value = true;
    } else if (create) {
      handleCreate();
    }
    listRef.value.fetchData({ keyword });
  });
</script>
<style lang="postcss">
  .notice-group-list {
    padding: 24px;
    background: white;

    /* 解决表格悬停超出 */
    .bk-table-fixed .column_fixed {
      bottom: 80px !important;
    }

    .action-header {
      display: flex;
      margin-bottom: 16px;

      .search-input {
        width: 480px;
        margin-left: auto;
      }
    }
  }
</style>
