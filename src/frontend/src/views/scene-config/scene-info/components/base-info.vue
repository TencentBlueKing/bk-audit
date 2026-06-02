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
  <div class="section">
    <div class="section-title">
      {{ t('基础信息') }}
    </div>
    <table class="info-table">
      <tbody>
        <tr
          v-for="row in infoRows"
          :key="row.key">
          <td class="info-label">
            <!-- 带 tooltip 的标签 -->
            <bk-popover
              v-if="row.tooltip"
              placement="top"
              theme="dark">
              <span class="dashed-underline">{{ row.label }}</span>
              <template #content>
                <div>{{ row.tooltip }}</div>
              </template>
            </bk-popover>
            <!-- 普通标签 -->
            <template v-else>
              {{ row.label }}
            </template>
          </td>
          <td class="info-value">
            <!-- 人员选择字段：编辑态 -->
            <template v-if="row.type === 'user-selector'">
              <div
                v-if="editingField === row.key"
                :ref="(el: any) => setEditorRef(row.key, el)"
                class="editor-wrapper">
                <audit-user-selector-tenant
                  v-model="editUserValue"
                  allow-create
                  auto-focus
                  multiple
                  @blur="handleUserSave(row.key)" />
              </div>
              <!-- 人员选择字段：查看态 -->
              <span
                v-else
                class="user-info">
                <edit-tag
                  :data="row.rawValue"
                  :max="5" />
                <audit-icon
                  v-if="canEdit && savingField !== row.key"
                  class="edit-icon"
                  type="edit-fill"
                  @click="handleUserEdit(row.key, row.rawValue)" />
                <audit-icon
                  v-else-if="savingField === row.key"
                  class="edit-loading"
                  type="loading" />
              </span>
            </template>
            <!-- 可编辑字段：编辑态 -->
            <div
              v-else-if="row.editable && editingField === row.key"
              :ref="(el: any) => setEditorRef(row.key, el)"
              class="editor-wrapper">
              <bk-input
                :ref="(el: any) => setInputRef(row.key, el)"
                v-model="editValue"
                class="inline-edit-input"
                @blur="handleSave(row.key)"
                @enter="handleSave(row.key)" />
            </div>
            <!-- 可编辑字段：查看态 -->
            <span
              v-else-if="row.editable"
              class="user-info">
              {{ row.value }}
              <audit-icon
                v-if="canEdit && savingField !== row.key"
                class="edit-icon"
                type="edit-fill"
                @click="handleEdit(row.key, row.value)" />
              <audit-icon
                v-else-if="savingField === row.key"
                class="edit-loading"
                type="loading" />
            </span>
            <!-- 普通字段 -->
            <template v-else>
              {{ row.value }}
            </template>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
  import {
    computed,
    nextTick,
    onBeforeUnmount,
    onMounted,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import EditTag from '@components/edit-box/tag.vue';

  interface SceneData {
    id: number;
    name: string;
    description: string;
    manager: string[];
    users: string[];
    updatedBy: string;
    updatedAt: string;
  }

  const { sceneData, savingField, canEdit } = defineProps<{
    sceneData: SceneData;
    savingField: string;
    canEdit: boolean;
  }>();

  const emit = defineEmits<{
    'update:sceneData': [value: SceneData, changedKey: string];
  }>();

  const { t } = useI18n();
  const infoRows = computed(() => [
    {
      key: 'id',
      label: t('场景ID'),
      value: sceneData.id,
      editable: false,
    },
    {
      key: 'name',
      label: t('场景名称'),
      value: sceneData.name,
      editable: false,
    },
    {
      key: 'description',
      label: t('场景描述'),
      value: sceneData.description,
      editable: true,
    },
    {
      key: 'manager',
      label: t('场景管理员'),
      value: sceneData.manager?.join('、') || '--',
      rawValue: sceneData.manager || [],
      tooltip: t('拥有场景的完整管理权限，包括策略配置、数据源管理、成员管理等'),
      type: 'user-selector',
    },
    {
      key: 'users',
      label: t('场景使用者'),
      value: sceneData.users?.join('、') || '--',
      rawValue: sceneData.users || [],
      tooltip: t('拥有场景下资源的只读使用权限（检索、报表、工具），无法更改场景配置'),
      type: 'user-selector',
    },
    {
      key: 'updatedBy',
      label: t('更新人'),
      value: sceneData.updatedBy,
      editable: false,
    },
    {
      key: 'updatedAt',
      label: t('更新时间'),
      value: sceneData.updatedAt,
      editable: false,
    },
  ]);
  const editingField = ref('');
  const editValue = ref('');
  const editUserValue = ref<string[]>([]);
  const inputRefs: Record<string, any> = {};
  const editorRefs: Record<string, HTMLElement | null> = {};
  // 防止 blur 和 mousedown/enter 事件同时触发导致重复保存
  let isSaving = false;

  const setInputRef = (key: string, el: any) => {
    if (el) {
      inputRefs[key] = el;
    }
  };

  const setEditorRef = (key: string, el: HTMLElement | null) => {
    editorRefs[key] = el;
  };

  // 普通文本字段编辑
  const handleEdit = (key: string, value: any) => {
    editValue.value = String(value);
    editingField.value = key;
    nextTick(() => {
      inputRefs[key]?.focus();
    });
  };

  // 普通文本字段保存
  const handleSave = (key: string) => {
    // 防止 blur + enter/mousedown 重复触发
    if (isSaving) return;
    isSaving = true;
    // 值未变化时不触发更新
    const originalValue = String((sceneData as any)[key] ?? '');
    if (editValue.value === originalValue) {
      editingField.value = '';
      nextTick(() => {
        isSaving = false;
      });
      return;
    }
    emit('update:sceneData', {
      ...sceneData,
      [key]: editValue.value,
    }, key);
    editingField.value = '';
    nextTick(() => {
      isSaving = false;
    });
  };

  // 人员选择字段编辑
  const handleUserEdit = (key: string, value: string[]) => {
    editUserValue.value = [...value];
    editingField.value = key;
  };

  // 人员选择字段保存
  const handleUserSave = (key: string) => {
    // 防止 blur + mousedown 重复触发
    if (isSaving) return;
    isSaving = true;
    // 值未变化时不触发更新
    const originalValue = (sceneData as any)[key] || [];
    const isSame = originalValue.length === editUserValue.value.length
      && originalValue.every((item: string, index: number) => item === editUserValue.value[index]);
    if (isSame) {
      editingField.value = '';
      nextTick(() => {
        isSaving = false;
      });
      return;
    }
    emit('update:sceneData', {
      ...sceneData,
      [key]: editUserValue.value,
    }, key);
    editingField.value = '';
    nextTick(() => {
      isSaving = false;
    });
  };

  // 判断点击位置是否在 bk-select 浮层内（人员选择器选项弹层挂在 body 上）
  const isInSelectPopover = (target: Node) => {
    const el = target as HTMLElement;
    if (!el || !el.closest) return false;
    return !!el.closest('.bk-select-popover, .bk-select-content, .bk-popover2, .bk-popover, .bk-pop2-content');
  };

  // 点击外部时保存并退出编辑态
  const handleClickOutside = (e: MouseEvent) => {
    const key = editingField.value;
    if (!key) return;
    const target = e.target as Node;
    const editorEl = editorRefs[key];
    // 点击在编辑器内部 或 在 bk-select 弹层内（选择项时），不退出
    if (editorEl && editorEl.contains(target)) return;
    if (isInSelectPopover(target)) return;
    // 触发保存
    const fieldType = infoRows.value.find(item => item.key === key)?.type;
    if (fieldType === 'user-selector') {
      handleUserSave(key);
    } else {
      handleSave(key);
    }
  };

  onMounted(() => {
    document.addEventListener('mousedown', handleClickOutside, true);
  });

  onBeforeUnmount(() => {
    document.removeEventListener('mousedown', handleClickOutside, true);
  });
</script>

<style lang="postcss" scoped>
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }

  .section {
    padding: 16px 24px 24px;
    margin-bottom: 24px;
    background-color: #fff;
    border-radius: 2px;
  }

  .section-title {
    display: flex;
    flex-wrap: nowrap;
    gap: 8px;
    align-items: center;
    margin-bottom: 16px;
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
  }

  .dashed-underline {
    cursor: pointer;
    border-bottom: 1px dashed #c4c6cc;
  }

  .edit-icon {
    flex-shrink: 0;
    margin-left: 4px;
    font-size: 14px;
    color: #4d4f56;
    cursor: pointer;

    &:hover {
      color: #3a84ff;
    }
  }

  .edit-loading {
    flex-shrink: 0;
    margin-left: 4px;
    font-size: 14px;
    color: #3a84ff;
    animation: spin 1s linear infinite;
  }

  .inline-edit-input {
    width: 100%;
  }

  .editor-wrapper {
    width: 400px;
    max-width: 100%;
  }

  /* 基础信息表格 */
  .info-table {
    width: 100%;
    border: 1px solid #dcdee5;
    border-collapse: collapse;

    tr {
      border-bottom: 1px solid #dcdee5;

      &:last-child {
        border-bottom: none;
      }
    }

    .info-label {
      width: 160px;
      padding: 8px 10px;
      font-size: 12px;
      line-height: 20px;
      color: #4d4f56;
      text-align: right;
      background-color: #fafbfd;
      border-right: 1px solid #dcdee5;
    }

    .info-value {
      padding: 8px 16px;
      font-size: 12px;
      line-height: 20px;
      color: #313238;
    }
  }

  .user-info {
    display: inline-flex;
    gap: 4px;
    align-items: center;
  }
</style>
