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
      :key="fieldConfigKey"
      ref="searchBoxRef"
      :field-config="FieldConfig"
      @change="handleSearchChange"
      @change-table-height="handleChangeTableHeight"
      @model-value-watch="handleModelValueWatch" />
    <div
      :key="fieldConfigKey"
      class="risk-manage-list">
      <div class="add-button">
        <bk-button
          v-bk-tooltips="{
            content: t('跨场景不支持新增风险'),
            disabled: getSceneSystemParams().scope_type !== 'cross_scene',
          }"
          :disabled="getSceneSystemParams().scope_type === 'cross_scene'"
          theme="primary"
          @click="handleAddRisk">
          <audit-icon
            class="add-icon"
            type="add" />
          {{ t('新增风险') }}
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
        is-need-scene-params
        need-empty-search-tip
        :row-class-name="getRowClassName"
        row-key="risk_id"
        :search-params="searchModel"
        secondary-sort-field="-event_time"
        :settings="settings"
        @clear-search="handleClearSearch"
        @on-setting-change="handleSettingChange"
        @request-success="handleRequestSuccess"
        @selection-change="handleSelectionChange" />
    </div>
  </div>
  <add-risk
    ref="addRiskRef"
    @add-success="handleAddRiskSuccess" />
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
    useRoute,
    useRouter,
  } from 'vue-router';

  import AccountManageService from '@service/account-manage';
  import RiskManageService from '@service/risk-manage';
  import SceneManageService from '@service/scene-manage';
  import StrategyManageService from '@service/strategy-manage';

  import AccountModel from '@model/account/account';
  import type RiskManageModel from '@model/risk/risk';

  import useEventBus from '@hooks/use-event-bus';
  import useRequest from '@hooks/use-request';
  import useRiskBatchExport from '@hooks/use-risk-batch-export';
  import useRiskExportLimit from '@hooks/use-risk-export-limit';

  import RiskExportButton from '@components/risk-export-button/index.vue';
  import useUrlSearch from '@hooks/use-url-search';

  import SearchBox from '@components/search-box/index.vue';
  import Tooltips from '@components/show-tooltips-text/index.vue';
  import TdesignList from '@components/tdesign-list/index.vue';

  import addRisk from '@views/risk-manage/list/add-risk/index.vue';
  import MarkRiskLabel from '@views/risk-manage/list/components/mark-risk-label.vue';
  import { useRiskColumns } from '@views/risk-manage/table-columns/risk/use-columns';

  import FieldConfig from './components/config';

  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  interface ISettings {
    checked: Array<string>,
    fields: Record<string, any>[],
    size: string
  }

  const strategyTagMap = ref<Record<string, string>>({});
  const { t } = useI18n();
  const router = useRouter();
  const route = useRoute();
  const { getSearchParamsPost } = useUrlSearch();
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
        detailRouteName: 'sceneRiskManageDetail',
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

  // 默认的可配置列键
  const defaultSettings = ['risk_id', 'title', 'event_content', 'risk_level', 'tags', 'operator', 'status', 'current_operator', 'notice_users', 'strategy_id', 'event_time', 'last_operate_time', 'has_report', 'risk_label'];

  // 用于在场景切换时强制刷新 settings 计算属性
  const settingsVersion = ref(0);

  // 从 localStorage 读取保存的设置
  const settings = computed(() => {
    // 强制依赖 settingsVersion，场景切换时触发重新计算
    void settingsVersion.value;
    const jsonStr = localStorage.getItem('audit-scene-risk-list-setting');
    let result: string[];
    if (jsonStr) {
      try {
        const savedSettings = JSON.parse(jsonStr);
        // 如果保存的设置中有 checked 字段，使用它；否则使用默认设置
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
    // 选择具体场景时，默认不展示所属场景(scene_id)列；
    // 选择所有风险(cross_scene/cross_system)时，默认勾选 scene_id
    const sceneParams = getSceneSystemParams();
    const isAllRisks = !sceneParams.scope_id
      || sceneParams.scope_type === 'cross_scene'
      || sceneParams.scope_type === 'cross_system';
    if (isAllRisks && !result.includes('scene_id')) {
      // 在 event_time 之后插入 scene_id，保持合理顺序
      const idx = result.indexOf('event_time');
      result.splice(idx + 1, 0, 'scene_id');
    } else if (!isAllRisks) {
      result = result.filter((key: string) => key !== 'scene_id');
    }
    return result;
  });
  const listRef = ref();
  const addRiskRef = ref();
  const searchBoxRef = ref();
  const searchModel = ref<Record<string, any>>({});
  const fieldConfigKey = ref(0);
  const newAddedRiskIds = ref<string[]>([]);
  const selectionMeta = ref({
    mode: '' as '' | 'page' | 'all',
    count: 0,
    total: 0,
    isSelectAll: false,
  });
  const dataSource = RiskManageService.fetchRiskList;

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
    riskViewType: 'scene',
    selectionMeta,
    isExportEnabled,
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

  const handleToDetail = (data: RiskManageModel, needToRiskContent = false) => {
    const params: Record<string, any> = {
      name: 'processedManageDetail',
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
    localStorage.setItem('audit-scene-risk-list-setting', JSON.stringify(setting));
  };

  const handleSearchChange = (value: Record<string, any>, exValue: Record<string, any>) => {
    searchModel.value = {
      ...value,
      event_filters: exValue,
    };
    listRef.value?.initTableHeight?.();
    fetchList();
  };
  const handleChangeTableHeight = () => {
    nextTick(() => {
      listRef.value?.initTableHeight?.();
    });
  };

  const handleClearSearch = () => {
    searchBoxRef.value.clearValue();
  };

  const fetchList = () => {
    if (!listRef.value) return;
    const params = {
      risk_id: '',
      tags: '',
      start_time: '',
      end_time: '',
      strategy_id: route.query.strategy_id || '',
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
    // 默认排序：按最后处理时间倒序，其次按风险ID倒序
    if (!dataParams.sort) {
      dataParams.sort = ['-last_operate_time', '-risk_id'];
    }
    listRef.value.fetchData(dataParams);
  };

  // 新增风险
  const handleAddRisk = () => {
    addRiskRef.value.show();
  };
  // 新增风险成功
  const handleAddRiskSuccess = () => {
    // 记录新增的风险ID，用于高亮显示
    const riskIds = sessionStorage.getItem('addEventRiskIds');
    if (riskIds) {
      newAddedRiskIds.value = JSON.parse(riskIds);
    }
    searchBoxRef.value.clearValue();
    fetchList();
  };

  // 行样式：新增的风险行显示绿色底色
  const getRowClassName = (row: Record<string, any>) => {
    if (newAddedRiskIds.value.includes(String(row.risk_id))) {
      return 'new-row';
    }
    return '';
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

  // 获取标签列表
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
    // 获取对应风险等级
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

  // 监听场景切换事件
  const { on, off } = useEventBus();
  onMounted(() => {
    // 页面刷新后重置新增风险ID高亮状态
    sessionStorage.removeItem('addEventRiskIds');
    newAddedRiskIds.value = [];
    getEventFields();
    getRiskTags({
      scope_id: getSceneSystemParams().scope_id,
      scope_type: getSceneSystemParams().scope_type,
    });
    on('scene-change', () => {
      fieldConfigKey.value += 1;
      // 场景切换时刷新表格列设置（所属场景列的显示/隐藏随场景变化）
      settingsVersion.value += 1;
      fetchList();
    });
  });

  onUnmounted(() => {
    off('scene-change');
    fieldConfigKey.value = 0;
  });


  onBeforeRouteLeave((to, from, next) => {
    if (to.name === 'processedManageDetail') {
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
  .risk-manage-list {
    padding: 5px 20px;
    margin-top: 16px;
    background-color: white;

    .add-button {
      display: flex;
      align-items: center;
      gap: 8px;
      padding-bottom: 5px;

      .add-icon {
        margin-right: 5px;
        font-size: 12px;
      }
    }
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
