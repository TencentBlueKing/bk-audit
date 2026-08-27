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
  <div class="select-system-card">
    <div class="card-body">
      <p class="card-tip">
        <img
          alt=""
          class="tip-icon"
          :src="wenhaoIcon">
        <span>
          先选择要查询的系统<span class="tip-extra">（仅限有权限的系统）</span>
        </span>
      </p>
      <div class="field-block">
        <div class="field-label">
          系统选择
        </div>
        <div class="field-control">
          <bk-select
            v-model="selectedId"
            class="sec-chat-system-picker"
            clearable
            filterable
            :input-search="false"
            :loading="systemListLoading"
            placeholder="请选择系统"
            :popover-options="selectPopoverOptions"
            :scroll-height="280"
            style="width: 100%; margin-left: 0;">
            <bk-option
              v-for="item in displaySystemList"
              :key="item.id"
              :label="`${item.name}(${item.id})`"
              :value="item.id" />
          </bk-select>
        </div>
      </div>
      <div class="card-actions">
        <bk-button
          class="confirm-btn"
          :disabled="!selectedId"
          theme="primary"
          @click="handleConfirm">
          确认选择
        </bk-button>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed, ref, watch } from 'vue';
  import { useRoute } from 'vue-router';

  import MetaManageService from '@service/meta-manage';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import wenhaoIcon from '@images/wenhao.svg';

  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  import type { SelectedSystem } from '../../types';

  export type { SelectedSystem };

  interface Props {
    modelValue?: string[];
  }

  const props = withDefaults(defineProps<Props>(), {
    modelValue: () => [],
  });

  const emit = defineEmits<{
    confirm: [systemIds: string[], systems: SelectedSystem[]];
    close: [];
  }>();

  const route = useRoute();
  const { messageWarn } = useMessage();
  const selectedId = ref<string>(props.modelValue?.[0] || '');

  // 与日志检索「系统名称」下拉使用同一接口；挂载时拉一次，场景切换后再拉
  const {
    loading: systemListLoading,
    data: systemList,
    run: fetchSystemList,
  } = useRequest(() => {
    const params = getSceneSystemParams();
    return MetaManageService.fetchSystemWithAction({
      scope_id: params.scope_id || '',
      scope_type: params.scope_type || '',
      audit_status__in: 'accessed',
    });
  }, {
    defaultValue: [],
    manual: true,
  });

  const displaySystemList = computed(() => (systemList.value || []).map(item => ({
    id: String(item.id),
    name: item.name,
  })));

  const selectedSystem = computed(() => {
    if (!selectedId.value) return null;
    return displaySystemList.value.find(item => item.id === selectedId.value)
      || { id: selectedId.value, name: selectedId.value };
  });

  const selectPopoverOptions = {
    extCls: 'sec-chat-system-select-popover',
    boundary: 'body',
    placement: 'bottom-start',
    autoPlacement: true,
    zIndex: 9999,
  } as const;

  watch(() => props.modelValue, (val) => {
    selectedId.value = val?.[0] || '';
  });

  // 场景选择器切换后 URL scope 变化，需按新场景重新拉取有权限系统
  watch(
    () => [
      String(route.query.scene_id || ''),
      String(route.query.scope_id || ''),
      String(route.query.scope_type || ''),
    ].join('|'),
    () => {
      fetchSystemList().then((list) => {
        const ids = (list || []).map(item => String(item.id));
        if (selectedId.value && !ids.includes(selectedId.value)) {
          selectedId.value = '';
        }
      });
    },
  );

  const handleConfirm = () => {
    if (!selectedId.value) {
      messageWarn('请选择系统');
      return;
    }
    const system = selectedSystem.value || { id: selectedId.value, name: selectedId.value };
    emit('confirm', [system.id], [system]);
  };
</script>

