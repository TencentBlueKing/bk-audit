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
  <div class="access-model-operation-list">
    <h3 style="margin-bottom: 16px; line-height: 22px;">
      {{ t('操作') }}
    </h3>
    <div class="access-model-action-header">
      <div class="btns-wrap">
        <bk-button
          v-bk-tooltips="{
            content: t('暂不支持变更，请前往权限中心变更'),
            disabled: canEditSystem
          }"
          class="mr8"
          :disabled="!canEditSystem"
          theme="primary"
          @click="handleCreate">
          <audit-icon
            style="margin-right: 8px;font-size: 14px;"
            type="add" />
          {{ t('新建操作') }}
        </bk-button>
      </div>
      <bk-search-select
        v-model="searchKey"
        class="search-input"
        clearable
        :condition="[]"
        :data="searchData"
        :defaut-using-item="{ inputHtml: t('请选择') }"
        :placeholder="placeholder"
        style="width: 480px;"
        unique-select
        value-split-code=","
        @update:model-value="handleSearch" />
    </div>
    <bk-loading :loading="loading">
      <bk-table
        :border="['outer']"
        :columns="tableColumn"
        :data="data" />
    </bk-loading>
  </div>
  <add-action
    ref="addActionRef"
    :action-list="data"
    @add-resource-type="handleAddResourceType"
    @update-action="handleUpdateAction" />
