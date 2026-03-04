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
  <bk-loading
    :loading="isGlobalsLoading"
    style="width: 800px;">
    <div class="log-filter-box">
      <bk-select
        :clearable="false"
        :model-value="localData.type"
        style="width: 160px;"
        @change="(value: string) => handleChange('type', value)">
        <bk-option
          v-for="item in globalsData.param_conditions_type"
          :key="item.id"
          :label="item.name"
          :value="item.id" />
      </bk-select>
      <bk-input
        class="ml8"
        :model-value="localData.match_content"
        :placeholder="t('请输入过滤内容')"
        style="width: 312px;"
        @input="(value: any) => handleChange('match_content', value as string)" />
      <bk-select
        class="ml8"
        :clearable="false"
        :model-value="localData.match_type"
        style="width: 240px;"
        @change="(value: string) => handleChange('match_type', value)">
        <bk-option
          v-for="item in globalsData.param_conditions_match"
          :key="item.id"
          :label="item.name"
          :value="item.id" />
      </bk-select>
    </div>
  </bk-loading>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';

  import GlobalsModel from '@model/meta/globals';

  import useRequest from '@hooks/use-request';

  interface Props {
    data: {
      type: string,
      match_type: string,
      match_content: string,
    }
  }

  const props = defineProps<Props>();

  const emits = defineEmits(['change']);
  const { t } = useI18n();

  const localData = ref<Props['data']>({
    type: '',
    match_type: '',
    match_content: '',
  });
  watch(() => props.data, () => {
    localData.value = _.cloneDeep(props.data);
  }, {
    immediate: true,
  });

  // 获取global数据
  const {
    loading: isGlobalsLoading,
    data: globalsData,
  } = useRequest(MetaManageService.fetchGlobals, {
    defaultValue: new GlobalsModel(),
    manual: true,
    onSuccess(data) {
      handleChange('match_type', data.param_conditions_match[0].id);
    },
  });

  const handleChange = (field: string, value: any) => {
    emits('change', {
      ...props.data,
      [field]: value,
    });
  };
</script>
<style lang="postcss" scoped>
  .log-filter-box {
    display: flex;
  }
</style>
