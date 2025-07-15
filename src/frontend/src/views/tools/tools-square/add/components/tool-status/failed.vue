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
  <div class="tool-status-failed">
    <div class="tool-status-failed-icon">
      <audit-icon
        type="delete-fill" />
    </div>
    <div class="tool-status-failed-text">
      <h1 style="margin-bottom: 16px;">
        <span>{{ name }}</span>
        {{ isEditMode ? t('工具编辑失败') : t('工具创建失败') }}
      </h1>
      <span>{{ t('接下来你可以重新修改工具，或返回工具广场') }}</span>
      <div style="margin-top: 16px;">
        <bk-button
          theme="primary"
          @click="handleModifyAgain">
          {{ t('重新修改') }}
        </bk-button>
        <bk-button
          class="ml8"
          @click="handleBack">
          {{ t('返回工具广场') }}
        </bk-button>
      </div>
    </div>
  </div>
</template>
<script setup lang='ts'>
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  interface Emits {
    (e: 'modifyAgain'): void;
  }
  interface Props {
    isEditMode: boolean;
    name: string;
  }

  defineProps<Props>();
  const emits = defineEmits<Emits>();
  const router = useRouter();
  const { t } = useI18n();

  const handleModifyAgain = () => {
    emits('modifyAgain');
  };

  const handleBack = () => {
    window.changeConfirm = false;
    router.push({
      name: 'toolsSquare',
    });
  };
</script>
<style lang="postcss" scoped>
.tool-status-failed {
  display: flex;
  height: 360px;
  text-align: center;
  background-color: #fff;
  flex-direction: column;
  justify-content: center;
  align-items: center;

  .tool-status-failed-icon {
    margin-bottom: 10px;
    font-size: 64px;
    color: red;
  }
}
</style>
