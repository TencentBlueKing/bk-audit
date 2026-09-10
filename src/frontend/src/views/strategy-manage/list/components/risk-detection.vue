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
  <div class="risk-detection">
    <div class="detail-info-card">
      <div class="detail-section">
        <div class="detail-section-title">
          {{ t('基础配置') }}
        </div>
        <div class="detail-section-body">
          <render-info-block>
            <render-info-item :label="t('策略名称')">
              {{ data.strategy_name }}
            </render-info-item>
          </render-info-block>
          <render-info-block>
            <render-info-item :label="t('标签')">
              <edit-tag :data="data.tags?.map(item=> strategyMap[item] || item) || ''" />
            </render-info-item>
          </render-info-block>
          <render-info-block>
            <render-info-item :label="t('描述')">
              {{ data.description || '--' }}
            </render-info-item>
          </render-info-block>
        </div>
      </div>

      <div class="detail-section-divider" />

      <div class="detail-section">
        <div class="detail-section-title">
          {{ t('方案') }}
        </div>
        <div class="detail-section-body">
          <render-info-block>
            <render-info-item :label="t('配置方式')">
              <div class="strategy-type-display">
                <img
                  :alt="strategyTypeTextMap[data.strategy_type]"
                  class="strategy-type-icon"
                  :src="strategyTypeIcon">
                <span class="strategy-type-text">
                  {{ strategyTypeTextMap[data.strategy_type] }}
                </span>
              </div>
            </render-info-item>
          </render-info-block>
          <render-info-block
            v-if="data.strategy_type === 'model'">
            <render-info-item :label="t('方案名称')">
              {{ currentControl?.control_name || '--' }} - V{{ data.control_version }}
            </render-info-item>
          </render-info-block>
          <!-- 自定义规则审计 -->
          <template v-if="data.strategy_type === 'rule'">
            <render-info-block>
              <render-info-item :label="t('数据源')">
                {{ getDataSourceText(data.configs) || '--' }}
              </render-info-item>
            </render-info-block>
            <render-info-block>
              <render-info-item :label="t('预期结果')">
                <template v-if="data.configs.select?.length">
                  <div class="panel-edit flex">
                    <div
                      v-for="element in data.configs.select"
                      :key="element.raw_name + element.aggregate + element.display_name"
                      class="query-field flex-center-wrap">
                      {{ getMetricName(element) }}
                    </div>
                  </div>
                </template>
                <div v-else>
                  --
                </div>
              </render-info-item>
            </render-info-block>
            <render-info-block>
              <render-info-item :label="t('调度方式')">
                {{ scheduleTypeText }}
              </render-info-item>
            </render-info-block>
            <render-info-block>
              <render-info-item :label="t('调度周期')">
                <template
                  v-if="data.configs.data_source?.source_type === 'batch_join_source'
                    && data.configs.schedule_config">
                  <span>
                    {{ data.configs.schedule_config.count_freq }}
                  </span>
                  <span>
                    {{ commonData.offset_unit
                      .find((item) =>
                        item.value === data.configs.schedule_config.schedule_period)?.label }}
                  </span>
                </template>
                <span v-else>
                  --
                </span>
              </render-info-item>
            </render-info-block>
          </template>

          <bk-loading :loading="controlLoading">
            <component
              :is="comMap[currentControl?.control_type_id || '--']"
              ref="comRef"
              :data="data" />
          </bk-loading>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';
  import LinkDataManageService from '@service/link-data-manage';
  import MetaManageService from '@service/meta-manage';
  import StrategyManageService from '@service/strategy-manage';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';
  import CommonDataModel from '@model/strategy/common-data';
  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import type StrategyModel from '@model/strategy/strategy';

  import useRequest from '@hooks/use-request';

  import EditTag from '@components/edit-box/tag.vue';

  import editWayIcon from '@images/strategy-manage/edit.svg';
  import modelWayIcon from '@images/strategy-manage/model.svg';

  import RenderAiops from './aiops/index.vue';
  import FilterCondition from './normal/filter-condition.vue';
  import RenderInfoBlock from './render-info-block.vue';
  import RenderInfoItem from './render-info-item.vue';

  import { getStrategyResourceSceneParams,
           getStrategySystemScopeParams,
           isPlatformStrategyRoute,
  } from '../../utils/strategy-routes';

  interface Props {
    data: StrategyModel,
    strategyMap: Record<string, string>
  }

  const props = defineProps<Props>();
  const { t } = useI18n();
  const route = useRoute();
  const isPlatformMode = computed(() => isPlatformStrategyRoute(route.name));

  const fetchStrategyTableList = (params: {
    table_type: string;
    scene_id?: string | number | null;
    bk_biz_id?: string | number;
  }) => {
    if (!params.table_type) {
      return Promise.resolve([]);
    }
    const { scene_id: sceneId, ...rest } = params;
    const requestParams = {
      ...rest,
      ...(sceneId !== undefined && sceneId !== null && sceneId !== ''
        ? { scene_id: String(sceneId) }
        : {}),
    };
    return isPlatformMode.value
      ? StrategyManageService.fetchTable(requestParams)
      : StrategyManageService.fetchScenePermissionTable(requestParams);
  };

  const currentControl = computed(() => controlList.value
    .find(item => item.control_id === props.data.control_id));// 当前方案
  const comMap: Record<string, any> = {
    BKM: FilterCondition,
    AIOps: RenderAiops,
  };

  const strategyTypeTextMap = {
    rule: t('自定义规则审计'),
    model: t('引入模型审计'),
  } as Record<string, string>;

  const strategyTypeIcon = computed(() => (
    props.data.strategy_type === 'rule' ? editWayIcon : modelWayIcon
  ));

  const scheduleTypeText = computed(() => {
    const sourceType = props.data.configs?.data_source?.source_type;
    if (sourceType === 'stream_source') {
      return t('实时调度');
    }
    if (sourceType === 'batch_join_source') {
      return t('固定周期调度');
    }
    return '--';
  });

  const {
    data: commonData,
    run: fetchStrategyCommon,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
  });

  const getMetricName = (element: DatabaseTableFieldModel) => {
    const item = commonData.value.rule_audit_aggregate_type.find(item => item.value === element.aggregate);
    return `[${item?.label || t('不聚合')}] ${element.display_name}`;
  };

  const formatNodeNameId = (label: string, id: string) => {
    const name = label || '';
    const realId = id || '';
    if (!realId) return name;
    if (!name) return realId;
    if (name.includes(`(${realId})`)) return name;
    return `${name}(${realId})`;
  };

  const joinDisplayPath = (parts: Array<string | undefined>) => parts
    .map(part => (part || '').trim())
    .filter(Boolean)
    .join(' / ');

  const resolveRtId = (rtId: string | string[] | undefined) => {
    if (Array.isArray(rtId)) {
      return String(rtId[0] || '');
    }
    return String(rtId || '');
  };

  const extractBizIdFromRtId = (rtId: string) => {
    const first = String(rtId || '').split('_')[0];
    return /^\d+$/.test(first) ? first : '';
  };

  const formatRtName = (raw: string) => {
    const real = String(raw || '');
    if (!real) return '';
    const bizId = extractBizIdFromRtId(real);
    if (bizId && real.length > bizId.length + 1) {
      return real.slice(bizId.length + 1);
    }
    return real;
  };

  const isMatchedRt = (nodeValue: string, nodeLabel: string, rtId: string) => {
    if (!rtId) return false;
    const value = String(nodeValue || '');
    if (value === rtId || nodeLabel === rtId) return true;
    if (formatRtName(value) === formatRtName(rtId)) return true;
    if (nodeLabel && nodeLabel === formatRtName(rtId)) return true;
    const bizId = extractBizIdFromRtId(value) || extractBizIdFromRtId(rtId);
    return Boolean(bizId && (
      value === `${bizId}_${rtId}`
      || rtId === `${bizId}_${value}`
    ));
  };

  const formatLeftNodeLabel = (node: { label?: string; value?: string }) => {
    const realId = String(node.value || '');
    const maybeBizId = realId.includes('_') ? realId.split('_')[0] : realId;
    const idForDisplay = /^\d+$/.test(maybeBizId) ? maybeBizId : realId;
    return formatNodeNameId(String(node.label || ''), idForDisplay);
  };

  const findTableNode = (
    data: Array<{ label?: string; value?: string; children?: any[] }>,
    searchValue: string,
    parent: { label?: string; value?: string } | null = null,
  ): { label?: string; value?: string } | null => {
    const target = String(searchValue || '');
    if (!target) return null;
    for (const item of data || []) {
      if (String(item.value) === target) {
        return parent || item;
      }
      if (item.children?.length) {
        const found = findTableNode(item.children, target, item);
        if (found) return found;
      }
    }
    return null;
  };

  const findRtPath = (
    nodes: Array<{ label?: string; value?: string; children?: any[] }>,
    rtId: string,
  ) => {
    for (const left of nodes || []) {
      const children = left.children || [];
      const right = children.find(child => (
        isMatchedRt(String(child.value), String(child.label || ''), rtId)
      ));
      if (right) {
        return { left, right };
      }
      if (!children.length && isMatchedRt(String(left.value), String(left.label || ''), rtId)) {
        return { left, right: null };
      }
    }
    const bizId = extractBizIdFromRtId(rtId);
    if (bizId) {
      const left = (nodes || []).find(item => (
        String(item.value) === bizId
        || extractBizIdFromRtId(String(item.value || '')) === bizId
      ));
      if (left) {
        return { left, right: null };
      }
    }
    return null;
  };

  type TableTypeNode = {
    label?: string;
    value?: string;
    children?: TableTypeNode[];
  };

  const tableTypeMap = ref<Record<string, TableTypeNode[]>>({});

  const findBestPath = (rtId: string, preferredType?: string) => {
    if (!rtId) return null;
    const entries = Object.entries(tableTypeMap.value);
    if (!entries.length) return null;
    const ordered = [
      ...entries.filter(([type]) => type === preferredType),
      ...entries.filter(([type]) => type !== preferredType),
    ];
    for (const [tableType, nodes] of ordered) {
      const path = findRtPath(nodes, rtId);
      if (path?.right) {
        return { tableType, ...path };
      }
    }
    // 业务节点已命中但子表未展开：优先走三级文案，避免资产数据的同名二级叶子盖住真实路径
    for (const [tableType, nodes] of ordered) {
      const path = findRtPath(nodes, rtId);
      if (
        path
        && !path.right
        && !isMatchedRt(String(path.left.value), String(path.left.label || ''), rtId)
      ) {
        return { tableType, ...path };
      }
    }
    for (const [tableType, nodes] of ordered) {
      const path = findRtPath(nodes, rtId);
      if (path) {
        return { tableType, ...path };
      }
    }
    return null;
  };

  const getConfigTypeLabel = (configType?: string) => (
    commonData.value.rule_audit_config_type.find(item => item.value === configType)?.label || ''
  );

  const getDataSourceText = (config: StrategyModel['configs']) => {
    const rtId = resolveRtId(config.data_source?.rt_id);

    if (config.config_type === 'EventLog') {
      const typeLabel = getConfigTypeLabel('EventLog');
      const plugin = findTableNode(tableData.value, rtId);
      const pluginLabel = plugin?.label || rtId;
      const selectedIds = (config.data_source?.system_ids || []).map(String);
      const availableSystems = eventLogSelectableSystems.value.length
        ? eventLogSelectableSystems.value
        : systemList.value;
      const allSelected = availableSystems.length > 0
        && availableSystems.every(item => selectedIds.includes(String(item.id)));
      if (allSelected) {
        return joinDisplayPath([typeLabel, pluginLabel, t('全部系统')]);
      }
      const systemLabels = selectedIds.map((id) => {
        const sys = availableSystems.find(item => String(item.id) === id);
        return formatNodeNameId(sys?.name || id, id);
      }).join('、');
      return joinDisplayPath([typeLabel, pluginLabel, systemLabels]);
    }

    if (config.config_type === 'LinkTable') {
      return joinDisplayPath([getConfigTypeLabel('LinkTable'), LinkDataDetail.value.name]);
    }

    const path = findBestPath(rtId, config.config_type);
    if (!path) {
      return joinDisplayPath([
        getConfigTypeLabel(config.config_type),
        formatRtName(rtId) || rtId,
      ]);
    }
    const typeLabel = getConfigTypeLabel(path.tableType);
    if (path.right) {
      return joinDisplayPath([
        typeLabel,
        formatLeftNodeLabel(path.left),
        path.right.label || formatRtName(String(path.right.value || rtId)),
      ]);
    }
    if (isMatchedRt(String(path.left.value), String(path.left.label || ''), rtId)) {
      return joinDisplayPath([typeLabel, path.left.label || formatRtName(rtId)]);
    }
    return joinDisplayPath([
      typeLabel,
      formatLeftNodeLabel(path.left),
      formatRtName(rtId),
    ]);
  };

  // 获取方案列表
  const {
    data: controlList,
    loading: controlLoading,
    run: fetchControlList,
  } = useRequest(StrategyManageService.fetchControlList, {
    defaultValue: [],
  });

  // 获取tableid
  const {
    data: tableData,
    run: fetchTable,
  } = useRequest(fetchStrategyTableList, {
    defaultValue: [],
  });

  // 获取系统
  const {
    data: systemList,
    run: fetchSystemWithAction,
  } = useRequest(MetaManageService.fetchSystemWithAction, {
    defaultValue: [],
  });

  const eventLogSelectableSystems = ref<Array<{ id: string; name: string }>>([]);

  const attachBizChildren = (
    nodes: TableTypeNode[],
    bizId: string,
    children: TableTypeNode[],
  ) => nodes.map((item) => {
    if (
      String(item.value) === String(bizId)
      || extractBizIdFromRtId(String(item.value || '')) === String(bizId)
    ) {
      return { ...item, children };
    }
    return item;
  });

  const normalizeBizChildren = (raw: TableTypeNode[], bizId: string) => {
    let tableList = raw || [];
    if (tableList[0]?.children) {
      const bizNode = tableList.find(item => String(item.value) === String(bizId));
      tableList = bizNode?.children || [];
    }
    return tableList;
  };

  const loadTableTypeMap = async (preferred?: string) => {
    const extraTypes = ['BuildIn', 'BizRt', 'MineBizRt'];
    const types = [...new Set([preferred, ...extraTypes].filter(item => (
      Boolean(item) && item !== 'EventLog' && item !== 'LinkTable'
    )))] as string[];
    const sceneParams = getStrategyResourceSceneParams(route);
    const result: Record<string, TableTypeNode[]> = { ...tableTypeMap.value };
    await Promise.all(types.map(async (tableType) => {
      const data = await fetchStrategyTableList({
        table_type: tableType,
        ...sceneParams,
      }) || [];
      result[tableType] = data;
    }));
    tableTypeMap.value = result;

    const rtId = resolveRtId(props.data.configs?.data_source?.rt_id);
    const bizId = extractBizIdFromRtId(rtId);
    if (!bizId) return;

    const bizTypes = types.filter(item => item === 'BizRt' || item === 'MineBizRt');
    await Promise.all(bizTypes.map(async (tableType) => {
      const nodes = result[tableType] || [];
      const left = nodes.find(item => (
        String(item.value) === String(bizId)
        || extractBizIdFromRtId(String(item.value || '')) === String(bizId)
      ));
      if (left?.children?.length) return;
      const childrenRaw = await fetchStrategyTableList({
        table_type: tableType,
        bk_biz_id: bizId,
        ...sceneParams,
      }) || [];
      result[tableType] = attachBizChildren(
        nodes,
        bizId,
        normalizeBizChildren(childrenRaw, bizId),
      );
    }));
    tableTypeMap.value = { ...result };
  };

  const loadEventLogSelectableSystems = async (systems: Array<{ id: string; name: string }>) => {
    const list = systems || [];
    const systemIds = list.map(item => item.id).join(',');
    if (!systemIds) {
      eventLogSelectableSystems.value = [];
      return;
    }
    const statusMap = await CollectorManageService.fetchBatchSystemCollectorStatusList({
      system_ids: systemIds,
    });
    eventLogSelectableSystems.value = list.filter(item => statusMap?.[item.id]?.status !== 'unset');
  };

  // 获取关联表详情
  const {
    data: LinkDataDetail,
    run: fetchLinkDataSheetDetail,
  } = useRequest(LinkDataManageService.fetchLinkDataDetail, {
    defaultValue: new LinkDataDetailModel(),
  });

  let commonDataRequested = false;

  watch(() => props.data, (data) => {
    if (!data?.strategy_id) return;

    if (!commonDataRequested) {
      commonDataRequested = true;
      fetchStrategyCommon();
    }

    if (data.strategy_type === 'model') {
      fetchControlList();
      return;
    }

    if (data.strategy_type !== 'rule' || !data.configs?.config_type) return;

    const configType = data.configs.config_type;
    if (configType === 'LinkTable') {
      if (data.link_table_uid) {
        fetchLinkDataSheetDetail({
          uid: data.link_table_uid,
        });
      }
    } else if (configType === 'EventLog') {
      fetchTable({
        table_type: configType,
        ...getStrategyResourceSceneParams(route),
      });
    } else {
      loadTableTypeMap(configType);
    }

    if (configType === 'EventLog') {
      fetchSystemWithAction({
        action_ids: 'view_system',
        ...getStrategySystemScopeParams(route),
      }).then((systems) => {
        loadEventLogSelectableSystems(systems?.length ? systems : systemList.value);
      });
    }

    if (data.configs.having?.conditions?.length && data.configs.where) {
      // 将 having 条件合并到 where 条件中, conditions 根据 item.index 进行排序合并
      // eslint-disable-next-line no-param-reassign
      data.configs.where.conditions = data.configs.where.conditions.concat(data.configs.having.conditions);
      data.configs.where.conditions.sort((a, b) => a.index - b.index);
      // eslint-disable-next-line no-param-reassign
      data.configs.having.conditions = [];
    }
  }, {
    immediate: true,
  });

