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
  <bk-sideslider
    v-model:isShow="isShowRight"
    class="inset-var"
    quick-close
    :title="t('引用变量')"
    transfer
    :width="960">
    <template #default>
      <div class="inset-var-content">
        <bk-tab
          v-model:active="active"
          class="inset-var-tab"
          type="card-grid">
          <bk-tab-panel
            :label="t('风险信息')"
            name="risk">
            <div clss="risk-panel">
              <risk-info
                @insert="handleInsert" />
            </div>
          </bk-tab-panel>
          <bk-tab-panel
            :label="t('事件信息')"
            name="event">
            <event-info
              @insert="handleInsert" />
          </bk-tab-panel>
        </bk-tab>
      </div>
    </template>
  </bk-sideslider>
</template>

<script setup lang="tsx">
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import EventInfo from './event-info.vue';
  import RiskInfo from './risk-info.vue';

  interface Props {
    visible: boolean;
  }

  interface Emits {
    (e: 'update:visible', value: boolean): void;
    (e: 'confirm', value: string): void;
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const isShowRight = ref(false);
  const { t } = useI18n();
  const active = ref('risk');


  const handleInsert = (variableText: string) => {
    emits('confirm', variableText);
    isShowRight.value = false;
  };

  // 同步 visible 和 isShowRight
  watch(() => props.visible, (newVal: boolean) => {
    isShowRight.value = newVal;
  }, { immediate: true });

  watch(() => isShowRight.value, (newVal: boolean) => {
    if (!newVal) {
      emits('update:visible', false);
    }
  });
</script>

<style lang="postcss" scoped>
.inset-var-content {
  margin-top: 10px;
}

.inset-var {
  :deep(.bk-modal-body) {
    position: relative;
    background-color: #f5f7fa;
  }

  :deep(.bk-tab-content) {
    padding: 0;
  }
}

.risk-panel {
  margin-left: 30px;
  background-color: #f5f7fa;
}

.inset-var-tab {
  :deep(.bk-tab-header) {
    margin-left: 40px;
  }

  :deep(.t-table__header--fixed:not(.t-table__header--multiple) > tr > th) {
    background-color: #f0f1f5;
  }
}

</style>
