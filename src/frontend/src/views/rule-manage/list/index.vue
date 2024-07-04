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
      class="rule-manage-wrap">
      <div class="action-header">
        <div class="btns-wrap">
          <auth-button
            action-id="create_rule"
            class="mr8"
            :permission="permissionCheckData.create_rule"
            theme="primary"
            @click="handleCreate">
            <audit-icon
              style="margin-right: 8px;font-size: 14px;"
              type="add" />
            {{ t('处理规则', 2) }}
          </auth-button>
          <auth-button
            action-id="edit_rule"
            :permission="permissionCheckData.edit_rule"
            @click="handleShowBatchPriorityIndexSlider">
            {{ t('批量调整优先级') }}
          </auth-button>
        </div>
        <bk-search-select
          v-model="searchKey"
          class="search-input"
          clearable
          :condition="[]"
          :data="searchData"
          :defaut-using-item="{ inputHtml: t('请选择') }"
          :get-menu-list="getMenuList"
          :placeholder="t('规则ID、规则名称、最近更新人、启停状态')"
          style="width: 480px;"
          unique-select
          :validate-values="validateValues"
          value-split-code=","
          @update:model-value="handleSearch" />
      </div>
      <render-list
        ref="listRef"
        class="audit-highlight-table mt16"
        :columns="tableColumn"
        :data-source="dataSource"
        :settings="settings"
        @clear-search="handleClearSearch"
        @on-setting-change="handleSettingChange"
        @request-success="handleRequestSuccess" />
    </div>
  </skeleton-loading>


  <!-- 规则详情页 -->
  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="showDetail"
    :show-footer="false"
    show-header-slot
    title="规则详情"
    :width="640">
    <template #header>
      <div
        class="flex"
        style="width: 100%;padding-right: 40px;justify-content: space-between;align-items: center;">
        <span> {{ t('规则详情') }}</span>
        <div style="display: flex;align-items: center;">
          <span
            class="mr8"
            style="margin-left: 24px;font-size: 14px;color: #63656e;">
            {{ t('启/停') }}
          </span>
          <auth-switch
            v-if="!permissionCheckData.edit_rule"
            action-id="edit_rule"
            :model-value="riskRuleDetailItem.is_enabled"
            :permission="permissionCheckData.edit_rule"
            theme="primary"
            @click="()=>handleToggle(riskRuleDetailItem)" />
          <template v-else>
            <audit-popconfirm
              :confirm-handler="()=>handleToggle(riskRuleDetailItem)"
              :confirm-text="riskRuleDetailItem.is_enabled ? t('停用') : t('启用')"
              :content="riskRuleDetailItem.is_enabled
                ? t('处理规则停用后，即使有风险命中该规则也不会按照规则制定的套餐自动处理。请确认是否停用规则？')
                : t('处理规则启用后，若有风险命中本规则会按照规则制定的套餐自动处理。请确认是否启用规则？')"
              :title="riskRuleDetailItem.is_enabled ? t('规则停用确认') : t('规则启用确认')">
              <auth-switch
                action-id="edit_rule"
                :model-value="riskRuleDetailItem.is_enabled"
                :permission="permissionCheckData.edit_rule"
                theme="primary" />
            </audit-popconfirm>
          </template>
          <auth-button
            action-id="edit_rule"
            class="mr8 ml8"
            :permission="permissionCheckData.edit_rule"
            theme="primary"
            @click="()=>handleEdit(riskRuleDetailItem)">
            {{ t('编辑') }}
          </auth-button>
          <bk-button
            class="mr8"
            @click="()=>handleShowScopeRiskDetail(riskRuleDetailItem)">
            {{ t('查看命中风险') }}
          </bk-button>

          <bk-dropdown
            :loading="deleteLoading"
            trigger="click">
            <bk-button>
              <audit-icon type="more" />
            </bk-button>
            <template #content>
              <bk-dropdown-menu>
                <bk-dropdown-item>
                  <auth-button
                    action-id="create_rule"
                    :permission="permissionCheckData.create_rule"
                    text
                    @click="()=>handleClone(riskRuleDetailItem)">
                    {{ t('克隆') }}
                  </auth-button>
                </bk-dropdown-item>
                <bk-dropdown-item>
                  <auth-button
                    v-if="!permissionCheckData.delete_rule"
                    action-id="delete_rule"
                    :permission="permissionCheckData.delete_rule"
                    text
                    @click="()=>handleDelete(riskRuleDetailItem)">
                    {{ t('删除') }}
                  </auth-button>
                  <audit-popconfirm
                    v-else
                    :confirm-handler="()=>handleDelete(riskRuleDetailItem)"
                    :content="t('删除后不可恢复')"
                    :title="t('确认删除？')">
                    <auth-button
                      action-id="delete_rule"
                      :permission="permissionCheckData.delete_rule"
                      text>
                      {{ t('删除') }}
                    </auth-button>
                  </audit-popconfirm>
                </bk-dropdown-item>
              </bk-dropdown-menu>
            </template>
          </bk-dropdown>
        </div>
      </div>
    </template>
    <div>
      <risk-rule-detail :data="riskRuleDetailItem" />
    </div>
  </audit-sideslider>

  <!-- 命中风险 -->
  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="showScopeRiskDetail"
    :show-footer="false"
    show-header-slot
    title="查看命中风险"
    :width="960">
    <template #header>
      <div>
        <span> {{ t('命中风险') }}</span>
        <span style="padding-left: 8px;margin-left: 8px;font-size: 12px;color: #979ba5;border-left: 1px solid #dcdee5;">
          {{ t('规则：') }}{{ riskScopeRiskDetailItem.name }}
        </span>
      </div>
    </template>
    <scope-risk-rule-detail :data="riskScopeRiskDetailItem" />
  </audit-sideslider>

  <!-- 批量调整优先级 -->
  <batch-priority-index-slider
    ref="batchPrioritySliderRef"
    :loading="listLoading"
    :permission-check-data="permissionCheckData"
    @refresh-list="fetchList"
    @show-detail="handleDetail" />
