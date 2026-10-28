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
  <div class="step-basic-info-loading">
    <card-part :title="t('基础信息')">
      <template #content>
        <div
          v-if="status === 'failed'"
          class="load-error"
          data-testid="strategy-detail-load-error">
          <span>{{ t('数据加载失败') }}</span>
          <bk-button
            text
            theme="primary"
            @click="emits('retry')">
            {{ t('重试') }}
          </bk-button>
        </div>
        <template v-else>
          <div class="basic-row">
            <div class="form-item">
              <div class="skeleton label name-label" />
              <div class="skeleton control" />
            </div>
            <div class="form-item">
              <div class="skeleton label tag-label" />
              <div class="skeleton control" />
            </div>
          </div>
          <div class="form-item is-last">
            <div class="skeleton label tag-label" />
            <div class="skeleton textarea" />
          </div>
        </template>
      </template>
    </card-part>

    <card-part :title="t('方案')">
      <template #content>
        <div
          v-if="status === 'failed'"
          class="load-error-placeholder">
          {{ t('数据加载失败') }}
        </div>
        <template v-else>
          <div class="form-item">
            <div class="skeleton label name-label" />
            <div class="way-row">
              <div class="skeleton way" />
              <div class="skeleton way" />
            </div>
          </div>
          <div class="form-item field-item">
            <div class="skeleton label source-label" />
            <div class="skeleton control" />
          </div>
          <div class="form-item field-item">
            <div class="skeleton label result-label" />
            <div class="skeleton control" />
          </div>
          <div class="form-item field-item is-last">
            <div class="skeleton label name-label" />
            <div class="skeleton schedule" />
          </div>
        </template>
      </template>
    </card-part>
  </div>
</template>

<script setup lang="ts">
  import { useI18n } from 'vue-i18n';

  import CardPart from '../step1/components/card-part.vue';

  interface Props {
    status?: 'loading' | 'failed'
  }

  withDefaults(defineProps<Props>(), {
    status: 'loading',
  });

  const emits = defineEmits<{
    retry: []
  }>();

  const { t } = useI18n();
</script>

<style scoped lang="postcss">
.step-basic-info-loading {
  padding-top: 4px;
  margin-bottom: 74px;

  .basic-row {
    display: flex;
    gap: var(--audit-space-16);
  }

  .form-item {
    margin-bottom: var(--audit-space-24);
  }

  .basic-row .form-item {
    flex: 1;
    min-width: 0;
  }

  .form-item.is-last {
    margin-bottom: 0;
  }

  .load-error,
  .load-error-placeholder {
    display: flex;
    min-height: 64px;
    color: var(--audit-neutral-text-03);
    align-items: center;
    justify-content: center;
  }

  .load-error {
    gap: var(--audit-space-8);
  }

  .skeleton {
    background: #e4e7ee;
    border-radius: var(--audit-radius-control);
    animation: step-basic-info-shimmer 1.6s ease-in-out infinite;
  }

  .label {
    height: 20px;
    margin-bottom: 6px;
  }

  .name-label {
    width: 56px;
  }

  .tag-label {
    width: 24px;
  }

  .source-label {
    width: 36px;
  }

  .result-label {
    width: 48px;
  }

  .control {
    height: 32px;
  }

  .textarea,
  .field-item .control {
    width: 624px;
    max-width: 100%;
  }

  .textarea {
    height: 64px;
  }

  .way-row {
    display: flex;
    gap: var(--audit-space-16);
  }

  .way {
    width: 200px;
    height: 48px;
    border-radius: var(--audit-radius-container);
  }

  .schedule {
    width: 280px;
    height: 32px;
  }
}

@keyframes step-basic-info-shimmer {
  0%,
  100% {
    background: #e4e7ee;
  }

  50% {
    background: #f2f3f7;
  }
}
</style>
