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
  <div
    class="detail-base-info"
    :style="borderStyle">
    <div class="title">
      {{ data.risk_title }}
    </div>
    <template v-if="isShowMore">
      <render-info-block
        class="flex mt16"
        style="margin-bottom: 12px;">
        <render-info-item
          :label="t('风险ID')"
          :label-width="labelWidth">
          {{ t('以实际内容为准') }}
        </render-info-item>
        <render-info-item
          :label="t('风险描述')"
          :label-width="labelWidth">
          {{ t('以实际内容为准') }}
        </render-info-item>
      </render-info-block>
      <render-info-block
        class="flex mt16"
        style="margin-bottom: 12px;">
        <render-info-item
          :label="t('风险标签')"
          :label-width="labelWidth">
          <edit-tag :data="data.tags?.map(item=>strategyTagMap[item] || item) || ''" />
        </render-info-item>
        <render-info-item
          :label="t('风险类型')"
          :label-width="labelWidth">
          {{ t('以实际内容为准') }}
        </render-info-item>
      </render-info-block>
      <render-info-block
        class="flex mt16"
        style="margin-bottom: 12px;">
        <render-info-item
          :label="t('风险等级')"
          :label-width="labelWidth">
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
          <span v-else>{{ t('以实际内容为准') }}</span>
        </render-info-item>
        <render-info-item
          :label="t('风险命中策略')"
          :label-width="labelWidth">
          {{ data.strategy_name }}
        </render-info-item>
      </render-info-block>
      <render-info-block
        class="flex "
        style="margin-bottom: 12px;">
        <render-info-item
          :label="t('最后发现时间')"
          :label-width="labelWidth">
          {{ t('以实际内容为准') }}
        </render-info-item>
        <render-info-item
          :label="t('首次发现时间')"
          :label-width="labelWidth">
          {{ t('以实际内容为准') }}
        </render-info-item>
      </render-info-block>
      <render-info-block
        class="flex "
        style="margin-bottom: 12px;">
        <render-info-item
          :label="t('风险危害')"
          :label-width="labelWidth">
          {{ data.risk_hazard || '--' }}
        </render-info-item>
      </render-info-block>
      <render-info-block
        class="flex "
        style="margin-bottom: 12px;">
        <render-info-item
          :label="t('处理指引')"
          :label-width="labelWidth">
          {{ data.risk_guidance || '--' }}
        </render-info-item>
      </render-info-block>
      <render-info-block
        class="flex "
        style=" margin-top: 30px;margin-bottom: 12px">
        <render-info-item
          :label="t('处理状态')"
          :label-width="labelWidth">
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
          <div v-else>
            {{ t('以实际内容为准') }}
          </div>
        </render-info-item>
        <render-info-item
          :label="t('处理规则')"
          :label-width="labelWidth">
          {{ t('以实际内容为准') }}
        </render-info-item>
      </render-info-block>
      <render-info-block style="display: flex;">
        <render-info-item
          :label="t('责任人')"
          :label-width="labelWidth">
          {{ t('以实际内容为准') }}
        </render-info-item>
        <render-info-item
          :label="t('当前处理人')"
          :label-width="labelWidth">
          {{ t('以实际内容为准') }}
        </render-info-item>
      </render-info-block>
      <render-info-block>
        <render-info-item
          :label="t('关注人')"
          :label-width="labelWidth"
          style="width: 100%;">
          {{ t('以实际内容为准') }}
        </render-info-item>
      </render-info-block>
    </template>
    <!-- 折叠 -->
    <template v-else>
      <render-info-block
        class="flex mt16"
        style="margin-bottom: 12px;">
        <render-info-item
          :label="t('风险ID')"
          :label-width="labelWidth">
          {{ t('以实际内容为准') }}
        </render-info-item>
        <render-info-item
          :label="t('风险标签')"
          :label-width="labelWidth">
          <edit-tag :data="data.tags?.map(item=>strategyTagMap[item] || item) || ''" />
        </render-info-item>
      </render-info-block>
      <render-info-block
        class="flex "
        style="margin-bottom: 12px;">
        <render-info-item
          :label="t('风险等级')"
          :label-width="labelWidth">
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
          <span v-else>{{ t('以实际内容为准') }}</span>
        </render-info-item>
        <render-info-item
          :label="t('处理状态')"
          :label-width="labelWidth">
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
          <div v-else>
            {{ t('以实际内容为准') }}
          </div>
        </render-info-item>
      </render-info-block>
      <render-info-block
        class="flex "
        style="margin-bottom: 12px;">
        <render-info-item
          :label="t('当前处理人')"
          :label-width="labelWidth">
          {{ t('以实际内容为准') }}
        </render-info-item>
      </render-info-block>
      <render-info-block
        class="flex "
        style="margin-bottom: 12px;">
        <render-info-item
          :label="t('风险危害')"
          :label-width="labelWidth">
          {{ data.risk_hazard || '--' }}
        </render-info-item>
      </render-info-block>
      <render-info-block
        class="flex "
        style="margin-bottom: 12px;">
        <render-info-item
          :label="t('处理指引')"
          :label-width="labelWidth">
          {{ data.risk_guidance || '--' }}
        </render-info-item>
      </render-info-block>
    </template>
    <div class="show-more-condition-btn">
      <bk-button
        class="show-more-btn"
        text
        @click="() => isShowMore = !isShowMore">
        <audit-icon
          :class="{ active: isShowMore }"
          style=" margin-right: 5px;"
          type="angle-double-down" />
        {{ t('展开全部字段') }}
      </bk-button>
    </div>
  </div>
