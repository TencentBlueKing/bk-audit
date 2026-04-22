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
    :width="isDelete ? 480 : 400">
    <!-- 删除模式 -->
    <div
      v-if="isDelete"
      class="delete-dialog-content">
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
    <!-- 启用/停用模式 -->
    <div
      v-else
      class="toggle-status-dialog-content">
      <div class="toggle-status-title">
        {{ isEnabling ? t('确认启用该工具？') : t('确认停用该工具？') }}
      </div>
      <div class="toggle-status-tip">
        {{ isEnabling ? t('启用后，该工具将在「工具广场」中展示') : t('停用后，该工具将从「工具广场」中隐藏') }}
      </div>
    </div>
    <template #footer>
      <bk-button
        class="mr8"
        :disabled="isDelete && confirmInput !== target?.name"
        :loading="loading"
        :theme="confirmTheme"
        @click="handleConfirm">
        {{ confirmText }}
      </bk-button>
      <bk-button @click="handleCancel">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>

<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
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

  const isDelete = computed(() => props.actionType === 'delete');
  const isEnabling = computed(() => props.actionType === 'enable');

  const confirmTheme = computed(() => {
    if (isDelete.value || props.actionType === 'disable') return 'danger';
    return 'primary';
  });

  const confirmText = computed(() => {
    if (isDelete.value) return t('删除');
    return isEnabling.value ? t('启用') : t('停用');
  });

  // 监听弹窗显示状态，重置输入
  watch(isShow, (val) => {
    if (val) {
      confirmInput.value = '';
    }
  });

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
    loading: toggleLoading,
    run: publishPlatformTool,
  } = useRequest(ToolManageService.publishPlatformTool, {
    defaultValue: null,
    onSuccess: () => {
      messageSuccess(isEnabling.value ? t('启用成功') : t('停用成功'));
      close();
      emit('success');
    },
  });

  const loading = computed(() => deleteLoading.value || toggleLoading.value);

  const handleConfirm = () => {
    if (!props.target) return;
    const scopeParams = getSceneSystemParams();
    if (isDelete.value) {
      if (confirmInput.value !== props.target.name) return;
      runDeleteSceneTool({
        uid: props.target.uid,
        scene_id: Number(scopeParams.scope_id) || 0,
      });
    } else {
      publishPlatformTool({
        uid: props.target.uid,
        scene_id: Number(scopeParams.scope_id) || 0,
      });
    }
  };

  const close = () => {
    isShow.value = false;
    confirmInput.value = '';
  };

  const handleCancel = () => {
    close();
  };

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

  /* 启用/停用弹窗样式 */
  .toggle-status-dialog-content {
    padding: 16px 0;
    text-align: center;

    .toggle-status-title {
      margin-bottom: 8px;
      font-size: 20px;
      font-weight: 700;
      line-height: 32px;
      color: #313238;
    }

    .toggle-status-tip {
      font-size: 14px;
      line-height: 22px;
      color: #63656e;
    }
  }
</style>
