<!-- eslint-disable max-len -->
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
  <div class="risk-manage-detail-linkevent-part">
    <bk-loading :loading="loading">
      <div
        :key="detailRenderKey"
        class="body">
        <template v-if="hasLoadedData">
          <link-event-timeline
            v-if="linkEventList.length > 0"
            :active-index="active"
            :events="linkEventList"
            :has-more="hasMoreTimelineEvents"
            :loading-more="isLoadingMore"
            :show-add="data.status !== 'closed'"
            @add="handleAddEvent"
            @load-more="handleTimelineLoadMore"
            @select="handlerSelectByIndex" />
          <div
            v-else-if="data.status !== 'closed'"
            class="timeline-empty-action">
            <span
              class="add-event"
              @click="handleAddEvent">
              <audit-icon
                class="add-fill-event"
                type="add-fill" />
              {{ t('新建关联事件') }}
            </span>
          </div>

          <div
            v-if="linkEventList.length === 0"
            class="list-item-detail">
            <bk-exception
              class="exception-part"
              scene="part"
              type="empty">
              {{ t('暂无数据') }}
            </bk-exception>
          </div>
          <div
            v-else-if="activeStatus === 'new' && newIndex.includes(active)"
            class="list-item-detail event-create-detail-loading">
            <bk-loading
              class="event-create-loading"
              loading
              mode="spin"
              size="small"
              theme="primary"
              :title="t('事件创建中')">
              <div class="event-create-loading-box" />
            </bk-loading>
          </div>
          <div
            v-else
            class="list-item-detail">
            <div class="detail-content">
              <!-- 基本信息 -->
              <template v-if="basicInfo.length">
                <div class="title mt16">
                  {{ t('基本信息') }}
                </div>
                <div class="base-info info-field-rows">
                  <div
                    v-for="(basicArr, basicIndex) in basicInfo"
                    :key="basicIndex"
                    class="info-field-row">
                    <render-info-item
                      v-for="(basicItem, itemIndex) in basicArr"
                      :key="basicItem.field_name || itemIndex"
                      :description="basicItem.description"
                      :label="basicItem.field_name === 'strategy_id' ? t('风险命中策略(ID)') : basicItem.display_name"
                      :label-width="labelWidth">
                      <!-- 策略id -->
                      <template v-if="basicItem.field_name === 'strategy_id'">
                        <bk-button
                          v-if="getStrategyDisplayText(eventItem?.strategy_id)"
                          text
                          theme="primary"
                          @click="handlerStrategy()">
                          {{ getStrategyDisplayText(eventItem?.strategy_id) }}
                        </bk-button>
                        <span v-else> -- </span>
                        <audit-icon
                          v-if="getStrategyDisplayText(eventItem?.strategy_id)"
                          v-bk-tooltips="t('复制')"
                          class="copy-btn"
                          type="copy"
                          @click.stop="handleCopyValue(getStrategyDisplayText(eventItem?.strategy_id))" />
                      </template>
                      <!-- 其他字段 -->
                      <template v-else>
                        <!-- 有字段映射或者有证据下探 -->
                        <bk-popover
                          v-if="displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.isMappings
                            || drillMap.get(basicItem.field_name)"
                          placement="top"
                          theme="black">
                          <span
                            :class="[
                              displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.isMappings
                                ? 'tips' : ''
                            ]"
                            :style="{
                              color: drillMap.get(basicItem.field_name) ? '#3a84ff' : '#313238',
                              cursor: drillMap.get(basicItem.field_name) ? 'pointer' : 'default',
                            }"
                            @click="handleUseTool(
                              drillMap.get(basicItem.field_name),
                              basicItem.field_name
                            )">
                            <span v-if="basicItem.field_name === 'operator'">
                              <edit-tag
                                :data="handleShowText(displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.value)"
                                :max="99"
                                :show-copy="hasCopyableValue(displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.value)"
                                style="display: inline-block;"
                                @click="handleUseTool(
                                  drillMap.get(basicItem.field_name),
                                  basicItem.field_name
                                )" />
                            </span>
                            <span v-else>
                              {{ handleShowText(displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.value ) }}
                            </span>
                          </span>
                          <template #content>
                            <div>
                              <div
                                v-if="
                                  displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.isMappings
                                ">
                                <span>{{ t('存储值: ') }}</span>
                                <span>
                                  {{
                                    displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.dict?.key
                                  }}
                                </span>
                                <br>
                                <span>{{ t('展示文本: ') }}</span>
                                <span>
                                  {{
                                    displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.dict?.name
                                  }}
                                </span>
                              </div>
                              <div
                                v-if="drillMap.get(basicItem.field_name)"
                                :style="{
                                  // eslint-disable-next-line max-len
                                  marginTop: displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.isMappings
                                    ? '8px' : '0'
                                }">
                                {{ t('点击查看此字段的证据下探') }}
                              </div>
                            </div>
                          </template>
                        </bk-popover>
                        <!-- 没有字段映射或者没有证据下探 -->
                        <span v-else>
                          <edit-tag
                            v-if="basicItem.field_name === 'operator'"
                            :data="handleShowText(displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.value)"
                            :max="99"
                            :show-copy="hasCopyableValue(displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.value)"
                            style="display: inline-block;" />
                          <span v-else>
                            {{ handleShowText(displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.value ) || '--' }}
                          </span>
                          <audit-icon
                            v-if="basicItem.field_name !== 'operator'
                              && hasCopyableValue(displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.value)"
                            v-bk-tooltips="t('复制')"
                            class="copy-btn"
                            type="copy"
                            @click.stop="handleCopyValue(displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.value)" />
                        </span>
                      </template>
                      <!-- 证据下探按钮 -->
                      <template v-if="drillMap.get(basicItem.field_name)">
                        <bk-popover
                          placement="top"
                          theme="black">
                          <bk-button
                            class="ml8"
                            text
                            theme="primary"
                            @click="handleUseTool(
                              drillMap.get(basicItem.field_name),
                              basicItem.field_name
                            )">
                            <span
                              style="
                              padding: 2px 10px;
                              color: #3a84ff;
                              cursor: pointer;
                              background-color: #cddffe;
                              border-radius: 8px;
                            ">
                              {{ drillMap.get(basicItem.field_name).drill_config.length }}
                            </span>
                          </bk-button>
                          <template #content>
                            <div>
                              <div
                                v-for="config in drillMap.get(basicItem.field_name).drill_config"
                                :key="config.tool.uid">
                                {{ config.drill_name || getToolNameAndType(config.tool.uid).name }}
                                <bk-button
                                  class="ml8"
                                  text
                                  theme="primary"
                                  @click="(e: any) => {
                                    e.stopPropagation(); // 阻止事件冒泡
                                    handleUseTool(drillMap.get(basicItem.field_name),
                                                  basicItem.field_name, config.tool.uid);
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
                        <audit-icon
                          v-bk-tooltips="t('复制')"
                          class="copy-btn"
                          type="copy"
                          @click.stop="handleCopyDrillTitles(basicItem.field_name)" />
                      </template>
                    </render-info-item>
                  </div>
                </div>
              </template>

              <div
                v-if="basicInfo.length"
                class="section-divider" />

              <!-- 事件详情 -->
              <div class="title">
                {{ t('事件详情') }}
              </div>
              <template v-if="eventDataKeyArr.length || eventDataKeyArrNormal.length">
                <div
                  v-if="visibleEventDetailRows.length"
                  class="data-info info-field-rows">
                  <div
                    v-for="(keyArr, keyIndex) in visibleEventDetailRows"
                    :key="keyIndex"
                    class="info-field-row">
                    <render-info-item
                      v-for="key in keyArr"
                      :key="key"
                      :description="strategyInfo.find((item: any) => item.field_name === key)?.description || ''"
                      :label="strategyInfo.find((item: any) => item.field_name === key)?.display_name || key"
                      :label-width="labelWidth">
                      <!-- 有字段映射或者有证据下探 -->
                      <bk-popover
                        v-if="displayValueDict.eventData[key]?.isMappings
                          || drillMap.get(key)"
                        placement="top"
                        theme="black">
                        <span
                          :class="[
                            displayValueDict.eventData[key]?.isMappings
                              ? 'tips space' : 'space'
                          ]"
                          :style="{
                            color: drillMap.get(key) ? '#3a84ff' : '#313238',
                            cursor: drillMap.get(key) ? 'pointer' : 'default',
                          }"
                          @click="handleUseTool(
                            drillMap.get(key),
                            key
                          )">
                          {{ handleShowText(displayValueDict.eventData[key]?.value) }}
                          <audit-icon
                            v-if="hasCopyableValue(displayValueDict.eventData[key]?.value)"
                            v-bk-tooltips="t('复制')"
                            class="copy-btn"
                            type="copy"
                            @click.stop="handleCopyValue(displayValueDict.eventData[key]?.value)" />
                        </span>
                        <template #content>
                          <div>
                            <div
                              v-if="displayValueDict.eventData[key]?.isMappings">
                              <span>{{ t('存储值: ') }}</span>
                              <span>
                                {{ displayValueDict.eventData[key]?.dict?.key }}
                              </span>
                              <br>
                              <span>{{ t('展示文本: ') }}</span>
                              <span class="space">
                                {{ handleShowText(displayValueDict.eventData[key]?.dict?.name) }}
                              </span>
                            </div>
                            <div
                              v-if="drillMap.get(key)"
                              style="margin-top: 8px;">
                              {{ t('点击查看此字段的证据下探') }}
                            </div>
                          </div>
                        </template>
                      </bk-popover>
                      <!-- 没有字段映射或者没有证据下探 -->
                      <span
                        v-else
                        class="space">
                        {{ handleShowText(displayValueDict.eventData[key]?.value) }}
                        <audit-icon
                          v-if="hasCopyableValue(displayValueDict.eventData[key]?.value)"
                          v-bk-tooltips="t('复制')"
                          class="copy-btn"
                          type="copy"
                          @click.stop="handleCopyValue(displayValueDict.eventData[key]?.value)" />
                      </span>
                      <!-- 证据下探按钮 -->
                      <template v-if="drillMap.get(key)">
                        <bk-popover
                          placement="top"
                          theme="black">
                          <bk-button
                            class="ml8"
                            text
                            theme="primary"
                            @click="handleUseTool(
                              drillMap.get(key),
                              key
                            )">
                            <span
                              style="
                              padding: 2px 10px;
                              color: #3a84ff;
                              cursor: pointer;
                              background-color: #cddffe;
                              border-radius: 8px;
                            ">
                              {{ drillMap.get(key).drill_config.length }}
                            </span>
                          </bk-button>
                          <template #content>
                            <div>
                              <div
                                v-for="config in drillMap.get(key).drill_config"
                                :key="config.tool.uid">
                                {{ config.drill_name || getToolNameAndType(config.tool.uid).name }}
                                <bk-button
                                  class="ml8"
                                  text
                                  theme="primary"
                                  @click="(e: any) => {
                                    e.stopPropagation(); // 阻止事件冒泡
                                    handleUseTool(drillMap.get(key), key, config.tool.uid);
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
                        <audit-icon
                          v-bk-tooltips="t('复制')"
                          class="copy-btn"
                          type="copy"
                          @click.stop="handleCopyDrillTitles(key)" />
                      </template>
                    </render-info-item>
                  </div>
                </div>
              </template>
              <bk-exception
                v-else
                class="exception-part"
                scene="part"
                type="empty">
                {{ t('暂无数据') }}
              </bk-exception>
            </div>
          </div>
        </template>
        <bk-exception
          v-else
          class="exception-part"
          scene="part"
          type="empty">
          {{ t('暂无数据') }}
        </bk-exception>
      </div>
    </bk-loading>
    <div
      v-if="showMoreFieldsBtn"
      class="show-more-condition-btn">
      <bk-button
        class="show-more-btn"
        text
        @click="handleToggleShowMore">
        {{ isShowMore ? t('收起字段') : t('展开更多字段') }}
        <audit-icon
          class="show-more-icon"
          :class="{ active: isShowMore }"
          type="angle-double-down" />
      </bk-button>
    </div>
  </div>
  <!-- 循环所有工具 -->
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
  <add-event
    ref="addEventRef"
    :event-data="data"
    @add-success="handleAddSuccess" />
