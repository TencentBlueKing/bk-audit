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
    v-if="isShow"
    class="header-tips">
    <audit-icon
      class="menu-item-icon"
      type="remind-fill" />
    <span class="tips-text">
      {{ t('当前系统未完成配置') }}：1.<span>
        {{ t('注册系统信息') }}</span>
      -> 2.<span
        :class="isCompleted ? 'tips-link' : ''"
        @click="handleRouterChange('systemAccessSteps', false, 2)">{{ t('注册权限模型') }}
      </span>-> 3.<span
        :class="isCompleted ? 'tips-link' : ''"
        @click="handleRouterChange('systemAccessSteps', false, 3)">{{ t('上报日志数据') }}</span>
    </span>
  </div>
</template>

<script setup lang="ts">
  import { onMounted, onUnmounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
    useRouter,
  } from 'vue-router';

  import SystemModel from '@model/meta/system';

  import useEventBus from '@hooks/use-event-bus';

  const { t } = useI18n();
  const router = useRouter();
  const route = useRoute();
  const { on, off } = useEventBus();
  const isCompleted = ref(false);
  const isShow = ref(false);

  const handleRouterChange = (name: string, isNewSystem: boolean, step: number) => {
    if (isCompleted.value) {
      router.push({
        name,
        query: {
          step: step.toString(),
          showModelType: 'false',
          isNewSystem: isNewSystem.toString(),
        },
        params: {
          id: route.params.id,
        },
      });
    }
  };
  // 监听事件
  onMounted(() => {
    on('get-system-info', (data: unknown) => {
      const systemInfo = data as SystemModel;
      isCompleted.value = (systemInfo.system_status === 'completed');
      isShow.value = !(systemInfo.system_status === 'normal' || systemInfo.system_status === 'abnormal');
    // 处理数据...
    });
  });

  // 组件卸载时移除监听
  onUnmounted(() => {
    off('get-system-info');
  });
</script>

<style scoped lang="postcss">
.header-tips {
  width: 100%;
  height: 32px;
  font-size: 12px;
  line-height: 32px;
  letter-spacing: 0;
  color: #4d4f56;
  background: #fdf4e8;
  border: 1px solid #f9d090;

  .menu-item-icon {
    margin-right: 5px;
    margin-left: 10px;
    color: #f59500;
  }

  .tips-text {
    .tips-link {
      color: #77a8f8;
      cursor: pointer;
    }
  }

}
</style>
