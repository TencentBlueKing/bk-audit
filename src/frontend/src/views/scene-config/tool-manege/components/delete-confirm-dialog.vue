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
    v-model:is-show="isShow"
    footer-align="center"
    :show-head="false"
    width="480">
    <div class="delete-dialog-content">
      <img
        class="tip-icon"
        src="@images/tip-icon.svg">
      <div class="delete-title">
        {{ t('确定删除该工具？') }}
      </div>
      <div class="delete-warning">
        {{ t('此操作将') }}
        <span class="danger-text">{{ t('永久删除该工具') }}</span>
        {{ t('，且不可恢复，请谨慎操作！') }}
      </div>
      <div class="delete-confirm-tip">
        {{ t('请输入工具名称') }}「<span
          v-bk-tooltips="{ content: t('点击复制') }"
          class="tool-name"
          @click="handleCopyToolName">{{ deleteTarget?.name }}</span>」{{ t('以确认删除') }}
      </div>
      <bk-input
        v-model="confirmInput"
        :placeholder="t('请输入工具名称')" />
    </div>
    <template #footer>
      <bk-button
        class="mr8"
        :disabled="confirmInput !== deleteTarget?.name"
        :loading="deleteLoading"
        theme="danger"
        @click="handleConfirmDelete">
        {{ t('删除') }}
      </bk-button>
      <bk-button @click="handleCancel">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>

<script setup lang="ts">
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolManageService from '@service/tool-manage';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  interface ToolItem {
    uid: string;
    name: string;
  }

  interface Props {
    deleteTarget: ToolItem | null;
  }

  interface Emits {
    (e: 'deleted'): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const { messageSuccess } = useMessage();

  const isShow = defineModel<boolean>('isShow', { default: false });
  const confirmInput = ref('');

  // 监听弹窗显示状态，重置输入
  watch(isShow, (val) => {
    if (val) {
      confirmInput.value = '';
    }
  });

  // 删除工具
  const {
    loading: deleteLoading,
    run: runDeleteTool,
  } = useRequest(ToolManageService.fetchDeleteTool, {
    defaultValue: null,
    onSuccess: () => {
      messageSuccess(t('删除成功'));
      isShow.value = false;
      confirmInput.value = '';
      emit('deleted');
    },
  });

  // 确认删除
  const handleConfirmDelete = () => {
    if (props.deleteTarget && confirmInput.value === props.deleteTarget.name) {
      runDeleteTool({ uid: props.deleteTarget.uid });
    }
  };

  // 取消删除
  const handleCancel = () => {
    isShow.value = false;
    confirmInput.value = '';
  };

  // 复制工具名称到剪贴板
  const handleCopyToolName = () => {
    if (props.deleteTarget?.name) {
      navigator.clipboard.writeText(props.deleteTarget.name)
        .then(() => {
          messageSuccess(t('复制成功'));
        })
        .catch((err) => {
          console.error('复制失败:', err);
        });
    }
  };
</script>

<style lang="postcss">
  /* 删除确认弹窗样式 */
  .delete-dialog-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 24px 0 8px;

    .tip-icon {
      position: absolute;
      top: -25px;
      left: 50%;
      width: 50px;
      height: 50px;
      margin-bottom: 16px;
      transform: translateX(-50%);
    }

    .delete-title {
      margin-bottom: 24px;
      font-size: 20px;
      color: #313238;
    }

    .delete-warning {
      width: 100%;
      padding: 12px 16px;
      margin-bottom: 16px;
      font-size: 14px;
      color: #63656e;
      text-align: center;
      background: #f5f7fa;
      border-radius: 2px;
    }

    .danger-text {
      font-weight: 600;
      color: #ea3636;
    }

    .delete-confirm-tip {
      width: 100%;
      margin-bottom: 8px;
      font-size: 14px;
      color: #63656e;
      text-align: left;
    }

    .tool-name {
      color: #3a84ff;
      cursor: pointer;
    }

    .bk-input {
      width: 100%;
    }
  }
</style>
