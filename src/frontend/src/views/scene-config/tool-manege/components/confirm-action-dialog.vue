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
  <!-- 删除模式：保留 bk-dialog（含输入框验证） -->
  <bk-dialog
    v-if="actionType === 'delete'"
    v-model:is-show="isShow"
    ext-cls="confirm-action-dialog"
    footer-align="center"
    :show-head="false"
    :width="480">
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
          @click="handleCopyToolName">{{ target?.name }}</span>」{{ t('以确认删除') }}
      </div>
      <bk-input
        v-model="confirmInput"
        :placeholder="t('请输入工具名称')" />
    </div>
    <template #footer>
      <bk-button
        class="mr8 confirm-action-btn"
        :disabled="confirmInput !== target?.name"
        :loading="deleteLoading"
        theme="danger"
        @click="handleDeleteConfirm">
        {{ t('删除') }}
      </bk-button>
      <bk-button
        class="confirm-action-btn"
        @click="handleCancel">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>

<script setup lang="ts">
  import { InfoBox } from 'bkui-vue';
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolManageService from '@service/tool-manage';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  type ActionType = 'delete' | 'enable' | 'disable';

  interface ToolItem {
    uid: string;
    name: string;
    status?: 'published' | '';
  }

  interface Props {
    target: ToolItem | null;
    actionType: ActionType;
  }

  interface Emits {
    (e: 'success'): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const { messageSuccess } = useMessage();

  const isShow = defineModel<boolean>('isShow', { default: false });
  const confirmInput = ref('');

  // 监听弹窗显示状态：删除时清空输入
  watch(isShow, (val) => {
    if (val && props.actionType === 'delete') {
      confirmInput.value = '';
    }
  });

  // 启用/停用 — 使用全局 InfoBox
  const showToggleStatusInfoBox = (target?: ToolItem | null, actionType?: ActionType) => {
    const currentTarget = target || props.target;
    const currentActionType = actionType || props.actionType;
    if (!currentTarget) return;
    const isEnabling = currentActionType === 'enable';
    InfoBox({
      title: isEnabling ? t('确认启用该工具？') : t('确认停用该工具？'),
      subTitle: isEnabling
        ? t('启用后，该工具将在「工具广场」中展示')
        : t('停用后，该工具将从「工具广场」中隐藏'),
      confirmText: isEnabling ? t('启用') : t('停用'),
      cancelText: t('取消'),
      headerAlign: 'center',
      contentAlign: 'center',
      footerAlign: 'center',
      confirmButtonTheme: isEnabling ? 'primary' : 'danger',
      onConfirm() {
        const scopeParams = getSceneSystemParams();
        return publishPlatformTool({
          uid: currentTarget.uid,
          scene_id: Number(scopeParams.scope_id) || 0,
        });
      },
    });
  };

  // 删除接口
  const {
    loading: deleteLoading,
    run: runDeleteSceneTool,
  } = useRequest(ToolManageService.fetchDeleteSceneTool, {
    defaultValue: null,
    onSuccess: () => {
      messageSuccess(t('删除成功'));
      close();
      emit('success');
    },
  });

  // 启用/停用接口
  const {
    run: publishPlatformTool,
  } = useRequest(ToolManageService.publishPlatformTool, {
    defaultValue: null,
    onSuccess: () => {
      const isEnabling = props.actionType === 'enable';
      messageSuccess(isEnabling ? t('启用成功') : t('停用成功'));
      emit('success');
    },
  });

  // 删除确认
  const handleDeleteConfirm = () => {
    if (!props.target || confirmInput.value !== props.target.name) return;
    const scopeParams = getSceneSystemParams();
    runDeleteSceneTool({
      uid: props.target.uid,
      scene_id: Number(scopeParams.scope_id) || 0,
    });
  };

  const close = () => {
    isShow.value = false;
    confirmInput.value = '';
  };

  const handleCancel = () => {
    close();
  };

  defineExpose({
    showToggleStatusInfoBox,
  });

  // 复制工具名称到剪贴板
  const handleCopyToolName = () => {
    if (props.target?.name) {
      navigator.clipboard.writeText(props.target.name)
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
  .confirm-action-dialog {
    .bk-dialog-footer {
      background: none !important;
      border-top: none !important;
    }

    .confirm-action-btn {
      min-width: 120px;
    }
  }

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
      font-weight: 700;
      color: #313238;
    }

    .delete-warning {
      width: 100%;
      padding: 12px 16px;
      margin-bottom: 16px;
      font-size: 14px;
      color: #63656e;
      text-align: center;
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
