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
  <div class="stat-cards">
    <div
      v-for="card in cardList"
      :key="card.key"
      class="stat-card">
      <div class="stat-card-content">
        <div class="stat-info">
          <div class="stat-label">
            {{ card.label }}
          </div>
          <div class="stat-value">
            {{ card.value }}
          </div>
        </div>
        <div class="stat-right">
          <bk-button
            v-if="card.linkEvent"
            class="stat-link"
            text
            theme="primary"
            @click="handleCardClick(card.linkEvent)">
            {{ t('查看详情') }} →
          </bk-button>
          <img
            alt=""
            class="stat-icon"
            :src="card.icon">
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  import sceneInfo1 from '@images/sceneInfo-1.svg';
  import sceneInfo2 from '@images/sceneInfo-2.svg';
  import sceneInfo3 from '@images/sceneInfo-3.svg';
  import sceneInfo4 from '@images/sceneInfo-4.svg';

  interface SceneData {
    systemCount: number;
    dataTableCount: number;
    strategyCount: number;
    activeRiskCount: number;
  }

  const props = defineProps<{
    sceneData: SceneData;
  }>();

  const emit = defineEmits<{
    'go-strategy': [];
    'go-risk': [];
  }>();

  const handleCardClick = (event?: 'go-strategy' | 'go-risk') => {
    if (event === 'go-strategy') {
      emit('go-strategy');
    } else if (event === 'go-risk') {
      emit('go-risk');
    }
  };

  const { t } = useI18n();
  const cardList = computed(() => [
    {
      key: 'system',
      label: t('关联系统'),
      value: props.sceneData.systemCount,
      icon: sceneInfo1,
    },
    {
      key: 'dataTable',
      label: t('关联数据表'),
      value: props.sceneData.dataTableCount,
      icon: sceneInfo2,
    },
    {
      key: 'strategy',
      label: t('审计策略'),
      value: props.sceneData.strategyCount,
      icon: sceneInfo3,
      linkEvent: 'go-strategy' as const,
    },
    {
      key: 'risk',
      label: t('活跃风险'),
      value: props.sceneData.activeRiskCount,
      icon: sceneInfo4,
      linkEvent: 'go-risk' as const,
    },
  ]);
</script>

<style lang="postcss" scoped>
  .stat-cards {
    display: flex;
    gap: 16px;
    margin-bottom: 24px;
  }

  .stat-card {
    position: relative;
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
    padding: 20px 24px;
    background-color: #fff;
    border: 1px solid #e1e6f0;
    border-radius: 2px;
  }

  .stat-card-content {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .stat-info {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
  }

  .stat-right {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    justify-content: flex-end;
  }

  .stat-label {
    margin-bottom: 8px;
    font-size: 14px;
    line-height: 20px;
    color: #4d4f56;
  }

  .stat-value {
    font-size: 32px;
    font-weight: 700;
    line-height: 40px;
    color: #313238;
  }

  .stat-icon {
    width: 64px;
    height: 64px;
  }

  .stat-link {
    position: relative;
    z-index: 1;
    margin-bottom: -16px;
    font-size: 12px;
  }
</style>
