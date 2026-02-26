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
    <!-- 左侧标签-->
    <render-label
      ref="renderLabelRef"
      active="-3"
      :final="3"
      :labels="strategyLabelList"
      :render-style="renderStyle"
      :total="total"
      :upgrade-total="upgradeTotal"
      @checked="handleChecked" />

    <!-- 右侧内容-->
    <div class="content-content">
      <div class="content-card">
        <content-card
          ref="ContentCardRef"
          :my-created="tagId === '-4'"
          :recent-used="tagId === '-5'"
          :tag-id="tagId"
          :tags-enums="tagsEnums"
          @change="handleChange" />
      </div>
    </div>
  </div>
</template>

<script setup lang='ts'>
  import { onMounted, ref } from 'vue';

  import ToolManageService from '@service/tool-manage';

  import RenderLabel from '@views/strategy-manage/list/components/render-label.vue';

  import ContentCard from './square-content/concent-card.vue';

  import useRequest from '@/hooks/use-request';

  interface TagItem {
    tag_id: string;
    tag_name: string;
    tool_count: number;
    icon?: string;
  }
  const renderLabelRef = ref();

  const ContentCardRef = ref<InstanceType<typeof ContentCard>>();


  const tagsEnums = ref<Array<TagItem>>([]);
  const upgradeTotal = ref(0);
  const total = ref(0);
  const tagId = ref('');
  const strategyLabelList = ref<Array<TagItem>>([]);
  const renderStyle = ref({
    backgroundColor: '#fff',
  });
  // 选中左侧label
  const handleChecked = (name: string) => {
    tagId.value = name;
    ContentCardRef.value?.getToolsList(name);
  };
  // 右边数据刷新
  const handleChange = () => {
    fetchToolsTagsList();
  };
  // 工具标签列表
  const {
    run: fetchToolsTagsList,
  } = useRequest(ToolManageService.fetchToolTags, {
    defaultValue: [],
    onSuccess: (data) => {
      const strategyList = data.map(item => ({ strategy_count: item.tool_count, ...item, icon: '' }));
      // 自定义strategyLabelList.value 的前三个icon
      const iconMap: Record<number, string> = {
        0: 'quanbu-xuanzhong',
        1: 'morentouxiang',
        2: 'shijian',
        3: 'weifenpei',
      };
      strategyLabelList.value = strategyList.map((item: any, index: number) => ({
        ...item,
        icon: iconMap[index] || 'tag',
      }));

      tagsEnums.value = strategyLabelList.value;
      renderLabelRef.value?.resetAll([]);
    },
  });


  onMounted(() => {
    fetchToolsTagsList();
  });
</script>

<style scoped lang="postcss">
.tools-square {
  position: absolute;
  display: flex;
  width: 100vw;
  height: 100%;
  background-color: #fff;
  inset: 0;

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
    margin-top: 0;
    background-color: #f5f7fa;

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
}
</style>

