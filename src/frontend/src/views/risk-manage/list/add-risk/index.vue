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
  <bk-sideslider
    v-model:isShow="isShow"
    background-color="#f5f7fa"
    :esc-close="false"
    :quick-close="false"
    render-directive="if"
    :title="t( isEdit ? '新建风险' : '风险单预览')"
    :width="800">
    <edit
      v-if="isEdit"
      ref="editRef" />
    <preview
      v-else
      ref="previewRef" />
    <template #footer>
      <div class="foot-button">
        <bk-button
          v-if="isEdit"
          theme="primary"
          @click="handlePreview">
          {{ t('预览') }}
        </bk-button>
        <bk-button
          v-if="!isEdit"
          theme="primary">
          {{ t('提交') }}
        </bk-button>
        <bk-button
          v-if="!isEdit"
          @click="handleReturn">
          {{ t('返回修改') }}
        </bk-button>
        <bk-button>
          {{ t('取消') }}
        </bk-button>
      </div>
    </template>
  </bk-sideslider>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import edit from './edit.vue';
  import preview from './preview.vue';

  const isShow = ref(true);
  const { t } = useI18n();
  const editRef = ref();
  const previewRef = ref();
  const isEdit = ref(true);

  const handlePreview = () => {
    isEdit.value = false;
  };

  const handleReturn = () => {
    isEdit.value = true;
  };
</script>

<style lang="postcss" scoped>
.foot-button {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
}
</style>


