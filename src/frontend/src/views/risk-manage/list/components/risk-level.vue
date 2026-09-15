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
  <span
    v-if="riskLevelInfo"
    :style="{
      'background-color': riskLevelInfo.color,
      padding: '3px 8px',
      'border-radius': '3px',
      color: 'white'
    }">
    {{ riskLevelInfo.label }}
  </span>
  <span v-else>--</span>
</template>

<script setup lang='ts'>
  import {
    computed,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';

  import type RiskManageModel from '@model/risk/risk';

  interface RiskItem {
    risk_id: string | number;
    risk_level?: string;
    strategy_id?: number;
    title?: string;
  }

  interface Props{
    data: RiskManageModel | RiskItem,
  }

  const props = defineProps<Props>();
  const { t } = useI18n();

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

  const riskLevelInfo = computed(() => {
    const level = props.data.risk_level;
    return level ? riskLevelMap[level] : undefined;
  });
</script>
