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
  <bk-dialog
    footer-align="center"
    :is-show="visible"
    :quick-close="false"
    theme="primary"
    :width="400"
    @update:is-show="handleVisibleChange">
    <div class="delete-dialog-title">
      {{ t('是否删除该智能体?') }}
    </div>
    <div class="delete-dialog-content">
      <div class="delete-dialog-name">
        {{ t('名称') }}: {{ agentName }}
      </div>
      <div class="delete-dialog-warning">
        {{ t('删除该智能体后将无法恢复,请谨慎操作') }}
      </div>
    </div>
    <template #footer>
      <bk-button
        class="mr8"
        theme="danger"
        @click="handleConfirm">
        {{ t('删除') }}
      </bk-button>
      <bk-button
        @click="handleCancel">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>

<script lang="ts" setup>
  import { useI18n } from 'vue-i18n';

  defineProps<Props>();

  const emit = defineEmits<Emits>();

  const { t } = useI18n();

  interface Props {
    visible: boolean;
    agentName: string;
  }

  interface Emits {
    (e: 'update:visible', value: boolean): void;
    (e: 'confirm'): void;
    (e: 'cancel'): void;
  }

  const handleVisibleChange = (value: boolean) => {
    emit('update:visible', value);
  };

  const handleConfirm = () => {
    emit('confirm');
  };

  const handleCancel = () => {
    emit('cancel');
  };
</script>

<style lang="postcss" scoped>
.delete-dialog-title {
  margin-bottom: 20px;
  font-size: 16px;
  font-weight: 700;
  line-height: 24px;
  color: #313238;
  text-align: center;
}

.delete-dialog-content {
  padding: 0 20px;
}

.delete-dialog-name {
  margin-bottom: 12px;
  font-size: 14px;
  line-height: 22px;
  color: #313238;
}

.delete-dialog-warning {
  font-size: 12px;
  line-height: 20px;
  color: #63656e;
}

.mr8 {
  margin-right: 8px;
}
</style>

