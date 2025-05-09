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
  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="showDetail"
    :show-footer="false"
    :title="linkDataDetail.name || ''"
    :width="960">
    <bk-loading :loading="loading">
      <div class="link-data-detail">
        <bk-tab
          v-model:active="active"
          type="card-grid">
          <bk-tab-panel
            v-for="item in panels"
            :key="item.name"
            :label="item.label"
            :name="item.name">
            <scroll-faker>
              <component
                :is="renderCom"
                v-if="!loading"
                :data="linkDataDetail"
                :max-version-map="maxVersionMap"
                :strategy-tag-map="strategyTagMap"
                style="height: calc(100% - 50px)" />
            </scroll-faker>
          </bk-tab-panel>
        </bk-tab>
      </div>
    </bk-loading>
  </audit-sideslider>
</template>
<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import linkDataManageService from '@service/link-data-manage';
  import MetaManageService from '@service/meta-manage';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';

  import useRequest from '@hooks/use-request';

  import BasicInfo from './components/basic-info.vue';
  import LinkStrategy from './components/link-strategy.vue';

  interface Exposes {
    show(uid?:string):void
  }
  interface Props {
    maxVersionMap: Record<string, number>
  }

  defineProps<Props>();
  const { t } = useI18n();

  const showDetail = ref(false);
  const renderCom = computed(() => comMap[active.value]);
  const comMap: Record<string, any> = {
    basicInfo: BasicInfo,
    linkStrategy: LinkStrategy,
  };
  const strategyTagMap = ref<Record<string, string>>({});

  const panels = [
    { name: 'basicInfo', label: t('基础信息') },
    { name: 'linkStrategy', label: t('关联策略') },
  ];
  const active = ref<keyof typeof comMap>('basicInfo');

  // 获取标签列表
  useRequest(MetaManageService.fetchTags, {
    defaultParams: {
      page: 1,
      page_size: 1,
    },
    defaultValue: [],
    manual: true,
    onSuccess: (data) => {
      data.forEach((item) => {
        strategyTagMap.value[item.tag_id] = item.tag_name;
      });
    },
  });

  const {
    loading,
    data: linkDataDetail,
    run: fetchLinkDataDetail,
  } = useRequest(linkDataManageService.fetchLinkDataDetail, {
    defaultValue: new LinkDataDetailModel(),
  });

  defineExpose<Exposes>({
    show(uid: string, showLinkStrategy?: boolean) {
      showDetail.value = true;
      if (showLinkStrategy) {
        active.value = 'linkStrategy';
      }
      fetchLinkDataDetail({
        uid,
      });
    },
  });
</script>
<style scoped lang="postcss">
.link-data-detail {
  padding-top: 24px;
  background-color: #f5f7fa;

  :deep(.bk-tab) {
    height: calc(100vh - 100px);

    .bk-tab-header {
      margin-left: 24px;
    }

    .bk-tab-content {
      height: 100%;
    }
  }
}
</style>
