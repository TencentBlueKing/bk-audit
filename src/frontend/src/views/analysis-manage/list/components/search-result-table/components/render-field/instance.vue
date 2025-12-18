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
    ref="popoverRef"
    :width="poverWidth"
    @after-show="handleAfterShow">
    <render-field-text>
      {{ data.instance_name || '--' }} ({{ data.instance_id || '--' }})
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
              {{ item.key }}
            </td>
            <td class="hover-table-value">
              <!-- <multiple-line-clamp
                :data="item.value" /> -->
              <component
                :is="comMap[item.type as keyof typeof comMap]"
                :data="item.value"
                target="_blank"
                :to="item.value" />
            </td>
            <template v-if="length>4">
              <template v-if="colDataRight[index]">
                <td
                  class="hover-table-title  border-bottom"
                  style="width: 84px;">
                  {{ colDataRight[index].key }}
                </td>
                <td
                  class="hover-table-value border-bottom"
                  style="width: 36%;word-break: break-all;">
                  <!-- <multiple-line-clamp
                    :data="colDataRight[index].value" /> -->
                  <component
                    :is="comMap[colDataRight[index].type as keyof typeof comMap]"
                    :data="colDataRight[index].value"
                    target="_blank"
                    :to="colDataRight[index].value" />
                </td>
              </template>
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

  // import { useI18n } from 'vue-i18n';
  import MetaManageService from '@service/meta-manage';

  import type ResourceTypeSchemaModel from '@model/meta/resource-type-schema';

  import useRequest from '@hooks/use-request';

  import MultipleLineClamp from '@components/multiple-line-clamp/index.vue';

  import DescPopover from './components/desc-popover.vue';
  import RenderRouterLink from './components/field-link.vue';
  import RenderFieldText from './components/field-text.vue';

  interface Props{
    data: Record<string, any>;
  }
  const props = defineProps<Props>();

  interface IResults {
    key:string;
    value:string;
    type: string;
  }
  // const { t } = useI18n();

  const colDataLeft = ref<Array<IResults>>([]);
  const colDataRight = ref<Array<IResults>>([]);
  const length = ref(0);
  const popoverRef = ref();
  const poverWidth = ref(325);
  const updateAfterValues = ref();

  const comMap = {
    url: RenderRouterLink,
    other: MultipleLineClamp,
  };

  /**
   * 从接口获取中文字段名称
   */
  const {
    run: fetchResourceTypeSchemaSearch,
  // eslint-disable-next-line vue/no-setup-props-destructure
  } = useRequest(MetaManageService.fetchResourceTypeSchemaSearch, {
    defaultParams: {
      system_id: props.data.system_id,
      id: props.data.resource_type_id,
      resource_type_id: props.data.resource_type_id,
    },
    defaultValue: [],
    onSuccess: (data) => {
      if (data.length > 0) {
        const tmpSchemaResult = data.reduce((result, item) => ({
          // eslint-disable-next-line no-param-reassign
          ...result,
          [item.id]: item,
        }), {} as Record<string, ResourceTypeSchemaModel>);
        colDataLeft.value = colDataLeft.value.map((item: IResults, index) => updateItem(item, index, 'left', tmpSchemaResult));
        colDataRight.value = colDataRight.value.map((item: IResults, index) => updateItem(item, index, 'right', tmpSchemaResult));
      }
    },
  });

  const updateItem = (item: IResults, index: number, type: 'left' | 'right', tmpSchemaResult: Record<string, any>) => {
    const key = (tmpSchemaResult[item.key] && tmpSchemaResult[item.key].description) || item.key;
    const value = updateAfterValues.value[item.key];
    const itemType = tmpSchemaResult[item.key] && tmpSchemaResult[item.key].type;
    const typeResult = itemType === 'url' ? 'url' : 'other';

    return {
      key,
      value,
      type: typeResult,
    };
  };

  const handleAfterShow = async () => {
    /**
     * 弹框展示后处理数据
     */
    const updateFields = Object.keys(props.data.instance_data);
    updateAfterValues.value = props.data.instance_data;
    const data = (updateFields as Array<string>).map((item: string) => ({
      key: item,
      value: updateAfterValues.value[item],
      type: 'other',
    }));
    /**
     * 当有超过四条数据一行展示两个数据
     */
    length.value = data.length;
    colDataLeft.value = data;
    if (length.value > 4) {
      poverWidth.value = 588;
      const middleIndex = Math.ceil(data.length / 2);
      colDataLeft.value = data.splice(0, middleIndex);
      colDataRight.value = data.splice(-middleIndex);
    }
    fetchResourceTypeSchemaSearch({
      system_id: props.data.system_id,
      id: props.data.resource_type_id,
      resource_type_id: props.data.resource_type_id,
    });
  };
</script>
