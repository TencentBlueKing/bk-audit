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
  <div class="risk-other">
    <render-info-block>
      <render-info-item
        class="group-render-item"
        :label="t('风险单处理人')">
        <span v-if="data.processor_groups.length">
          <router-link
            v-for="item in data.processor_groups"
            :key="item"
            class="notice-box"
            :to="{
              name:'noticeGroupList',
              query:{
                keyword: userGroupList.find((list: DictObject) => list.id === item)?.name
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
    <render-info-block>
      <render-info-item
        class="group-render-item"
        :label="t('关注人')">
        <span v-if="data.notice_groups.length">
          <router-link
            v-for="item in data.notice_groups"
            :key="item"
            class="notice-box"
            :to="{
              name:'noticeGroupList',
              query:{
                keyword: userGroupList.find((list: DictObject) => list.id === item)?.name
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
  import { useI18n } from 'vue-i18n';

  import type StrategyModel from '@model/strategy/strategy';

  import RenderInfoBlock from './render-info-block.vue';
  import RenderInfoItem from './render-info-item.vue';

  interface Props {
    data: StrategyModel,
    userGroupList: Array<{id: number, name: string}>
  }
  interface DictObject {
    id: number | string,
    name: string
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const props = defineProps<Props>();
  const { t } = useI18n();
</script>
<style lang="postcss">
.risk-other {
  margin-top: 8px;
  margin-left: 24px;

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
