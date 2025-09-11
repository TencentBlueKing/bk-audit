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
    <div class="title">
      {{ t('关联事件') }}
    </div>
    <div class="body">
      <template v-if="linkEventList.length">
        <div
          class="list"
          :style="isShowMore ? 'width: 15px' : 'min-width: 164px;'">
          <scroll-faker @scroll="handleScroll">
            <transition name="draw">
              <div>
                <div
                  v-for="(item, index) in linkEventList"
                  v-show="!isShowMore"
                  :key="index"
                  class="list-item"
                  :class="[
                    { active: active === index },
                  ]"
                  @click="handlerSelect(item, index)">
                  {{ item.event_time }}
                </div>
                <div class="show-more-condition-btn">
                  <bk-button
                    class="show-more-btn"
                    text
                    @click="() => isShowMore = !isShowMore">
                    <audit-icon
                      :class="{ audit: isShowMore }"
                      style="margin-top: -15px;"
                      type="angle-double-up" />
                  </bk-button>
                </div>
              </div>
            </transition>
          </scroll-faker>
        </div>


        <!-- detail -->
        <div
          class="list-item-detail"
          :style="isShowMore ? `width: calc(100% - 15px);`: `width: calc(100% - 164px);`">
          <div
            v-if="importantInformation.length"
            class="important-information">
            <!-- 重点信息 -->
            <div class="title">
              {{ t('重点信息') }}
            </div>
            <render-info-block
              v-for="(item, index) in importantInformation"
              :key="index"
              class="flex mt16"
              style="margin-bottom: 12px;">
              <render-info-item
                v-for="(subItem, subIndex) in item"
                :key="subIndex"
                :description="subItem.description"
                :label="subItem.display_name"
                :label-width="labelWidth">
                <span
                  v-bk-tooltips="{
                    content: t('映射对象', {
                      key: displayValueDict[subItem.field_name as DisplayValueKeysWithoutEventData]?.dict?.key ||
                        displayValueDict.eventData[subItem.field_name]?.dict?.key,
                      name: displayValueDict[subItem.field_name as DisplayValueKeysWithoutEventData]?.dict?.name ||
                        displayValueDict.eventData[subItem.field_name]?.dict?.name,
                    }),
                    disabled: !displayValueDict[subItem.field_name as DisplayValueKeysWithoutEventData]?.isMappings &&
                      !displayValueDict.eventData[subItem.field_name]?.isMappings,
                  }"
                  :class="[
                    displayValueDict[subItem.field_name as DisplayValueKeysWithoutEventData]?.isMappings ||
                      displayValueDict.eventData[subItem.field_name]?.isMappings ?
                        'tips' : '',
                  ]">
                  {{ displayValueDict[subItem.field_name as DisplayValueKeysWithoutEventData]?.value ||
                    displayValueDict.eventData[subItem.field_name]?.value }}
                </span>
                <template v-if="drillMap.get(subItem.field_name)">
                  <bk-button
                    class="ml8"
                    text
                    theme="primary"
                    @click="handleClick(
                      subItem,
                      drillMap.get(subItem.field_name).drill_config.tool.uid,
                      subItem.field_name
                    )">
                    {{ t('查看') }}
                  </bk-button>
                </template>
              </render-info-item>
            </render-info-block>
          </div>

          <div style="padding-left: 12px">
            <!-- 基本信息 -->
            <div class="title mt16">
              {{ t('基本信息') }}
            </div>
            <div
              v-if="eventItem.event_id || eventItem.strategy_id"
              class="base-info">
              <render-info-block
                v-for="(basicArr, basicIndex) in basicInfo"
                :key="basicIndex"
                class="flex mt16"
                style="margin-bottom: 12px;">
                <render-info-item
                  v-for="(basicItem, itemIndex) in basicArr"
                  :key="itemIndex"
                  :label="basicItem.display_name"
                  :label-width="labelWidth">
                  <template v-if="basicItem.field_name === 'strategy_id'">
                    <bk-button
                      v-if="strategyList.find(item => item.value === eventItem.strategy_id)?.label"
                      text
                      theme="primary"
                      @click="handlerStrategy()">
                      {{ strategyList.find(item => item.value === eventItem.strategy_id)?.label }}
                    </bk-button>
                    <span v-else> -- </span>
                  </template>
                  <template v-else>
                    <span
                      v-bk-tooltips="{
                        content: t('映射对象', {
                          key: displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.dict?.key,
                          name: displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.dict?.name,
                        }),
                        // eslint-disable-next-line max-len
                        disabled: !displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.isMappings,
                      }"
                      :class="[
                        // eslint-disable-next-line max-len
                        displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.isMappings ? 'tips' : ''
                      ]">
                      {{ displayValueDict[basicItem.field_name as DisplayValueKeysWithoutEventData]?.value }}
                    </span>
                  </template>
                  <template v-if="drillMap.get(basicItem.field_name)">
                    <bk-button
                      class="ml8"
                      text
                      theme="primary"
                      @click="handleClick(
                        drillMap.get(basicItem.field_name),
                        drillMap.get(basicItem.field_name).drill_config.tool.uid,
                        basicItem.field_name
                      )">
                      {{ t('查看') }}
                    </bk-button>
                  </template>
                </render-info-item>
              </render-info-block>
            </div>
            <bk-exception
              v-else
              class="exception-part"
              scene="part"
              type="empty">
              {{ t('暂无数据') }}
            </bk-exception>

            <!-- 事件数据 -->
            <div class="title">
              {{ t('事件数据') }}
            </div>
            <div
              v-if="eventDataKeyArr.length"
              class="data-info">
              <div
                v-for="(keyArr, keyIndex) in eventDataKeyArr"
                :key="keyIndex"
                class="flex data-info-row">
                <div
                  v-for="(key, index) in keyArr"
                  :key="index"
                  class="flex data-info-item">
                  <div
                    class="data-info-item-key"
                    style="display: flex; flex-direction: column; justify-content: center;">
                    <tooltips
                      :data="strategyInfo.find(item => item.field_name === key)?.display_name || key"
                      style="width: 100%;" />
                  </div>
                  <div class="data-info-item-value">
                    <div
                      v-bk-tooltips="{
                        content: JSON.stringify(eventItem.event_data[key]),
                        disabled: !showTooltips,
                        extCls: 'evidence-info-value-tooltips',
                      }"
                      @mouseenter="handlerEnter($event)">
                      <span
                        v-bk-tooltips="{
                          content: t('映射对象', {
                            key: displayValueDict.eventData[key]?.dict?.key,
                            name: displayValueDict.eventData[key]?.dict?.name,
                          }),
                          disabled: !displayValueDict.eventData[key]?.isMappings,
                        }"
                        :class="[
                          displayValueDict.eventData[key]?.isMappings ? 'tips' : '',
                        ]">{{ displayValueDict.eventData[key]?.value }}</span>
                      <template v-if="drillMap.get(key)">
                        <bk-button
                          class="ml8"
                          text
                          theme="primary"
                          @click="handleClick(
                            drillMap.get(key),
                            drillMap.get(key).drill_config.tool.uid,
                            key
                          )">
                          {{ t('查看') }}
                        </bk-button>
                      </template>
                    </div>
                  </div>
                </div>
              </div>
            </div>
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
  </div>
  <!-- 循环所有工具 -->
  <div
    v-for="item in allToolsData"
    :key="item">
    <component
      :is="DialogVue"
      :ref="(el: any) => dialogRefs[item] = el"
      source="risk"
      :tags-enums="tagData"
      @close="handleClose"
      @open-field-down="openFieldDown" />
  </div>
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
  import ToolManageService from '@service/tool-manage';

  import EventModel from '@model/event/event';
  import type RiskManageModel from '@model/risk/risk';
  import type StrategyInfo from '@model/risk/strategy-info';

  import Tooltips from '@components/show-tooltips-text/index.vue';

  import RenderInfoBlock from '@views/strategy-manage/list/components/render-info-block.vue';
  import DialogVue from '@views/tools/tools-square/components/dialog.vue';

  import RenderInfoItem from './render-info-item.vue';

  import useRequest from '@/hooks/use-request';

  interface DrillItem {
    field_name: string;
    is_priority: boolean;
    description: string
    display_name: string;
    map_config?: {
      target_value: string | undefined,
      source_field: string | undefined,
    };
    drill_config: {
      tool: {
        uid: string;
        version: number;
      };
      config: Array<{
        source_field: string;
        target_value_type: string;
        target_value: string;
        target_field_type: string;
      }>
    };
  }

  interface DrillDownItem {
    raw_name: string;
    display_name: string;
    description: string;
    drill_config: {
      tool: {
        uid: string;
        version: number;
      };
      config: Array<{
        source_field: string;
        target_value_type: string;
        target_value: string;
      }>
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

  type DisplayValueDict = {
    [K in keyof Omit<typeof eventItem.value, 'event_data'>]: DisplayValue;
  } & {
    eventData: Record<string, DisplayValue>;
  };

  type DisplayValueKeys = keyof typeof displayValueDict.value;

  type DisplayValueKeysWithoutEventData = Exclude<DisplayValueKeys, 'eventData'>;
  const props = defineProps<Props>();

  const isShowMore = ref(false);

  const router = useRouter();
  const { t, locale } = useI18n();
  const linkEventList = ref<Array<EventModel>>([]); // 事件列表
  const currentPage = ref(1); // 当前页数
  const active = ref<number>(0);
  const eventItem = ref(new EventModel()); // 当前选中事件
  // const eventItemDataKeyArr = ref<Array<string[]>>([]); // 当前选中事件-事件数据
  const showTooltips = ref(false); // 是否显示tooltips
  const allToolsData = ref<string[]>([]);

  const dialogRefs = ref<Record<string, any>>({});

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
  const basicInfo = computed(() => group(props.data.event_basic_field_configs));

  // 不显示的字段
  // const notDisplay = computed(() => strategyInfo.value.filter(item => !item.is_show).map(item => item.field_name));

  // 重点信息（如果is_show为false, 则is_priority也一定为false）
  const importantInformation = computed(() => group(strategyInfo.value.filter(item => item.is_priority)));

  // 显示字段下钻的字段
  const drillMap = computed(() => {
    const map = new Map();
    strategyInfo.value.forEach((item) => {
      if (item.drill_config?.tool.uid) {
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
  });

  // 事件数据展示字段，从策略中获取
  const eventDataKeyArr = computed(() => {
    const eventInfo = [
      ...props.data.event_data_field_configs,
      ...props.data.event_evidence_field_configs,
    ];
    const eventInfoKeys = eventInfo.filter(item => item.is_show).map(item => item.field_name);
    return group(eventInfoKeys);
  });

  // 获取标签列表
  const {
    data: tagData,
  } = useRequest(ToolManageService.fetchToolTags, {
    defaultValue: [],
    manual: true,
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
      if (linkEventData.value.results.length) {
        // 触底加载，拼接
        linkEventList.value = [...linkEventList.value, ...linkEventData.value.results].
          filter((item, index, self) => index === self.findIndex(t => t.event_id === item.event_id));

        // 默认获取第一个
        [eventItem.value] = linkEventList.value;
        isShowMore.value = !(linkEventList.value.length > 1);
      // 事件event_data数据处理
      // const eventDataKey = getEventDataKey(eventItem.value.event_data);
      // eventItemDataKeyArr.value = group(eventDataKey);
      }
    },
  });

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

  // 是否显示tooltips
  const handlerEnter = (event: Event) => {
    // 获取div宽度
    const target = event?.target as HTMLDivElement;
    const parentWidth = target.offsetWidth;
    // 获取子元素宽度
    const span = target.firstElementChild as HTMLSpanElement;
    const spanWidth = span.offsetWidth;
    showTooltips.value = spanWidth > parentWidth;
  };

  // 过滤事件event_data数据，只保留有数据的key和策略配置is_show为true的数据
  // const getEventDataKey = (eventData: Record<string, any>) => {
  //   const eventDataKeys = Object.keys(eventData);
  //   return eventDataKeys.filter((key) => {
  //     // 排除 notDisplay 中的键
  //     if (notDisplay.value.includes(key)) {
  //       return false;
  //     }

  //     const value = eventItem.value.event_data[key];
  //     if (typeof value !== 'object' && value !== null && value !== '') {
  //       return true;
  //     }
  //     if ((_.isArray(value) || _.isObject(value)) && !_.isEmpty(value)) {
  //       return true;
  //     }
  //     return false;
  //   });
  // };

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

  // 事件event_data数据处理
  // const eventDataKey = getEventDataKey(eventItem.value.event_data);
  // eventItemDataKeyArr.value = group(eventDataKey);
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

  // 下转打开
  const openFieldDown = (drillDownItem: DrillDownItem, drillDownItemRowData: Record<any, string>) => {
    const { uid } = drillDownItem.drill_config.tool;
    if (!(allToolsData.value.find(item => item === uid))) {
      allToolsData.value.push(uid);
    }

    nextTick(() => {
      if (dialogRefs.value[uid]) {
        dialogRefs.value[uid].openDialog(uid, drillDownItem, drillDownItemRowData, riskToolParams.value);
      }
    });
  };

  // 打开工具
  const handleClick = (item: DrillItem, id: string, fieldName: string) => {
    riskToolParams.value.drill_field = fieldName;
    if (!(allToolsData.value.find(tool => tool === id))) {
      allToolsData.value.push(id);
    }
    nextTick(() => {
      if (dialogRefs.value[id]) {
        dialogRefs.value[id].openDialog(id, item, eventItem.value, riskToolParams.value);
      }
    });
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

  // 关闭弹窗
  const handleClose = (ToolInfo: string | undefined) => {
    if (ToolInfo) {
      allToolsData.value = allToolsData.value.filter(item => item !== ToolInfo);
    }
  };

  watch(() => props.data, (data) => {
    if (data.risk_id) {
      fetchLinkEvent({
        start_time: data.event_time,
        end_time: data.event_end_time,
        risk_id: data.risk_id,
        page: currentPage.value,
        page_size: 50,
      });
    }
  }, {
    immediate: true,
  });

  onMounted(() => {
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
    });
  });
</script>
<style lang="postcss">
.risk-manage-detail-linkevent-part {
  .title {
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
  }

  .body {
    display: flex;
    margin-top: 14px;

    .list {
      display: inline-block;
      height: 500px;
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

    .show-more-condition-btn {
      position: absolute;
      top: 50%;
      right: -60px;
      transform: rotate(-90deg);
      box-shadow: 0 2px 4px 0 #1919290d;

      .show-more-btn {
        width: 120px;
        height: 30px;
        line-height: 5px;
        color: #fff;
        background: #c4c6cc;
        border-radius: 10px;

        &:hover {
          background-color: #3a84ff;
        }
      }

      .audit {
        transform: rotateZ(-180deg);
        transition: all .15s;
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
          }
        }
      }

      .data-info {
        margin: 16px 0 24px;
        border: 1px solid #ecedf1;

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
    }
  }
}

.evidence-info-value-tooltips {
  max-width: 80%
}
</style>
