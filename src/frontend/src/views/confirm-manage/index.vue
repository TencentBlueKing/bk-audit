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
    <nl-search-box
      :key="fieldConfigKey"
      ref="searchBoxRef"
      :field-config="FieldConfig"
      risk-view-type="pending_confirm"
      @change="handleSearchChange"
      @model-value-watch="handleModelValueWatch"
      @parsing="handleParsing" />
    <div
      :key="fieldConfigKey"
      class="risk-manage-list">
      <div class="add-button">
        <bk-button
          :disabled="!selectionMeta.count"
          theme="primary"
          @click="handleBatchConfirm">
          {{ t('批量确认') }}
        </bk-button>
        <risk-export-button
          :disabled="!isExportEnabled"
          :export-fn="runExport"
          :tooltip="exportTooltip" />
      </div>
      <tdesign-list
        ref="listRef"
        :columns="tableColumns"
        :data-source="dataSource"
        enable-cross-page-select
        is-need-scene-id
        is-need-scene-params
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
    <batch-confirm-dialog
      ref="batchConfirmRef"
      @success="handleBatchConfirmSuccess" />
  </div>
</template>

<script setup lang='tsx'>
  import {
    computed,
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

  import useEventBus from '@hooks/use-event-bus';
  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';
  import useRiskBatchExport from '@hooks/use-risk-batch-export';
  import useRiskExportLimit from '@hooks/use-risk-export-limit';
  import useUrlSearch from '@hooks/use-url-search';

  import RiskExportButton from '@components/risk-export-button/index.vue';
  import Tooltips from '@components/show-tooltips-text/index.vue';
  import TdesignList from '@components/tdesign-list/index.vue';

  import NlSearchBox from '@views/risk-manage/list/components/nl-search-box/index.vue';
  import MarkRiskLabel from '@views/risk-manage/list/components/mark-risk-label.vue';
  import { useRiskColumns } from '@views/risk-manage/table-columns/risk/use-columns';

  import BatchConfirmDialog from './components/batch-confirm-dialog.vue';
  import FieldConfig from './components/config';

  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  interface ISettings {
    checked: Array<string>,
    fields: Record<string, any>[],
    size: string
  }

  const strategyTagMap = ref<Record<string, string>>({});
  const { t } = useI18n();
  const { messageWarn } = useMessage();
  const router = useRouter();
  const { getSearchParamsPost } = useUrlSearch();

  const actionColumn = {
    title: t('操作'),
    colKey: 'action',
    width: 180,
    fixed: 'right',
    cell: (h: any, { row }: { row: RiskManageModel }) => (
      <p>
        <auth-button
          text
          theme='primary'
          class='mr16'
          permission={row.permission.process_risk}
          action-id='process_risk'
          resource={row.risk_id}
          onClick={() => handleToDetail(row)}>
          {t('确认')}
        </auth-button>
        <MarkRiskLabel
          onUpdate={() => fetchList()}
          userInfo={userInfo.value}
          data={row} />
      </p>
    ),
  };

  let initTableColumns: any[] = [];
  const tableColumns = computed(() => {
    if (!initTableColumns.length) {
      initTableColumns = useRiskColumns({
        t,
        deps: { levelData, strategyTagMap, strategyList, riskStatusCommon, sceneList, handleToDetail },
        detailRouteName: 'confirmManageDetail',
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

  const defaultSettings = ['risk_id', 'title', 'event_content', 'scene_id', 'risk_level', 'tags', 'operator', 'status', 'current_operator', 'notice_users', 'strategy_id', 'event_time', 'last_operate_time', 'has_report', 'risk_label'];
  const settingsVersion = ref(0);

  const settings = computed(() => {
    void settingsVersion.value;
    const jsonStr = localStorage.getItem('audit-confirm-risk-list-setting');
    let result: string[];
    if (jsonStr) {
      try {
        const savedSettings = JSON.parse(jsonStr);
        result = savedSettings.checked && Array.isArray(savedSettings.checked)
          ? savedSettings.checked
          : defaultSettings;
      } catch (e) {
        console.error('本地设置解析失败，使用默认配置', e);
        result = defaultSettings;
      }
    } else {
      result = defaultSettings;
    }
    const sceneParams = getSceneSystemParams();
    const isAllRisks = !sceneParams.scope_id
      || sceneParams.scope_type === 'cross_scene'
      || sceneParams.scope_type === 'cross_system';
    if (isAllRisks && !result.includes('scene_id')) {
      const idx = result.indexOf('event_time');
      result.splice(idx + 1, 0, 'scene_id');
    } else if (!isAllRisks) {
      result = result.filter((key: string) => key !== 'scene_id');
    }
    return result;
  });

  const listRef = ref();
  const searchBoxRef = ref();
  const batchConfirmRef = ref();
  const searchModel = ref<Record<string, any>>({});
  const fieldConfigKey = ref(0);
  const isParsing = ref(false);
  const selectionMeta = ref({
    mode: '' as '' | 'page' | 'all',
    count: 0,
    total: 0,
    isSelectAll: false,
  });
  const dataSource = RiskManageService.fetchConfirmRiskList;

  const handleSelectionChange = (meta: typeof selectionMeta.value) => {
    selectionMeta.value = meta;
  };

  const {
    isExportEnabled,
    exportTooltip,
  } = useRiskExportLimit(selectionMeta);

  const {
    runExport,
  } = useRiskBatchExport({
    listRef,
    searchBoxRef,
    riskViewType: 'pending_confirm',
    selectionMeta,
    isExportEnabled,
  });

  const handleToDetail = (data: RiskManageModel, needToRiskContent = false) => {
    const params: Record<string, any> = {
      name: 'confirmManageDetail',
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

  const handleSettingChange = (setting: ISettings) => {
    localStorage.setItem('audit-confirm-risk-list-setting', JSON.stringify(setting));
  };

  const handleSearchChange = (value: Record<string, any>, exValue: Record<string, any>, isClear?: boolean) => {
    searchModel.value = {
      ...value,
      event_filters: exValue,
    };
    if (!isParsing.value) {
      fetchList(isClear);
    }
  };

  const handleParsing = (parsing: boolean) => {
    isParsing.value = parsing;
    if (listRef.value) {
      listRef.value.loading = parsing;
    }
  };

  const handleClearSearch = () => {
    searchBoxRef.value.clearValue();
  };

  const fetchList = (resetSearch = false) => {
    if (!listRef.value) return;
    const params = {
      risk_id: '',
      tags: '',
      start_time: '',
      end_time: '',
      strategy_id: '',
      operator: '',
      current_operator: '',
      status: '',
      risk_label: '',
      event_content: '',
      risk_level: '',
      title: '',
      notice_users: '',
      has_report: '',
    };
    const dataParams: Record<string, any> = {
      ...params,
      ...searchModel.value,
    };
    if (!dataParams.sort) {
      dataParams.sort = ['-last_operate_time', '-risk_id'];
    }
    listRef.value.fetchData(
      dataParams,
      resetSearch ? { resetSearch: true } : undefined,
    );
  };

  const handleBatchConfirm = async () => {
    if (!selectionMeta.value.count) {
      messageWarn(t('请选择要操作的数据'));
      return;
    }
    const { keys } = await listRef.value.resolveExportSelection();
    batchConfirmRef.value.show(keys.map(String));
  };

  const handleBatchConfirmSuccess = () => {
    fetchList();
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

  const {
    data: userInfo,
  } = useRequest(AccountManageService.fetchUserInfo, {
    defaultValue: new AccountModel(),
    manual: true,
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

  const {
    run: getRiskTags,
  } = useRequest(RiskManageService.fetchRiskTags, {
    defaultParams: {},
    defaultValue: [],
    onSuccess: (data) => {
      data.forEach((item) => {
        strategyTagMap.value[item.id] = item.name;
      });
    },
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
    fetchRiskLevel({
      strategy_ids: results.map(item => item.strategy_id).join(','),
    });
  };

  const handleModelValueWatch = (val: any) => {
    if (val?.strategy_id?.length) {
      getEventFields({
        strategy_ids: val.strategy_id,
      });
    } else {
      getEventFields();
    }
  };

  const { on, off } = useEventBus();
  onMounted(() => {
    getEventFields();
    getRiskTags({
      scope_id: getSceneSystemParams().scope_id,
      scope_type: getSceneSystemParams().scope_type,
    });
    on('scene-change', () => {
      fieldConfigKey.value += 1;
      settingsVersion.value += 1;
      fetchList();
    });
  });

  onUnmounted(() => {
    off('scene-change');
    fieldConfigKey.value = 0;
  });

  onBeforeRouteLeave((to, from, next) => {
    if (to.name === 'confirmManageDetail') {
      const params = getSearchParamsPost('event_filters');
      const paramsEventFilters = JSON.stringify(params.event_filters);
      const EventFiltersParams = {
        ...params,
        event_filters: paramsEventFilters,
      };
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
  .risk-manage-list {
    padding: 5px 20px;
    margin-top: 16px;
    background-color: white;

    .add-button {
      display: flex;
      align-items: center;
      gap: 8px;
      padding-bottom: 5px;
    }
  }
}
</style>
