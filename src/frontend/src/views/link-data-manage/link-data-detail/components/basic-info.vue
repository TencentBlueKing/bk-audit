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
        <inline-tag
          :editable="tagEditable"
          :is-editing="isTagEditing"
          :saving="isTagSaving"
          :tag-list="tagList"
          :tags="(data.tags || []).map(item => strategyTagMap[item] || item)"
          @cancel="isTagEditing = false"
          @edit="isTagEditing = true"
          @save="handleTagSave" />
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
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';

  import InlineTag from '@components/edit-box/inline-tag.vue';

  import RenderInfoBlock from '@views/strategy-manage/list/components/render-info-block.vue';
  import RenderInfoItem from '@views/strategy-manage/list/components/render-info-item.vue';

  interface Props {
    data: LinkDataDetailModel,
    strategyTagMap: Record<string, string>,
    tagEditable?: boolean,
    tagList?: Array<{ tag_id: string | number, tag_name: string }>,
    tagSave?: (tags: string[]) => Promise<unknown>,
  }

  const props = withDefaults(defineProps<Props>(), {
    tagEditable: false,
    tagList: () => [],
    tagSave: undefined,
  });
  const { t } = useI18n();

  const isTagEditing = ref(false);
  const isTagSaving = ref(false);

  const handleTagSave = (tags: string[]) => {
    if (!props.tagSave) {
      return;
    }
    isTagSaving.value = true;
    props.tagSave(tags)
      .then(() => {
        isTagEditing.value = false;
      })
      .catch(() => undefined)
      .finally(() => {
        isTagSaving.value = false;
      });
  };
</script>
<style scoped lang="postcss">
.link-data-basic-info {
  padding: 0 25px;
}
</style>
