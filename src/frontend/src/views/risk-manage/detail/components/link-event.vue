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
    <div
      v-if="linkEventList.length"
      class="show-side-condition-btn"
      :style="{ left: isShowSide ? '-16px' : '164px' }">
      <bk-button
        class="show-more-btn"
        text
        @click="() => isShowSide = !isShowSide">
        <audit-icon
          :style="{ transform: isShowSide ? 'rotateZ(90deg)' : 'rotateZ(-90deg)' }"
          type="angle-double-up" />
      </bk-button>
    </div>

    <div class="title">
      <span> {{ t('关联事件') }}</span>
      <span
        v-if="data.status !== 'closed'"
        class="add-event"
        @click="handleAddEvent">
        <audit-icon
          class="add-fill-event"
          type="add-fill" />{{ t('新建关联事件') }}</span>
    </div>
    <bk-loading :loading="loading">
      <div
        :key="detailRenderKey"
        class="body">
        <template v-if="linkEventList.length">
          <div
            class="list"
            :style="isShowSide ? 'width: 0px' : 'min-width: 164px;'">
            <scroll-faker @scroll="handleScroll">
              <transition name="draw">
                <div>
                  <div
                    v-for="(item, index) in linkEventList"
                    v-show="!isShowSide"
                    :key="index"
                    class="list-item"
                    :class="[
                      { active: active === index },
                    ]"
                    @click="handlerSelect(item, index)">
                    {{ item?.event_time }}
                  </div>
                </div>
              </transition>
            </scroll-faker>
          </div>

          <!-- detail -->
          <div v-if="activeStatus === 'new' && newIndex.includes(active)">
            <div class="frontend-create">
              <audit-icon
                class="create-icon"
                type="loading" />
              {{ t('事件创建中') }}
            </div>
          </div>
          <div
            v-else
            class="list-item-detail"
            :style="{
              width: isShowSide ? '100%' : 'calc(100% - 164px)',
            }">
            <div style=" height: auto;padding-left: 12px;">
              <!-- 基本信息 -->
              <template v-if="basicInfo.length">
                <div class="title mt16">
                  {{ t('基本信息') }}
                </div>
                <div class="base-info">
                  <render-info-block
                    v-for="(basicArr, basicIndex) in basicInfo"
                    :key="basicIndex"
                    class="flex mt16"
                    style="justify-content: space-between; gap: 24px;">
                    <render-info-item
                      v-for="(basicItem, itemIndex) in basicArr"
                      :key="itemIndex"
                      :description="basicItem.description"
                      :label="basicItem.display_name"
                      :label-width="labelWidth"
                      :label-width-percent="25"
                      style="flex-basis: 50%;">
                      <!-- 策略id -->
                      <template v-if="basicItem.field_name === 'strategy_id'">
                        <bk-button
                          v-if="strategyList.find((item: any) => item.value === eventItem.strategy_id)?.label"
                          text
                          theme="primary"
                          @click="handlerStrategy()">
                          {{ strategyList.find((item: any) => item.value === eventItem.strategy_id)?.label }}
                        </bk-button>
                        <span v-else> -- </span>
                        <audit-icon
                          v-bk-tooltips="t('复制')"
                          class="copy-btn"
                          type="copy"
                          @click.stop="handleCopyValue(strategyList.find((item: any) => item.value === eventItem.strategy_id)?.label)" />
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
                                :show-copy="false"
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
                            style="display: inline-block;" />
                          <span v-else>
                            {{ handleShowText(displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.value ) || '--' }}
                          </span>
                          <audit-icon
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
                          <audit-icon
                            v-bk-tooltips="t('复制')"
                            class="copy-btn"
                            type="copy"
                            @click.stop="handleCopyValue(displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.value)" />
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
                      </template>
                    </render-info-item>
                  </render-info-block>
                </div>
              </template>

              <!-- 事件数据 -->
              <div class="title">
                {{ t('事件数据') }}
              </div>
              <template v-if="eventDataKeyArr.length || eventDataKeyArrNormal.length">
                <div
                  v-if="eventDataKeyArr.length"
                  class="data-info"
                  style="background-color: #f5f7fa;">
                  <render-info-block
                    v-for="(keyArr, keyIndex) in eventDataKeyArr"
                    :key="keyIndex"
                    class="flex mt16"
                    style="justify-content: space-between; gap: 24px;">
                    <render-info-item
                      v-for="(key, index) in keyArr"
                      :key="index"
                      :description="strategyInfo.find((item: any) => item.field_name === key)?.description || ''"
                      :label="strategyInfo.find((item: any) => item.field_name === key)?.display_name || key"
                      :label-width="labelWidth"
                      :label-width-percent="25"
                      style="flex-basis: 50%;">
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
                          <audit-icon
                            v-bk-tooltips="t('复制')"
                            class="copy-btn"
                            type="copy"
                            @click.stop="handleCopyValue(displayValueDict.eventData[key]?.value)" />
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
                      </template>
                    </render-info-item>
                  </render-info-block>
                </div>
                <div
                  v-if="(eventDataKeyArrNormal.length && isShowMore) || !eventDataKeyArr.length"
                  class="data-info"
                  style="margin-top: 0;">
                  <render-info-block
                    v-for="(keyArr, keyIndex) in eventDataKeyArrNormal"
                    :key="keyIndex"
                    class="flex mt16">
                    <render-info-item
                      v-for="(key, index) in keyArr"
                      :key="index"
                      :description="strategyInfo.find((item: any) => item.field_name === key)?.description || ''"
                      :label="strategyInfo.find((item: any) => item.field_name === key)?.display_name || key"
                      :label-width="labelWidth"
                      :label-width-percent="25"
                      style="width: 50%;">
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
                                {{ displayValueDict.eventData[key]?.dict?.name }}
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
                            <audit-icon
                              v-bk-tooltips="t('复制')"
                              class="copy-btn"
                              type="copy"
                              @click.stop="handleCopyValue(displayValueDict.eventData[key]?.value)" />
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
                      </template>
                    </render-info-item>
                  </render-info-block>
                </div>
                <div
                  v-if="eventDataKeyArr.length && eventDataKeyArrNormal.length"
                  style="height: 20px; margin-top: 10px;">
                  <bk-button
                    style="float: right;"
                    text
                    theme="primary"
                    @click="handleToggleShowMore">
                    <audit-icon
                      :class="{ active: isShowMore }"
                      style=" margin-right: 5px;"
                      type="angle-double-down" />
                    {{ isShowMore ? t('收起字段') : t('展开更多字段') }}
                  </bk-button>
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
  import RenderInfoBlock from '@views/strategy-manage/list/components/render-info-block.vue';
  import DialogVue from '@views/tools/tools-square/components/dialog.vue';

  import { execCopy } from '@utils/assist';

  import addEvent from '../add-event/index.vue';

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
  const isShowSide = ref(false);
  let timeout: number| undefined = undefined;

  const activeStatus = ref('');
  const loading = ref(false);
  const newIndex = ref<number[]>([]);
  const addEventRef = ref();
  const router = useRouter();
  const { t, locale } = useI18n();
  const linkEventList = ref<Array<EventModel>>([]); // 事件列表
  const currentPage = ref(1); // 当前页数
  const active = ref<number>(0);
  const eventItem = ref(new EventModel()); // 当前选中事件
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

  const handleCopyValue = (value: any) => {
    const text = handleShowText(value);
    if (text === undefined || text === null || text === '' || text === '--') {
      return;
    }
    execCopy(String(text), t('复制成功'));
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
  } = useRequest(ToolManageService.fetchAllTools, {
    defaultValue: [],
    manual: true,
  });

  // 获取标签列表
  const {
    data: tagData,
  } = useRequest(ToolManageService.fetchToolTags, {
    defaultValue: [],
    manual: true,
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
        linkEventList.value = [];
        newIndex.value = [];
        if (linkEventData.value.results.length) {
          activeStatus.value =  '';
          const allEvents = [...linkEventList.value, ...linkEventData.value.results];
          linkEventList.value = allEvents;
          if (distinctEventDataKeyArr.value.length) {
            // 根据指定字段组合进行去重（包含关系）
            linkEventList.value =  allEvents.filter((event, index, self) => {
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
        }
        if (addEventData.value.unsynced_events.length > 0) {
          linkEventList.value = addEventData.value.unsynced_events.concat(linkEventList.value);
          activeStatus.value = linkEventList.value[0]?.status || '';
        }

        newIndex.value = linkEventList.value.map((item, index) => {
          if (item.status === 'new') {
            return index;
          }
          return -1;
        }).filter(item => item !== -1);

        if (linkEventList.value.some(item => item.status === 'new')) {
          // 执行定时器刷新列表
          activeStatus.value = 'new';
          timeout = setTimeout(() => {
            timeoutRefresh();
          }, 5000);
        } else {
          // 消除定时器 慢5秒确保最新数据
          if (timeout) {
            activeStatus.value = 'new';
            setTimeout(() => {
              activeStatus.value = '';
              emits('updatedData');
              timeoutRefresh();
              clearTimeout(timeout);
              timeout = undefined;
            }, 5000);
          }
        }
        // 默认获取第一个
        [eventItem.value] = linkEventList.value;
        isShowSide.value = !(linkEventList.value.length > 1);
      });
    },
  });
  // 执行定时器刷新列表
  const timeoutRefresh = () => {
    getAddEventList({
      id: props.data.risk_id,
    }).then((data) => {
      fetchLinkEvent({
        start_time: data.event_time,
        end_time: data.event_end_time,
        risk_id: data.risk_id,
        page: currentPage.value,
        page_size: 50,
      });
    });
  };
  const handleScroll = (event: Event) => {
    const target = event.target as HTMLDivElement;
    // 下拉触底没有加载完时，继续获取列表
    // eslint-disable-next-line max-len
    if ((target.scrollTop + target.clientHeight === target.scrollHeight) && linkEventList.value.length < linkEventData.value.total) {
      currentPage.value += 1;
      fetchLinkEvent({
        start_time: props.data.event_time,
        end_time: props.data.event_end_time,
        risk_id: props.data.risk_id,
        page: currentPage.value,
        page_size: 50,
      });
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
    linkEventList.value = [];
    nextTick(() => {
      fetchLinkEvent({
        start_time: props.data.event_time,
        end_time: props.data.event_end_time,
        risk_id: props.data.risk_id,
        page: currentPage.value,
        page_size: 50,
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

  onMounted(() => {
    loading.value = true;
    const observer = new MutationObserver(() => {
      const detail = document.querySelector('.list-item-detail');
      const list = document.querySelector('.list') as HTMLDivElement;
      if (detail && list) {
        // 设置左边list的高度和右边详情一样高
        list.style.height = `${detail.scrollHeight}px`;
      }
    });
    observer.observe(document.querySelector('.body') as Node, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
    });

    onBeforeUnmount(() => {
      observer.takeRecords();
      observer.disconnect();
      // 清理定时器
      if (fetchTimeout) {
        clearTimeout(fetchTimeout);
      }
    });
  });
</script>
<style lang="postcss">
.risk-manage-detail-linkevent-part {
  position: relative;

  .show-side-condition-btn {
    position: absolute;
    top: 50%;
    overflow: hidden;
    border-radius: 0 5px 5px 0;
    box-shadow: 0 2px 4px 0 #1919290d;

    .show-more-btn {
      width: 14px;
      height: 65px;
      line-height: 5px;
      color: #fff;
      background: #eaecef;

      &:hover {
        background-color: #c4c6cc;
      }
    }
  }

  .title {
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;

    .add-event {
      margin-left: 20px;
      font-size: 12px;
      font-weight: 400;
      line-height: 20px;
      letter-spacing: 0;
      color: #3a84ff;
      cursor: pointer;

      .add-fill-event {
        margin-right: 3px;
      }
    }
  }

  .body {
    display: flex;
    margin-top: 14px;

    .list {
      display: inline-block;
      min-height: 200px;

      /* height: 500px; */
      overflow: hidden;
      text-align: center;
      background: #f5f7fa;
      border-radius: 4px;

      .list-item {
        height: 32px;
        line-height: 32px;
        cursor: pointer;

        &:hover {
          background-color: #eaebf0;
        }
      }

      .active {
        color: #3a84ff !important;
        background: #e1ecff;
        border-left: 2px solid #3a84ff;

        &:hover {
          background: #e1ecff !important;
        }
      }
    }

    .list-item-detail {
      padding-left: 12px;

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
        margin-bottom: 24px;

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

      .data-info {
        padding: 10px 0;
        margin-top: 16px;

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
}

.evidence-info-value-tooltips {
  max-width: 80%
}

.frontend-create {
  position: absolute;
  top: 50px;
  left: 50%;
  color: #3a84ff;
  transform: translateX(-50%);

  .create-icon {
    animation: spin 1s linear infinite
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
