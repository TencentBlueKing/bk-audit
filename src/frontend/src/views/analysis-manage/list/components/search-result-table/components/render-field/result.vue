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
  <desc-popover
    :width="345"
    @after-show="handleAfterShow">
    <render-field-text>
      {{ data.result_code }}
    </render-field-text>
    <template #content>
      <div class="flex  hover-table">
        <table class="hover-table-content">
          <tr
            v-for="(item, index) in colData"
            :key="index">
            <td
              class="hover-table-title"
              :style="{width: `${labelWidth}px`}">
              {{ t(item.key) }}
            </td>
            <td class="hover-table-value">
              <span v-if="item.type == 'link'">
                <a
                  class="cursor"
                  :href="item.value"
                  target="_blank">{{ item.value }}</a>
              </span>
              <span v-else-if="item.type == 'boolean'">
                <audit-icon
                  svg
                  :type="item.value?'normal':'abnormal'" />
                {{ item.value? '正常':'未部署' }}
              </span>
              <multiple-line-clamp
                :data=" item.value " />
            </td>
          </tr>
        </table>
      </div>
    </template>
  </desc-popover>
</template>
<script setup lang="tsx">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MultipleLineClamp from '@components/multiple-line-clamp/index.vue';

  import DescPopover from './components/desc-popover.vue';
  import RenderFieldText from './components/field-text.vue';

  interface Props{
    data: Record<string, any>;
  }
  const props = defineProps<Props>();
  interface IResult {
    id: string;
    key:string;
    value:string;
    type?: string,
  }
  const { t, locale } = useI18n();
  const labelWidth = computed(() => (locale.value === 'en-US' ? 150 : 84));

  // eslint-disable-next-line vue/no-setup-props-destructure
  const initData = [
    {
      id: 'result_code',
      key: '结果(code)',
      value: props.data.result_code,
    },
    {
      id: 'result_content',
      key: '结果描述',
      value: props.data.result_content,
    },
  ];
  const colData = ref<Array<IResult>>();
  const handleAfterShow = () => {
    colData.value = initData;
  };
</script>
