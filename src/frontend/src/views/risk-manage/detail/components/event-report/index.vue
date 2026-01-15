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
  <div class="event-report">
    <render-info-block class="flex mt16">
      <render-info-item label="状态">
        {{ data.report?.status }}
      </render-info-item>
      <render-info-item label="更新人">
        {{ data.report?.update_at }}
      </render-info-item>
    </render-info-block>
    <render-info-block class="flex mt16">
      <render-info-item label="状态说明">
        {{ data.report?.status === 'auto' ? t('自动生成') : t('人工编辑') }}
      </render-info-item>
      <render-info-item label="更新时间">
        {{ data.report?.update_at }}
      </render-info-item>
    </render-info-block>

    <quill-editor
      ref="editorRef"
      v-model:content="content"
      content-type="html"
      disabled
      :options="options"
      theme="snow" />

    <bk-button
      class="event-report-edit-button"
      outline
      theme="primary"
      @click="handleEditReport">
      {{ t('编辑') }}
    </bk-button>

    <edit-event-report
      v-model:isShowEditEventReport="isShowEditEventReport"
      :report-content="content"
      :report-enabled="data.report_enabled"
      :status="data.report?.status" />
  </div>
</template>
<script setup lang="ts">
  import { computed, reactive, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type RiskManageModel from '@model/risk/risk';
  import type StrategyInfo from '@model/risk/strategy-info';

  import RenderInfoBlock from '@views/strategy-manage/list/components/render-info-block.vue';

  import { QuillEditor } from '@vueup/vue-quill';

  import RenderInfoItem from '../render-info-item.vue';

  import EditEventReport from './edit-event-report.vue';

  interface Props {
    data: RiskManageModel & StrategyInfo
  }

  const props = defineProps<Props>();
  const { t } = useI18n();

  const isShowEditEventReport = ref(false);

  // 事件调查报告内容
  const content = computed(() => props.data.report?.content);

  // 配置编辑器选项：不显示工具栏，只用于渲染
  const options = reactive({
    modules: {
      toolbar: false, // 隐藏工具栏
    },
    readOnly: true, // 只读模式
  });

  const handleEditReport = () => {
    isShowEditEventReport.value = true;
  };
</script>
<style lang="postcss" scoped>
.event-report {
  position: relative;
  padding: 10px;
  margin-bottom: 10px;

  .event-report-edit-button {
    position: absolute;
    top: 0;
    right: 0;
  }

  .render-info-item {
    min-width: 50%;
    align-items: flex-start;
  }

  :deep(.ql-disabled) {
    background-color: #fff !important;
  }
}
</style>
