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
  <div
    class="detail-base-info"
    :style="borderStyle">
    <div class="title">
      <template v-if="isEditingTitle">
        <bk-input
          v-model="draftTitle"
          class="title-input"
          size="small"
          @blur="handleTitleSave"
          @keydown.enter.prevent="handleTitleSave"
          @keydown.esc.prevent="handleTitleCancel" />
      </template>
      <template v-else>
        {{ data.title }}
        <audit-icon
          v-if="data.permission.edit_risk_v2"
          class="edit-fill"
          type="edit-fill"
          @click="handleTitleEdit" />
      </template>
    </div>
    <base-info-form
      v-if="priorityFieldNames.length"
      :data="data"
      :risk-status-common="riskStatusCommon"
      :show-field-names="priorityFieldNames"
      :strategy-list="strategyList"
      style="background-color: #f5f7fa;" />
    <template v-if="(normalFieldNames.length && isShowMore) || !priorityFieldNames.length">
      <base-info-form
        :data="data"
        :risk-status-common="riskStatusCommon"
        :show-field-names="normalFieldNames"
        :strategy-list="strategyList" />
    </template>
    <div
      v-if="priorityFieldNames.length && normalFieldNames.length"
      class="show-more-condition-btn">
      <bk-button
        class="show-more-btn"
        text
        @click="() => isShowMore = !isShowMore">
        <audit-icon
          :class="{ active: isShowMore }"
          style=" margin-right: 5px;"
          type="angle-double-down" />
        {{ isShowMore ? t('收起字段') : t('展开更多字段') }}
      </bk-button>
    </div>
  </div>
</template>

<script setup lang='ts'>
  import {
    computed,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';

  import type RiskManageModel from '@model/risk/risk';
  import type StrategyInfo from '@model/risk/strategy-info';

  import useRequest from '@hooks/use-request';

  import BaseInfoForm from './base-info-form.vue';

  import useMessage from '@/hooks/use-message';

  interface Props{
    data: RiskManageModel & StrategyInfo
    strategyList: Array<{
      label: string,
      value: number
    }>,
    riskStatusCommon: Array<{
      id: string,
      name: string,
    }>,
  }

  const props = defineProps<Props>();
  const emits = defineEmits<{
    'updated-data': [];
  }>();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();

  // 重点展示字段的 field_name 数组
  const priorityFieldNames = computed(() => props.data.risk_meta_field_config
    .filter(item => item.is_priority));

  // 非重点展示字段的 field_name 数组
  const normalFieldNames = computed(() => props.data.risk_meta_field_config
    .filter(item => !item.is_priority));

  const riskLevelMap: Record<string, {
    label: string,
    color: string,
  }> =  {
    HIGH: {
      label: t('高'),
      color: '#ea3636',
    },
    MIDDLE: {
      label: t('中'),
      color: '#ff9c01',
    },
    LOW: {
      label: t('低'),
      color: '#979ba5',
    },
  };

  const isShowMore = ref(false);
  const isEditingTitle = ref(false);
  const draftTitle = ref('');

  const handleTitleEdit = () => {
    isEditingTitle.value = true;
    draftTitle.value = props.data.title || '';
  };

  const handleTitleSave = () => {
    console.log('draftTitle>>', draftTitle.value);
    updateRiskTitle({
      risk_id: props.data.risk_id,
      title: draftTitle.value,
    });
    isEditingTitle.value = false;
  };

  const handleTitleCancel = () => {
    isEditingTitle.value = false;
  };

  const borderStyle = computed(() => ({
    'border-top': `6px solid ${riskLevelMap[props.data.risk_level]?.color}`,
  }));

  const {
    run: updateRiskTitle,
  } = useRequest(RiskManageService.updateRiskTitle, {
    defaultValue: {},
    defaultParams: {
      risk_id: props.data.risk_id,
      title: draftTitle.value,
    },
    onSuccess() {
      messageSuccess(t('修改成功'));
      emits('updated-data');
    },
  });
</script>
<style lang="postcss" scoped>
.detail-base-info {
  position: relative;
  padding: 10px 16px;
  background: #fff;
  border-radius: 2px;
  box-shadow: 0 2px 4px 0 #1919290d;

  .title {
    margin-bottom: 10px;
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;

    .title-input {
      max-width: 320px;
    }

    .edit-fill {
      margin-left: 10px;
      cursor: pointer;

      &:hover {
        color: #3a84ff;
      }
    }
  }

  .show-more-condition-btn {
    position: absolute;
    right: calc(50% - 52px);
    bottom: -11px;
    box-shadow: 0 2px 4px 0 #1919290d;

    .show-more-btn {
      width: 120px;
      height: 22px;
      color: #fff;
      background: #c4c6cc;;
      border-radius: 12px;

      &:hover {
        background-color: #3a84ff;
      }
    }

    .active {
      transform: rotateZ(-180deg);
      transition: all .15s;
    }
  }
}
</style>