</template>
<script setup lang="tsx">
  import _ from 'lodash';
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import MetaManageService from '@service/meta-manage';

  import SystemActionModel from '@model/meta/system-action';

  import useRequest from '@hooks/use-request';

  import addAction from './add-action/index.vue';

  import useMessage from '@/hooks/use-message';

  interface Emits {
    (e: 'updateResource'): void;
    (e: 'updateListLength', listLength: number): void;
    (e: 'addResourceType'): void;
  }
  interface Props {
    canEditSystem: boolean;
  }
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

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const route = useRoute();
  const addActionRef = ref();
  const { messageSuccess } = useMessage();

  const isSimpleSystem = computed(() => route.query.type === 'simple');

  const placeholder = computed(() => (isSimpleSystem.value
    ? t('搜索操作ID、操作事件名、风险等级、操作事件类型')
    : t('搜索操作ID、操作事件名、关联资源类型、风险等级、操作事件类型')));

  const tableColumn = computed(() => [
    {
      label: () => t('操作 ID'),
      field: () => 'action_id',
    },
    {
      label: () => t('操作事件名称'),
      render: ({ data }: {data: SystemActionModel}) => (
        data.description
          ? (<span
                class="tips"
                v-bk-tooltips={ t(data.description) }>
                {data.name}
              </span>)
          : (<span>{data.name}</span>)
      ),
    },
    // 根据 isSimpleSystem 决定是否添加关联资源类型列
    ...(isSimpleSystem.value ? [] : [{
      label: () => t('关联资源类型'),
      render: ({ data }: {data: SystemActionModel}) => (
        <>
          { (data.resource_type_ids && data.resource_type_ids.length)
            ? data.resource_type_ids.map((item, index) => (
              <div key={index}>
                { item}
              </div>
            )) : '--'
          }
        </>
      ),
    }]),
    {
      label: () => t('敏感等级'),
      render: ({ data }: {data: SystemActionModel}) => (
        <render-sensitivity-level value={data.sensitivity} />
      ),
    },
    {
      label: () => t('操作事件类型'),
      showOverflowTooltip: true,
      render: ({ data }: {data: SystemActionModel}) => data.type || '--',
    },
    {
      label: () => t('操作'),
      width: 120,
      fixed: 'right',
      render: ({ data }: {data: SystemActionModel}) => <>
        <div style="display: flex">
          <bk-button
            theme='primary'
            class='mr16'
            disabled={!props.canEditSystem}
            v-bk-tooltips={{
              content: t('暂不支持变更，请前往权限中心变更'),
              disabled: props.canEditSystem,
            }}
            onClick={() => handleEdit(data)}
            text>
            {t('编辑')}
          </bk-button>
          <audit-popconfirm
            title={t('确认删除该操作？')}
            content={t('删除操作无法撤回，请谨慎操作！')}
            class="ml8"
            confirmHandler={() => handleDelete(data)}>
            <bk-button
              disabled={!props.canEditSystem}
              v-bk-tooltips={{
                content: t('暂不支持变更，请前往权限中心变更'),
                disabled: props.canEditSystem,
              }}
              theme='primary'
              text>
              {t('删除')}
            </bk-button>
          </audit-popconfirm>
        </div>
      </>,
    },
  ]);

  const searchData = computed<SearchData[]>(() => [
    {
      name: t('操作ID'),
      id: 'action_id',
      placeholder: t('请输入资源类型'),
    },
    {
      name: t('操作事件名'),
      id: 'name__icontains',
      placeholder: t('请输入资源名称'),
    },
    // 根据 isSimpleSystem 动态决定是否添加该项
    ...(isSimpleSystem.value ? [] : [{
      name: t('关联资源类型'),
      id: 'resource_type_ids',
      placeholder: t('请输入资源操作'),
    }]),
    {
      name: t('风险等级'),
      id: 'sensitivity',
      placeholder: t('请输入敏感等级'),
    },
    {
      name: t('操作事件类型'),
      id: 'type',
      placeholder: t('请输入资源状态'),
    },
  ]);

  const searchKey = ref<Array<SearchKey>>([]);

  const {
    run: fetchSystemActionList,
    loading,
    data,
  }  = useRequest(MetaManageService.fetchSystemActionList, {
    defaultParams: {
      id: route.params.id,
    },
    defaultValue: [],
    manual: true,
  });

  // 删除操作
  const {
    run: deleteAction,
  } = useRequest(MetaManageService.deleteAction, {
    defaultValue: {},
    onSuccess: () => {
      messageSuccess(t('删除成功'));
      fetchSystemActionList({
        id: route.params.id,
      });
      emits('updateResource');
    },
  });

  // 获取操作
  // const {
  //   data: actionData,
  //   run: fetchActionByUniqueId,
  // } = useRequest(MetaManageService.fetchActionByUniqueId, {
  //   defaultValue: new SystemActionModel(),
  //   onSuccess: () => {
  //     addActionRef.value.handleOpen(false, actionData.value);
  //   },
  // });

  const handleEdit = (data: SystemActionModel) => {
    // fetchActionByUniqueId({
    //   unique_id: data.unique_id,
    // });
    addActionRef.value.handleOpen(data);
  };

  const handleDelete = (data: SystemActionModel) => {
    deleteAction({
      unique_id: data.unique_id,
    });
  };

  const handleCreate = () => {
    addActionRef.value.handleOpen();
  };

  const handleUpdateAction = () => {
    fetchSystemActionList({
      id: route.params.id,
    });
    emits('updateResource');
  };

  const handleAddResourceType = () => {
    emits('addResourceType');
  };

  const handleSearch = (keyword: Array<any>) => {
    const search = {
      action_id: '',
      name__icontains: '',
      resource_type_ids: '',
      sensitivity: '',
      type: '',
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
        const list = search.name__icontains.split(',').filter((item: string) => !!item);
        list.push(item.id);
        _.uniq(list);
        search.name__icontains = list.join(',');
        searchKey.value[index] = ({ id: 'name__icontains', name: t('操作事件名'), values: [{ id: item.id, name: item.id }] });
      }
    });
    fetchSystemActionList(search);
  };

  watch(() => data.value, (newList) => {
    emits('updateListLength', newList.length);
  }, {
    deep: true,
  });

  defineExpose({
    updateAction() {
      fetchSystemActionList({
        id: route.params.id,
      });
    },
  });
</script>
<style lang="postcss">
.access-model-operation-list {
  padding: 16px 24px;
  margin-top: 16px;
  color: #313238;
  background-color: #fff;

  .access-model-action-header {
    display: flex;
    margin-bottom: 14px;
    align-items: center;
    justify-content: space-between;
  }

  .sensitivity-tag {
    display: inline-block;
    height: 22px;
    padding: 0 10px;
    line-height: 22px;
    color: #ea3536;
    background: #feebea;
    border-radius: 2px;
  }

  .not-sensitivity-tag {
    display: inline-block;
    height: 22px;
    padding: 0 10px;
    line-height: 22px;
    color: #63656e;
    background: #f0f1f5;
    border-radius: 2px;
  }
}
</style>