</template>

<script setup lang='tsx'>
  import _ from 'lodash';
  import {
    computed,
    // nextTick,
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
  import RiskRuleManageService from '@service/rule-manage';

  import RiskRuleManageModel from '@model/risk-rule/risk-rule';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import Tooltips from '@components/show-tooltips-text/index.vue';

  import getAssetsFile from '@utils/getAssetsFile';

  import BatchPriorityIndexSlider from './components/batch-priority-index-slider.vue';
  import RiskRuleDetail from './components/risk-rule-detail.vue';
  import ScopeRiskRuleDetail from './components/scope-rule-detail.vue';

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
  interface SearchData{
    name: string;
    id: string;
    children?: Array<SearchData>;
    placeholder?: string;
    multiple?: boolean;
    onlyRecommendChildren?: boolean,
  }
  const tableColumn = [
    {
      label: () => t('规则ID'),
      field: () => 'rule_id',
      sort: 'custom',
      render: ({ data }: { data: RiskRuleManageModel }) => <Tooltips data={data.rule_id}></Tooltips>,
    },
    {
      label: () => t('规则名称'),
      field: () => 'name',
      sort: 'custom',
      render: ({ data }: { data: RiskRuleManageModel }) => {
        const isNew = isNewData(data);
        return isNew ? (
            <a
              class='tooltip-btn'
              style='width: 100%;display: flex;align-items: center;'
              onClick={() => handleDetail(data)}>
              <Tooltips data={data.name } />
              <img class='table-new-tip' src={getAssetsFile('new-tip.png')}
              style='width: 30px;margin-left: 4px;'/>
            </a>
          )
          : (
            <a
              class='tooltip-btn'
              style='width: 100%;'
              onClick={() => handleDetail(data)}>
              <Tooltips data={data.name } />
            </a>
        );
      },
    },
    {
      label: () => <p>
        <audit-icon
          v-bk-tooltips={ {
            content: t('数值越大，优先级越高'),
          }}
          style="margin-right: 4px;font-size: 14px;color: #979BA5;"
          type="info-fill" />
       { t('执行优先级')}
      </p>,
      field: () => 'priority_index',
      sort: 'custom',
      render: ({ data }: { data: RiskRuleManageModel }) => <p style='text-align: right;width: 100px;'>
        {data.priority_index}
      </p>,
    },
    {
      label: () => t('最近更新人'),
      field: () => 'updated_by',
      render: ({ data }: { data: RiskRuleManageModel }) => data.updated_by || '--',
    },
    {
      label: () => t('最近更新时间'),
      field: () => 'updated_at',
      width: 180,
      sort: 'custom',
      render: ({ data }: { data: RiskRuleManageModel }) => data.updated_at || '--',
    },
    {
      label: () => t('创建人'),
      field: () => 'created_by',
      render: ({ data }: { data: RiskRuleManageModel }) => data.created_by || '--',
    },
    {
      label: () => t('创建时间'),
      field: () => 'created_at',
      width: 180,
      render: ({ data }: { data: RiskRuleManageModel }) => data.created_at || '--',
    },
    {
      label: () => t('启用/停用'),
      field: () => 'is_enabled',
      align: 'center',
      render: ({ data }: { data: RiskRuleManageModel }) => (
        permissionCheckData.value.edit_rule
          ? (
            <audit-popconfirm
              confirm-text={data.is_enabled ? t('停用') : t('启用')}
              content={data.is_enabled
                ? t('处理规则停用后，即使有风险命中该规则也不会按照规则制定的套餐自动处理。请确认是否停用规则？')
                : t('处理规则启用后，若有风险命中本规则会按照规则制定的套餐自动处理。请确认是否启用规则？')}
              title={data.is_enabled ? t('规则停用确认') : t('规则启用确认')}
              confirm-handler={() => handleToggle(data)}>
              <auth-switch
                size="small"
                action-id="edit_rule"
                model-value={data.is_enabled}
                permission={permissionCheckData.value.edit_rule}
                theme="primary"
                />
          </audit-popconfirm>
          )
          : (
          <auth-switch
          size="small"
          action-id="edit_rule"
          model-value={data.is_enabled}
          permission={permissionCheckData.value.edit_rule}
          onClick = { () => handleToggle(data)}
          theme="primary"
        />
        )
      ),
    },

    {
      label: () => t('操作'),
      width: 170,
      render: ({ data }: { data: RiskRuleManageModel }) => <p style='display: flex;align-items: center;height: 100%;'>
          <auth-button
            theme='primary'
            class='mr16'
            action-id='edit_rule'
            permission={permissionCheckData.value.edit_rule}
            onClick={() => handleEdit(data)}
            text>
            {t('编辑')}
          </auth-button>
          <bk-button
            theme='primary'
            class='mr16'
            onClick={() => handleShowScopeRiskDetail(data)}
            text>
            {t('查看命中风险')}
        </bk-button>
        <bk-dropdown trigger='click'>
            {{
            default: () => <bk-button text><audit-icon type='more' /></bk-button>,
            content: () => (
                         <bk-dropdown-menu >
                          <bk-dropdown-item >
                            <auth-button
                              text
                              action-id='create_rule'
                              permission={permissionCheckData.value.create_rule}
                              onClick={() => handleClone(data)}>
                                {t('克隆')}
                            </auth-button>
                          </bk-dropdown-item>
                          <bk-dropdown-item >
                          {
                            permissionCheckData.value.delete_rule
                              ? (
                                <audit-popconfirm
                                  title={t('确认删除？')}
                                  content={t('删除后不可恢复')}
                                  confirmHandler={() => handleDelete(data)}>
                                  <bk-button
                                    text
                                    action-id='delete_rule'>
                                      {t('删除')}
                                  </bk-button>
                                </audit-popconfirm>)
                              : (
                                <auth-button
                                  text
                                  action-id='delete_rule'
                                  permission={permissionCheckData.value.delete_rule}
                                  onClick={() => handleDelete(data)}>
                                    {t('删除')}
                                </auth-button>)
                                }
                                </bk-dropdown-item>
                        </bk-dropdown-menu>),
            }}
        </bk-dropdown>
          </p>,
    },
  ] as any[];

  const dataSource = RiskRuleManageService.fetchRuleList;
  const listRef = ref();
  const { t } = useI18n();
  const router = useRouter();
  const { messageSuccess } = useMessage();
  const { getSearchParams, removeSearchParam, replaceSearchParams } = useUrlSearch();
  let isInit = false;
  const searchData: SearchData[] = [
    {
      name: t('规则ID'),
      id: 'rule_id',
      placeholder: t('请输入规则ID'),
    },
    {
      name: t('规则名称'),
      id: 'name',
      placeholder: t('请输入规则名称'),
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
  const searchKey = ref<Array<SearchKey>>([]);
  const batchPrioritySliderRef = ref();
  const isSearching = ref(false);
  const rootRef = ref();
  const isLoading = ref(false);

  const isNeedShowDetail = ref(false);
  const isNeedShowBatchPriorityIndexSldier = ref(false);
  const tableData = ref<RiskRuleManageModel[]>([]);
  // 风险详情
  const showDetail = ref(false);
  const riskRuleDetailItem = ref(new RiskRuleManageModel());
  // 查看命中风险
  const showScopeRiskDetail = ref(false);
  const riskScopeRiskDetailItem = ref(new RiskRuleManageModel());
  const permissionCheckData = ref<Record<string, boolean>>({
    create_rule: false,
    edit_rule: false,
    // list_event: false,
    delete_rule: false,
  });
  const data = ref < RiskRuleManageModel[]>([]);
  for (let index = 0; index < 50; index++) {
    data.value.push(new RiskRuleManageModel());
  }
  const listLoading = computed(() => listRef.value?.loading);

  const initSettings = () => ({
    fields: [
      {
        label: t('规则ID'),
        field: 'rule_id',
        disabled: true,
      },
      {
        label: t('规则名称'),
        field: 'name',
        disabled: true,
      },
      {
        label: t('执行优先级'),
        field: 'priority_index',
        disabled: true,
      },
      {
        label: t('最近更新人'),
        field: 'updated_by',
      },
      {
        label: t('最近更新时间'),
        field: 'updated_at',
      },
      {
        label: t('创建人'),
        field: 'created_by',
      },
      {
        label: t('创建时间'),
        field: 'created_at',
      },
      {
        label: t('启用/停用'),
        field: 'is_enabled',
        disabled: true,
      },
    ],
    checked: ['rule_id', 'name', 'priority_index', 'updated_by', 'updated_at', 'is_enabled'],
    showLineHeight: false,
  });

  const settings = computed(() => {
    const jsonStr = localStorage.getItem('audit-rule-manage-list-setting');
    if (jsonStr) {
      const jsonSetting = JSON.parse(jsonStr);
      jsonSetting.showLineHeight = false;
      return jsonSetting;
    }
    return initSettings();
  });

  // 判断是否有全新啊
  useRequest(IamManageService.check, {
    defaultParams: {
      action_ids: 'create_rule,edit_rule,delete_rule',
    },
    defaultValue: {},
    manual: true,
    onSuccess: (data) => {
      permissionCheckData.value = data;
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
  const {
    run: toggleRiskRules,
  }  = useRequest(RiskRuleManageService.toggleRiskRules, {
    defaultValue: null,
    onSuccess(data) {
      if (!data) return;
      fetchList();
      messageSuccess(data.is_enabled ? t('启用成功') : t('停用成功'));
    },
  });
  const {
    run: deleteRiskRule,
    loading: deleteLoading,
  } = useRequest(RiskRuleManageService.deleteRiskRule, {
    defaultValue: null,
    onSuccess() {
      messageSuccess(t('删除成功'));
      showDetail.value = false;
      fetchList();
    },
  });

  const handleClearSearch = () => {
    searchKey.value = [];
    handleSearch([]);
  };
  const validateValues = async (item: Record<string, any>, value: Array<{
    id: number | string,
    name: string
  }>) => {
    if (item && item.id === 'rule_id') {
      return /^[0-9]*$/.test(`${value[0].id}`) ? true : t('规则ID只允许输入整数');
    }
    if (item && item.id === 'is_enabled') {
      const enabled = value[0].id;
      return searchData[3].children?.find(cItem => cItem.id === enabled)
        ? true
        : t('该启停状态不存在');
    }
    return true;
  };
  // 显示批量调整优先级的slider
  const handleShowBatchPriorityIndexSlider = () => {
    batchPrioritySliderRef.value.show(tableData.value);
  };
  const handleClone = (data: RiskRuleManageModel) => {
    router.push({
      name: 'riskRuleClone',
      params: {
        id: data.rule_id,
      },
    });
  };
  const handleDelete = (data: RiskRuleManageModel) => deleteRiskRule({
    id: data.rule_id,
  });
  const handleRequestSuccess = ({ results }:{results: RiskRuleManageModel[]}) => {
    tableData.value = results;
    if (isNeedShowBatchPriorityIndexSldier.value) {
      handleShowBatchPriorityIndexSlider();
      isNeedShowBatchPriorityIndexSldier.value = false;
    }
    if (isNeedShowDetail.value) {
      if (results && results.length) {
        handleDetail(results[0]);
      }
      isNeedShowDetail.value = false;
    }
    setTimeout(() => {
      results.forEach((item, index) => {
        const isNew = isNewData(item);
        setNewCreateTrHighlight(index, isNew);
      });
    }, 300);
  };

  // 判断是否是新建数据
  const isNewData = (data: RiskRuleManageModel) => {
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
  const handleSearch = (keyword: Array<any>) => {
    const search = {
      rule_id: '',
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
        // 默认输入字段后匹配规则名称
        const list = search.name.split(',').filter((item: string) => !!item);
        list.push(item.id);
        _.uniq(list);
        search.name = list.join(',');
        searchKey.value[index] = ({ id: 'name', name: t('规则名称'), values: [{ id: item.id, name: item.id }] });
      }
    });
    fetchList(search);
  };
  const getMenuList = async (item: any, keyword: string)  => {
    if (!item) {
      return searchData;
    }
    const searchItem = searchData.find(searchItem => searchItem.id === item.id);
    if (searchItem && item.id === 'updated_by') {
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

  const handleEdit = (data: RiskRuleManageModel) => {
    router.push({
      name: 'riskRuleEdit',
      params: {
        id: data.rule_id,
      },
    });
  };
  const handleShowScopeRiskDetail = (data: RiskRuleManageModel) => {
    showScopeRiskDetail.value = true;
    riskScopeRiskDetailItem.value = data;
  };
  const handleToggle = (data: RiskRuleManageModel) => toggleRiskRules({
    rule_id: data.rule_id,
    is_enabled: !data.is_enabled,
  }).then((ret) => {
    if (!ret) return;
    riskRuleDetailItem.value.is_enabled = ret.is_enabled;
  });
  const handleDetail = (data: RiskRuleManageModel) => {
    riskRuleDetailItem.value = data;
    showDetail.value = true;
  };
  const handleCreate = () => {
    router.push({
      name: 'riskRuleCreate',
    });
  };
  const handleSettingChange = (setting: ISettings) => {
    localStorage.setItem('audit-rule-manage-list-setting', JSON.stringify(setting));
  };
  const fetchList = (params = {} as Record<string, any>) => {
    if (!isInit) return;
    const filterParams = Object.keys(params).reduce((res, key) => {
      if (params[key]) res[key] = params[key];
      return res;
    }, {} as Record<string, string>);
    replaceSearchParams(filterParams);
    isSearching.value = Object.keys(filterParams).length > 0;
    listRef.value.fetchData(params);
  };


  onMounted(() => {
    const params = getSearchParams();
    if (params.batchPriorityIndex) {
      isNeedShowBatchPriorityIndexSldier.value = true;
      removeSearchParam('batchPriorityIndex');
    }
    isInit = true;
    if (params.rule_id) {
      isNeedShowDetail.value = true;
      searchKey.value.push({ id: 'rule_id', name: t('规则ID'), values: [{ id: params.rule_id, name: params.rule_id }] });
      fetchList(params);
    } else {
      fetchList();
    }
  });
</script>
<style scoped lang="postcss">
:deep(.tooltip-btn .bk-button-text) {
  width: 100% !important;

  .show-tooltips-text {
    width: 100%;
    height: 100%;
    max-width: 100%;
    text-align: left;
  }
}

.rule-table :deep(thead th) {
  background-color: #f5f7fa;
}

.rule-table :deep(.bk-table-body) {
  max-height: calc(100vh - 277px);
}

.rule-manage-wrap {
  padding: 16px;
  background: #fff;

  .action-header {
    display: flex;
    align-items: center;
    justify-content: space-between;

    .btns-wrap {
      flex: 1;
      display: flex;
      align-items: center;
    }
  }

}
</style>
