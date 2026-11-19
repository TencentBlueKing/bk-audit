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
  <card-part-vue :title="t('基础信息')">
    <template #content>
      <div class="flex-center">
        <bk-form-item
          class="is-required"
          :label="t('工具名称')"
          label-width="160"
          property="name"
          required
          style="flex: 1; margin-right: var(--bk-theme-space-16)">
          <audit-skeleton
            v-if="detailLoading"
            custom-class="tool-field-skeleton"
            height="32"
            width="100%" />
          <bk-input
            v-else
            v-model.trim="formData.name"
            :maxlength="32"
            :placeholder="namePlaceholder"
            show-word-limit
            style="width: 100%;" />
        </bk-form-item>
        <bk-form-item
          :label="t('工具标签')"
          label-width="160"
          property="tags"
          style="flex: 1;">
          <audit-skeleton
            v-if="detailLoading || tagLoading"
            custom-class="tool-field-skeleton"
            height="32"
            width="100%" />
          <bk-select
            v-else
            v-model="formData.tags"
            allow-create
            class="bk-select"
            filterable
            :input-search="false"
            multiple
            multiple-mode="tag"
            :placeholder="t('请选择')"
            :search-placeholder="t('请输入关键字')">
            <bk-option
              v-for="(item, index) in allTagData"
              :key="index"
              :label="item.tag_name"
              :value="item.tag_id" />
          </bk-select>
        </bk-form-item>
      </div>
      <div class="base-info-row">
        <bk-form-item
          class="mr16"
          :label="t('工具说明')"
          label-width="160"
          property="description"
          required
          style="flex: 1;">
          <audit-skeleton
            v-if="detailLoading"
            custom-class="tool-field-skeleton"
            height="76"
            width="100%" />
          <bk-input
            v-else
            v-model.trim="formData.description"
            :maxlength="2000"
            :placeholder="t('请输入说明')"
            :resize="false"
            show-word-limit
            style="width: 100%;"
            type="textarea" />
        </bk-form-item>
        <bk-form-item
          class="square-display-item"
          :label="t('是否展示')"
          style="flex: 1;">
          <template #label>
            <span class="square-display-label">
              {{ t('是否展示') }}
              <audit-icon
                v-bk-tooltips="{
                  content: squareDisplayTip,
                }"
                class="square-display-tip"
                type="info-fill" />
            </span>
          </template>
          <audit-skeleton
            v-if="detailLoading"
            custom-class="tool-field-skeleton"
            height="32"
            width="44" />
          <bk-switcher
            v-else
            v-model="showInSquare"
            theme="primary" />
        </bk-form-item>
      </div>
    </template>
  </card-part-vue>
</template>

<script setup lang="ts">
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { FormData } from '../types';

  import CardPartVue from './card-part.vue';

  defineProps<{
    tagLoading: boolean;
    detailLoading?: boolean;
    allTagData: Array<{
      tag_id: string;
      tag_name: string;
    }>;
  }>();

  const formData = defineModel<FormData>('formData', { required: true });

  const { t } = useI18n();
  const namePlaceholder = t('请输入，32字符内');
  const squareDisplayTip = t('仅控制工具是否在工具广场展示。关闭后，审计策略中配置的下钻仍可正常使用。');
  const showInSquare = computed({
    get: () => formData.value.status !== 'unpublished',
    set: (value: boolean) => {
      formData.value.status = value ? 'published' : 'unpublished';
    },
  });
</script>

<style lang="postcss" scoped>
  .flex-center {
    display: flex;
    align-items: center;
  }

  .base-info-row {
    display: flex;
    align-items: flex-start;
  }

  .square-display-item {
    flex: 1;
  }

  .square-display-item :deep(.bk-form-content) {
    display: flex;
    align-items: center;
    height: var(--bk-theme-space-32);
  }

  .square-display-label {
    display: inline-flex;
    align-items: center;
  }

  .square-display-tip {
    margin-left: var(--bk-theme-space-4);
    font-size: var(--bk-theme-font-size-base);
    color: var(--bk-theme-text-weak);
    cursor: default;
  }

  :deep(.tool-field-skeleton) {
    border-radius: var(--bk-theme-control-radius);
  }
</style>
