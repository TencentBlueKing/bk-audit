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
          class="is-required mr16"
          :label="t('工具名称')"
          label-width="160"
          property="name"
          required
          style="flex: 1;">
          <bk-input
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
          <bk-loading
            :loading="tagLoading"
            style="width: 100%;">
            <bk-select
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
          </bk-loading>
        </bk-form-item>
      </div>
      <bk-form-item
        :label="t('工具说明')"
        label-width="160"
        property="description"
        required>
        <bk-input
          v-model.trim="formData.description"
          :maxlength="100"
          :placeholder="t('请输入说明')"
          :resize="false"
          show-word-limit
          style="width: 50%;"
          type="textarea" />
      </bk-form-item>
    </template>
  </card-part-vue>
</template>

<script setup lang="ts">
  import { useI18n } from 'vue-i18n';

  import type { FormData } from '../types';

  import CardPartVue from './card-part.vue';

  defineProps<{
    tagLoading: boolean;
    allTagData: Array<{
      tag_id: string;
      tag_name: string;
    }>;
  }>();

  const formData = defineModel<FormData>('formData', { required: true });

  const { t } = useI18n();
  // eslint-disable-next-line no-useless-concat
  const namePlaceholder = t('请输入，32字符内，可由汉字、小写字母、数字、' + '"_"' + '组成');
</script>

<style lang="postcss" scoped>
  .flex-center {
    display: flex;
    align-items: center;
  }
</style>
