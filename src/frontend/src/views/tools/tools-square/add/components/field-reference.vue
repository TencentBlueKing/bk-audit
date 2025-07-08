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
    v-model:isShow="showEditSql"
    class="field-reference-sideslider"
    show-header-slot
    :title="t('配置数据下钻')"
    width="1100">
    <template #header>
      <div class="flex mr24 custom-title">
        <span> {{ t('配置数据下钻') }}</span>
        <div class="line" />
        <span style="font-size: 12px; color: #979ba5;">
          {{ t('引用已配置工具，对当前字段进行解释或下钻；比如：字段为 username，可配置根据 oa 查询用户 hr 详细信息的工具，即可在字段位置直接下探查看。') }}
        </span>
      </div>
    </template>
    <audit-form
      ref="formRef"
      class="field-reference-form"
      form-type="vertical"
      :model="formData">
      <bk-form-item
        error-display-type="tooltips"
        :label="t('选择工具')"
        label-width="160"
        property="tool"
        required>
        <div style="display: flex;">
          <bk-cascader
            v-model="SelectTool"
            filterable
            :list="tagList"
            :show-complete-name="false"
            style="flex: 1;"
            trigger="hover"
            @change="handleSelectTool">
            <template #extension>
              <div class="view-mode">
                <auth-router-link
                  action-id="create_notice_group"
                  class="create_notice_group"
                  target="_blank"
                  :to="{
                    name: 'noticeGroupList',
                    query: {
                      create: true
                    }
                  }">
                  <audit-icon
                    style="font-size: 14px;color: #3a84ff;"
                    type="plus-circle" />
                  {{ t('新建工具') }}
                </auth-router-link>
                <span class="divider-wrapper">
                  <span
                    class="add-node"
                    @click="handleRefresh">
                    <plus class="icon-plus" />
                    {{ t('刷新') }}
                  </span>
                </span>
              </div>
            </template>
          </bk-cascader>
          <bk-button
            class="ml16"
            text
            theme="primary">
            {{ t('去使用') }}
          </bk-button>
        </div>
      </bk-form-item>
      <bk-form-item
        error-display-type="tooltips"
        :label="t('字段值引用')"
        label-width="160"
        property="tool"
        required>
        <div style="display: flex;">
          <div class="field-list">
            <div
              v-for="(item, index) in formData.config"
              :key="index"
              class="field-item">
              <div class="field-key">
                <bk-input
                  v-model="item.field_source"
                  disabled
                  style="flex: 1;" />
              </div>
              <div class="field-reference-type">
                <bk-dropdown trigger="click">
                  <bk-button style="width: 100px;">
                    {{ getDictName(item.target_value_type) }}
                  </bk-button>
                  <template #content>
                    <bk-dropdown-menu>
                      <bk-dropdown-item
                        v-for="TypeItem in referenceTypeList"
                        :key="TypeItem.id"
                        @click="() => item.target_value_type = TypeItem.id">
                        {{ TypeItem.name }}
                      </bk-dropdown-item>
                    </bk-dropdown-menu>
                  </template>
                </bk-dropdown>
              </div>
              <div class="field-value">
                <select-map-value
                  ref="selectMapValueRef"
                  :alternative-field-list="outputFields"
                  :data="item"
                  :value="item.source_field"
                  @change="value => handleSelectMapValueChange(index, value)" />
              </div>
              <div style="margin-left: 10px; color: #979ba5;">
                {{ t('的值作为输入') }}
              </div>
            </div>
          </div>
          <alternative-field
            :data="outputFields" />
        </div>
      </bk-form-item>
    </audit-form>
  </audit-sideslider>
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolManageService from '@service/tool-manage';

  import ToolDetailModel from '@model/tool/tool-detail';

  import AlternativeField from './alternative-field.vue';
  import SelectMapValue from './select-map-value.vue';

  import useRequest from '@/hooks/use-request';

  interface Props {
    outputFields: Array<{
      raw_name: string;
      display_name: string;
      description: string;
      field_down: string;
    }>;
  }

  interface TagItem {
    id: string;
    name: string;
    children: Array<{
      id: string;
      name: string;
      version: number;
    }>;
  }

  interface FormData {
    tool: {
      uid: string;
      version: number;
    };
    config: Array<{
      field_source: string;
      target_value_type: string;
      source_field: Record<string, any>[];
    }>;
  }

  defineProps<Props>();
  const { t } = useI18n();
  const showEditSql = defineModel<boolean>('showFieldReference', {
    required: true,
  });

  const referenceTypeList = ref([{
    id: 'reference',
    name: t('直接引用'),
  }, {
    id: 'default',
    name: t('使用默认值'),
  }]);

  const tagList = ref<Array<TagItem>>([]);
  const SelectTool = ref<Array<string>>([]);

  const formData = ref<FormData>({
    tool: {
      uid: '',
      version: 1,
    },
    config: [],
  });

  const {
    data: toolsDetailData,
    run: fetchToolsDetail,
  } = useRequest(ToolManageService.fetchToolsDetail, {
    defaultValue: new ToolDetailModel(),
    onSuccess: () => {
      formData.value.config = toolsDetailData.value.config.input_variable.map(item => ({
        field_source: item.raw_name,
        target_value_type: 'reference',
        source_field: [],
      }));
    },
  });

  // 获取标签列表
  const {
    data: tagData,
  } = useRequest(ToolManageService.fetchToolTags, {
    defaultValue: [],
    manual: true,
    onSuccess: () => {
      fetchAllTools();
    },
  });

  // 获取所有工具
  const {
    data: AllToolsData,
    run: fetchAllTools,
  } = useRequest(ToolManageService.fetchAllTools, {
    defaultValue: [],
    onSuccess: () => {
      tagList.value = tagData.value
        .map(item => ({
          id: item.tag_id,
          name: item.tag_name,
          children: item.tag_id === '-2'
            ? AllToolsData.value
              .filter(tool => !tool.tags || tool.tags.length === 0)
              .map(({ uid, version, name }) => ({ id: uid, version, name }))
            : AllToolsData.value
              .filter(tool => tool.tags && tool.tags.includes(item.tag_id))
              .map(({ uid, version, name }) => ({ id: uid, version, name })),
        }))
        .filter(item => item.children.length > 0);
      console.log(tagList.value);
    },
  });

  const handleSelectTool = (value: Array<string>) => {
    const tool = AllToolsData.value.find(item => item.uid === value[1]);
    if (tool) {
      formData.value.tool.uid = tool.uid;
      formData.value.tool.version = tool.version;
      fetchToolsDetail({
        uid: formData.value.tool.uid,
      });
    } else {
      formData.value.tool.uid = '';
      formData.value.tool.version = 1;
    }
  };

  const handleRefresh = () => {
    fetchAllTools();
  };

  const getDictName = (value: string) => {
    const selectItem = referenceTypeList.value.find(item => item.id === value);
    return selectItem ? selectItem.name : '';
  };

  const handleSelectMapValueChange = (index: number, value: Array<Record<string, any>>) => {
    const configItem = formData.value.config[index];
    configItem.source_field = [...value];
    console.log(configItem);
  };
</script>
<style scoped lang="postcss">
.field-reference-sideslider {
  .custom-title {
    align-items: center;

    .line {
      width: 1px;
      height: 12px;
      margin: auto 10px;
      background-color: #ccc;
    }
  }

  .field-reference-form {
    padding: 16px 40px;

    .field-list {
      flex: 1;
      display: flex;
      padding: 16px;
      background: #f5f7fa;
      flex-direction: column;

      .field-item {
        display: flex;
        align-items: center;
        margin: 5px 0;

        .field-reference-type {
          width: 100px;
          margin: 0 10px;
        }

        .field-key,
        .field-value {
          flex: 1 1 220px;
        }

        .field-value {
          color: #63656e;
          border: 1px solid #c4c6cc;
        }
      }
    }
  }
}
</style>
