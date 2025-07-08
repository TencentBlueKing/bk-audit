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
  <div class="square-content">
    <div class="heard-tag">
      <div
        class="heard-left"
        :class="{ 'collapsed': isCollapsed }">
        <bk-tag
          v-for="tagItem in tags"
          :key="tagItem.tag_id"
          checkable
          :checked="checkedTags.includes(tagItem.tag_name)"
          :style="checkedTags.includes(tagItem.tag_name) ? tagStyle : checkedTagStyle"
          @change="(checked: any) => handleCheckChange(checked, tagItem)">
          {{ tagItem.tag_name }}
        </bk-tag>
      </div>
      <div
        class="heard-right"
        @click="toggleCollapse">
        <span v-if="!isCollapsed"> {{ t('收起') }} <audit-icon type="angle-double-up" /></span>
        <span v-else> {{ t('展开') }} <audit-icon type="angle-double-down" /></span>
      </div>
    </div>
  </div>
</template>

<script setup lang='ts'>
  import { onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolsSquare from '@service/tools-square';

  import useRequest from '@/hooks/use-request';

  interface TagItem {
    tag_id: string
    tag_name: string
    tool_count: number
  }
  interface Emits {
    (e: 'handle-checked-tags', tags: Array<TagItem>, tagsName: Array<string>): void;
    (e: 'handle-tags-enums', tags: Array<TagItem>): void;
  }
  interface Exposes {
    checkedTags: Array<string>;
    checkedTagsList: Array<TagItem>;
    clearCheckedTags: () => void;
  }
  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const isCollapsed = ref(true);
  const toggleCollapse = () => {
    isCollapsed.value = !isCollapsed.value;
  };
  const tags = ref<TagItem[]>([]);

  const checkedTags = ref<string[]>([]);
  const checkedTagsId = ref<string[]>([]);
  const checkedTagsList = ref<Array<TagItem>>([]);

  const tagStyle = ref({
    background: '#E1ECFF',
    color: '#1768EF',
  });

  const checkedTagStyle = ref({
    background: '#ffffff',
    color: '#4D4F56',
  });
  // 工具标签列表
  const {
    run: fetchToolsTagsList,
  } = useRequest(ToolsSquare.fetchToolsTagsList, {
    defaultValue: [],
    onSuccess: (data) => {
      tags.value = data;
      emit('handle-tags-enums', data);
    },
  });

  const handleCheckChange = (checked: any, tag: TagItem) => {
    if (checked) {
      checkedTags.value.push(tag.tag_name);
      checkedTagsList.value.push(tag);
      checkedTagsId.value.push(tag.tag_id);
    } else {
      checkedTags.value = checkedTags.value.filter(tagItem => tagItem !== tag.tag_name);
      checkedTagsList.value = checkedTagsList.value.filter(tagItem => tagItem.tag_id !== tag.tag_id);
      checkedTagsId.value = checkedTagsId.value.filter(tagItem => tagItem !== tag.tag_id);
    }
  };

  watch(() => checkedTags.value, (val: Array<string>) => {
    emit('handle-checked-tags', checkedTagsList.value, val);
  }, {
    deep: true,
    immediate: true,
  });

  onMounted(() => {
    fetchToolsTagsList();
  });

  defineExpose<Exposes>({
    get checkedTags() {
      return [...checkedTags.value]; // 返回副本避免直接修改
    },
    get checkedTagsList() {
      return [...checkedTagsList.value];
    },
    clearCheckedTags() {
      checkedTags.value = [];
      checkedTagsId.value = [];
      checkedTagsList.value = [];
      emit('handle-checked-tags', [], []);
    },
  });
</script>

<style scoped lang="postcss">
.square-content {
  .heard-tag {
    display: flex;
    justify-content: space-between;

    .heard-left {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 10px;

      &.collapsed {
        max-height: 30px;
        overflow: hidden;
      }
    }

    .heard-right {
      display: flex;
      width: 120px;
      color: #3a84ff;
      text-align: right;
      cursor: pointer;
      align-items: center;
      justify-content: center;

      &:hover {
        color: #1768ef;
      }
    }
  }

  :deep(.bk-tag) {
    &:hover {
      background-color: #f0f1f5 !important;
    }
  }
}
</style>