</script>
<style scoped lang="postcss">
.risk-detection {
  .detail-info-card {
    padding-top: 24px;
    background: #fff;
  }

  .detail-section-title {
    margin-bottom: 16px;
    font-size: 14px;
    font-weight: 600;
    line-height: 22px;
    color: #313238;
  }

  .detail-section-divider {
    margin: 24px 0;
    border-top: 1px solid #f0f1f5;
  }

  .strategy-type-display {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .strategy-type-icon {
    width: 16px;
    height: 16px;
    flex-shrink: 0;
  }

  .strategy-type-text {
    font-size: 12px;
    line-height: 20px;
    color: #313238;
  }

  .panel-edit {
    position: relative;
    min-height: 32px;
    padding: 0 3px;
    background: #f5f7fa;
    border-radius: 2px;
    flex-wrap: wrap;

    .query-field {
      position: relative;
      height: 26px;
      margin: 3px 4px 3px 0;
      line-height: 26px;
      color: #fff;
      white-space: nowrap;
      background: #1eab8b;
      border-radius: 2px;

      &:hover {
        .query-field-remove {
          visibility: visible;
        }
      }

      .dragging-handle {
        padding: 0 4px;
        cursor: move;
      }

      .query-field-remove {
        padding: 0 4px;
        text-align: center;
        visibility: hidden;
      }
    }

    .flex-center-wrap {
      display: flex;
      align-items: center;
      justify-content: center;
      flex-wrap: wrap;
    }
  }
}
</style>
