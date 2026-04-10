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
            <!-- 可编辑字段：编辑态 -->
            <bk-input
              v-if="row.editable && editingField === row.key"
              :ref="(el: any) => setInputRef(row.key, el)"
              v-model="editValue"
              class="inline-edit-input"
              @blur="handleSave(row.key)"
              @enter="handleSave(row.key)" />
            <!-- 可编辑字段：查看态 -->
            <span
              v-else-if="row.editable"
              class="user-info">
              {{ row.value }}
              <audit-icon
                class="edit-icon"
                type="edit-fill"
                @click="handleEdit(row.key, row.value)" />
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
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface SceneData {
    id: number;
    name: string;
    description: string;
    manager: string;
    users: string;
    updatedBy: string;
    updatedAt: string;
  }

  const props = defineProps<{
    sceneData: SceneData;
  }>();

  const emit = defineEmits<{
    'update:sceneData': [value: SceneData];
  }>();

  const { t } = useI18n();
  const infoRows = computed(() => [
    {
      key: 'id',
      label: t('场景ID'),
      value: props.sceneData.id,
    },
    {
      key: 'name',
      label: t('场景名称'),
      value: props.sceneData.name,
    },
    {
      key: 'description',
      label: t('场景描述'),
      value: props.sceneData.description,
    },
    {
      key: 'manager',
      label: t('场景管理员'),
      value: props.sceneData.manager,
      tooltip: t('拥有场景的完整管理权限，包括策略配置、数据源管理、成员管理等'),
      editable: true,
    },
    {
      key: 'users',
      label: t('场景使用者'),
      value: props.sceneData.users,
      tooltip: t('拥有场景下资源的只读使用权限（检索、报表、工具），无法更改场景配置'),
      editable: true,
    },
    {
      key: 'updatedBy',
      label: t('更新人'),
      value: props.sceneData.updatedBy,
    },
    {
      key: 'updatedAt',
      label: t('更新时间'),
      value: props.sceneData.updatedAt,
    },
  ]);
  const editingField = ref('');
  const editValue = ref('');
  const inputRefs: Record<string, any> = {};

  const setInputRef = (key: string, el: any) => {
    if (el) {
      inputRefs[key] = el;
    }
  };

  const handleEdit = (key: string, value: any) => {
    editValue.value = String(value);
    editingField.value = key;
    nextTick(() => {
      inputRefs[key]?.focus();
    });
  };

  const handleSave = (key: string) => {
    emit('update:sceneData', {
      ...props.sceneData,
      [key]: editValue.value,
    });
    editingField.value = '';
  };
</script>

<style lang="postcss" scoped>
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
  }

  .inline-edit-input {
    width: 560px;
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
