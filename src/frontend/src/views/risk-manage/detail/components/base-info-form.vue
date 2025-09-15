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
  <div class="base-info-form">
    <template
      v-for="(fieldGroup, groupIndex) in renderShowFieldNames"
      :key="groupIndex">
      <render-info-block
        class="flex mt16"
        :style="{ marginBottom: groupIndex === renderShowFieldNames.length - 1 ? '0px' : '12px' }">
        <render-info-item
          v-for="(fieldItem, itemIndex) in fieldGroup.filter(item => item)"
          :key="itemIndex"
          :label="fieldItem.display_name"
          :label-width="labelWidth"
          :style="getFieldStyle(fieldItem.field_name)">
          <template v-if="fieldItem.field_name === 'risk_id'">
            {{ data.risk_id }}
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
              {{ riskLevelMap[data.risk_level].label }}
            </span>
            <span v-else>--</span>
          </template>
          <template v-else-if="fieldItem.field_name === 'event_type'">
            {{ data.event_type?.join('、') || '--' }}
          </template>
          <template v-else-if="fieldItem.field_name === 'risk_tags'">
            <edit-tag :data="data.tags?.map(item=>strategyTagMap[item] || item) || ''" />
          </template>
          <template v-else-if="fieldItem.field_name === 'strategy_name'">
            <router-link
              v-if="strategyName"
              target="_blank"
              :to="{
                name: 'strategyList',
                query: {
                  strategy_id: data.strategy_id,
                },
              }">
              {{ strategyName }}
            </router-link>
            <span v-else>--</span>
          </template>
          <template v-else-if="fieldItem.field_name === 'event_content'">
            {{ data.event_content }}
          </template>
          <template v-else-if="fieldItem.field_name === 'risk_hazard'">
            {{ data.risk_hazard || '--' }}
          </template>
          <template v-else-if="fieldItem.field_name === 'risk_guidance'">
            {{ data.risk_guidance || '--' }}
          </template>
          <template v-else-if="fieldItem.field_name === 'status'">
            <template v-if="statusToMap[data.status]">
              <bk-tag :theme="statusToMap[data.status].theme">
                <p style="display: flex;align-items: center;">
                  <audit-icon
                    :style="`margin-right: 6px;color: ${statusToMap[data.status].color || ''}`"
                    :type="statusToMap[data.status].icon" />
                  {{ riskStatusCommon.find(item=>item.id===data.status)?.name || '--' }}
                </p>
              </bk-tag>
            </template>
          </template>
          <template v-else-if="fieldItem.field_name === 'operator'">
            <edit-tag :data="data.operator || ''" />
          </template>
          <template v-else-if="fieldItem.field_name === 'current_operator'">
            <edit-tag :data="data.current_operator || ''" />
          </template>
          <template v-else-if="fieldItem.field_name === 'notice_users'">
            <edit-tag :data="data.notice_users || ''" />
          </template>
          <template v-else-if="fieldItem.field_name === 'event_time'">
            {{ data.event_time || '--' }}
          </template>
          <template v-else-if="fieldItem.field_name === 'event_end_time'">
            {{ data.event_end_time || '--' }}
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
              {{ data.risk_label === 'normal' ? t('正常') : t('误报') }}
            </span>
          </template>
          <template v-else>
            {{ data[fieldItem.field_name as keyof RiskManageModel] || '--' }}
          </template>
        </render-info-item>
      </render-info-block>
    </template>
  </div>
</template>
<script setup lang='ts'>
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';
  import RiskRuleManageService from '@service/rule-manage';

  import type RiskManageModel from '@model/risk/risk';
  import type StrategyInfo from '@model/risk/strategy-info';

  import EditTag from '@components/edit-box/tag.vue';

  import RenderInfoBlock from '@views/strategy-manage/list/components/render-info-block.vue';

  import RenderInfoItem from './render-info-item.vue';

  import useRequest from '@/hooks/use-request';

  interface Props{
    data: RiskManageModel & StrategyInfo
    strategyList: Array<{
      label: string,
      value: number
    }>,
    riskStatusCommon: Array<{
      id: string,
      name: string,
    }>,
    showFieldNames: Array<StrategyInfo['risk_meta_field_config'][0]>,
  }

  const props = defineProps<Props>();

  const { t, locale } = useI18n();

  const labelWidth = computed(() => (locale.value === 'en-US' ? 120 : 100));

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

  const statusToMap: Record<string, {
    theme: 'info' | 'warning' | 'success' | 'danger' | undefined,
    icon: string,
    color: string,
  }> = {
    new: {
      theme: 'info',
      icon: 'auto',
      color: '#3A84FF',
    },
    closed: {
      theme: undefined,
      icon: 'corret-fill',
      color: '#979BA5',
    },
    await_deal: {
      theme: 'warning',
      icon: 'daichuli',
      color: '#FF9E00',
    },
    for_approve: {
      theme: 'info',
      icon: 'auto',
      color: '#3A84FF',
    },
    auto_process: {
      theme: 'success',
      icon: 'taocanchulizhong',
      color: '#0CA668',
    },
  };

  const strategyName = computed(() => {
    const { data } = props;
    const item = props.strategyList.find(item => item.value === data.strategy_id);
    return item && item.label ? item.label : '';
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

  const renderShowFieldNames = computed(() => group(props.showFieldNames));

  // 获取字段样式
  const getFieldStyle = (fieldName: string) => {
    if (fieldName === 'notice_users') {
      return 'width: 100%;';
    }
    // risk_guidance 和 risk_hazard 单独占一行，宽度为100%
    if (fieldName === 'risk_guidance' || fieldName === 'risk_hazard') {
      return 'width: 100%;';
    }
    return '';
  };

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

  // 获取所有处理规则
  const {
    data: riskRuleList,
  } = useRequest(RiskRuleManageService.fetchRuleAll, {
    defaultValue: [],
    manual: true,
  });
</script>
<style lang="postcss" scoped>
.base-info-form {
  /* background-color: #f5f7fa; */
  padding: 10px;
  margin-bottom: 10px;

  .render-info-item {
    min-width: 50%;
    align-items: flex-start;
  }
}
</style>
