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
    name="strategyList">
    <div
      ref="rootRef"
      class="application-list-wrap">
      <div class="action-header">
        <auth-button
          action-id="create_pa"
          class="mr8"
          :loading="checkLoading"
          :permission="permissionCheckData.create_pa"
          theme="primary"
          @click="handleCreate">
          <audit-icon
            style="margin-right: 8px;font-size: 14px;"
            type="add" />
          {{ t('处理套餐') }}
        </auth-button>
        <bk-search-select
          v-model="searchKey"
          class="search-input"
          clearable
          :condition="[]"
          :data="searchData"
          :defaut-using-item="{ inputHtml: t('请选择') }"
          :get-menu-list="getMenuList"
          :placeholder="t('套餐ID、套餐名称、最近更新人、启停状态')"
          style="width: 480px;"
          unique-select
          :validate-values="validateValues"
          value-split-code=","
          @update:model-value="handleSearch" />
      </div>
      <bk-loading :loading="checkLoading">
        <render-list
          ref="listRef"
          class="audit-highlight-table mt16"
          :columns="tableColumn"
          :data-source="dataSource"
          :settings="settings"
          @clear-search="handleClearSearch"
          @on-setting-change="handleSettingChange"
          @request-success="handleRequestSuccess" />
      </bk-loading>
    </div>
  </skeleton-loading>
  <!-- 套餐详情页 -->
  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="showDetail"
    :show-footer="false"
    show-header-slot
    title="套餐详情"
    :width="640">
    <template #header>
      <div
        class="flex"
        style="width: 100%;padding-right: 40px;justify-content: space-between;align-items: center;">
        <span> {{ t('套餐详情') }}</span>
        <div style="display: flex;align-items: center;">
          <span
            class="mr8"
            style="margin-left: 24px;font-size: 14px;color: #63656e;">
            {{ t('启/停') }}
          </span>
          <auth-switch
            v-if="!permissionCheckData.edit_pa"
            action-id="edit_pa"
            :model-value="detailItem.is_enabled"
            :permission="permissionCheckData.edit_pa"
            theme="primary"
            @change="()=>handleToggle(detailItem)" />
          <template v-else>
            <audit-popconfirm
              :confirm-handler="()=>handleToggle(detailItem)"
              :content="detailItem.is_enabled
                ? t('套餐停用后，新建/编辑处理规则时不可再选择该套餐，请确认是否停用')
                : t('套餐启用后，新建/编辑处理规则时可以选择该套餐，请确认是否启用')"
              :title="detailItem.is_enabled ? t('套餐停用确认') : t('套餐启用确认')">
              <auth-switch
                action-id="edit_pa"
                :model-value="detailItem.is_enabled"
                :permission="permissionCheckData.edit_pa"
                theme="primary" />
            </audit-popconfirm>
          </template>
          <auth-button
            action-id="edit_pa"
            class="mr8 ml8"
            :permission="permissionCheckData.edit_pa"
            theme="primary"
            @click="()=>handleEdit(detailItem)">
            {{ t('编辑') }}
          </auth-button>
          <auth-button
            action-id="list_rule"
            class="mr8"
            :permission="permissionCheckData.list_rule"
            @click="()=>showRisks(detailItem)">
            {{ t('查看关联规则') }}
          </auth-button>

          <bk-dropdown>
            <bk-button>
              <audit-icon type="more" />
            </bk-button>
            <template #content>
              <bk-dropdown-menu>
                <bk-dropdown-item>
                  <auth-button
                    action-id="create_pa"
                    :permission="permissionCheckData.create_pa"
                    text
                    @click="()=>handleClone(detailItem)">
                    {{ t('克隆') }}
                  </auth-button>
                </bk-dropdown-item>
              </bk-dropdown-menu>
            </template>
          </bk-dropdown>
        </div>
      </div>
    </template>
    <process-detail :data="detailItem" />
  </audit-sideslider>


  <!-- 应用风险页 -->
  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="showScopeRiskDetail"
    :show-footer="false"
    show-header-slot
    title="查看关联规则"
    :width="640">
    <template #header>
      <div>
        <span> {{ t('查看关联规则') }}</span>
        <span style="padding-left: 8px;margin-left: 8px;font-size: 12px;color: #979ba5;border-left: 1px solid #dcdee5;">
          {{ t('套餐：') }} {{ detailItem.name || '--' }}
        </span>
      </div>
    </template>
    <scope-risk-detail :data="detailItem" />
  </audit-sideslider>
