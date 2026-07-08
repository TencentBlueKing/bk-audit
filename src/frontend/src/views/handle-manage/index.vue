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
  <div class="risk-manage-list-page-wrap">
    <search-box
      ref="searchBoxRef"
      :export-disabled="!isExportEnabled"
      :export-request="runExport"
      :export-tooltip="exportTooltip"
      :field-config="FieldConfig"
      is-export
      is-reassignment
      @batch="handleBatch"
      @change="handleSearchChange"
      @change-table-height="handleChangeTableHeight"
      @model-value-watch="handleModelValueWatch" />
    <div class="risk-manage-list">
      <tdesign-list
        ref="listRef"
        :columns="tableColumns"
        :data-source="dataSource"
        enable-cross-page-select
        need-empty-search-tip
        row-key="risk_id"
        :search-params="searchModel"
        secondary-sort-field="-event_time"
        :settings="settings"
        @clear-search="handleClearSearch"
        @on-setting-change="handleSettingChange"
        @request-success="handleRequestSuccess"
        @selection-change="handleSelectionChange" />
    </div>

    <bk-dialog
      v-model:is-show="isShow"
      theme="primary"
      :title="t('批量转单')"
      @closed="handleClosed"
      @confirm="handleConfirm">
      <audit-form
        ref="formRef"
        form-type="vertical"
        :model="formData"
        :rules="rules">
        <bk-form-item
          :label="t('转单人员')"
          property="new_operators"
          required>
          <audit-user-selector-tenant
            v-model="formData.new_operators"
            allow-create
            :placeholder="t('请输入人员')" />
        </bk-form-item>
        <bk-form-item
          :label="t('处理说明')"
          property="description"
          required>
          <bk-input
            v-model.trim="formData.description"
            :maxlength="1000"
            :placeholder="t('请输入')"
            show-word-limit
            style="resize: none;"
            type="textarea" />
        </bk-form-item>
      </audit-form>
    </bk-dialog>
  </div>
</template>

