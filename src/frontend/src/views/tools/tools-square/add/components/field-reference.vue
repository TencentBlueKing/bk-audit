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
    :show-footer="false"
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
    <smart-action
      class="field-reference-form"
      :offset-target="getSmartActionOffsetTarget">
      <audit-form
        ref="formRef"
        form-type="vertical"
        :model="formData">
        <bk-form-item
          error-display-type="tooltips"
          :label="t('选择工具')"
          label-width="160"
          property="tool.uid"
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
              <div class="field-title">
                <div style="flex: 1">
                  <span style="font-weight: 700;">{{ toolsDetailData.name }}</span>
                  <span>{{ t('的输入字段') }}</span>
                </div>
                <div style="width: 38px;" />
                <div style="flex: 1">
                  <span style="font-weight: 700;">{{ newToolName }}</span>
                  <span>{{ t('的结果字段') }}</span>
                </div>
              </div>
              <div
                v-for="(item, index) in formData.config"
                :key="index"
                class="field-item">
                <div class="field-key">
                  <bk-input
                    v-model="item.source_field"
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
                <div
                  v-if="item.target_value_type === 'field'"
                  class="field-value">
                  <select-map-value
                    ref="selectMapValueRef"
                    :alternative-field-list="localOutputFields"
                    :value="item.target_value"
                    @change="value => handleSelectMapValueChange(index, value)" />
                </div>
                <div
                  v-else
                  class="field-value"
                  style="border: none;">
                  <bk-input v-model="item.target_value" />
                </div>
                <div style="margin-left: 10px; color: #979ba5;">
                  {{ t('的值作为输入') }}
                </div>
              </div>
            </div>
            <alternative-field
              :data="localOutputFields" />
          </div>
        </bk-form-item>
      </audit-form>
      <template #action>
        <bk-button
          class="w88"
          theme="primary"
          @click="handleSubmit">
          {{ t('确定') }}
        </bk-button>
        <bk-button
          class="ml8"
          @click="closeDialog">
          {{ t('取消') }}
        </bk-button>
      </template>
    </smart-action>
  </audit-sideslider>
</template>
<script setup lang="ts">
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolManageService from '@service/tool-manage';

  import ToolDetailModel from '@model/tool/tool-detail';

  import AlternativeField from './alternative-field.vue';
  import SelectMapValue from './select-map-value.vue';

  import useRequest from '@/hooks/use-request';

  interface LocalOutputFields {
    raw_name: string;
    display_name: string;
    description: string;
  }

  interface Emits {
    (e: 'submit', data: FormData): void;
    (e: 'updateAllToolsData', allData: Array<ToolDetailModel>): void;
  }

  interface Props {
    outputFields: Array<Record<string, any>>;
    newToolName: string;
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
      source_field: string;
      target_value_type: string;
      target_value: string;
    }>;
  }

  const props =  defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const showEditSql = defineModel<boolean>('showFieldReference', {
    required: true,
  });
  const formRef = ref();
  const localOutputFields = ref<Array<LocalOutputFields>>([]);

  const referenceTypeList = ref([{
    id: 'field',
    name: t('直接引用'),
  }, {
    id: 'fixed_value',
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

  const getSmartActionOffsetTarget = () => document.querySelector('.bk-form-content');

  const {
    data: toolsDetailData,
    run: fetchToolsDetail,
  } = useRequest(ToolManageService.fetchToolsDetail, {
    defaultValue: new ToolDetailModel(),
    onSuccess: () => {
      formData.value.config = toolsDetailData.value.config.input_variable.map(item => ({
        source_field: item.raw_name,
        target_value_type: 'field',
        target_value: '',
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
    data: allToolsData,
    run: fetchAllTools,
  } = useRequest(ToolManageService.fetchAllTools, {
    defaultValue: [],
    onSuccess: () => {
      emit('updateAllToolsData', allToolsData.value);
      tagList.value = tagData.value
        .map(item => ({
          id: item.tag_id,
          name: item.tag_name,
          children: item.tag_id === '-2'
            ? allToolsData.value
              .filter(tool => !tool.tags || tool.tags.length === 0)
              .map(({ uid, version, name }) => ({ id: uid, version, name }))
            : allToolsData.value
              .filter(tool => tool.tags && tool.tags.includes(item.tag_id))
              .map(({ uid, version, name }) => ({ id: uid, version, name })),
        }))
        .filter(item => item.children.length > 0);
    },
  });

  const resetFormData = () => {
    formData.value.tool.uid = '';
    formData.value.tool.version = 1;
    formData.value.config = [];
  };

  const handleSelectTool = (value: Array<string>) => {
    const tool = allToolsData.value.find(item => item.uid === value[1]);
    if (tool) {
      formData.value.tool.uid = tool.uid;
      formData.value.tool.version = tool.version;
      fetchToolsDetail({
        uid: formData.value.tool.uid,
      });
    } else {
      resetFormData();
    }
  };

  const handleRefresh = () => {
    fetchAllTools();
  };

  const getDictName = (value: string) => {
    const selectItem = referenceTypeList.value.find(item => item.id === value);
    return selectItem ? selectItem.name : '';
  };

  const handleSelectMapValueChange = (index: number, value: Array<string>) => {
    const originConfigItem = JSON.parse(JSON.stringify(formData.value.config[index]));
    const [targetValue]  = value;
    const configItem = formData.value.config[index];
    // 选择删除localOutputFields对应选项，清空添加对应选项
    const outputField = value.length > 0
      ? props.outputFields.find(item => item.raw_name === targetValue)
      : props.outputFields.find(item => item.raw_name === originConfigItem.target_value);
    if (outputField && value.length === 0) {
      localOutputFields.value.unshift({
        raw_name: outputField.raw_name,
        display_name: outputField.display_name,
        description: outputField.description,
      });
    } else if (outputField && value.length > 0) {
      localOutputFields.value = localOutputFields.value.filter(item => item.raw_name !== outputField.raw_name);
    }
    // 赋值
    configItem.target_value = targetValue || '';
  };

  const handleSubmit = () => {
    const tastQueue = [formRef.value.validate()];

    Promise.all(tastQueue).then(() => {
      emit('submit', formData.value);
      closeDialog();
    });
  };

  const closeDialog = () => {
    resetFormData();
    showEditSql.value = false;
    SelectTool.value = [];
  };

  watch(() => props.outputFields, (val) => {
    localOutputFields.value = val.map(item => ({
      raw_name: item.raw_name,
      display_name: item.display_name,
      description: item.description,
    }));
  }, {
    immediate: true,
  });
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

      .field-title,
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
