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
      ref="searchBoxRef"
      :field-config="FieldConfig"
      is-export
      :scenes="nlSearchBoxScenes"
      @change="handleSearchChange"
      @export="handleExport"
      @model-value-watch="handleModelValueWatch"
      @parsing="handleParsing" />
    <ai-analyzes
      ref="aiAnalyzesRef"
      :condition-tags="conditionTags"
      :search-params="searchModel"
      :total="totalCount">
      <template #toolbar-before-analyze>
        <bk-button
          theme="primary"
          @click="handleAddRisk">
          <audit-icon
            class="add-icon"
            type="add" />
          {{ t('新增风险') }}
        </bk-button>
      </template>
      <template #toolbar-after-analyze>
        <bk-button
          outline
          @click="handleExport">
          {{ t('批量导出') }}
        </bk-button>
      </template>
      <tdesign-list
        ref="listRef"
        :columns="tableColumns"
        :data-source="dataSource"
        need-empty-search-tip
        :row-class-name="getRowClassName"
        row-key="risk_id"
        :search-params="searchModel"
        secondary-sort-field="-event_time"
        :settings="settings"
        @clear-search="handleClearSearch"
        @on-setting-change="handleSettingChange"
        @request-success="handleRequestSuccess" />
    </ai-analyzes>
  </div>
  <add-risk
    ref="addRiskRef"
    use-all-strategy-list
    @add-success="handleAddRiskSuccess" />
</template>

