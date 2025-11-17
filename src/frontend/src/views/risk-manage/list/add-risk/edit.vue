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
  <div class="config">
    <card-part-vue :title="t('基础配置')">
      <template #content>
        <div class="flex-center">
          <audit-form
            class="example"
            form-type="vertical"
            :model="formData"
            :rules="rules">
            <div class="base-form-item">
              <bk-form-item
                class="base-item"
                required>
                <template #label>
                  <span
                    v-bk-tooltips="t('手动创建风险单，事件字段来源于审计策略配置')"
                    class="dashed-underline">{{ t("审计策略") }}</span>
                </template>
                <bk-select
                  v-model="formData.strategy_id"
                  auto-focus
                  class="bk-select"
                  filterable
                  @select="handleSelect">
                  <bk-option
                    v-for="item in strategyList.results"
                    :id="item.strategy_id"
                    :key="item.strategy_id"
                    :name="item.strategy_name" />
                </bk-select>
              </bk-form-item>
              <bk-form-item
                class="base-item"
                :label="t('责任人')"
                required>
                <audit-user-selector
                  v-model="formData.owner"
                  allow-create
                  :auto-focus="false"
                  class="consition-value" />
              </bk-form-item>
            </div>
            <div class="base-form-item">
              <bk-form-item
                class="base-item"
                :label="t('事件发生时间')"
                required>
                <bk-date-picker
                  v-model="formData.time"
                  append-to-body
                  clearable
                  type="datetime" />
              </bk-form-item>
            </div>
            <div class="base-form-item">
              <bk-form-item
                class="base-item"
                :label="t('事件来源')"
                required>
                <bk-input
                  v-model="formData.source"
                  clearable
                  placeholder="请输入" />
              </bk-form-item>
              <bk-form-item
                class="base-item"
                :label="t('事件类型')"
                required>
                <bk-input
                  v-model="formData.event_type"
                  clearable />
              </bk-form-item>
            </div>

            <div>
              <bk-form-item
                class="base-item"
                :label="t('事件描述')"
                required>
                <bk-input
                  v-model="formData.description"
                  :maxlength="100"
                  :rows="4"
                  type="textarea" />
              </bk-form-item>
            </div>
          </audit-form>
        </div>
      </template>
    </card-part-vue>
    <card-part-vue :title="t('事件数据')">
      <template #content>
        事件数据
      </template>
    </card-part-vue>
  </div>
</template>

<script setup lang="ts">
  import { onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import AccountManageService from '@service/account-manage';
  import StrategyManageService from '@service/strategy-manage';

  import AccountModel from '@model/account/account';

  import useRequest from '@hooks/use-request';

  import CardPartVue from '../../../tools/tools-square/add/components/card-part.vue';

  const { t } = useI18n();
  const formData = ref({
    strategy_id: '',
    owner: '',
    time: '',
    source: '',
    event_type: '',
    description: '',
  });
  const rules = ref();

  const selectedValue = ref('');
  const handleSelect = (value: string) => {
    selectedValue.value = value;
  };
  // const strategyList = ref();

  // 策略列表
  const {
    data: strategyList,
  } = useRequest(StrategyManageService.fetchStrategyList, {
    defaultValue: {
      results: [],
      page: 1,
      num_pages: 1,
      total: 1,
    },
    manual: true,
    onSuccess: (data) => {
      console.log('data', data);
    },
  });
  // 用户信息
  const {
    run: fetchUserInfo,
  } = useRequest(AccountManageService.fetchUserInfo, {
    defaultValue: new AccountModel(),
    onSuccess: (data) => {
      console.log('用户信息', data);
      formData.value.owner = data.username;
    },
  });

  onMounted(() => {
    fetchUserInfo();
  });
</script>

<style lang="postcss" scoped>
.config {
  width: 96%;
  margin-top: 20px;
  margin-left: 2%;

  /* background-color: #f5f7fa; */
  overflow: hidden;

  .base-form-item {
    display: flex;
    justify-content: space-between;

    .base-item {
      width: 48%;
    }
  }

  .dashed-underline {
    padding-bottom: 2px; /* 可选，增加文字和虚线间距 */
    border-bottom: 1px dashed #c4c6cc;
  }
}
</style>