</template>

<script setup lang='ts'>
  import {
    computed,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';

  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  import useRequest from '@hooks/use-request';

  import EditTag from '@components/edit-box/tag.vue';

  import RenderInfoBlock from '@views/strategy-manage/list/components/render-info-block.vue';

  import RenderInfoItem from './render-info-item.vue';

  interface IFormData {
    strategy_id?: number,
    strategy_name: string,
    tags: Array<string>,
    description: string,
    control_id: string,
    control_version?: number,
    configs: Record<string, any>,
    status: string,
    risk_level: string,
    risk_hazard: string,
    risk_guidance: string,
    risk_title: string,
    event_data_field_configs: StrategyFieldEvent['event_data_field_configs'],
    event_basic_field_configs: StrategyFieldEvent['event_basic_field_configs'],
    processor_groups: [],
    notice_groups: []
  }

  interface Props{
    data: IFormData,
    riskStatusCommon: Array<{
      id: string,
      name: string,
    }>,
  }
  const props = defineProps<Props>();
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
  const riskLevelMap: Record<string, {
    label: string,
    color: string,
  }> =  {
    HIGH: {
      label: '高',
      color: '#ea3636',
    },
    MIDDLE: {
      label: '中',
      color: '#ff9c01',
    },
    LOW: {
      label: '低',
      color: '#979ba5',
    },
  };
  const { t, locale } = useI18n();

  const isShowMore = ref(false);
  const strategyTagMap = ref<Record<string, string>>({});

  const labelWidth = computed(() => (locale.value === 'en-US' ? 120 : 80));
  const borderStyle = computed(() => ({
    'border-top': `6px solid ${riskLevelMap[props.data.risk_level].color}`,
  }));

  // 获取标签列表
  useRequest(MetaManageService.fetchTags, {
    defaultParams: {
      page: 1,
      page_size: 1,
    },
    defaultValue: [],
    manual: true,
    onSuccess: (data) => {
      data.forEach((item) => {
        strategyTagMap.value[item.tag_id] = item.tag_name;
      });
    },
  });
</script>
<style lang="postcss" scoped>
.detail-base-info {
  position: relative;
  padding: 10px 16px;
  background: #fff;
  border-radius: 2px;
  box-shadow: 0 2px 4px 0 #1919290d;

  .title {
    margin-bottom: 10px;
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
  }

  .render-info-item {
    min-width: 50%;
    align-items: flex-start;
  }

  .show-more-condition-btn {
    position: absolute;
    right: calc(50% - 52px);
    bottom: -11px;
    box-shadow: 0 2px 4px 0 #1919290d;

    .show-more-btn {
      width: 120px;
      height: 22px;
      color: #fff;
      background: #c4c6cc;;
      border-radius: 12px;

      &:hover {
        background-color: #3a84ff;
      }
    }

    .active {
      transform: rotateZ(-180deg);
      transition: all .15s;
    }
  }
}
</style>
