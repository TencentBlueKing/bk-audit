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
  <div
    class="diff-text">
    <template
      v-if="data && data.extra_config && Object.keys(data.extra_config).length">
      <collapse-panel
        is-active
        :label="t('方案描述')"
        title-style="height: 28px;line-height: 28px;background: #F0F1F5;">
        <div class="diff-content">
          {{ data.extra_config.plan_document.content || '--' }}
        </div>
      </collapse-panel>
      <collapse-panel
        class="mt24"
        is-active
        :label="t('版本信息')"
        title-style="height: 28px;line-height: 28px;background: #F0F1F5;">
        <div class="diff-content">
          <p> {{ t('版本号') }} : {{ data.control_version ? `V${data.control_version}` : '--' }}</p>
          <div>
            <p
              v-if="data.extra_config.tags"
              style="display: flex; align-items: center;">
              <span style="margin-right: 4px;"> {{ t('发布标签') }} :  </span>
              <edit-tag
                :data="data.extra_config.tags" />
            </p>
            <p v-else>
              {{ t('发布标签') }} : --
            </p>
          </div>

          <p> {{ t('发布人') }} : {{ data.extra_config.developer?.join('、') || '--' }} </p>
          <p> {{ t('发布时间') }} : {{ data.extra_config.updated_at || '--' }} </p>
        </div>
      </collapse-panel>
      <collapse-panel
        class="mt24"
        is-active
        :label="t('方案输出')"
        title-style="height: 28px;line-height: 28px;background: #F0F1F5;">
        <div class="diff-content">
          <p
            v-for="item in data.output_config[0].fields"
            :key="item.field_index"
            class="field-output">
            <img
              class="field-type-icon"
              :src="getAssetsFile(`field-type/${item.field_type}.png`)">
            <span>
              {{ `${item.field_name}(${item.field_alias})` }}
            </span>
          </p>
        </div>
      </collapse-panel>
    </template>
    <div
      v-else
      class="exception-empty-part">
      <img
        src="@images/content-empty.png"
        style="width: 220px;">
      <p class="tip">
        {{ t('暂无方案说明') }}
      </p>
    </div>
  </div>
</template>

<script setup lang='ts'>
  import { useI18n } from 'vue-i18n';

  import EditTag from '@components/edit-box/tag.vue';

  import getAssetsFile from '@utils/getAssetsFile';

  import CollapsePanel from './aiops/components/components/collapse-panel.vue';

  interface Props{
    data: Record<string, any> | null
  }
  defineProps<Props>();
  const { t } = useI18n();

</script>
<style scoped lang="postcss">
.diff-text {
  height: 100%;
  min-width: 246px;
  margin-right: 24px;
  margin-left: 12px;
  color: #63656e;
  background: #f5f7fa;

  /* flex: 0 0 236px; */
  flex-shrink: 0;


  .exception-empty-part {
    display: flex;
    height: 60%;
    padding-top: 240px;
    margin-left: 20px;
    text-align: center;
    align-items: center;
    justify-content: center;
    flex-direction: column;

    >.tip {
      font-size: 12px;
      color: #63656e;
    }
  }

  .diff-content {
    padding: 8px 16px;
    line-height: 20px;

    .collapse-panel-title {
      height: 24px;
      background-color: red !important;
    }

    .field-output {
      display: flex;
      margin-bottom: 10px;
      align-items: center;

      .field-type-icon {
        width: 46px;
        margin-right: 6px;
      }

    }

  }


  .diff-text-title {
    margin-bottom: 12px;
    font-size: 14px;
    color: #313238;
  }
}
</style>
