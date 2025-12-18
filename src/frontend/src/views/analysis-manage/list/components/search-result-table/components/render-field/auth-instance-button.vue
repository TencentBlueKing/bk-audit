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
  <auth-button
    v-bk-tooltips="t('暂无查看权限')"
    :action-id="sensitiveData ? 'access_audit_sensitive_info' :''"
    :permission="false"
    :resource="sensitiveData ? sensitiveData.id : ''"
    text
    theme="primary">
    <render-field-text>
      {{ data.instance_name || '--' }} ({{ data.instance_id || '--' }})
    </render-field-text>
  </auth-button>
</template>

<script setup lang='ts'>
  import { watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';

  import type SearchModel from '@model/es-query/search';

  import useRequest from '@hooks/use-request';

  import RenderFieldText from './components/field-text.vue';

  interface Props{
    data: SearchModel;
  }
  const props = defineProps<Props>();
  const { t } = useI18n();
  // 获取敏感信息列表
  const {
    data: sensitiveData,
    run: fetchSensitiveList,
  } = useRequest(MetaManageService.fetchSensitiveList, {
    defaultValue: null,
  });
  watch(() => props.data, () => {
    if (!sensitiveData.value) {
      fetchSensitiveList({
        system_id: props.data.system_id,
        resource_type: 'sensitive_resource_object',
        resource_id: props.data.resource_type_id,
      });
    }
  }, {
    immediate: true,
  });
</script>
<!-- <style scoped>

</style> -->