<script setup lang='tsx'>
  import {
    computed,
    nextTick,
    onMounted,
    onUnmounted,
    ref,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';
  import {
    onBeforeRouteLeave,
    useRouter,
  } from 'vue-router';

  import AccountManageService from '@service/account-manage';
  import RiskManageService from '@service/risk-manage';
  import SceneManageService from '@service/scene-manage';
  import StrategyManageService from '@service/strategy-manage';

  import AccountModel from '@model/account/account';
  import type RiskManageModel from '@model/risk/risk';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';
  import { createRiskExportRequest } from '@hooks/use-risk-batch-export';
  import useRiskExportLimit from '@hooks/use-risk-export-limit';
  import useUrlSearch from '@hooks/use-url-search';

  import SearchBox from '@components/search-box/index.vue';
  import Tooltips from '@components/show-tooltips-text/index.vue';
  import TdesignList from '@components/tdesign-list/index.vue';

  import MarkRiskLabel from '@views/risk-manage/list/components/mark-risk-label.vue';
  import { useRiskColumns } from '@views/risk-manage/table-columns/risk/use-columns';

  import FieldConfig from './components/config';

  const dataSource = RiskManageService.fetchTodoRiskList;
  interface ISettings{
    checked: Array<string>,
    fields: Record<string, any>[],
    size: string
  }

  const { messageWarn, messageSuccess } = useMessage();

  const strategyTagMap = ref<Record<string, string>>({});
  const { t } = useI18n();
  const router = useRouter();
  const { getSearchParamsPost } = useUrlSearch();
  const isShow = ref(false);
  const actionColumn = {
    title: t('操作'),
    colKey: 'action',
    width: 180,
    fixed: 'right',
    cell: (h: any, { row }: { row: RiskManageModel }) => <p>
      <auth-button
        text
        theme='primary'
        class='mr16'
        permission={row.permission.process_risk || row.current_operator.includes(userInfo.value.username)}
        action-id='process_risk'
        resource={row.risk_id}
        onClick={() => handleToDetail(row)}>
        {t('处理')}
      </auth-button>
      {
        row.status === 'auto_process'
          ? <bk-button text theme='primary'
            class="is-disabled"
            v-bk-tooltips={{
              content: row.risk_label === 'normal'
                ? t('"套餐处理中"的风险单暂时不支持直接标记误报；请点开风险单详情，终止套餐或等套餐执行完毕后再标记误报。')
                : t('"套餐处理中"的风险单暂时不支持直接解除误报；请点开风险单详情，终止套餐或等套餐执行完毕后再标记误报。'),
            }}>
            {row.risk_label === 'normal' ? t('标记误报') : t('解除误报')}
          </bk-button>
          : <MarkRiskLabel
            onUpdate={() => fetchList()}
            userInfo={userInfo.value}
            data={row} />
      }
      <bk-dropdown
        style="margin-left: 8px">
        {{
          default: () => <bk-button text>
            <audit-icon type="more" />
          </bk-button>,
          content: () => (
            <bk-dropdown-menu>
              <bk-dropdown-item>
                <auth-button
                  style="width: 100%;"
                  actionId="edit_risk_v2"
                  permission={row.permission.edit_risk_v2}
                  resource={row.strategy_id}
                  onClick={() => handleGenerateReport(row)}
                  text>
                  {row.has_report ? t('编辑调查报告') : t('创建调查报告')}
                </auth-button>
              </bk-dropdown-item>
            </bk-dropdown-menu>
          ),
        }}
      </bk-dropdown>
    </p>,
  };

  // 根据 event_filters 动态添加关联事件列，插入到操作列之前
  let initTableColumns: any[] = [];
  const tableColumns = computed(() => {
    if (!initTableColumns.length) {
      initTableColumns = useRiskColumns({
        deps: { levelData, strategyTagMap, strategyList, riskStatusCommon, sceneList, handleToDetail },
        detailRouteName: 'handleManageDetail',
        appendColumns: [actionColumn],
      });
    }
    const eventFilters = searchModel.value?.event_filters;
    if (!eventFilters || !Array.isArray(eventFilters) || eventFilters.length === 0) {
      return initTableColumns;
    }
    const actionIndex = initTableColumns.findIndex((c: any) => c.colKey === 'action');
    const beforeAction = actionIndex >= 0 ? initTableColumns.slice(0, actionIndex) : initTableColumns;
    const afterAction = actionIndex >= 0 ? initTableColumns.slice(actionIndex) : [];
    const eventColumns = eventFilters
      .filter((f: any) => f && typeof f.field === 'string')
      .map((f: any) => ({
        title: f.display_name || f.field,
        colKey: `event_data.${f.field}`,
        minWidth: 120,
        ellipsis: true,
        sortType: 'all' as const,
        sorter: true,
        cell: (h: any, { row }: { row: any }) => <Tooltips data={row.event_data?.[f.field] ?? '--'} />,
      }));
    return [...beforeAction, ...eventColumns, ...afterAction];
  });

  const listRef = ref();
  const searchBoxRef = ref();
  const searchModel = ref<Record<string, any>>({});
  const selectionMeta = ref({
    mode: '' as '' | 'page' | 'all',
    count: 0,
    total: 0,
    isSelectAll: false,
  });

  const handleSelectionChange = (meta: typeof selectionMeta.value) => {
    selectionMeta.value = meta;
  };

  const {
    isExportEnabled,
    exportTooltip,
  } = useRiskExportLimit(selectionMeta);

  const runExport = createRiskExportRequest({
    listRef,
    searchBoxRef,
    riskViewType: 'todo',
    selectionMeta,
  });

  // 默认的可配置列键
  const defaultSettings = ['risk_id', 'title', 'event_content', 'risk_level', 'tags', 'operator', 'status', 'current_operator', 'notice_users', 'strategy_id', 'event_time', 'last_operate_time', 'has_report', 'risk_label'];

  // 从 localStorage 读取保存的设置
  const settings = computed(() => {
    const jsonStr = localStorage.getItem('audit-handle-risk-list-setting');
    if (jsonStr) {
      try {
        const savedSettings = JSON.parse(jsonStr);
        // 如果保存的设置中有 checked 字段，使用它；否则使用默认设置
        return savedSettings.checked && Array.isArray(savedSettings.checked)
          ? savedSettings.checked
          : defaultSettings;
      } catch (e) {
        console.error('本地设置解析失败，使用默认配置', e);
        return defaultSettings;
      }
    }
    return defaultSettings;
  });
  // 批量操作
  const {
    run: batchTransRisk,
  } = useRequest(RiskManageService.batchTransRisk, {
    defaultValue: [],
    onSuccess() {
      messageSuccess(t('转单成功'));
    },
  });

  const formData = ref<Record<string, any>>({
    new_operators: [],
    description: '',
  });
  const handleGenerateReport = (data: RiskManageModel) => {
    router.push({
      name: 'riskManageDetail',
      params: {
        riskId: data.risk_id,
      },
      query: {
        openEditReport: data.has_report ? 'true' : 'false',
      },
    });
  };
  const formRef = ref();
  const rules = ref<Record<string, any>>({});
  const handleConfirm = () => {
    formRef.value.validate().then(async () => {
      const keys = await listRef.value?.resolveSelectedRowKeys?.() || [];
      if (!keys.length) {
        messageWarn(t('请选择要操作的数据'));
        return;
      }
      batchTransRisk({
        risk_ids: keys.map((id: string | number) => String(id)),
        new_operators: formData.value.new_operators,
        description: formData.value.description,
      }).then(() => {
        isShow.value = false;
        handleClosed();
        fetchList();
      });
    });
  };
  const handleClosed = () => {
    formRef.value?.clearValidate();
    formData.value = {
      new_operators: [],
      description: '',
    };
  };
  // 批量操作
  const handleBatch = async () => {
    const keys = await listRef.value?.resolveSelectedRowKeys?.() || [];
    if (!keys.length) {
      messageWarn(t('请选择要操作的数据'));
      return;
    }
    isShow.value = true;
    nextTick(() => {
      formRef.value.clearValidate();
    });
  };
  // 获取标签列表
  useRequest(RiskManageService.fetchRiskTags, {
    defaultParams: {
      noNeedSceneParams: true,
    },
    defaultValue: [],
    manual: true,
    onSuccess: (data) => {
      data.forEach((item) => {
        strategyTagMap.value[item.id] = item.name;
      });
    },
  });
  const {
    data: riskStatusCommon,
  } = useRequest(RiskManageService.fetchRiskStatusCommon, {
    manual: true,
    defaultValue: [],
  });
  const {
    data: strategyList,
  } = useRequest(StrategyManageService.fetchAllStrategyList, {
    manual: true,
    defaultValue: [],
  });
  // 获取userinfo
  const {
    data: userInfo,
  } = useRequest(AccountManageService.fetchUserInfo, {
    defaultValue: new AccountModel(),
    manual: true,
  });


  const {
    data: sceneList,
  } = useRequest(SceneManageService.fetchSceneAll, {
    manual: true,
    defaultValue: [],
  });
  const {
    data: levelData,
    run: fetchRiskLevel,
  } = useRequest(StrategyManageService.fetchRiskLevel, {
    defaultValue: {},
  });

  const handleRequestSuccess = ({ results }: { results: Array<RiskManageModel> }) => {
    if (!results.length) return;
    // 获取对应风险等级
    fetchRiskLevel({
      strategy_ids: results.map(item => item.strategy_id).join(','),
    });
  };


  const handleSettingChange = (setting: ISettings) => {
    localStorage.setItem('audit-handle-risk-list-setting', JSON.stringify(setting));
  };

  const handleToDetail = (data: RiskManageModel, needToRiskContent = false) => {
    const params: Record<string, any> = {
      name: 'handleManageDetail',
      params: {
        riskId: data.risk_id,
      },
      query: {
        tab: 'handleRisk',
      },
    };
    if (needToRiskContent) {
      params.query.scrollToContent = 1;
    }
    router.push(params);
  };
  // 搜索
  const handleSearchChange = (value: Record<string, any>, exValue:  Record<string, any>, isClear?: boolean) => {
    searchModel.value = {
      ...value,
      event_filters: exValue };
    listRef.value?.initTableHeight?.();
    fetchList(isClear);
  };
  const handleChangeTableHeight = () => {
    nextTick(() => {
      listRef.value?.initTableHeight?.();
    });
  };
  const handleClearSearch = () => {
    searchBoxRef.value.clearValue();
  };
  const fetchList = (resetSearch = false) => {
    if (!listRef.value) return;
    const params = {
      risk_id: '',
      tags: '',
      scene_id: '',
      start_time: '',
      end_time: '',
      strategy_id: '',
      operator: '',
      status: '',
      event_content: '',
      risk_level: '',
      title: '',
      notice_users: '',
    };
    const dataParams: Record<string, any> = {
      ...params,
      ...searchModel.value,
    };
    // 如果没有 sort 参数，设置默认排序
    if (!dataParams.sort) {
      dataParams.sort = ['-risk_level', '-event_time', '-risk_id'];
    }
    // use_bkbase 参数已移除，由 event_filters 自动决定
    listRef.value.fetchData(
      dataParams,
      resetSearch ? { resetSearch: true } : undefined,
    );
  };

  const {
    run: getEventFields,
  } = useRequest(RiskManageService.fetchEventFields, {
    defaultValue: [],
    onSuccess: (data) => {
      const eventFields = data.map((item: any) => ({
        ...item,
      }));
      searchBoxRef.value?.initSelectedItems(eventFields);
    },
  });
  const handleModelValueWatch = (val: any) => {
    if (val?.strategy_id?.length) {
      getEventFields({
        strategy_ids: val.strategy_id,
      });
    } else {
      getEventFields();
    }
  };
  onMounted(() => {
    getEventFields();
  });
  onUnmounted(() => {
    // clearTimeout(timeout);
  });

  onBeforeRouteLeave((to, from, next) => {
    if (to.name === 'handleManageDetail') {
      const params = getSearchParamsPost('event_filters');
      const paramsEventFilters = JSON.stringify(params.event_filters);
      const EventFiltersParams = {
        ...params,
        event_filters: paramsEventFilters,
      };
      // 保存当前查询参数到目标路由的 query 中
      // eslint-disable-next-line no-param-reassign
      to.query = {
        ...to.query,
        ...EventFiltersParams,
      };
    }
    next();
  });
</script>
<style lang='postcss'>
.risk-manage-list-page-wrap {
  padding-bottom: 44px;

  .risk-manage-list {
    margin-top: 16px;
    background-color: white;
  }

}

.risk-label-status {
  padding: 1px 8px;
  font-size: 12px;
  color: #14a568;
  background-color: #e4faf0;
  border: 1px solid rgb(20 165 104 / 30%);
  border-radius: 11px;
}

.risk-label-status.misreport {
  color: #ea3536;
  background: #fedddc99;
  border: 1px solid #ea35364d;
}
</style>
