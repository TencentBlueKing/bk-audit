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
  <div class="link-data-basic-info">
    <render-info-block class="mt16">
      <render-info-item :label="t('联表数据名称')">
        {{ data.name }}
      </render-info-item>
    </render-info-block>
    <render-info-block>
      <render-info-item :label="t('标签')">
        <span v-if="data.tags && data.tags.length">
          <span
            v-for="tagItem in data.tags"
            :key="tagItem"
            class="label-item"> {{ strategyTagMap[tagItem] }}</span>
        </span>
        <span v-else>
          --
        </span>
      </render-info-item>
    </render-info-block>
    <render-info-block>
      <render-info-item :label="t('最近更新人')">
        {{ data.updated_by }}
      </render-info-item>
    </render-info-block>
    <render-info-block>
      <render-info-item :label="t('最近更新时间')">
        {{ data.updated_at }}
      </render-info-item>
    </render-info-block>
    <render-info-block>
      <render-info-item :label="t('创建人')">
        {{ data.created_by }}
      </render-info-item>
    </render-info-block>
    <render-info-block>
      <render-info-item :label="t('创建时间')">
        {{ data.created_at }}
      </render-info-item>
    </render-info-block>
  </div>
</template>
<script setup lang="ts">
  import { useI18n } from 'vue-i18n';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';

  import RenderInfoBlock from '@views/strategy-manage/list/components/render-info-block.vue';
  import RenderInfoItem from '@views/strategy-manage/list/components/render-info-item.vue';

  interface Props {
    data: LinkDataDetailModel
    strategyTagMap: Record<string, string>
  }

  defineProps<Props>();
  const { t } = useI18n();
</script>
<style scoped lang="postcss">
.link-data-basic-info {
  padding: 0 25px;
}
</style>
