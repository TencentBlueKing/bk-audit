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
    name="storageList">
    <div class="storage-manage-list">
      <div class="action-header">
        <auth-button
          action-id="create_storage"
          style="width: 88px;"
          theme="primary"
          @click="handleShowOperation">
          {{ t('新建') }}
        </auth-button>
        <bk-input
          v-model="search"
          class="search-input"
          :placeholder="t('搜索 ES 源名称、地址')"
          @change="handleSearch" />
      </div>
      <bk-loading :loading="isLoading">
        <bk-table
          ref="listRef"
          :border="['outer']"
          :columns="tableColumn"
          :data="data"
          :settings="settings"
          @setting-change="onSettingChange">
          <template #empty>
            <bk-exception
              v-if="isSearching"
              scene="part"
              style="height: 280px;padding-top: 40px;"
              type="search-empty">
              <div>
                <div style="color: #63656e;">
                  {{ t('搜索结果为空') }}
                </div>
                <div style="margin-top: 8px; color: #979ba5;">
                  {{ t('可以尝试调整关键词') }} {{ t('或') }}
                  <bk-button
                    text
                    theme="primary"
                    @click="handleClearSearch">
                    {{ t('清空搜索条件') }}
                  </bk-button>
                </div>
              </div>
            </bk-exception>
            <bk-exception
              v-else
              scene="part"
              style="height: 280px;padding-top: 40px;color: #63656e;"
              type="empty">
              {{ t('暂无数据') }}
            </bk-exception>
          </template>
        </bk-table>
      </bk-loading>
      <audit-sideslider
        ref="sidesliderRef"
        v-bind="operationSidersliderInfo"
        v-model:isShow="isShowOperation"
        :show-footer-slot="showFooterSlot"
        :width="640">
        <storage-operation
          v-model:btnLoading="btnLoading"
          v-model:disabled="disabled"
          :data="editData"
          @change="handleOperationChange" />
        <template #footer>
          <div
            :class="{'footer-fixed':disabled}"
            style="padding-left: 16px;">
            <bk-button
              v-if="!disabled"
              v-bk-tooltips="t('请先完成连通性测试')"
              class="mr8 is-disabled"
              :loading="btnLoading"
              style="width: 102px;"
              theme="primary">
              {{ isEditMode ? t('保存'): t('提交') }}
            </bk-button>
            <bk-button
              v-else
              class="mr8"
              :loading="btnLoading"
              style="width: 102px;"
              theme="primary"
              @click="handleConfirm">
              {{ isEditMode ? t('保存'): t('提交') }}
            </bk-button>
            <bk-button
              style="min-width: 64px;"
              @click="handleCancle">
              {{ t('取消') }}
            </bk-button>
          </div>
        </template>
      </audit-sideslider>
    </div>
  </skeleton-loading>