<style lang="postcss" scoped>
  .select-system-card {
    width: 100%;
    max-width: 100%;
    min-width: 0;
    overflow: visible;
    padding: 20px 24px 24px;
    font-size: 14px;
    font-weight: 400;
    line-height: 22px;
    color: #63656e;
    letter-spacing: 0;
    text-align: left;
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 12px 32px 0 rgb(0 0 0 / 4%);
    box-sizing: border-box;
  }

  .card-body {
    display: flex;
    padding: 0;
    background: transparent;
    flex-direction: column;
  }

  .card-tip {
    display: flex;
    margin: 0 0 16px;
    font-size: 14px;
    font-weight: 400;
    line-height: 22px;
    color: #63656e;
    letter-spacing: 0;
    text-align: left;
    align-items: flex-start;
    gap: 8px;

    .tip-icon {
      display: block;
      width: 18px;
      height: 18px;
      margin-top: 2px;
      flex-shrink: 0;
    }

    .tip-extra {
      color: #9ea1aa;
    }
  }

  .field-block {
    display: flex;
    width: 100%;
    margin: 0 0 16px;
    padding: 0;
    overflow: visible;
    flex-direction: column;
  }

  .field-label {
    display: block;
    width: 100%;
    margin-bottom: 8px;
    padding: 0;
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
    letter-spacing: 0;
    text-align: left;
    flex-shrink: 0;
    box-sizing: border-box;
  }

  .field-control {
    display: block;
    width: 100%;
    margin: 0;
    padding: 0;
    flex-shrink: 0;
    box-sizing: border-box;
  }

  .sec-chat-system-picker {
    display: block;
    width: 100%;
    max-width: 100%;
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  .field-control :deep(.bk-select),
  .field-control :deep(.sec-chat-system-picker) {
    display: block;
    width: 100%;
    max-width: 100%;
    margin: 0;
    padding: 0;
    background: transparent;
    box-sizing: border-box;
  }

  .field-control :deep(.bk-select-trigger) {
    width: 100%;
    background: #fff;
  }

  .field-control :deep(.bk-input),
  .field-control :deep(.bk-select-trigger .bk-input) {
    width: 100%;
    min-height: 32px;
    margin: 0;
    font-family: inherit;
    font-size: 14px;
    color: #313238;
    letter-spacing: 0;
    border: 1px solid #c4c6cc;
    border-radius: 2px;
    background: #fff;
    box-shadow: none;
    box-sizing: border-box;
  }

  .field-control :deep(.bk-input:hover) {
    border-color: #979ba5;
  }

  .field-control :deep(.is-focus > .bk-input),
  .field-control :deep(.bk-select.is-focus .bk-input) {
    border-color: #3a84ff;
    box-shadow: none;
    background: #fff;
  }

  .field-control :deep(.bk-input--text),
  .field-control :deep(.bk-input input),
  .field-control :deep(input) {
    font-family: inherit;
    font-size: 14px;
    color: #313238;
    letter-spacing: 0;
    background: transparent;
    background-color: transparent;
  }

  .field-control :deep(.bk-input--text::placeholder),
  .field-control :deep(input::placeholder) {
    font-family: inherit;
    font-size: 14px;
    color: #c4c6cc;
    letter-spacing: 0;
  }

  .field-control :deep(.bk-input--suffix-icon) {
    color: #979ba5;
    background: transparent;
  }

  .field-control :deep(.bk-loading),
  .field-control :deep(.bk-loading-wrapper),
  .field-control :deep(.bk-spin) {
    width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    background: transparent;
  }

  .card-actions {
    display: flex;
    justify-content: flex-start;

    .confirm-btn {
      min-width: 88px;
      height: 32px;
      padding: 0 16px;
      font-family: inherit;
      font-size: 14px;
      font-weight: 400;
      line-height: 32px;
      letter-spacing: 0;
      border-radius: 2px;
    }
  }
</style>

<style lang="postcss">
  .sec-chat-system-select-popover {
    z-index: 9999 !important;
  }
</style>
