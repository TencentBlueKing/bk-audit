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
  <div>
    <bk-form-item
      class="is-required"
      :label="t('采集目标')"
      property="target_nodes">
      <!-- <AuthComponent
        v-if="data.bk_biz_id"
        action-id="create_collection_v2_bk_log"
        :resource="data.bk_biz_id">
        <IpSelector
          :biz-id="data.bk_biz_id"
          :model-value="formData.target_nodes"
          :type="formData.target_node_type"
          @change="handleIPChange" />
      </AuthComponent>
      <IpSelector v-else /> -->
      <ip-selector
        :biz-id="data.bk_biz_id"
        :model-value="data.target_nodes"
        :space-type-id="spaceTypeId"
        :type="formData.target_node_type"
        @change="handleIPChange" />
    </bk-form-item>
    <bk-form-item
      :label="t('采集路径')"
      property="params.paths"
      required>
      <path-stack
        v-model="formData.params.paths"
        @update:model-value="handeUpdate" />
    </bk-form-item>
    <bk-form-item
      class="is-required"
      :label="t('日志字符集')"
      property="data_encoding">
      <bk-loading
        class="form-item-common"
        :loading="isGlobalsLoading">
        <bk-select
          v-model="formData.data_encoding"
          :clearable="false"
          filterable
          :no-match-text="t('无匹配数据')"
          :placeholder="t('请选择日志字符集')"
          @update:model-value="handeUpdate">
          <bk-option
            v-for="item in globalsData.data_encoding"
            :key="item.id"
            :label="item.name"
            :value="item.id" />
        </bk-select>
      </bk-loading>
    </bk-form-item>
  </div>
</template>
<script setup lang="ts">
  import {
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';

  import GlobalsModel from '@model/meta/globals';

  import useRequest from '@hooks/use-request';

  import type { TFormData } from '../../index.vue';
  import IpSelector from '../ip-selector.vue';
  import PathStack from '../path-stack.vue';

  interface Props {
    data: TFormData,
    spaceTypeId: string
  }
  interface Emits{
    (e:'change', value: Props['data'], isShow?: boolean): void
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const formData = ref({
    target_node_type: '',
    target_nodes: [] as Array<Record<string, any>>,
    data_encoding: '',
    params: {
      paths: [''],
      conditions: {
        type: 'match',
        match_type: '',
        match_content: '',
        separator: '',
        separator_filters: [
          {
            logic_op: 'AND',
            fieldindex: '',
            word: '',
          },
        ],
      },
    },
  });
  // 全局数据
  const {
    loading: isGlobalsLoading,
    data: globalsData,
  } = useRequest(MetaManageService.fetchGlobals, {
    defaultValue: new GlobalsModel(),
    manual: true,
    onSuccess(data) {
      if (!formData.value.data_encoding) {
        formData.value.data_encoding = data.data_encoding[0].id;
      }
      if (!formData.value.params.conditions.type) {
        formData.value.params.conditions.type = data.param_conditions_type[0].id;
      }
    },
  });

  const handleIPChange = ({ type, value }: { type: string, value: Array<unknown> }) => {
    // eslint-disable-next-line vue/no-mutating-props
    formData.value.target_node_type = type;
    // eslint-disable-next-line vue/no-mutating-props
    formData.value.target_nodes = value as never;
    emits('change', {
      ...props.data,
      ...formData.value,
    });
  };
  const handeUpdate = () => {
    emits('change', {
      ...props.data,
      ...formData.value,
    });
  };

  watch(() => props.data, (data) => {
    formData.value.target_node_type = data.target_node_type;
    formData.value.target_nodes = data.target_nodes;
    formData.value.data_encoding = data.data_encoding;
    formData.value.params = data.params;
  }, {
    deep: true,
  });
</script>
