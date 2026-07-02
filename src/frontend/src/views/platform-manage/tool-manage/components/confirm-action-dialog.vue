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
<script setup lang="ts">
  import { h, ref } from 'vue';
  import { InfoBox } from 'bkui-vue';
  import { useI18n } from 'vue-i18n';

  import ToolManageService from '@service/tool-manage';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  type ActionType = 'delete' | 'enable' | 'disable';

  interface ToolItem {
    uid: string;
    name: string;
    status?: 'published' | 'unpublished' | '';
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

  // 删除 — 使用全局 InfoBox
  const showDeleteInfoBox = (target?: ToolItem | null) => {
    const currentTarget = target || props.target;
    if (!currentTarget) return;
    const confirmName = ref('');
    let deleteInfoInstance: any; // eslint-disable-line prefer-const
    const handleConfirm = () => {
      if (confirmName.value !== currentTarget.name) return;
      ToolManageService.deletePlatformTool(currentTarget.uid).then(() => {
        messageSuccess(t('删除成功'));
        deleteInfoInstance?.hide();
        emit('success');
      });
    };
    deleteInfoInstance = InfoBox({
      type: 'warning',
      title: t('确定删除该工具？'),
      subTitle: () => h('div', { style: { textAlign: 'left' } }, [
        h('div', {
          style: {
            padding: '12px 16px',
            marginBottom: '16px',
            fontSize: '14px',
            color: '#63656e',
            textAlign: 'center',
            backgroundColor: '#f5f7fa',
            borderRadius: '2px',
          },
        }, [
          t('此操作将'),
          h('span', { style: { fontWeight: 600, color: '#ea3636' } }, t('永久删除该工具')),
          t('，且不可恢复，请谨慎操作！'),
        ]),
        h('div', {
          style: { marginBottom: '8px', fontSize: '14px', color: '#63656e', textAlign: 'left' },
        }, [
          t('请输入工具名称「'),
          h('span', {
            style: { color: '#4D4F56', cursor: 'pointer', fontSize: '12px', fontWeight: 700 },
            onClick: () => handleCopyToolName(currentTarget.name),
          }, currentTarget.name),
          t('」以确认删除'),
        ]),
        h('input', {
          value: confirmName.value,
          placeholder: t('请输入工具名称'),
          onInput: (e: any) => {
            confirmName.value = e.target.value;
          },
          style: {
            width: '100%',
            height: '32px',
            padding: '0 10px',
            fontSize: '14px',
            border: '1px solid #c4c6cc',
            borderRadius: '2px',
            outline: 'none',
            boxSizing: 'border-box',
          },
        }),
      ]),
      headerAlign: 'center',
      contentAlign: 'center',
      footerAlign: 'center',
      footer: () => h('div', { style: { display: 'flex', justifyContent: 'center', alignItems: 'center' } }, [
        h('button', {
          class: 'info-box-confirm-btn',
          style: getConfirmBtnStyle(confirmName.value === currentTarget.name),
          onClick: handleConfirm,
        }, t('删除')),
        h('button', {
          style: cancelBtnStyle,
          onClick: () => deleteInfoInstance?.hide(),
        }, t('取消')),
      ]),
      onClose() {
        confirmName.value = '';
      },
    });
  };

  // 确认按钮样式（根据输入是否匹配切换禁用态）
  const getConfirmBtnStyle = (isMatch: boolean) => ({
    height: '32px',
    padding: '0 16px',
    fontSize: '14px',
    lineHeight: '32px',
    borderRadius: '2px',
    border: '1px solid',
    outline: 'none',
    marginRight: '8px',
    backgroundColor: isMatch ? '#ea3636' : '#fff',
    borderColor: isMatch ? '#ea3636' : '#dcdee5',
    color: isMatch ? '#fff' : '#c4c6cc',
    cursor: isMatch ? 'pointer' : 'not-allowed',
  });

  const cancelBtnStyle = {
    height: '32px',
    padding: '0 16px',
    fontSize: '14px',
    lineHeight: '32px',
    borderRadius: '2px',
    border: '1px solid #c4c6cc',
    outline: 'none',
    marginRight: '0',
    backgroundColor: '#fff',
    color: '#63656e',
    cursor: 'pointer',
  };

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
        return publishPlatformToolStatus({
          id: currentTarget.uid,
          status: isEnabling ? 'published' : 'unpublished',
        });
      },
    });
  };

  // 启用/停用接口（平台级）
  const {
    run: publishPlatformToolStatus,
  } = useRequest(ToolManageService.publishPlatformToolStatus, {
    defaultValue: null,
    onSuccess: () => {
      const isEnabling = props.actionType === 'enable';
      messageSuccess(isEnabling ? t('启用成功') : t('停用成功'));
      emit('success');
    },
  });

  defineExpose({
    showToggleStatusInfoBox,
    showDeleteInfoBox,
  });

  // 复制工具名称到剪贴板
  const handleCopyToolName = (name: string) => {
    if (name) {
      navigator.clipboard.writeText(name)
        .then(() => {
          messageSuccess(t('复制成功'));
        })
        .catch((err) => {
          console.error('复制失败:', err);
        });
    }
  };
</script>

