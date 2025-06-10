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
  <skeleton-loading
    :loading="isLoading"
    name="systemDetailLogCollector">
    <div
      ref="rootRef"
      class="log-collection-card"
      :style="{ height: height }">
      <div class="title">
        {{ t('日志拉取') }}
        <span class="tag">pull</span>
        <auth-router-link
          v-if="taskStatus !== 'taskEmpty'"
          action-id="edit_system"
          class="create-collector"
          :resource="route.params.id || props.id"
          :to="{
            name: 'collectorCreate',
            params: {
              systemId: route.params.id || props.id
            }
          }">
          {{ t('新建') }}
        </auth-router-link>
      </div>
      <div class="log-collection-content">
        <component
          :is="statusComponent"
          :id="id"
          ref="listRef"
          @change-checked="(value: any) => handleChecked(value)"
          @change-status-com="(value: any) => handleStatusCom(value)" />
      </div>
    </div>
  </skeleton-loading>
</template>
<script setup lang="ts">
  import {
    computed,
    onMounted,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import TaskEmpty from './components/task-empty.vue';
  import TaskList from './components/task-list/index.vue';

  import { getOffset } from '@/utils/assist';

  interface Emits {
    (e: 'changeChecked', value: {id: number, name: string}): void
  }
  interface Exposes {
    handleCancelCheck: ()=> void
  }

  interface Props {
    id: string;
  }
  const props = withDefaults(defineProps<Props>(), {
    id: '',
  });
  const emit = defineEmits<Emits>();
  const route = useRoute();

  const { t } = useI18n();
  const rootRef = ref();
  const listRef = ref();

  const statusCom = {
    taskEmpty: TaskEmpty,
    taskList: TaskList,
  };

  const statusComponent = computed(() => statusCom[taskStatus.value]);
  const isLoading = computed(() => (listRef.value ? listRef.value.loading : true));

  const taskStatus = ref<keyof typeof statusCom>('taskList');

  const height = ref('');

  const handleChecked = (value: {id: number, name: string}) => {
    emit('changeChecked',  value);
  };
  const handleStatusCom = (value: keyof typeof statusCom) => {
    taskStatus.value = value ? 'taskList' : 'taskEmpty';
  };

  onMounted(() => {
    const { top } = getOffset(rootRef.value);
    height.value = `calc(100vh - ${top + 155}px)`;
  });

  defineExpose<Exposes>({
    handleCancelCheck() {
      if (taskStatus.value === 'taskList') {
        return listRef.value.handleCancelCheck();
      }
    },
  });
</script>
<style lang="postcss">
.log-collection-card {
  padding: 16px 0;
  background-color: #fff;
  border-radius: 2px;
  box-shadow: 0 1px 2px 0 rgb(0 0 0 / 16%);

  .title {
    display: flex;
    align-items: center;
    padding: 0 24px;
    margin-bottom: 10px;
    font-size: 14px;
    line-height: 22px;
    color: #313238;

    .tag {
      display: inline-block;
      height: 16px;
      padding: 0 4px;
      margin-left: 6px;
      font-size: 12px;
      line-height: 16px;
      color: #fff;
      background: #979ba5;
      border-radius: 2px;
      user-select: none;
    }

    .create-collector {
      margin-left: auto;
      font-size: 12px;
      color: #3a84ff;
      cursor: pointer;
    }
  }
}
</style>
