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
  <div class="report-title-cell">
    <bk-loading
      class="report-title-loading"
      :loading="loading"
      size="mini">
      <template v-if="isEditing">
        <bk-input
          ref="inputRef"
          v-model="draftTitle"
          class="report-title-input"
          size="small"
          @blur="handleSave"
          @enter="handleSave" />
      </template>
      <template v-else>
        <span
          v-if="canOpen"
          class="report-title-link"
          @click="emit('open')">
          {{ title }}
        </span>
        <span
          v-else
          class="report-title-text">
          {{ title }}
        </span>
        <audit-icon
          v-if="!loading && canEdit"
          class="report-title-edit hover-show-icon"
          type="edit-fill"
          @click.stop="handleEdit" />
      </template>
    </bk-loading>
  </div>
</template>

<script setup lang="ts">
  import {
    nextTick,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';

  import useMessage from '@hooks/use-message';

  interface Props {
    title: string;
    reportId: string | number;
    canOpen?: boolean;
    canEdit?: boolean;
  }

  interface Emits {
    (e: 'open'): void;
    (e: 'updated', title: string): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    canOpen: false,
    canEdit: false,
  });
  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const { messageSuccess, messageError } = useMessage();

  const isEditing = ref(false);
  const draftTitle = ref('');
  const loading = ref(false);
  const inputRef = ref();
  let isSaving = false;

  const resetEditState = () => {
    isEditing.value = false;
  };

  const handleEdit = () => {
    if (loading.value || isEditing.value || !props.reportId || !props.canEdit) return;
    draftTitle.value = props.title || '';
    isEditing.value = true;
    nextTick(() => {
      inputRef.value?.focus?.();
    });
  };

  const handleSave = async () => {
    if (isSaving || loading.value || !props.reportId) return;
    isSaving = true;

    const nextTitle = draftTitle.value.trim();
    if (!nextTitle || nextTitle === props.title) {
      resetEditState();
      nextTick(() => {
        isSaving = false;
      });
      return;
    }

    loading.value = true;
    try {
      const detail = await RiskManageService.getAiAnalyseReportDetail({
        report_id: props.reportId,
      });
      const content = detail?.content ?? '';
      if (!content) {
        messageError(t('报告内容为空，无法编辑标题'));
        return;
      }
      await RiskManageService.updateAiAnalyseReport({
        report_id: props.reportId,
        title: nextTitle,
        content,
      });
      messageSuccess(t('保存成功'));
      emit('updated', nextTitle);
      resetEditState();
    } finally {
      loading.value = false;
      nextTick(() => {
        isSaving = false;
      });
    }
  };
</script>

<style lang="postcss" scoped>
.report-title-cell {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
}

.report-title-loading {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
}

.report-title-link {
  overflow: hidden;
  color: #3a84ff;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;

  &:hover {
    color: #699df4;
    text-decoration: underline;
  }
}

.report-title-text {
  overflow: hidden;
  color: #313238;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.report-title-input {
  width: 100%;
  min-width: 120px;
}

.report-title-edit {
  flex-shrink: 0;
  margin-left: 4px;
  font-size: 14px;
  color: #4d4f56;
  cursor: pointer;

  &:hover {
    color: #3a84ff;
  }
}
</style>
