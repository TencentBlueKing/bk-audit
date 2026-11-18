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
  <div class="base-info-form info-field-rows">
    <template
      v-for="(rowItem, rowIndex) in fieldRows"
      :key="rowIndex">
      <div
        v-if="rowItem.type === 'divider'"
        class="fields-section-divider" />
      <div
        v-else
        class="info-field-row"
        :class="{
          'is-full-row': rowItem.group.length === 1
            && rowItem.group[0]
            && isFullRowField(rowItem.group[0].field_name),
        }">
        <render-info-item
          v-for="(fieldItem, itemIndex) in rowItem.group.filter(isValidFieldItem)"
          :key="`${rowIndex}-${itemIndex}-${fieldItem.field_name}`"
          :label="fieldItem.field_name === 'strategy_name' ? t('风险命中策略(ID)') : fieldItem.display_name"
          :label-width="labelWidth">
          <div class="risk-field-value-wrap">
            <div
              v-bk-tooltips="{
                disabled: !hasFieldDrill(fieldItem) || isLinkField(fieldItem),
                content: t('点击查看此字段的证据下探'),
              }"
              class="risk-field-value"
              :class="{ 'is-drill': hasFieldDrill(fieldItem) && !isLinkField(fieldItem) }"
              @click="handleFieldValueClick(fieldItem)">
              <template v-if="fieldItem.field_name === 'risk_id'">
                {{ data.risk_id || '--' }}
              </template>
              <template v-else-if="fieldItem.field_name === 'risk_level'">
                <span
                  v-if="data.risk_level"
                  :style="{
                    'background-color': riskLevelMap[data.risk_level].color,
                    padding: '3px 8px',
                    'border-radius': '3px',
                    color: 'white'
                  }">
                  {{ riskLevelMap[data.risk_level].label || '--' }}
                </span>
                <span v-else>--</span>
              </template>
              <template v-else-if="fieldItem.field_name === 'event_type'">
                <span v-if="isAddRisk">
                  <edit-tag
                    v-if="eventTypeComfig[0]?.typeValue === 'user-selector'"
                    :data="eventTypeComfig[0].value || ''"
                    style="display: inline-block;" />
                  <span v-else> {{ eventTypeComfig[0]?.value === '' ? '--' : eventTypeComfig[0]?.value }} </span>
                </span>
                <span v-else>
                  {{ handleShowText(data.event_type) || '--' }}
                </span>
              </template>
              <template v-else-if="fieldItem.field_name === 'risk_tags'">
                <edit-tag :data="data.tags?.map(item=>strategyTagMap[item] || item) || ''" />
              </template>
              <template v-else-if="fieldItem.field_name === 'strategy_name'">
                <router-link
                  v-if="strategyDisplayText"
                  target="_blank"
                  :to="{
                    name: 'strategyList',
                    query: {
                      strategy_id: data.strategy_id,
                      scope_id: data.scene_id,
                      scope_type: 'scene',
                    },
                  }">
                  {{ strategyDisplayText }}
                </router-link>
                <span v-else>--</span>
              </template>
              <template v-else-if="fieldItem.field_name === 'scene_id'">
                <span>{{ sceneName || '--' }}</span>
              </template>
              <template v-else-if="fieldItem.field_name === 'event_content'">
                <span v-if="isAddRisk">
                  <edit-tag
                    v-if="eventContentComfig[0]?.typeValue === 'user-selector'"
                    :data="eventContentComfig[0].value || ''"
                    style="display: inline-block;" />
                  <span
                    v-else
                    class="multiline-text">
                    {{ eventContentComfig[0]?.value === '' ? '--' : eventContentComfig[0]?.value }}
                  </span>
                </span>
                <span
                  v-else
                  class="multiline-text">
                  {{ handleShowText(data.event_content) || '--' }}
                </span>
              </template>
              <template v-else-if="fieldItem.field_name === 'risk_hazard'">
                <span class="multiline-text">{{ displayEmptyText(data.risk_hazard) }}</span>
              </template>
              <template v-else-if="fieldItem.field_name === 'risk_guidance'">
                <span class="multiline-text">{{ displayEmptyText(data.risk_guidance) }}</span>
              </template>
              <template v-else-if="fieldItem.field_name === 'status'">
                <template v-if="statusToMap[data.status]">
                  <bk-tag :theme="statusToMap[data.status].theme">
                    <p style="display: flex;align-items: center;">
                      <audit-icon
                        :style="`margin-right: 6px;color: ${statusToMap[data.status]?.color || ''}`"
                        :type="statusToMap[data.status].icon" />
                      {{ resolveRiskStatusName(data.status, riskStatusCommon) || '--' }}
                    </p>
                  </bk-tag>
                </template>
                <span v-else>--</span>
              </template>
              <template v-else-if="fieldItem.field_name === 'operator'">
                <span v-if="isAddRisk">
                  <edit-tag
                    v-if="operatorsComfig[0]?.typeValue === 'user-selector'"
                    :data="operatorsComfig[0].value || ''"
                    style="display: inline-block;" />
                  <span v-else> {{ operatorsComfig[0]?.value === '' ? '--' : operatorsComfig[0]?.value }} </span>
                </span>
                <edit-tag
                  v-else
                  :data="(typeof data.operator === 'string' ?
                    handleShowText(data.operator).split(',') : data.operator) || ''" />
              </template>
              <template v-else-if="fieldItem.field_name === 'current_operator'">
                <edit-tag :data="(isAddRisk ? processorGroups : data.current_operator) || []" />
              </template>
              <template v-else-if="fieldItem.field_name === 'notice_users'">
                <edit-tag :data="(isAddRisk ? noticeGroups : data.notice_users) || []" />
              </template>
              <template v-else-if="fieldItem.field_name === 'event_time'">
                {{ (isAddRisk ? editData?.formData.event_time : data.event_time) === '' ? '--' :
                  (isAddRisk ? editData?.formData.event_time : data.event_time) }}
              </template>
              <template v-else-if="fieldItem.field_name === 'event_end_time'">
                {{ (isAddRisk ? editData?.formData.event_time : data.event_end_time) === '' ? '--' :
                  (isAddRisk ? editData?.formData.event_time : data.event_end_time) }}
              </template>
              <template v-else-if="fieldItem.field_name === 'rule_id'">
                <router-link
                  v-if="riskRule"
                  target="_blank"
                  :to="{
                    name:'ruleManageList',
                    query:{
                      rule_id: data.rule_id
                    }
                  }">
                  {{ riskRule }}
                </router-link>
                <span v-else>--</span>
              </template>
              <template v-else-if="fieldItem.field_name === 'risk_label'">
                <span
                  class="risk-label-status"
                  :class="{
                    misreport: data.risk_label === 'misreport',
                  }">
                  <span v-if="isAddRisk">{{ t('正常') }}</span>
                  <span v-else>{{ data.risk_label === 'normal' ? t('正常') : t('误报') }}</span>
                </span>
              </template>
              <template v-else>
                {{ (isAddRisk ? '--'
                  : (data[fieldItem.field_name as keyof RiskManageModel]) === '' ? '--'
                    : data[fieldItem.field_name as keyof RiskManageModel]) }}
              </template>
            </div>
            <template v-if="hasFieldDrill(fieldItem)">
              <bk-popover
                placement="top"
                theme="black">
                <bk-button
                  class="ml8"
                  text
                  theme="primary"
                  @click="handleUseTool(fieldItem)">
                  <span class="drill-count-badge">
                    {{ getFieldDrill(fieldItem).length }}
                  </span>
                </bk-button>
                <template #content>
                  <div>
                    <div
                      v-for="config in getFieldDrill(fieldItem)"
                      :key="config.tool?.uid">
                      {{ config.drill_name || getToolNameAndType(config.tool?.uid).name }}
                      <bk-button
                        class="ml8"
                        text
                        theme="primary"
                        @click="(e: Event) => {
                          e.stopPropagation();
                          handleUseTool(fieldItem, config.tool?.uid);
                        }">
                        {{ t('去查看') }}
                        <audit-icon
                          class="mr-18"
                          type="jump-link" />
                      </bk-button>
                    </div>
                  </div>
                </template>
              </bk-popover>
            </template>
          </div>
        </render-info-item>
      </div>
    </template>
  </div>
  <div
    v-for="item in allOpenToolsData"
    :key="item">
    <component
      :is="DialogVue"
      :ref="(el: any) => dialogRefs[item] = el"
      :all-tools-data="allToolsData"
      source="risk"
      :tags-enums="tagData"
      @open-field-down="openFieldDown" />
  </div>