</template>

<script setup lang='tsx'>
// import _ from 'lodash';
  import {
    computed,
    nextTick,
    onBeforeUnmount,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import EventManageService from '@service/event-manage';
  import RiskManageService from '@service/risk-manage';
  import ToolManageService from '@service/tool-manage';

  import EventModel from '@model/event/event';
  import type RiskManageModel from '@model/risk/risk';
  import type StrategyInfo from '@model/risk/strategy-info';

  import EditTag from '@components/edit-box/tag.vue';

  // import Tooltips from '@components/show-tooltips-text/index.vue';
  import DialogVue from '@views/tools/tools-square/components/dialog/dialog.vue';

  import { execCopy } from '@utils/assist';
  import { formatStrategyNameWithId } from '@utils/format-strategy-name';

  import addEvent from '../add-event/index.vue';

  import LinkEventTimeline from './link-event-timeline.vue';
  import RenderInfoItem from './render-info-item.vue';

  import useRequest from '@/hooks/use-request';
  import { useToolDialog } from '@/hooks/use-tool-dialog';


  interface DrillItem {
    field_name: string;
    is_priority: boolean;
    description: string
    display_name: string;
    map_config?: {
      target_value: string | undefined,
      source_field: string | undefined,
    };
    drill_config: Array<{
      tool: {
        uid: string;
        version: number;
      };
      config: Array<{
        source_field: string;
        target_value_type: string;
        target_value: string;
        target_field_type: string;
      }>;
      drill_name?: string;
    }>;
    enum_mappings: {
      collection_id: string;
      mappings: Array<{
        key: string;
        name: string;
      }>;
    };
  }


  interface Props {
    strategyList: Array<{
      label: string,
      value: number
    }>,
    data: RiskManageModel & StrategyInfo
  }

  interface DisplayValue {
    value: any;
    isMappings: boolean;
    dict?: { name: string; key: string };
  }

  interface Emits {
    (e: 'getEventData', value: any): void
    (e: 'updatedData'): void
  }

  type DisplayValueDict = {
    [K in keyof Omit<typeof eventItem.value, 'event_data'>]: DisplayValue;
  } & {
    eventData: Record<string, DisplayValue>;
  };

  type DisplayValueKeys = keyof typeof displayValueDict.value;

  type DisplayValueKeysWithoutEventData = Exclude<DisplayValueKeys, 'eventData'>;
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const getStrategyDisplayText = (strategyId?: string | number | null) => {
    if (strategyId === undefined || strategyId === null || strategyId === '') {
      return '';
    }
    const normalizedId = Number(strategyId);
    const label = props.strategyList.find(item => item.value === normalizedId)?.label;
    return formatStrategyNameWithId(label, strategyId);
  };

  let timeout: number| undefined = undefined;

  const activeStatus = ref('');
  const loading = ref(false);
  const newIndex = ref<number[]>([]);
  const addEventRef = ref();
  const router = useRouter();
  const { t, locale } = useI18n();
  const linkEventList = ref<Array<EventModel>>([]); // 事件列表
  const hasLoadedData = ref(false); // 标记是否曾经加载过数据
  const currentPage = ref(1); // 当前页数
  const active = ref<number>(0);
  const eventItem = ref(new EventModel()); // 当前选中事件
  const isLoadingMore = ref(false); // 是否正在加载更多
  // const eventItemDataKeyArr = ref<Array<string[]>>([]); // 当前选中事件-事件数据
  // const showTooltips = ref(false); // 是否显示tooltips
  const isShowMore = ref(false);
  const detailRenderKey = ref(0);

  // 使用工具对话框hooks
  const {
    allOpenToolsData,
    dialogRefs,
    openFieldDown,
  } = useToolDialog();

  const labelWidth = computed(() => (locale.value === 'en-US' ? 160 : 120));

  const riskToolParams = computed(() => ({
    caller_resource_type: 'risk',
    caller_resource_id: props.data.risk_id,
    drill_field: '',
    event_start_time: props.data.event_time,
    event_end_time: props.data.event_end_time,
  }));

  const strategyInfo = computed(() => [
    ...props.data.event_basic_field_configs,
    ...props.data.event_data_field_configs,
    ...props.data.event_evidence_field_configs,
  ]);

  // 基本信息
  const basicInfo = computed(() => group(props.data.event_basic_field_configs.filter(item => item.is_show)));

  // 显示字段下钻的字段
  const drillMap = computed(() => {
    const map = new Map();
    strategyInfo.value.forEach((item) => {
      if (item.drill_config && item.drill_config.length) {
        map.set(item.field_name, item);
      }
    });
    return map;
  });

  // 有字典翻译的字段
  const dictDataMap = computed(() => {
    const map: Map<string, { name: string; key: string }[]> = new Map();
    strategyInfo.value.forEach((item) => {
      if (item.enum_mappings?.mappings.length) {
        map.set(item.field_name, item.enum_mappings.mappings);
      }
    });
    return map;
  });

  // 预处理所有展示值
  const displayValueDict = computed<DisplayValueDict>(() => {
    if (!eventItem.value) {
      return {
        eventData: {},
      };
    }
    const baseKeys = Object.keys(eventItem.value).filter(key => key !== 'event_data');
    const baseResult = baseKeys.reduce((acc, key) => {
      acc[key as keyof typeof acc] = getDisplayValue(key, eventItem.value[key as keyof typeof eventItem.value]);
      return acc;
    }, {} as any);

    const eventDataResult = Object.keys(eventItem.value.event_data || {}).reduce((acc, key) => {
      acc[key] = getDisplayValue(key, eventItem.value.event_data[key]);
      return acc;
    }, {} as Record<string, DisplayValue>);

    return {
      ...baseResult,
      eventData: eventDataResult,
    };
  }) ;

  // 套餐下拉列表使用
  const displayValueDictEventData = computed(() => {
    // 遍历 displayValueDict.value.eventData 对象的Key value 输出数组
    const result = Object.keys(displayValueDict.value.eventData).map((key) => {
      // 如果key在dictMap里面，使用原始值；否则使用翻译后的值
      const isInDictMap = dictDataMap.value.has(key);
      const rawValue = eventItem.value.event_data?.[key];
      const displayValue = isInDictMap ? rawValue : displayValueDict.value.eventData[key].value;

      return {
        text: key,
        value: displayValue,
        lable: strategyInfo.value.find(item => item.field_name === key)?.display_name || key,
      };
    });
    return result;
  });

  // 事件数据展示字段，从策略中获取，重点展示的字段
  const eventDataKeyArr = computed(() => {
    const eventInfo = [
      ...props.data.event_data_field_configs,
      ...props.data.event_evidence_field_configs,
    ];
    const eventInfoKeys = eventInfo.filter(item => item.is_show && item.is_priority).map(item => item.field_name);
    return group(eventInfoKeys);
  });

  // 事件数据展示字段，从策略中获取，非重点展示的字段
  const eventDataKeyArrNormal = computed(() => {
    const eventInfo = [
      ...props.data.event_data_field_configs,
      ...props.data.event_evidence_field_configs,
    ];
    const eventInfoKeys = eventInfo.filter(item => item.is_show && !item.is_priority).map(item => item.field_name);
    return group(eventInfoKeys);
  });

  const showEventDataNormal = computed(() => (
    (eventDataKeyArrNormal.value.length && isShowMore.value) || !eventDataKeyArr.value.length
  ));

  const visibleEventDetailRows = computed(() => {
    const rows: Array<string[]> = [...eventDataKeyArr.value];
    if (showEventDataNormal.value) {
      rows.push(...eventDataKeyArrNormal.value);
    }
    return rows;
  });

  const showMoreFieldsBtn = computed(() => (
    hasLoadedData.value
    && linkEventList.value.length > 0
    // 有重点字段时非重点字段才会被收起；两者都有才需要展开组件
    && eventDataKeyArr.value.length > 0
    && eventDataKeyArrNormal.value.length > 0
    && !(activeStatus.value === 'new' && newIndex.value.includes(active.value))
  ));

  // 去重字段
  const distinctEventDataKeyArr = computed(() => {
    const eventInfo = [
      ...props.data.event_basic_field_configs,
      ...props.data.event_data_field_configs,
      ...props.data.event_evidence_field_configs,
    ];
    return eventInfo.filter(item => item.duplicate_field).map(item => item.field_name);
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
          return parsedArray.length > 0 ? parsedArray.join(',') : '--';
        }
      } catch (error) {
        return value  || '--';
      }
    }
    if (value === '') {
      return '--';
    }
    // 3. 其他情况直接返回原值
    return value;
  };

  const hasCopyableValue = (value: any) => {
    const text = handleShowText(value);
    return text !== undefined && text !== null && text !== '' && text !== '--';
  };

  const handleCopyValue = (value: any) => {
    if (!hasCopyableValue(value)) {
      return;
    }
    execCopy(String(handleShowText(value)), t('复制成功'));
  };

  // 复制证据下探的全部标题
  const handleCopyDrillTitles = (fieldName: string) => {
    const drillItem = drillMap.value.get(fieldName);
    const titles = (drillItem?.drill_config || [])
      .map((config: any) => config.drill_name || getToolNameAndType(config.tool.uid).name)
      .filter((name: string) => !!name);
    if (!titles.length) {
      return;
    }
    execCopy(titles.join('\n'), t('复制成功'));
  };

  // 将各种类型转换为字符串，模拟 Vue 模板的显示效果
  const convertToString = (value: any): string => {
    // Vue 模板显示逻辑：
    // 1. null/undefined 显示为空字符串
    if (value === null || value === undefined) {
      return '';
    }

    // 2. 布尔值在 Vue 模板中显示为字符串
    if (typeof value === 'boolean') {
      return value.toString();
    }

    // 3. 数字直接转换为字符串
    if (typeof value === 'number') {
      return value.toString();
    }

    // 4. 字符串直接返回
    if (typeof value === 'string') {
      return value;
    }

    // 5. 数组在 Vue 模板中会调用 join() 方法，默认用逗号连接
    if (Array.isArray(value)) {
      return value.join(',');
    }

    // 6. 对象在 Vue 模板中会调用 JSON.stringify()
    if (typeof value === 'object') {
      try {
        return JSON.stringify(value);
      } catch {
        return '[object Object]';
      }
    }

    // 7. 其他类型转换为字符串
    return String(value);
  };

  // 获取所有工具
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

  // 获取标签列表
  const {
    data: tagData,
    run: fetchToolTags,
  } = useRequest(ToolManageService.fetchToolTags, {
    defaultValue: [],
  });

  const getToolNameAndType = (uid: string) => {
    const tool = allToolsData.value?.find(item => item.uid === uid);
    return tool ? {
      name: tool.name,
      type: tool.tool_type,
    } : {
      name: '',
      type: '',
    };
  };
  const getLinkEventKey = (item: EventModel & { manual_event_id?: string | number }) => {
    if (item.event_id) {
      return `event:${item.event_id}`;
    }
    if (item.manual_event_id !== undefined && item.manual_event_id !== null && item.manual_event_id !== '') {
      return `manual:${item.manual_event_id}`;
    }
    return `raw:${item.raw_event_id || ''}_${item.event_time || ''}`;
  };

  const mergeLinkEvents = (existing: EventModel[], incoming: EventModel[]) => {
    const seen = new Set(existing.map(item => getLinkEventKey(item)));
    const merged = [...existing];
    incoming.forEach((item) => {
      const key = getLinkEventKey(item);
      if (!seen.has(key)) {
        merged.push(item);
        seen.add(key);
      }
    });
    return merged;
  };

  // 未同步事件前置合并（按 event_id / manual_event_id 去重，避免轮询重复堆叠）
  const mergeUnsyncedEvents = (unsynced: EventModel[], existing: EventModel[]) => {
    const seen = new Set(existing.map(item => getLinkEventKey(item)));
    const uniqueUnsynced = unsynced.filter((item) => {
      const key = getLinkEventKey(item);
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
    return uniqueUnsynced.concat(existing);
  };

  const clearRefreshTimeout = () => {
    if (timeout) {
      clearTimeout(timeout);
      timeout = undefined;
    }
  };

  const scheduleNewEventPoll = () => {
    clearRefreshTimeout();
    timeout = window.setTimeout(() => {
      timeout = undefined;
      timeoutRefresh();
    }, 5000);
  };

  const {
    data: addEventData,
    run: getAddEventList,
  } = useRequest(RiskManageService.fetchAddEventList, {
    defaultValue: {
      di: '',
    },
    onSuccess() {
    },
  });

  const {
    data: linkEventData,
    run: fetchLinkEvent,
  } = useRequest(EventManageService.fetchEventList, {
    defaultValue: {
      results: [],
      page: 1,
      num_pages: 1,
      total: 1,
    },
    onSuccess() {
      getAddEventList({
        id: props.data.risk_id,
      }).then(() => {
        // 触底加载，拼接 - 使用动态去重字段
        loading.value = false;
        isLoadingMore.value = false;

        // 如果是第一页，重置新事件索引；保留当前列表避免弹层闪闭
        if (currentPage.value === 1) {
          newIndex.value = [];
        }

        nextTick(() => {
          const wasPollingNewEvents = Boolean(timeout) || activeStatus.value === 'new';

          if (linkEventData.value.results.length) {
            activeStatus.value = '';
            // 触底加载时追加数据，首次加载时替换数据
            let allEvents = currentPage.value === 1
              ? linkEventData.value.results
              : mergeLinkEvents(linkEventList.value, linkEventData.value.results);
            if (distinctEventDataKeyArr.value.length) {
              // 根据指定字段组合进行去重（包含关系）
              allEvents = allEvents.filter((event, index, self) => {
                // 根据 distinctEventDataKeyArr 中的字段生成当前事件的字段值数组
                const currentValues = distinctEventDataKeyArr.value.map(key => event[key as keyof EventModel] || event.event_data?.[key] || '');

                // 查找第一个具有包含关系的事件索引
                const firstIndex = self.findIndex((e) => {
                  const eValues = distinctEventDataKeyArr.value.map(key => e[key as keyof EventModel] || e.event_data?.[key] || '');
                  // 检查所有字段值都完全相同（转换为字符串比较）
                  return currentValues.every((currentValue, i) => {
                    // 将值转换为字符串进行比较，处理各种特殊类型
                    const currentStr = convertToString(currentValue);
                    const eValueStr = convertToString(eValues[i]);
                    return currentStr === eValueStr;
                  });
                });

                // 只保留第一次出现的事件（去重）
                return index === firstIndex;
              });
            }
            linkEventList.value = allEvents;
          }
          if (addEventData.value.unsynced_events?.length > 0) {
            linkEventList.value = mergeUnsyncedEvents(
              addEventData.value.unsynced_events,
              linkEventList.value,
            );
            activeStatus.value = linkEventList.value[0]?.status || '';
          }

          newIndex.value = linkEventList.value.map((item, index) => {
            if (item.status === 'new') {
              return index;
            }
            return -1;
          }).filter(item => item !== -1);

          if (linkEventList.value.some(item => item.status === 'new')) {
            // 仍有未同步事件，继续轮询（先清旧定时器，避免叠加）
            activeStatus.value = 'new';
            scheduleNewEventPoll();
          } else {
            // 同步完成，停止轮询；仅在此前处于轮询态时通知父组件刷新一次
            clearRefreshTimeout();
            activeStatus.value = '';
            if (wasPollingNewEvents) {
              emits('updatedData');
            }
          }
          // 默认获取第一个
          [eventItem.value] = linkEventList.value;
          // 标记已加载过数据
          hasLoadedData.value = true;
        });
      });
    },
  });

  const hasMoreTimelineEvents = computed(() => {
    const { total, num_pages: numPages } = linkEventData.value;
    if (!total) {
      return false;
    }
    if (linkEventList.value.length >= total) {
      return false;
    }
    if (numPages && currentPage.value >= numPages) {
      return false;
    }
    return true;
  });

  // 执行定时器刷新列表
  const timeoutRefresh = () => {
    getAddEventList({
      id: props.data.risk_id,
    }).then((data) => {
      currentPage.value = 1; // 重置页码
      fetchLinkEvent({
        start_time: data.event_time,
        end_time: data.event_end_time,
        risk_id: data.risk_id,
        page: currentPage.value,
        page_size: 50,
        scope_id: props.data.scene_id,
        scope_type: 'scene',
      });
    });
  };
  const handleTimelineLoadMore = () => {
    if (!hasMoreTimelineEvents.value || isLoadingMore.value) {
      return;
    }
    isLoadingMore.value = true;
    currentPage.value += 1;
    fetchLinkEvent({
      start_time: props.data.event_time,
      end_time: props.data.event_end_time,
      risk_id: props.data.risk_id,
      page: currentPage.value,
      page_size: 50,
      scope_id: props.data.scene_id,
      scope_type: 'scene',
    });
  };

  const handlerSelectByIndex = (index: number) => {
    const item = linkEventList.value[index];
    if (item) {
      handlerSelect(item, index);
    }
  };

  // 转为二维数组
  const group = (array: Array<any>, subGroupLength: number = 2) => {
    let index = 0;
    const newArray = [];
    while (index < array.length) {
      newArray.push(array.slice(index, index += subGroupLength));
    }
    return newArray;
  };

  const handlerSelect = (item: EventModel, index: number) => {
    eventItem.value = item;
    active.value = index;
    activeStatus.value = item?.status || '';
  };

  const handlerStrategy = () => {
    const to = router.resolve({
      name: 'strategyList',
      query: {
        strategy_id: eventItem.value.strategy_id,
        scope_id: props.data.scene_id,
        scope_type: 'scene',
      },
    });
    window.open(to.href, '_blank');
  };


  // 打开工具(风险单打开就是下钻模式)
  const handleUseTool = (
    drillDownItem: DrillItem,
    fieldName: string,
    activeUid?: string,
  ) => {
    riskToolParams.value.drill_field = fieldName;
    const drillDownItemRowData = eventItem.value;

    // 需要传递额外的riskToolParams参数
    const uids = drillDownItem.drill_config.map(config => config.tool.uid).join('&');
    if (!(allOpenToolsData.value.find(item => item === uids))) {
      allOpenToolsData.value.push(uids);
    }

    nextTick(() => {
      if (dialogRefs.value[uids]) {
        dialogRefs.value[uids].openDialog(uids, drillDownItem, drillDownItemRowData, activeUid, riskToolParams.value);
      }
    });
  };

  // 切换显示更多字段
  const handleToggleShowMore = () => {
    isShowMore.value = !isShowMore.value;
    detailRenderKey.value += 1;
  };

  // 如果有字段从字典取name
  const getDisplayValue = (key: string, value: unknown) => {
    if (dictDataMap.value.has(key)) {
      const dictValue = dictDataMap.value.get(key)?.find(item => item.key === String(value));
      if (dictValue) {
        return {
          isMappings: true,
          value: dictValue.name,
          dict: dictValue,
        };
      }
      return {
        isMappings: false,
        value,
      };
    }
    return {
      isMappings: false,
      value,
    };
  };

  const handleAddEvent = () => {
    addEventRef.value?.show();
  };

  // 添加事件成功
  const handleAddSuccess = () => {
    active.value = 0;
    // 立即触发父组件刷新数据，更新 report_generating 状态
    emits('updatedData');
    // 先立即获取未同步的事件，让新添加的事件立即显示
    getAddEventList({
      id: props.data.risk_id,
    }).then(() => {
      // 如果有未同步的事件，立即显示在列表中
      if (addEventData.value.unsynced_events?.length > 0) {
        linkEventList.value = mergeUnsyncedEvents(
          addEventData.value.unsynced_events,
          linkEventList.value,
        );
        activeStatus.value = linkEventList.value[0]?.status || '';
        [eventItem.value] = linkEventList.value;
        hasLoadedData.value = true;
        // 标记新添加的事件索引
        newIndex.value = linkEventList.value.map((item, index) => {
          if (item.status === 'new') {
            return index;
          }
          return -1;
        }).filter(item => item !== -1);
        // 如果有新事件，启动定时器刷新（避免重复叠加定时器）
        if (linkEventList.value.some(item => item.status === 'new')) {
          activeStatus.value = 'new';
          scheduleNewEventPoll();
        }
      }
      // 然后刷新完整的事件列表
      currentPage.value = 1; // 重置页码
      fetchLinkEvent({
        start_time: props.data.event_time,
        end_time: props.data.event_end_time,
        risk_id: props.data.risk_id,
        page: currentPage.value,
        page_size: 50,
        scope_id: props.data.scene_id,
        scope_type: 'scene',
      });
    });
  };
  // 防抖处理
  let fetchTimeout: number | undefined;
  watch(() => props.data, (data, oldData) => {
    // 只有当 risk_id 真正发生变化时才触发
    if (data.risk_id && data.risk_id !== oldData?.risk_id) {
      // 清除之前的定时器，实现防抖
      if (fetchTimeout) {
        clearTimeout(fetchTimeout);
      }

      fetchTimeout = setTimeout(() => {
        fetchLinkEvent({
          start_time: data.event_time,
          end_time: data.event_end_time,
          risk_id: data.risk_id,
          page: currentPage.value,
          page_size: 50,
          scope_id: props.data.scene_id,
          scope_type: 'scene',
        });
      }, 100); // 100ms 防抖延迟
    }
  }, {
    immediate: true,
  });

  watch(() => displayValueDictEventData.value, (data) => {
    emits('getEventData', data);
  }, {
    immediate: true,
    deep: true,
  });

  watch(() => props.data, (data) => {
    if (data) {
      setTimeout(() => {
        fetchAllTools({
          scope_id: data.scene_id,
          scope_type: 'scene',
        });
        fetchToolTags({
          scope_id: data.scene_id,
          scope_type: 'scene',
        });
      }, 0);
    }
  });
  onMounted(() => {
    loading.value = true;
  });

  onBeforeUnmount(() => {
    if (fetchTimeout) {
      clearTimeout(fetchTimeout);
    }
    clearRefreshTimeout();
  });
</script>
<style lang="postcss" scoped>
.risk-manage-detail-linkevent-part {
  position: relative;

  .show-more-condition-btn {
    position: absolute;
    bottom: calc(-11px - var(--link-event-wrap-padding-bottom, 10px));
    left: 50%;
    z-index: 2;
    transform: translateX(-50%);

    .show-more-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 120px;
      height: 22px;
      color: #63656e;
      background: #f0f1f5;
      border: 1px solid #dcdee5;
      border-radius: 12px;

      &:hover {
        color: #63656e;
        background: #e1e3e9;
      }
    }

    .show-more-icon {
      margin-left: 4px;
    }

    .active {
      transform: rotateZ(-180deg);
      transition: all .15s;
    }
  }

  .timeline-empty-action {
    display: flex;
    justify-content: flex-end;
    padding: 8px 24px 16px;
  }

  .add-event {
    font-size: 12px;
    line-height: 20px;
    color: #3a84ff;
    cursor: pointer;

    .add-fill-event {
      margin-right: 4px;
    }
  }

  .body {
    display: flex;
    flex-direction: column;
    width: 100%;
  }

  .list-item-detail {
    width: 100%;
    padding: 0 24px;
    box-sizing: border-box;

    .title {
      margin-bottom: 16px;
      font-size: 14px;
      font-weight: 700;
      line-height: 22px;
      color: #313238;
    }

    .detail-content {
      width: 100%;
      height: auto;
    }

    .section-divider {
      height: 1px;
      margin: 24px 0;
      background: #dcdee5;
    }

    .exception-part {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 300px;
    }

    .important-information {
      padding: 12px 0;
      margin-bottom: 24px;
      background-color: #fafbfd;

      .title {
        padding-left: 8px;
        border-left: 3px solid #3a84ff;
      }

      .render-info-item {
        width: 50%;
        align-items: flex-start;

        .info-value {
          word-break: break-all;

          &:hover {
            .copy-btn {
              opacity: 100%;
            }
          }
        }
      }
    }

    .base-info {
      .render-info-item .info-value:hover .copy-btn {
        opacity: 100%;
      }
    }

    .data-info {
      /* border: 1px solid #ecedf1; */

      .data-info-row:last-child {
        .data-info-item-key,
        .data-info-item-value {
          border-bottom: 0;
        }
      }

      .data-info-item:last-child {
        .data-info-item-value {
          border-right: 0;
        }
      }

      .data-info-item {
        width: 50%;

        .data-info-item-key,
        .data-info-item-value {
          display: flex;
          align-items: center;
          padding: 6px 12px;
          border-right: 1px solid #ecedf1;
          border-bottom: 1px solid #ecedf1;
        }

        .data-info-item-key {
          width: 160px;
          background-color: #fafbfd;
          justify-self: flex-end;

          &>span {
            display: inline-block;
            width: 100%;
            text-align: right;
          }
        }

        .data-info-item-value {
          flex: 1;
          word-break: break-all;
        }
      }
    }

    .evidence-info {
      display: flex;
      max-width: 1000px;
      border-top: 1px solid #ecedf1;
      border-left: 1px solid #ecedf1;

      .evidence-info-value-wrap {
        display: flex;
        flex-wrap: nowrap;
      }

      .evidence-info-key,
      .evidence-info-value {
        display: inline-block;
        width: 168px;
        flex: 1;

        & > div {
          height: 32px;
          padding: 0 12px;
          line-height: 32px;
          border-right: 1px solid #ecedf1;
          border-bottom: 1px solid #ecedf1;

          .evidence-info-item-text {
            width: 100%;
            height: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            word-break: break-all;
            white-space: nowrap;
          }
        }
      }

      .evidence-info-key {
        width: 160px;
        text-align: right;
        background-color: #fafbfd;
      }
    }

    .active {
      transform: rotateZ(-180deg);
      transition: all .15s;
    }
  }
}

.evidence-info-value-tooltips {
  max-width: 80%
}

.event-create-detail-loading {
  width: 100%;

  .event-create-loading {
    .event-create-loading-box {
      position: relative;
      width: 100%;
      height: 50vh;
    }

    :deep(.bk-loading-indicator) {
      margin-left: -80px !important;
    }

    :deep(.bk-loading-title) {
      margin-left: -15px !important;
    }
  }
}

.space {
  white-space: pre-line;

  &:hover {
    .copy-btn {
      opacity: 100%;
    }
  }
}

.copy-btn {
  margin-left: 8px;
  color: #3a84ff;
  cursor: pointer;
  opacity: 0%;

  &:hover {
    opacity: 100%;
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}
</style>

