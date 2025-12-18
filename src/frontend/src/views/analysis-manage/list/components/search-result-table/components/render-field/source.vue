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
    :width="415"
    @after-show="handleAfterShow">
    <span
      class="tips cursor">
      {{ data.event_source_app }}
    </span>
    <template #content>
      <bk-loading
        :loading="loading">
        <div class="flex  hover-table">
          <table class="hover-table-content">
            <tr
              v-for="(item, index) in colData"
              :key="index">
              <td
                class="hover-table-title"
                style="width: 84px;">
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
                  v-else
                  :data="item.value" />
              </td>
            </tr>
          </table>
        </div>
      </bk-loading>
    </template>
  </desc-popover>
</template>
<script setup lang="tsx">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';

  import AppInfoModel from '@model/meta/app-info';

  import useRequest from '@hooks/use-request';

  import MultipleLineClamp from '@components/multiple-line-clamp/index.vue';

  import DescPopover from './components/desc-popover.vue';

  interface Props{
    data: Record<string, any>;
  }
  const props = defineProps<Props>();
  const { t } = useI18n();

  interface IResult {
    id: string;
    key:string;
    value:string;
    type?: string,
  }
  const initData = [
    {
      id: 'app_code',
      key: 'app_code',
      value: '',
    },
    {
      id: 'app_name',
      key: '应用名称',
      value: '',
    },
    {
      id: 'developerText',
      key: '应用负责人',
      value: '',
    },
    {
      id: 'status',
      key: '当前状态',
      value: '',
      type: 'boolean',
    },
    {
      id: 'system_url',
      key: '访问地址',
      value: '',
      type: 'link',
    },
  ];

  const colData = ref<Array<IResult>>(initData);
  const {
    loading,
    run: fetchAppInfo,
  // eslint-disable-next-line vue/no-setup-props-destructure
  } = useRequest(MetaManageService.fetchAppInfo, {
    defaultParams: {
      app_code: props.data.event_source_app,
    },
    defaultValue: new AppInfoModel(),
    onSuccess: (result) =>  {
      colData.value.forEach((item:IResult) => {
        // eslint-disable-next-line no-param-reassign
        item.value = result[item.id as keyof AppInfoModel] as string;
      });
    },
  });
  const handleAfterShow = () => {
    fetchAppInfo({
      app_code: props.data.event_source_app,
    });
  };
</script>
