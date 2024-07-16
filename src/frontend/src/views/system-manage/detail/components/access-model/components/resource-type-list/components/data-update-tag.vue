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
  <div class="data-update-type">
    <div
      class="type-tag"
      :style="styles">
      {{ renderText }}
    </div>
    <bk-dropdown
      :is-show="isShow"
      trigger="manual">
      <audit-icon
        class="type-edit"
        :class="[status !=='running' ? 'type-edit-disabled' : '' ]"
        :style="{display: isShow ? 'block' : ''}"
        type="edit-fill"
        @click="handleShow" />
      <template #content>
        <bk-dropdown-menu>
          <bk-dropdown-item
            v-for="item in dropdownList"
            :key="item.id"
            @click="handleSelectType(item.id)">
            {{ item.name }}
          </bk-dropdown-item>
        </bk-dropdown-menu>
      </template>
    </bk-dropdown>
  </div>
</template>
<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
  } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';

  import JoinDataModel from '@model/collector/join-data';
  import type SystemResourceTypeModel from '@model/meta/system-resource-type';

  import useRequest from '@/hooks/use-request';

  interface Props{
    data: SystemResourceTypeModel;
    type: 'partial' | 'full',
    status: 'failed' | 'preparing' | 'running' | 'closed',
  }
  interface Emits {
    (e: 'changeStatus'): void
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const route = useRoute();

  const { t, locale } = useI18n();

  const isShow = ref(false);

  const statusStyle = {
    full: {
      background: '#dedafc99',
      color: '#7D70E0',
      borderColor: '#7d70e04d',
      width: locale.value === 'en-US' ? '84px' : '64px',
    },
    partial: {
      background: '#ffe8c399',
      color: '#FE9C00',
      borderColor: '#fe9c004d',
      width: locale.value === 'en-US' ? '84px' : '64px',
    },
  };

  const dropdownList = [{ name: t('增量更新'), id: 'partial' }, { name: t('全量更新'), id: 'full' }];

  // 更改数据录入任务更新方式
  const {
    run: fetchJoinData,
  }  = useRequest(CollectorManageService.fetchJoinData, {
    defaultValue: new JoinDataModel(),
    onSuccess: () => {
      emits('changeStatus');
    },
  });

  const handleShow = () => {
    if (props.status !== 'running') return;
    isShow.value = !isShow.value;
  };

  const handleSelectType = (type: string) => {
    isShow.value = false;
    fetchJoinData({
      system_id: route.params.id,
      resource_type_id: props.data.resource_type_id,
      is_enabled: true,
      pull_type: type,
    });
  };

  const renderText = computed(() => {
    const textMap = {
      full: t('全量更新'),
      partial: t('增量更新'),
    } as Record<string, string>;

    return textMap[props.type];
  });

  const styles = computed(() => statusStyle[props.type]);

</script>
<style lang="postcss">
  .data-update-type {
    display: flex;
    align-items: center;

    .type-tag {
      height: 22px;
      line-height: 20px;
      text-align: center;
      border: 1px solid;
      border-radius: 11px;
    }

    .type-edit {
      display: none;
      width: 12px;
      height: 12px;
      margin-left: 9px;
      color: #979ba5;
      cursor: pointer;

      &:hover {
        color: #3a84ff;
      }
    }

    .type-edit-disabled {
      color: #dcdee5;
      cursor: not-allowed;
    }
  }
</style>
