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
    :width="558"
    @after-show="handleAfterShow">
    <render-field-text>
      {{ data.snapshot_action_info.name || '--' }} ({{ data.action_id || '--' }})
    </render-field-text>
    <template #content>
      <div class="flex hover-table">
        <table class="hover-table-content">
          <tr
            v-for="(item, index) in colDataLeft"
            :key="index">
            <td
              class="hover-table-title"
              style="width: 84px;">
              {{ t(item.key) }}
            </td>
            <td class="hover-table-value">
              <multiple-line-clamp
                :data="item.value" />
            </td>
            <template v-if="colDataRight[index]">
              <td
                class="hover-table-title  border-bottom"
                style="width: 84px;">
                {{ t(colDataRight[index].key) }}
              </td>
              <td
                class="hover-table-value border-bottom"
                style="width: 36%;word-break: break-all;">
                <multiple-line-clamp
                  :data=" colDataRight[index].value " />
              </td>
            </template>
          </tr>
        </table>
      </div>
    </template>
  </desc-popover>
</template>
<script setup lang="tsx">
  import {
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MultipleLineClamp from '@components/multiple-line-clamp/index.vue';

  import DescPopover from './components/desc-popover.vue';
  import RenderFieldText from './components/field-text.vue';

  const props = defineProps<Props>();
  interface IResult {
    key: string,
    value: string,
    id: string,
  }
  interface Props{
    data: Record<string, any>;
  }

  const { t } = useI18n();

  const initColDataLeft = () => [
    {
      id: 'action_id',
      key: '操作事件',
      value: '',
    },
    {
      id: 'description',
      key: '操作说明',
      value: '',
    },
    {
      id: 'type',
      key: '操作类型',
      value: '',
    },
    {
      id: 'sensitivity',
      key: '敏感等级',
      value: '',
    },
  ];
  const initColDataRight = () => [
    {
      id: 'name',
      key: '操作名称',
      value: '',
    },
    {
      id: 'updated_at',
      key: '同步时间',
      value: '',
    },
    {
      id: 'version',
      key: '操作版本',
      value: '',
    },
  ];
  const colDataLeft = ref<Array<IResult>>(initColDataLeft());
  const colDataRight = ref<Array<IResult>>(initColDataRight());
  // 监听值的变化
  const handleAfterShow = () => {
    colDataLeft.value.forEach((item:IResult) => {
      const value =  props.data.snapshot_action_info[item.id] as string;
      // eslint-disable-next-line no-param-reassign
      item.value = value !== '' && value !== undefined && value !== null ? value : '--';
    });
    colDataRight.value.forEach((item:IResult) => {
      const value =  props.data.snapshot_action_info[item.id] as string;
      // eslint-disable-next-line no-param-reassign
      item.value = value !== '' && value !== undefined && value !== null ? value : '--';
    });
  };
</script>
