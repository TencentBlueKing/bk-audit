/* eslint-disable linebreak-style */
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
    :width="480"
    @update:is-show="handleVisibleChange">
    <div class="delete-dialog-title">
      {{ t('确认删工具？') }}
    </div>
    <div class="delete-dialog-content">
      <div class="confirm-input-section">
        <div class="confirm-input-label">
          {{ t('请输入工具') }}
          <span
            v-bk-tooltips="t('点击复制')"
            class="service-name-highlight"
            role="button"
            tabindex="0"
            @click="handleCopyServiceName"
            @keydown.enter.prevent="handleCopyServiceName"
            @keydown.space.prevent="handleCopyServiceName">
            {{ serviceName }}
          </span>
          {{ t('以确认删除') }}
        </div>
        <bk-input
          v-model="confirmInput"
          :placeholder="t('请输入工具名称')" />
      </div>
    </div>
    <template #footer>
      <bk-button
        class="mr8"
        :disabled="!isConfirmValid"
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
  import { Message } from 'bkui-vue';
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  const props = defineProps<Props>();

  const emit = defineEmits<Emits>();

  const { t } = useI18n();

  interface Props {
    visible: boolean;
    serviceName: string;
  }

  interface Emits {
    (e: 'update:visible', value: boolean): void;
    (e: 'confirm'): void;
    (e: 'cancel'): void;
  }

  const confirmInput = ref('');

  const isConfirmValid = computed(() => confirmInput.value === props.serviceName);

  watch(
    () => props.visible,
    (visible) => {
      if (visible) {
        confirmInput.value = '';
      }
    },
  );

  const handleVisibleChange = (value: boolean) => {
    if (!value) {
      confirmInput.value = '';
    }
    emit('update:visible', value);
  };

  const handleConfirm = () => {
    if (isConfirmValid.value) {
      emit('confirm');
    }
  };

  const handleCancel = () => {
    confirmInput.value = '';
    emit('update:visible', false);
    emit('cancel');
  };

  const handleCopyServiceName = async () => {
    const text = props.serviceName || '';
    if (!text) {
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      Message({ theme: 'success', message: t('复制成功') });
    } catch {
      try {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.left = '-9999px';
        textarea.style.top = '0';
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        const ok = document.execCommand('copy');
        document.body.removeChild(textarea);
        if (ok) {
          Message({ theme: 'success', message: t('复制成功') });
        } else {
          Message({ theme: 'error', message: t('复制失败') });
        }
      } catch {
        Message({ theme: 'error', message: t('复制失败') });
      }
    }
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

.delete-dialog-warning {
  margin-bottom: 12px;
  font-size: 12px;
  line-height: 20px;
  color: #63656e;
}

.service-name-section {
  padding: 16px;
  margin: 20px 0;
  background-color: #f5f7fa;
  border-radius: 2px;
}

.service-name-label {
  margin-bottom: 8px;
  font-size: 12px;
  line-height: 20px;
  color: #63656e;
}

.service-name-value {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.service-name-text {
  font-size: 14px;
  font-weight: 600;
  line-height: 22px;
  color: #313238;
}

.copy-button {
  min-width: auto;
  padding: 0 8px;
  font-size: 12px;
}

.confirm-input-section {
  margin-top: 20px;
}

.confirm-input-label {
  margin-bottom: 8px;
  font-size: 12px;
  line-height: 20px;
  color: #63656e;
}

.service-name-highlight {
  font-weight: 600;
  color: inherit;
  cursor: pointer;
}

.mr8 {
  margin-right: 8px;
}
</style>