</template>

<script setup lang='tsx'>
  import _ from 'lodash';
  import {
    computed,
    onMounted,
    ref,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';
  import {
    useRouter,
  } from 'vue-router';

  import IamManageService from '@service/iam-manage';
  import MetaManageService from '@service/meta-manage';
  import ProcessApplicationManageService from '@service/process-application-manage';

  import ProcessApplicationManageModel from '@model/application/application';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import Tooltips from '@components/show-tooltips-text/index.vue';

  import ProcessDetail from './components/detail.vue';
  import ScopeRiskDetail from './components/scope-risk-detail.vue';

  // import RenderInfoBlock from '@/views/notice-group/list/components/render-info-block.vue';

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
  interface ISettings{
    checked: Array<string>,
    fields: Record<string, any>[],
    size: string
  }
  interface SearchData {
    name: string;
    id: string;
    children?: Array<SearchData>;
    placeholder?: string;
    multiple?: boolean;
    onlyRecommendChildren?: boolean,
  }
  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const { getSearchParams, replaceSearchParams } = useUrlSearch();
  const router = useRouter();
  const dataSource = ProcessApplicationManageService.fetchList;
  const isLoading = ref(false);
  const showDetail = ref(false);
  const showScopeRiskDetail = ref(false);
  const isNeedShowDetail = ref(false);

  const detailItem = ref(new ProcessApplicationManageModel());
  const searchKey = ref<Array<SearchKey>>([]);
  const rootRef = ref();
  const listRef = ref();
  const isSearching = ref(false);


  const disabledMap: Record<string, string> = {
    id: 'id',
    name: 'name',
    is_enabled: 'is_enabled',
  };
  const initSettings = () => ({
    fields: tableColumn.reduce((res, item) => {
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
    checked: ['id', 'name', 'updated_by', 'rule_count', 'updated_at', 'is_enabled'],
    showLineHeight: false,
  });
  const settings = computed(() => {
    const jsonStr = localStorage.getItem('audit-process-application-list-setting');
    if (jsonStr) {
      const jsonSetting = JSON.parse(jsonStr);
      jsonSetting.showLineHeight = false;
      return jsonSetting;
    }
    return initSettings();
  });


  const searchData: SearchData[] = [
    {
      name: t('套餐ID'),
      id: 'id',
      placeholder: t('请输入套餐ID'),
    },
    {
      name: t('套餐名称'),
      id: 'name',
      placeholder: t('请输入套餐名称'),
    },
    {
      name: t('最近更新人'),
      id: 'updated_by',
      placeholder: t('请输入最近更新人'),
    },
    {
      name: t('启停状态'),
      id: 'is_enabled',
      placeholder: t('请选择启停状态'),
      children: [
        {
          name: t('启用'),
          id: 'true',
          multiple: true,
        },
        {
          name: t('停用'),
          id: 'false',
          multiple: true,
        },
      ],
    },
  ];
  const tableColumn = [
    {
      label: () => t('套餐ID'),
      field: () => 'id',
      sort: 'custom',
      render: ({ data }: { data: ProcessApplicationManageModel }) => <Tooltips data={data.id}></Tooltips>,
    },
    {
      label: () => t('套餐名称'),
      field: () => 'name',
      sort: 'custom',
      render: ({ data }: { data: ProcessApplicationManageModel }) => (
        <a
          style='width: 100%;'
          onClick={() => handleDetail(data)}>
          <Tooltips data={ data.name} />
        </a>
      ),
    },
    {
      label: () => t('已关联规则'),
      field: () => 'rule_count',
      render: ({ data }: { data: ProcessApplicationManageModel }) => {
        if (data.rule_count) {
          return (
            <auth-button
              action-id='list_rule'
              permission={permissionCheckData.value.list_rule}
              theme='primary'
              onClick={() => showRisks(data)}
              class='mr16'
              text>
                  { t('查看关联规则')}：{data.rule_count}
            </auth-button>
          );
        }
        return <span>{ t('查看关联规则')}：{data.rule_count}</span>;
      },
    },
    {
      label: () => t('最近更新人'),
      field: () => 'updated_by',
      render: ({ data }: { data: ProcessApplicationManageModel }) => data.updated_by || '--',
    },
    {
      label: () => t('最近更新时间'),
      field: () => 'updated_at',
      width: 180,
      sort: 'custom',
      render: ({ data }: { data: ProcessApplicationManageModel }) => data.updated_at || '--',
    },
    {
      label: () => t('创建人'),
      field: () => 'created_by',
      width: 180,
      render: ({ data }: { data: ProcessApplicationManageModel }) => data.created_by || '--',
    },
    {
      label: () => t('创建时间'),
      field: () => 'created_at',
      width: 180,
      render: ({ data }: { data: ProcessApplicationManageModel }) => data.created_at || '--',
    },
    {
      label: () => t('启用/停用'),
      field: () => 'is_enabled',
      align: 'center',
      render: ({ data }: { data: ProcessApplicationManageModel }) => (
        permissionCheckData.value.edit_pa
          ? (
            <audit-popconfirm
              content={data.is_enabled
                ? t('套餐停用后，新建/编辑处理规则时不可再选择该套餐，请确认是否停用')
                : t('套餐启用后，新建/编辑处理规则时可以选择该套餐，请确认是否启用')}
              title={data.is_enabled ? t('套餐停用确认') : t('套餐启用确认')}
              confirm-handler={() => handleToggle(data)}>
            <auth-switch
              action-id="edit_pa"
              permission={permissionCheckData.value.edit_pa}
              model-value={data.is_enabled}
              theme="primary"
              size="small"
              />
          </audit-popconfirm>
         )
          : (
          <auth-switch
          size="small"
          action-id="edit_pa"
          permission={permissionCheckData.value.edit_pa}
          model-value={data.is_enabled}
          onClick={() => handleToggle(data)}
          theme="primary"
          />
        )
      ),
    },

    {
      label: () => t('操作'),
      width: 170,
      render: ({ data }: { data: ProcessApplicationManageModel }) => <p style='display: flex;align-items: center;height: 100%;'>
      <auth-button
        theme='primary'
        class='mr16'
        permission={permissionCheckData.value.edit_pa}
        action-id='edit_pa'
        onClick={() => handleEdit(data)}
        text>
        {t('编辑')}
      </auth-button>
      <bk-dropdown trigger='click'>
        {{
          default: () => <bk-button text><audit-icon type='more' /></bk-button>,
          content: () => (
            <bk-dropdown-menu >
              <bk-dropdown-item >
                <auth-button
                  permission={permissionCheckData.value.create_pa}
                  onClick={() => handleClone(data)}
                  text
                  action-id='create_pa'
                >
                  {t('克隆')}
                </auth-button>
              </bk-dropdown-item>
            </bk-dropdown-menu>),
        }}
      </bk-dropdown>
    </p>,
    },
  ] as any[];


  const permissionCheckData = ref<Record<string, boolean>>({
    create_pa: false,
    edit_pa: false,
  });

  const {
    loading: checkLoading,
  } = useRequest(IamManageService.check, {
    defaultParams: {
      action_ids: 'create_pa,edit_pa,list_rule',
    },
    defaultValue: {},
    manual: true,
    onSuccess: (data) => {
      permissionCheckData.value = data;
    },
  });
  const {
    run: toggleApplication,
  } = useRequest(ProcessApplicationManageService.toggleApplication, {
    defaultValue: null,
    onSuccess() {
      fetchList();
      const enabled = detailItem.value.is_enabled;
      messageSuccess(!enabled ? t('启用成功') : t('停用成功'));
      detailItem.value.is_enabled = !enabled;
    },
  });
  // 人员列表
  const {
    run: fetchUserList,
  } = useRequest(MetaManageService.fetchUserList, {
    defaultParams: {
      page: 1,
      page_size: 30,
      fuzzy_lookups: '',
    },
    defaultValue: {
      count: 0,
      results: [],
    },
  });


  const handleSettingChange = (setting: ISettings) => {
    localStorage.setItem('audit-process-application-list-setting', JSON.stringify(setting));
  };
  const handleRequestSuccess = ({ results }:{results: ProcessApplicationManageModel[]}) => {
    if (results.length && isNeedShowDetail.value) {
      handleDetail(results[0]);
      isNeedShowDetail.value = false;
    }
  };
  const validateValues = async (item: Record<string, any>, value: Array<{
    id: number | string,
    name: string
  }>) => {
    if (item && item.id === 'id') {
      return /^[0-9]*$/.test(`${value[0].id}`) ? true : t('套餐ID只允许输入整数');
    }
    if (item && item.id === 'is_enabled') {
      const enabled = value[0].id;
      return searchData[3].children?.find(cItem => cItem.id === enabled)
        ? true
        : t('该启停状态不存在');
    }
    return true;
  };
  const handleClearSearch = () => {
    searchKey.value = [];
    handleSearch([]);
  };
  const fetchList = (params = {} as Record<string, any>) => {
    const filterParams = Object.keys(params).reduce((res, key) => {
      if (params[key]) res[key] = params[key];
      return res;
    }, {} as Record<string, string>);
    isSearching.value = Object.keys(filterParams).length > 0;
    replaceSearchParams(filterParams);
    listRef.value.fetchData(params);
  };
  const getMenuList = async (item: any, keyword: string) => {
    if (!item) {
      return searchData;
    }
    const searchItem = searchData.find(searchItem => searchItem.id === item.id);
    if (searchItem && (item.id === 'updated_by')) {
      if (keyword) {
        const userList = await fetchUserList({
          fuzzy_lookups: keyword,
        });
        searchItem.children = userList.results.map(item => ({
          id: item.username,
          name: `${item.username}(${item.display_name})`,
        }));
      } else searchItem.children = [];
    }
    return searchData.find(searchItem => searchItem.id === item.id)?.children as [];
  };
  const handleSearch = (keyword: Array<any>) => {
    const search = {
      id: '',
      name: '',
      updated_by: '',
      is_enabled: '',
    } as Record<string, any>;
    keyword.forEach((item: SearchKey, index) => {
      if (item.values) {
        const value = item.values.map(item => item.id).join(',');
        const list = search[item.id].split(',').filter((item: string) => !!item);
        list.push(value);
        _.uniq(list);
        search[item.id] = list.join(',');
      } else {
        // 默认输入字段后匹配套餐名字
        const list = search.name.split(',').filter((item: string) => !!item);
        list.push(item.id);
        _.uniq(list);
        search.name = list.join(',');
        searchKey.value[index] = ({ id: 'name', name: t('套餐名称'), values: [{ id: item.id, name: item.id }] });
      }
    });
    fetchList(search);
  };


  // 查看命中风险
  const showRisks = (item: ProcessApplicationManageModel) => {
    detailItem.value = item;
    showScopeRiskDetail.value = true;
  };
  const handleToggle = (item: ProcessApplicationManageModel) => {
    detailItem.value = item;
    return toggleApplication({
      id: item.id,
      is_enabled: !item.is_enabled,
    });
  };
  const handleDetail = (item: ProcessApplicationManageModel) => {
    detailItem.value = item;
    showDetail.value = true;
  };
  const handleClone = (item: ProcessApplicationManageModel) => {
    router.push({
      name: 'processApplicationClone',
      params: {
        id: item.id,
      },
    });
  };
  const handleEdit = (item: ProcessApplicationManageModel) => {
    router.push({
      name: 'processApplicationEdit',
      params: {
        id: item.id,
      },
    });
  };
  const handleCreate = () => {
    router.push({
      name: 'processApplicationCreate',
    });
  };

  onMounted(() => {
    const params = getSearchParams();
    if (params.id) {
      isNeedShowDetail.value = true;
      searchKey.value.push({ id: 'id', name: t('套餐ID'), values: [{ id: params.id, name: params.id }] });
    }
    fetchList({
      id: params.id,
    });
  });
</script>
<style scoped lang="postcss">
:deep(.bk-button-text) {
  width: 100% !important;

  .show-tooltips-text {
    width: 100%;
    max-width: 100%;
    text-align: left;
  }
}

.process-table :deep(thead th) {
  background-color: #f5f7fa;
}

.process-table :deep(.bk-table-body) {
  max-height: calc(100vh - 277px);
}

.application-list-wrap {
  padding: 16px;
  background: #fff;

  .action-header {
    display: flex;
    align-items: center;
    justify-content: space-between;

  }
}
</style>