</template>
<script setup lang='ts'>
  import { computed, nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';
  import RiskRuleManageService from '@service/rule-manage';
  import SceneManageService from '@service/scene-manage';
  import ToolManageService from '@service/tool-manage';

  import type RiskManageModel from '@model/risk/risk';
  import type StrategyInfo from '@model/risk/strategy-info';

  import EditTag from '@components/edit-box/tag.vue';

  import { RISK_STATUS_THEME_MAP, resolveRiskStatusName } from '@views/risk-manage/constants';
  import DialogVue from '@views/tools/tools-square/components/dialog/dialog.vue';

  import { findStrategyLabel, formatStrategyNameWithId } from '@utils/format-strategy-name';

  import RenderInfoItem from './render-info-item.vue';

  import useRequest from '@/hooks/use-request';
  import { useToolDialog } from '@/hooks/use-tool-dialog';

  interface Props{
    data: RiskManageModel & StrategyInfo
    strategyList: Array<{
      label: string,
      value: number | string
    }>,
    riskStatusCommon: Array<{
      id: string,
      name: string,
    }>,
    showFieldNames: Array<StrategyInfo['risk_meta_field_config'][0]>,
    normalFieldNames?: Array<StrategyInfo['risk_meta_field_config'][0]>,
    showNormalFields?: boolean,
    isAddRisk?: boolean
    editData?: Record<string, any>
    noticeGroups?: string[] // 关注人
    processorGroups?: string[] // 处理人
    operatorsComfig?: Array<Record<string, any>> // 责任人
    eventContentComfig?: Array<Record<string, any>> // 事件描述
    eventTypeComfig?: Array<Record<string, any>> // 事件类型
  }

  const props = withDefaults(defineProps<Props>(), {
    isAddRisk: false,
    editData: () => ({}),
    noticeGroups: () => [],
    processorGroups: () => [],
    operatorsComfig: () => [],
    eventContentComfig: () => [],
    eventTypeComfig: () => [],
    normalFieldNames: () => [],
    showNormalFields: false,
  });
  const { t, locale } = useI18n();

  const labelWidth = computed(() => (locale.value === 'en-US' ? 160 : 120));

  type FieldItem = Props['showFieldNames'][0];

  const isValidFieldItem = (item: FieldItem | null | undefined): item is FieldItem => item !== null;

  type DrillConfigItem = NonNullable<FieldItem['drill_config']>[number];

  const LINK_FIELD_NAMES = ['strategy_name', 'rule_id'];

  const {
    allOpenToolsData,
    dialogRefs,
    openFieldDown,
  } = useToolDialog();

  const getFieldDrill = (fieldItem?: FieldItem | null): DrillConfigItem[] => {
    if (props.isAddRisk || !fieldItem) {
      return [];
    }
    const value = fieldItem.drill_config as DrillConfigItem | DrillConfigItem[] | undefined;
    if (!value) {
      return [];
    }
    const list = Array.isArray(value) ? value : [value];
    return list.filter(item => Boolean(item?.tool?.uid));
  };

  const hasFieldDrill = (fieldItem?: FieldItem | null) => getFieldDrill(fieldItem).length > 0;

  const isLinkField = (fieldItem?: FieldItem | null) => (
    Boolean(fieldItem && LINK_FIELD_NAMES.includes(fieldItem.field_name))
  );

  const riskToolParams = computed(() => ({
    caller_resource_type: 'risk',
    caller_resource_id: props.data.risk_id,
    drill_field: '',
    event_start_time: props.data.event_time,
    event_end_time: props.data.event_end_time,
  }));

  const {
    data: allToolsData,
    run: fetchAllTools,
  } = useRequest(ToolManageService.fetchAllTools, {
    defaultValue: [],
    defaultParams: {
      scope_type: 'scene',
      scope_id: props.data.scene_id,
    },
  });

  const {
    data: tagData,
    run: fetchToolTags,
  } = useRequest(ToolManageService.fetchToolTags, {
    defaultValue: [],
  });

  const getToolNameAndType = (uid?: string) => {
    if (!uid) {
      return {
        name: '',
        type: '',
      };
    }
    const tool = allToolsData.value?.find(item => item.uid === uid);
    return tool ? {
      name: tool.name,
      type: tool.tool_type,
    } : {
      name: '',
      type: '',
    };
  };

  const handleUseTool = (fieldItem: FieldItem, activeUid?: string) => {
    const drillConfig = getFieldDrill(fieldItem);
    if (!drillConfig.length) {
      return;
    }
    riskToolParams.value.drill_field = fieldItem.field_name;
    const drillDownItem = {
      ...fieldItem,
      drill_config: drillConfig,
    };
    const uids = drillConfig.map(config => config.tool.uid).join('&');
    if (!allOpenToolsData.value.find(item => item === uids)) {
      allOpenToolsData.value.push(uids);
    }
    nextTick(() => {
      if (dialogRefs.value[uids]) {
        dialogRefs.value[uids].openDialog(
          uids,
          drillDownItem,
          props.data,
          activeUid,
          riskToolParams.value,
        );
      }
    });
  };

  const handleFieldValueClick = (fieldItem: FieldItem) => {
    if (isLinkField(fieldItem) || !hasFieldDrill(fieldItem)) {
      return;
    }
    handleUseTool(fieldItem);
  };

  const strategyTagMap = ref<Record<string, string>>({});

  const riskLevelMap: Record<string, {
    label: string,
    color: string,
  }> =  {
    HIGH: {
      label: t('高'),
      color: '#ea3636',
    },
    MIDDLE: {
      label: t('中'),
      color: '#ff9c01',
    },
    LOW: {
      label: t('低'),
      color: '#979ba5',
    },
  };

  const statusToMap = RISK_STATUS_THEME_MAP;

  // 获取场景列表
  const {
    data: sceneList,
    run: fetchSceneAll,
  } = useRequest(SceneManageService.fetchSceneAll, {
    manual: true,
    defaultValue: [],
  });

  // 获取场景名称
  const sceneName = computed(() => {
    if (!props.data?.scene_id) return '';
    // 场景数据的ID字段为 scene_id
    const item = sceneList.value.find((s: any) => String(s.scene_id || s.id) === String(props.data.scene_id));
    return item ? (item.name || '') : props.data.scene_id;
  });
  // 判断值是否为数组（包括字符串形式的数组）
  const handleShowText = (value: any) => {
    // 1. 如果是真正的数组，直接连接
    if (Array.isArray(value)) {
      return value.length > 0 ? value.join(',') : '--';
    }

    // 2. 如果是字符串且看起来像数组，尝试解析
    if (typeof value === 'string' && value.trim().startsWith('[') && value.trim().endsWith(']')) {
      try {
        const parsedArray = JSON.parse(value);
        if (Array.isArray(parsedArray)) {
          return parsedArray.length > 0 ? parsedArray.join(',') : '';
        }
      } catch (error) {
        return value  || '';
      }
    }
    if (value === '') {
      return '--';
    }
    // 3. 其他情况直接返回原值
    return value ;
  };
  const strategyDisplayText = computed(() => {
    const { data } = props;
    const strategyName = findStrategyLabel(props.strategyList, data.strategy_id)
      || String((data as RiskManageModel & StrategyInfo & { strategy_name?: string }).strategy_name || '').trim();
    if (!strategyName && !data.strategy_id && data.strategy_id !== 0) {
      return '';
    }
    return formatStrategyNameWithId(strategyName, data.strategy_id);
  });

  const riskRule = computed(() => {
    if (!props.data || !props.data.rule_id) return '';
    const item = riskRuleList.value
      .find(item => item.id === props.data.rule_id && item.version === props.data.rule_version);
    return item && item.name ? item.name : '';
  });

  // 转为二维数组
  const group = (array: Array<any>, subGroupLength: number = 2): Array<Array<Props['showFieldNames'][0]>> => {
    const newArray = [];
    let index = 0;

    while (index < array.length) {
      const currentItem = array[index];

      // 检查是否为需要单独占一行的字段
      if (currentItem.field_name === 'risk_guidance' || currentItem.field_name === 'risk_hazard' || currentItem.field_name === 'event_content') {
        // 单独占一行，另一个元素为空
        newArray.push([currentItem, null]);
        index += 1;
      } else {
        // 正常分组逻辑
        const group = array.slice(index, index + subGroupLength);
        // 如果组内最后一个元素是特殊字段，需要调整
        if (group.length === 2 && group[1]
          && (group[1].field_name === 'risk_guidance' || group[1].field_name === 'risk_hazard' || group[1].field_name === 'event_content')) {
          // 如果第二个元素是特殊字段，第一个元素单独成组
          newArray.push([group[0], null]);
          index += 1;
        } else {
          // 正常添加组
          newArray.push(group);
          index += group.length;
        }
      }
    }
    return newArray;
  };

  const buildFieldGroups = (fields: Props['showFieldNames']) => {
    if (!fields.length) {
      return [];
    }
    // 在"风险命中策略"(strategy_name)前插入所属场景(scene_id)字段
    const strategyIndex = fields.findIndex(f => f.field_name === 'strategy_name');
    let processedFields = fields;
    if (strategyIndex > 0) {
      const sceneField = {
        field_name: 'scene_id',
        display_name: t('所属场景'),
        is_priority: false,
      };
      processedFields = [...fields];
      processedFields.splice(strategyIndex, 0, sceneField as any);
    }
    return group(processedFields);
  };

  const priorityFieldGroups = computed(() => buildFieldGroups(props.showFieldNames));

  const normalFieldGroups = computed(() => buildFieldGroups(props.normalFieldNames));

  const fieldRows = computed(() => {
    const rows: Array<{ type: 'divider' } | { type: 'row', group: Array<Props['showFieldNames'][0] | null> }> = [];
    priorityFieldGroups.value.forEach((fieldGroup) => {
      rows.push({ type: 'row', group: fieldGroup });
    });
    if (props.showNormalFields && normalFieldGroups.value.length) {
      if (priorityFieldGroups.value.length) {
        rows.push({ type: 'divider' });
      }
      normalFieldGroups.value.forEach((fieldGroup) => {
        rows.push({ type: 'row', group: fieldGroup });
      });
    }
    return rows;
  });

  // 是否独占整行
  const isFullRowField = (fieldName: string) => (
    ['notice_users', 'risk_guidance', 'risk_hazard', 'event_content'].includes(fieldName)
  );

  const displayEmptyText = (value: unknown) => {
    if (value === '' || value === undefined || value === null) {
      return '--';
    }
    return value;
  };

  // 获取标签列表
  const {
    run: fetchRiskTags,
  } = useRequest(RiskManageService.fetchRiskTags, {
    defaultParams: {
      page: 1,
      page_size: 1,
    },
    defaultValue: [],
    onSuccess: (data) => {
      data.forEach((item) => {
        strategyTagMap.value[item.id] = item.name;
      });
    },
  });
  // 获取所有处理规则
  const {
    data: riskRuleList,
    run: fetchRuleAll,
  } = useRequest(RiskRuleManageService.fetchRuleAll, {
    defaultValue: [],
    defaultParams: {
    },
  });
  watch(() => props.data?.scene_id, (sceneId, oldSceneId) => {
    if (!sceneId || sceneId === oldSceneId) {
      return;
    }
    fetchRuleAll({
      scene_id: sceneId,
    });
    fetchRiskTags({
      scope_id: sceneId,
      scope_type: 'scene',
    });
    fetchSceneAll();
    if (!props.isAddRisk) {
      fetchAllTools({
        scope_id: sceneId,
        scope_type: 'scene',
      });
      fetchToolTags({
        scope_id: sceneId,
        scope_type: 'scene',
      });
    }
  }, {
    immediate: true,
  });
</script>
<style lang="postcss" scoped>
.base-info-form {
  margin-bottom: 10px;
}

.risk-field-value-wrap {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  min-width: 0;
  max-width: 100%;
}

.risk-field-value.is-drill {
  color: #3a84ff;
  cursor: pointer;
}

.multiline-text {
  white-space: pre-line;
  word-break: break-word;
}

.drill-count-badge {
  padding: 2px 10px;
  color: #3a84ff;
  cursor: pointer;
  background-color: #cddffe;
  border-radius: 8px;
}
</style>
