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
  <div class="strategy-detail">
    <render-info-block>
      <render-info-item :label="t('策略名称')">
        {{ data.strategy_name }}
      </render-info-item>
    </render-info-block>
    <render-info-block>
      <render-info-item :label="t('标签')">
        <span v-if="data.tags.length">
          <span
            v-for="item in data.tags"
            :key="item"
            class="label-item"> {{ strategyMap[item] }}</span>
        </span>
        <span v-else>
          --
        </span>
      </render-info-item>
    </render-info-block>
    <render-info-block>
      <render-info-item :label="t('描述')">
        <span v-if="data.description">
          {{ data.description }}
        </span>
        <span v-else>
          --
        </span>
      </render-info-item>
    </render-info-block>
    <render-info-block>
      <render-info-item :label="t('方案')">
        {{ controlName }} - V{{ data.control_version }}
      </render-info-item>
    </render-info-block>

    <bk-loading :loading="controlLoading">
      <component
        :is="comMap[controlTypeId]"
        ref="comRef"
        :data="data" />
    </bk-loading>

    <render-info-block>
      <render-info-item
        class="group-render-item"
        :label="t('通知组',2)">
        <span v-if="data.notice_groups.length">
          <router-link
            v-for="item in data.notice_groups"
            :key="item"
            class="notice-box"
            :to="{
              name:'noticeGroupList',
              query:{
                keyword:userGroupList.find((list: DictObject) => list.id === item)?.name
              }
            }">
            {{ userGroupList.find((list: DictObject) => list.id === item)?.name }}
          </router-link>
        </span>
        <span v-else>
          --
        </span>
      </render-info-item>
    </render-info-block>
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import type StrategyModel from '@model/strategy/strategy';

  import useRequest from '@hooks/use-request';

  import RenderAiops from './aiops/index.vue';
  import FilterCondition from './normal/filter-condition.vue';
  import RenderInfoBlock from './render-info-block.vue';
  import RenderInfoItem from './render-info-item.vue';

  interface Props {
    data: StrategyModel,
    strategyMap: Record<string, string>
    userGroupList: Array<{id: number, name: string}>
  }
  interface DictObject {
    id: number | string,
    name: string
  }

  const props = defineProps<Props>();
  const { t } = useI18n();
  // let isRequest = false;
  const controlTypeId = computed(() => controlList.value
    .find(item => item.control_id === props.data.control_id)?.control_type_id || '');// 方案类型id
  const controlName = computed(() => controlList.value
    .find(item => item.control_id === props.data.control_id)?.control_name || '--');// 方案名称
  const comMap: Record<string, any> = {
    BKM: FilterCondition,
    AIOps: RenderAiops,
  };

  // 获取方案列表
  const {
    data: controlList,
    loading: controlLoading,
  } = useRequest(StrategyManageService.fetchControlList, {
    defaultValue: [],
    manual: true,
  });

</script>
<style lang="postcss">
.strategy-detail {
  padding: 24px 32px;

  .label-item {
    padding: 3px 8px;
    margin-right: 4px;
    background: #f0f1f5;
    border-radius: 2px;
  }

  .group-render-item {
    .info-value {
      margin-top: -3px;
    }
  }

  .notice-box {
    display: inline-block;
    height: 22px;
    padding: 2px 8px;
    margin-right: 4px;
    margin-bottom: 8px;
    text-align: center;
    background: #fafbfd;
    border: 1px solid rgb(151 155 165 / 30%);
    border-radius: 2px;
  }
}
</style>
