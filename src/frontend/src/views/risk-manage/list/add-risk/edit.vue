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
          <bk-form
            class="example"
            form-type="vertical"
            :model="formData"
            :rules="rules">
            <div class="base-form-item">
              <bk-form-item
                class="base-item"
                :label="t('审计策略')"
                required>
                <bk-select
                  v-model="selectedValue"
                  auto-focus
                  class="bk-select"
                  filterable
                  @select="handleSelect">
                  <bk-option
                    v-for="(item, index) in datasource"
                    :id="item.value"
                    :key="index"
                    :disabled="item.disabled"
                    :name="item.label" />
                </bk-select>
              </bk-form-item>
              <bk-form-item
                class="base-item"
                :label="t('责任人')"
                required>
                <bk-input
                  clearable
                  placeholder="请输入" />
              </bk-form-item>
            </div>
            <div class="base-form-item">
              <bk-form-item
                class="base-item"
                :label="t('事件发生时间')"
                required>
                <bk-input
                  clearable
                  placeholder="请输入" />
              </bk-form-item>
            </div>
            <div class="base-form-item">
              <bk-form-item
                class="base-item"
                :label="t('事件来源')"
                required>
                <bk-input
                  clearable
                  placeholder="请输入" />
              </bk-form-item>
              <bk-form-item
                class="base-item"
                :label="t('事件类型')"
                required>
                <bk-input
                  clearable
                  placeholder="请输入" />
              </bk-form-item>
            </div>

            <div>
              <bk-form-item
                class="base-item"
                :label="t('事件描述')"
                required>
                <bk-input
                  clearable
                  placeholder="请输入" />
              </bk-form-item>
            </div>
          </bk-form>
        </div>
      </template>
    </card-part-vue>
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import CardPartVue from '../../../tools/tools-square/add/components/card-part.vue';

  const { t } = useI18n();
  const formData = ref({
    name: '',
    description: '',
    type: '',
    status: '',
    owner: '',
    created_at: '',
    updated_at: '',
  });
  const rules = ref();

  const selectedValue = ref('');
  const handleSelect = (value: string) => {
    selectedValue.value = value;
  };
  const datasource = ref();
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
}
</style>
