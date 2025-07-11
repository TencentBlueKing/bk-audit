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
  <div class="tools-square">
    <div class="content-header">
      <bk-tab
        v-model:active="active"
        style="margin-left: 20px;"
        type="unborder-card">
        <bk-tab-panel
          v-for="item in panels"
          :key="item.name"
          :label="item.label"
          :name="item.name">
          <content
            ref="concentRef"
            @handle-checked-tags="handleCheckedTags"
            @handle-tags-enums="handleTagsEnums" />
        </bk-tab-panel>
      </bk-tab>
    </div>
    <div class="content-content">
      <div class="content-tag">
        {{ t('已选场景') }}:
        <span>{{ checkedTags.join('、') }}</span>
        <span
          v-show="checkedTags.length > 0"
          class="clear-tag"
          @click="handleClear">{{ t('清除已选') }}</span>
      </div>
      <div class="content-card">
        <content-card
          ref="ContentCardRef"
          :my-created="active === 'my'"
          :recent-used="active === 'history'"
          :tags="tagsList"
          :tags-enums="tagsEnums" />
      </div>
    </div>
  </div>
</template>

<script setup lang='ts'>
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ContentCard from './square-content/concent-card.vue';
  import Content from './square-content/index.vue';


  interface TagItem {
    tag_id: string
    tag_name: string
    tool_count: number
  }

  const { t } = useI18n();
  const active = ref('all');
  const concentRef = ref<InstanceType<typeof Content>[]>([]);
  const ContentCardRef = ref<InstanceType<typeof ContentCard>[]>([]);
  const panels = ref([
    { name: 'all', label: '全部' },
    { name: 'my', label: '我创建的' },
    { name: 'history', label: '最近使用的' },
  ]);
  const checkedTags = ref<Array<string>>([]);
  const tagsList = ref<Array<TagItem>>([]);
  const tagsEnums = ref<Array<TagItem>>([]);

  const handleCheckedTags = (tags: Array<TagItem>, tagsName: Array<string>) => {
    if (JSON.stringify(checkedTags.value) !== JSON.stringify(tagsName)) {
      checkedTags.value = tagsName;
      tagsList.value = tags;
    }
  };
  // 获取标签枚举
  const handleTagsEnums = (tags: Array<TagItem>) => {
    tagsEnums.value = tags;
  };
  // 清除已选
  const handleClear = () => {
    const activeIndex = panels.value.findIndex(p => p.name === active.value);
    if (activeIndex >= 0 && concentRef.value[activeIndex]) {
      concentRef.value[activeIndex].clearCheckedTags();
    } else {
      checkedTags.value = []; // 确保无论如何都能清空
    }
  };

  watch(() => active.value, (val) => {
    // 获取当前激活tab对应的组件实例
    const activeIndex = panels.value.findIndex(p => p.name === val);

    if (activeIndex >= 0 && concentRef.value[activeIndex]) {
      // 直接从子组件获取最新状态
      checkedTags.value = [...concentRef.value[activeIndex].checkedTags];
      tagsList.value = [...concentRef.value[activeIndex].checkedTagsList];
    } else {
      checkedTags.value = []; // 如果没有找到组件实例，清空选中状态
      tagsList.value = [];
    }
  }, { immediate: true });

</script>

<style scoped lang="postcss">
.tools-square {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  background-color: #fff;

  .content-header {
    top: 0;
    width: 100%;
    background-color: #fff;

    /deep/ .bk-tab--unborder-card .bk-tab-header {
      border-bottom: none;
      box-shadow: 0 3px 4px 0 #0000000a;
    }
  }

  .content-content {
    width: 100%;
    height: 100%;
    margin-top: 12px;

    .content-tag {
      margin-left: 20px;
      font-size: 12px;
      letter-spacing: 0;
      color: #979ba5;

      .clear-tag {
        margin-left: 20px;
        color: #3a84ff;
        cursor: pointer;
      }
    }
  }

  .content-card {
    margin-top: 12px;
    margin-left: 20px;
  }
}
</style>