<script setup lang='tsx'>
  import dayjs from 'dayjs';
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
  import useUrlSearch from '@hooks/use-url-search';

  import EditTag from '@components/edit-box/tag.vue';
  import Tooltips from '@components/show-tooltips-text/index.vue';
  import TdesignList from '@components/tdesign-list/index.vue';

  import { RISK_STATUS_TAG_MAP } from '@views/risk-manage/constants';
  import { useRiskColumns } from '@views/risk-manage/table-columns/risk/use-columns';

  import addRisk from './add-risk/index.vue';
  import aiAnalyzes from './components/ai-analyzes-tip/index.vue';
  import FieldConfig from './components/config';
  import MarkRiskLabel from './components/mark-risk-label.vue';
  import NlSearchBox from './components/nl-search-box/index.vue';

  const dataSource = RiskManageService.fetchRiskList;

  interface ISettings {
    checked: Array<string>,
    fields: Record<string, any>[],
    size: string
  }

  const { messageWarn } = useMessage();
  const strategyTagMap = ref<Record<string, string>>({});
  const { t } = useI18n();
  const { getSearchParamsPost } = useUrlSearch();
  const router = useRouter();
  const aiAnalyzesRef = ref<InstanceType<typeof aiAnalyzes> | null>(null);
  let timeout: number | undefined = undefined;
  const statusToMap = RISK_STATUS_TAG_MAP;

  const actionColumn = {
    title: t('操作'),
    colKey: 'action',
    width: 180,
    fixed: 'right',
    cell: (h: any, { row }: { row: RiskManageModel }) => (
      row.status === 'stand_by'
        ? <div>
          <bk-button text class='mr16'>--</bk-button>
        </div>
        : (<p>
        {
          ['for_approve', 'auto_process'].includes(row.status)
            ? (
              <bk-button
                v-bk-tooltips={t('当前状态不支持人工处理')}
                text
                theme='primary'
                class='mr16 is-disabled'>
                {t('处理')}
              </bk-button>
            )
            : (
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
          )
        }
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
        </p>)
    ),
  };

  // 根据 event_filters 动态添加关联事件列，插入到操作列之前
  let initTableColumns: any[] = [];
  const tableColumns = computed(() => {
    if (!initTableColumns.length) {
      initTableColumns = useRiskColumns({
        deps: { levelData, strategyTagMap, strategyList, riskStatusCommon, sceneList, handleToDetail },
        detailRouteName: 'riskManageDetail',
        overrides: {
          // risk_id 列：stand_by 状态不可点击
          risk_id: {
            cell: (h: any, { row }: { row: RiskManageModel }) => {
              const to = {
                name: 'riskManageDetail',
                params: {
                  riskId: row.risk_id,
                },
              };
              return (row.status === 'stand_by'
                ? <span>{row.risk_id}</span>
                : (<router-link to={to}>
                <Tooltips data={row.risk_id} />
              </router-link>));
            },
          },
          // operator 列：传 row.operator || []
          operator: {
            cell: (h: any, { row }: { row: RiskManageModel }) => <EditTag data={row.operator || []} />,
          },
          // 风险标签：超过 1 个时展示首个标签 +N，hover 查看全部
          tags: {
            width: 180,
            minWidth: 160,
            cell: (h: any, { row }: { row: RiskManageModel }) => {
              const tags = (row.tags || []).map((item: string) => strategyTagMap.value[item] || item);
              return (
                <EditTag
                  data={tags}
                  key={row.risk_id}
                  max={tags.length > 1 ? 1 : 0}
                />
              );
            },
          },
          // status 列：宽 130，增加 stand_by 状态处理
          status: {
            width: 130,
            cell: (h: any, { row }: { row: RiskManageModel }) => (
              // eslint-disable-next-line no-nested-ternary
              row.status === 'stand_by' ? (
                 <span style='font-size: 14px;color: #3a84ff;'>
                 <audit-icon  type="loading" style='font-size: 14px;color: #3a84ff; animation: spin 1s linear infinite' />  {t('风险创建中')}
                </span>
              )
                : (row.status === 'closed' && row.experiences > 0
                  ? (
                    <div style='display: flex;align-items: center;height: 100%;'>
                      <bk-tag
                        theme={statusToMap[row.status]?.tag}>
                        <p style='display: flex;align-items: center;'>
                          <audit-icon type={statusToMap[row.status]?.icon} style={`margin-right: 6px;color: ${statusToMap[row.status]?.color || ''}`} />
                          <span>{riskStatusCommon.value.find(item => item.id === row.status)?.name || '--'}</span>
                        </p>
                      </bk-tag>
                      <bk-button text theme='primary' onClick={() => handleToDetail(row, true)}>
                        <audit-icon v-bk-tooltips={t('已填写"风险总结"')} type="report" style='font-size: 14px;' />
                      </bk-button>
                    </div>
                  )
                  : (
                    <bk-tag
                      theme={statusToMap[row.status]?.tag}>
                      <p style='display: flex;align-items: center;'>
                        <audit-icon type={statusToMap[row.status]?.icon} style={`margin-right: 6px;color: ${statusToMap[row.status]?.color || ''}`} />
                        <span>{riskStatusCommon.value.find(item => item.id === row.status)?.name || '--'}</span>
                      </p>
                    </bk-tag>))
            ),
          },
        },
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
  const defaultSettings = ['risk_id', 'title', 'event_content', 'scene_id', 'risk_level', 'tags', 'operator', 'status', 'current_operator', 'notice_users', 'strategy_id', 'event_time', 'last_operate_time', 'has_report', 'risk_label'];

  const settingsVersion = ref(0);

  // 从 localStorage 读取保存的设置
  const settings = computed(() => {
    void settingsVersion.value;
    const jsonStr = localStorage.getItem('audit-all-risk-list-setting');
    let result: string[];
    if (jsonStr) {
      try {
        const savedSettings = JSON.parse(jsonStr);
        // 如果保存的设置中有 checked 字段，使用它；否则使用默认设置
        result = savedSettings.checked && Array.isArray(savedSettings.checked)
          ? [...savedSettings.checked]
          : [...defaultSettings];
      } catch (e) {
        console.error('本地设置解析失败，使用默认配置', e);
        result = [...defaultSettings];
      }
    } else {
      result = [...defaultSettings];
    }
    return result;
  });

  const listRef = ref();
  const addRiskRef = ref();
  const newAddedRiskIds = ref<string[]>([]);
  const searchBoxRef = ref();
  const searchModel = ref<Record<string, any>>({});
  const totalCount = ref(0);
  const conditionTags = ref<any[]>([]);

  // 导出数据
  const handleExport = () => {
    const selectedData = listRef.value.getSelection().map((i: any) => i.risk_id.toString());
    if (!selectedData.length) {
      messageWarn(t('请选择要操作的数据'));
      return;
    }
    searchBoxRef.value.exportData(selectedData, 'all');
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

  // 获取userinfo
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
  useRequest(RiskManageService.fetchRiskTags, {
    defaultParams: {
      page: 1,
      page_size: 1,
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
    data: sceneList,
    run: fetchSceneAll,
  } = useRequest(SceneManageService.fetchSceneAll, {
    manual: true,
    defaultValue: [],
  });

  // 获取AI搜索用的场景列表（与"所属场景"下拉选项保持一致，使用已筛选的场景）
  const {
    data: riskScenesData,
    run: fetchRiskScenes,
  } = useRequest(RiskManageService.fetchRiskScenes, {
    defaultParams: {
      risk_view_type: 'all',
      start_time: dayjs(Date.now() - (86400000 * 182)).format('YYYY-MM-DD HH:mm:ss'),
      end_time: dayjs().format('YYYY-MM-DD HH:mm:ss'),
    },
    defaultValue: [],
    manual: true,
  });

  const nlSearchBoxScenes = computed(() => riskScenesData.value?.map((item: any) => ({
    scene_id: Number(item.scene_id || item.id),
    name: item.name,
  })) || []);
  const {
    data: levelData,
    run: fetchRiskLevel,
  } = useRequest(StrategyManageService.fetchRiskLevel, {
    defaultValue: {},
  });

  const {
    run: fetchRiskList,
  } = useRequest(RiskManageService.fetchRiskList, {
    defaultValue: {
      results: [],
      page: 0,
      num_pages: 0,
      total: 0,
    },
  });

  const handleRequestSuccess = ({ results, total }: { results: Array<RiskManageModel>, total: number }) => {
    aiAnalyzesRef.value?.changeIsSearch();
    window.changeConfirm = false;
    totalCount.value = total || 0;

    // 通知搜索框：表格数据加载完成（用于智能搜索成功提示和 input 按钮停止转动）
    searchBoxRef.value?.notifySearchComplete();

    if (!results.length) {
      return;
    }

    // 获取对应风险等级
    fetchRiskLevel({
      strategy_ids: results.map(item => item.strategy_id).join(','),
    });
    if (results.some(item => item.status === 'stand_by')) {
      // 执行定时器
      safeSetTimeout(() => {
        const addEventRiskIds = JSON.parse(sessionStorage.getItem('addEventRiskIds') || '[]');
        if (addEventRiskIds.length === 0) {
          listRef.value?.initData();
        }
        fetchRiskList({
          risk_id: addEventRiskIds.join(','),
          page: 1,
          page_size: 20,
        }).then((data) => {
          if (isComponentMounted.value) {
            listRef.value?.initListData(data.results, 'risk_id');
          }
        });
      }, 5000);
    } else {
      // 消除定时器
      if (timeout) {
        clearTimeout(timeout);
        timeout = undefined;
      }
    }
  };

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
      name: 'riskManageDetail',
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
    localStorage.setItem('audit-all-risk-list-setting', JSON.stringify(setting));
    settingsVersion.value += 1;
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

  // 搜索
  const handleSearchChange = (value: Record<string, any>, exValue: Record<string, any>, isClear?: boolean) => {
    if (!isClear) {
      sessionStorage.removeItem('addEventRiskIds');
      newAddedRiskIds.value = [];
    }
    searchModel.value = {
      ...value,
      event_filters: exValue,
    };
    listRef.value?.initTableHeight();
    fetchList();
    // 更新conditionTags
    updateConditionTags();
  };

  // 更新conditionTags
  const updateConditionTags = () => {
    if (searchBoxRef.value?.getConditionTags) {
      conditionTags.value = searchBoxRef.value.getConditionTags();
    }
  };

  // NL 解析状态变化时，给列表设置 loading
  const handleParsing = (isParsing: boolean) => {
    if (listRef.value) {
      listRef.value.loading = isParsing;
    }
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
      scene_id: '',
    };
    const dataParams: Record<string, any> = {
      ...params,
      ...searchModel.value,
    };
    // 默认排序：按首次发现时间倒序，其次按风险ID倒序
    if (!dataParams.sort) {
      dataParams.sort = ['-event_time', '-risk_id'];
    }
    listRef.value.fetchData(dataParams);
  };

  const handleAddRisk = () => {
    addRiskRef.value.show();
  };

  const handleAddRiskSuccess = () => {
    const riskIds = sessionStorage.getItem('addEventRiskIds');
    if (riskIds) {
      newAddedRiskIds.value = JSON.parse(riskIds).map((id: string | number) => String(id));
    }
    searchBoxRef.value.clearValue();
    fetchList();
  };

  const getRowClassName = (row: Record<string, any>) => {
    const rowData = row?.row || row;
    if (newAddedRiskIds.value.includes(String(rowData?.risk_id))) {
      return 'new-row';
    }
    return '';
  };

  onMounted(() => {
    nextTick(() => {
      getEventFields();
      fetchRiskScenes();
      fetchSceneAll();
      sessionStorage.removeItem('addEventRiskIds');
      newAddedRiskIds.value = [];
      // 初始获取conditionTags
      updateConditionTags();
    });
  });

  const isComponentMounted = ref(true);

  onUnmounted(() => {
    isComponentMounted.value = false;
    if (timeout) {
      clearTimeout(timeout);
      timeout = undefined;
    }
  });

  // 添加定时器执行前的组件状态检查
  const safeSetTimeout = (callback: () => void, delay: number) => {
    timeout = setTimeout(() => {
      if (isComponentMounted.value) {
        callback();
      }
    }, delay);
  };

  onBeforeRouteLeave((to, from, next) => {
    if (to.name === 'riskManageDetail') {
      const params = getSearchParamsPost('event_filters');
      const paramsEventFilters = JSON.stringify(params.event_filters);
      const EventFiltersparams = {
        ...params,
        event_filters: paramsEventFilters,
      };
      // 保存当前查询参数到目标路由的 query 中
      // eslint-disable-next-line no-param-reassign
      to.query = {
        ...to.query,
        ...EventFiltersparams,
      };
    }
    next();
  });
</script>
<style lang='postcss'>
@keyframes spin {
  0% {
    transform: rotate(0deg);
  }

  100% {
    transform: rotate(360deg);
  }
}

.risk-manage-list-page-wrap {
  position: relative;
  overflow-x: hidden;
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
