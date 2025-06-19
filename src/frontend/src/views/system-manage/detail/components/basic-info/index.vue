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
  <div class="system-basic-info">
    <h3>{{ t('系统信息') }}</h3>
    <div style="display: flex">
      <div class="item">
        <div class="item-title">
          {{ t('应用ID') }}:
        </div>
        <div>{{ data.system_id }}</div>
      </div>
      <div class="item">
        <div class="item-title">
          {{ t('系统名称') }}:
        </div>
        <div>{{ data.name }}</div>
      </div>
      <div class="item">
        <div class="item-title">
          {{ t('管理员') }}:
        </div>
        <div class="item-value">
          <template v-if="!edits.managers">
            <edit-tag
              :data="data.managers"
              :max="5" />
            <audit-icon
              v-if="canEditSystem"
              class="edit-icon"
              type="edit-fill"
              @click="toggleEdit('managers')" />
          </template>
          <audit-user-selector
            v-else
            v-model="formData.managers"
            allow-create
            multiple
            @blur="handleBlur('managers')" />
        </div>
      </div>
      <div class="item">
        <div class="item-title">
          {{ t('系统域名') }}:
        </div>
        <div class="description-value">
          {{ data.system_url ||'--' }}
        </div>
      </div>
    </div>
    <div
      class="item"
      style="margin: 0">
      <div class="item-title">
        {{ t('描述') }}:
      </div>
      <div class="item-value">
        <template v-if="!edits.description">
          <span>{{ data.description || '--' }}</span>
          <audit-icon
            v-if="canEditSystem"
            class="edit-icon"
            type="edit-fill"
            @click="toggleEdit('description')" />
        </template>
        <bk-input
          v-else
          v-model="formData.description"
          @blur="handleBlur('description')" />
      </div>
    </div>
    <h3>{{ t('调用信息') }}</h3>
    <div class="item">
      <div class="item-title">
        {{ t('可访问客户端') }}:
      </div>
      <div
        v-for="item in data.clients"
        :key="item">
        {{ item }}
      </div>
    </div>
    <div class="item">
      <div class="item-title">
        {{ t('资源实例回调地址') }}:
      </div>
      <div class="item-value">
        <template v-if="!edits.callback_url">
          <span>{{ data.callback_url || '--' }}</span>
          <audit-icon
            v-if="canEditSystem"
            class="edit-icon"
            type="edit-fill"
            @click="toggleEdit('callback_url')" />
        </template>
        <bk-input
          v-else
          v-model="formData.callback_url"
          @blur="handleBlur('callback_url')" />
      </div>
    </div>
    <div class="item">
      <div class="item-title">
        {{ t('鉴权token') }}:
      </div>
      <div>
        {{ data.auth_token || '--' }}
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';

  import SystemModel from '@model/meta/system';

  import EditTag from '@components/edit-box/tag.vue';

  import useRequest from '@/hooks/use-request';

  interface Emits {
    (e: 'updateSystemDetail'): void;
  }

  interface Props {
    data: SystemModel
    canEditSystem: boolean;
  }

  type FormFieldType = {
    managers: string[];
    description: string;
    clients: string[];
    callback_url: string;
  };

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const edits = ref({
    managers: false,
    description: false,
    clients: false,
    callback_url: false,
  });

  const formData = ref<FormFieldType>({
    managers: [],
    description: '',
    clients: [],
    callback_url: '',
  });

  // 更新系统
  const {
    run: fetchSystemUpdate,
  } = useRequest(MetaManageService.fetchSystemUpdate, {
    defaultValue: [],
    onSuccess: () => {
      resetFormData();
      emits('updateSystemDetail');
    },
  });

  const resetFormData = () => {
    formData.value = {
      managers: [],
      description: '',
      clients: [],
      callback_url: '',
    };
  };

  const toggleEdit = (key:  keyof typeof edits.value) => {
    edits.value[key] = !edits.value[key];
    if (edits.value[key]) {
      formData.value[key] = props.data[key] as any;
    }
  };

  // 更新系统字段
  const handleBlur = (key: keyof typeof edits.value) => {
    toggleEdit(key);
    fetchSystemUpdate({
      system_id: props.data.system_id,
      [key]: formData.value[key],
    });
  };

</script>
<style scoped lang="postcss">
.system-basic-info {
  padding: 6px 14px;

  .item {
    display: flex;
    margin: 30px 0;
    font-size: 12px;
    line-height: 26px;
    color: #63656e;

    .item-title {
      width: 120px;
      margin-right: 12px;
      color: #979ba5;
      text-align: right;
    }

    .item-value {
      display: flex;
      align-items: center;
      flex: 1;

      .edit-icon {
        margin-left: 10px;
        cursor: pointer;
      }
    }
  }
}
</style>