</template>
<script setup lang="tsx">
  import type { Column } from 'bkui-vue/lib/table/props';
  import {
    computed,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StorageManageService from '@service/storage-manage';

  import type StorageModel from '@model/storage/storage';

  import useFeature from '@hooks/use-feature';
  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import StorageOperation from './components/storage-operation/index.vue';

  interface ISettings{
    checked: Array<string>,
    fields: Record<string, any>[],
    size: string
  }
  const isSearching = ref(false);
  const search = ref('');
  const { feature: showStorageEdit } = useFeature('storage_edit');
  const tableColumn = [
    {
      label: () => 'ID',
      width: '60px',
      field: () => 'cluster_config.cluster_id',
    },
    {
      label: () => t('名称'),
      field: () => 'cluster_config.cluster_name',
      width: '250px',
      render: ({ data }: {data: StorageModel}) => (
        <div>
          {data.cluster_config.cluster_name}
          {data.isDefault && <bk-tag class="ml8">{ t('默认') }</bk-tag>}
        </div>
      ),
    },
    {
      label: () => t('地址'),
      field: () => 'cluster_config.domain_name',
      width: '5%',
      minWidth: 200,
      showOverflowTooltip: true,
    },
    {
      label: () => t('来源'),
      width: '100px',
      field: () => 'cluster_config.custom_option.source_type',
      showOverflowTooltip: true,
    },
    {
      label: () => t('端口'),
      width: '70px',
      field: () => 'cluster_config.port',
      showOverflowTooltip: true,
    },
    {
      label: () => t('协议'),
      width: '70px',
      field: () => 'cluster_config.schema',
      showOverflowTooltip: true,
    },
    {
      label: () => t('状态'),
      width: '70px',
      render: ({ data }: {data: StorageModel}) => {
        if (data.isStatusLoading) {
          return <audit-icon class="rotate-loading" svg type="loading" />;
        }
        return (
            <div class="storage-status-box">
              <audit-icon svg type={data.status ? 'normal' : 'abnormal'} />
              <span style="padding-left: 6px;">{data.status ? t('正常') : t('异常')}</span>
            </div>
        );
      },
    },
    {
      label: () => t('创建人'),
      field: () => 'cluster_config.custom_option.option.creator',
      width: '100px',
      showOverflowTooltip: true,
    },
    {
      label: () => t('创建时间'),
      width: '170px',
      field: () => 'cluster_config.custom_option.option.create_at',
      showOverflowTooltip: true,
    },
    {
      label: () => t('更新人'),
      field: () => 'cluster_config.custom_option.option.updater',
      width: '100px',
      showOverflowTooltip: true,
    },
    {
      label: () => t('更新时间'),
      width: '170px',
      field: () => 'cluster_config.custom_option.option.update_at',
      showOverflowTooltip: true,
    },
    {
      label: () => t('操作'),
      width: '180px',
      fixed: 'right',
      render: ({ data }: {data: StorageModel}) => (
        <>
          <audit-popconfirm
            title={t('确认设为默认？')}
            content={t('切换集群后，将自动调整采集插件及采集项到新的集群，此操作将对新的审计事件生效，历史审计事件需要手动迁移')}
            confirmHandler={() => handleSetActicate(data)}>
            <auth-button
              permission={data.permission.edit_storage}
              actionId="edit_storage"
              text
              theme="primary"
              disabled={data.isDefault}>
              {t('设为默认')}
            </auth-button>
          </audit-popconfirm>
          {
            showStorageEdit.value.enabled
              ? <auth-button
                  permission={data.permission.edit_storage}
                  actionId="edit_storage"
                  text
                  theme="primary"
                  onClick={() => handleEdit(data)}
                  className="ml8">
                {t('编辑')}
              </auth-button>
              : ''
          }
          <audit-popconfirm
              title={t('确认删除？')}
              content={t('删除后不可恢复')}
              class="ml8"
              confirmHandler={() => handleRemove(data)}>
            <auth-button
                permission={data.permission.delete_storage}
                actionId="delete_storage"
              text
              disabled={data.isDefault}
              theme="primary">
              {t('删除')}
            </auth-button>
          </audit-popconfirm>
        </>
        ),
    },
  ] as Column[];

  const initSettings = () => ({
    showLineHeight: false,
    checked: [
      'cluster_config.cluster_id',
      'source_name',
      'cluster_config.domain_name',
      'cluster_config.custom_option.source_type',
      'cluster_config.port',
      'cluster_config.schema',
      'status',
      'cluster_config.custom_option.option.creator',
      'cluster_config.custom_option.option.create_at',
    ],
    fields: [{
               label: 'ID',
               field: 'cluster_config.cluster_id',
               disabled: true,
             },
             {
               label: t('名称'),
               field: 'source_name',
               disabled: true,
             },
             {
               label: t('地址'),
               field: 'cluster_config.domain_name',
             },
             {
               label: t('来源'),
               field: 'cluster_config.custom_option.source_type',
             },
             {
               label: t('端口'),
               field: 'cluster_config.port',
             },
             {
               label: t('协议'),
               field: 'cluster_config.schema',
             },
             {
               label: t('状态'),
               field: 'status',
             },
             {
               label: t('创建人'),
               field: 'cluster_config.custom_option.option.creator',
             },
             {
               label: t('创建时间'),
               field: 'cluster_config.custom_option.option.create_at',
             },
             {
               label: t('最近更新人'),
               field: 'cluster_config.custom_option.option.updater',
             },
             {
               label: t('最近更新时间'),
               field: 'cluster_config.custom_option.option.update_at',
             },
    ],
  });
  const settings = computed(() => {
    const jsonStr = localStorage.getItem('audit-storage-setting');
    if (jsonStr) {
      const jsonSetting = JSON.parse(jsonStr);
      jsonSetting.showLineHeight = false;
      return jsonSetting;
    }
    return initSettings();
  });
  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const isShowOperation = ref(false);
  const showFooterSlot = ref(true);
  const editData = ref({} as StorageModel);
  const disabled = ref(true);
  const btnLoading = ref(false);
  const sidesliderRef = ref();
  const operationSidersliderInfo = computed(() => {
    if (editData.value.cluster_config) {
      return {
        title: '编辑 ES 存储',
      };
    }
    return {
      title: '新建 ES 存储',
      confirmText: '保存',
    };
  });
  const isEditMode = computed(() => editData.value.cluster_config);
  // 列表数据
  const {
    data,
    loading: isLoading,
    run: fetchList,
    refresh: refreshList,
  } = useRequest(StorageManageService.fetchList, {
    manual: true,
    defaultValue: [],
    onSuccess: (result) => {
      if (result.length < 1) {
        return;
      }
      // 异步获取列表数据状态
      const clusterIds = result.map(item => item.cluster_config.cluster_id).join(',');
      StorageManageService.batchConnectivityDetect({
        cluster_ids: clusterIds,
      }).then((statusMap) => {
        result.forEach((item) => {
          // eslint-disable-next-line no-param-reassign
          item.status = statusMap[item.cluster_config.cluster_id];
          // eslint-disable-next-line no-param-reassign
          item.isStatusLoading = false;
        });
      });
    },
  });

  // 设为默认
  const {
    run: setActivate,
  } = useRequest(StorageManageService.setActivate, {
    defaultValue: 0,
    onSuccess() {
      refreshList();
    },
  });
  // 删除存储
  const {
    run: removeStorage,
  } = useRequest(StorageManageService.remove, {
    defaultValue: 0,
    onSuccess() {
      messageSuccess(t('删除成功'));
      refreshList();
    },
  });


  const onSettingChange = (setting: ISettings) => {
    localStorage.setItem('audit-storage-setting', JSON.stringify(setting));
  };
  // 新建
  const handleShowOperation = () => {
    isShowOperation.value = !isShowOperation.value;
    editData.value = {} as StorageModel;
  };

  // 搜索
  const handleSearch = (keyword: string|number) => {
    isSearching.value = true;
    fetchList({ keyword });
  };

  const handleClearSearch = () => {
    search.value = '';
    fetchList();
  };
  // 设为默认
  const handleSetActicate = (data: StorageModel) => setActivate({
    id: data.cluster_config.cluster_id,
  });

  // 编辑
  const handleEdit = (data: StorageModel) => {
    editData.value = data;
    isShowOperation.value = true;
  };

  // 删除
  const handleRemove = (data: StorageModel) => removeStorage({
    id: data.cluster_config.cluster_id,
  });

  const handleOperationChange = () => {
    refreshList();
  };

  const handleConfirm = () => {
    sidesliderRef.value.handleConfirm();
  };
  const handleCancle = () => {
    sidesliderRef.value.handleCancle();
  };
</script>
<style lang="postcss">
.storage-manage-list {
  padding: 24px;
  background: #fff;

  .action-header {
    display: flex;
    margin-bottom: 16px;

    .search-input {
      width: 480px;
      margin-left: auto;
    }
  }

  .storage-status-box {
    display: flex;
    align-items: center;
  }
}

.footer-fixed {
  display: flex;
  padding: 8px 10px;
  background: #fafbfd;
  flex: 1;
  border-top: 1px solid #dcdee5;
}
</style>
