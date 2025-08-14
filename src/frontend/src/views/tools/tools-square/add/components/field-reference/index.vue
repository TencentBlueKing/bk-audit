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
    show-footer
    show-footer-slot
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
        property="tool.uid"
        required>
        <div style="display: flex;">
          <bk-cascader
            v-model="SelectTool"
            filterable
            :list="toolCascaderList"
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
            :disabled="SelectTool.length === 0"
            text
            theme="primary"
            @click="handleOpenTool">
            {{ t('去使用') }}
          </bk-button>
        </div>
      </bk-form-item>
      <!--         v-if="currenToolType !== 'bk_vision'"
 -->
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
                <bk-select
                  v-model="item.target_value_type"
                  class="bk-select"
                  :filterable="false"
                  :input-search="false"
                  @change="() => handleTypeChange(index)">
                  <template #trigger>
                    <bk-button style="width: 100px;">
                      {{ getDictName(item.target_value_type) }}
                    </bk-button>
                  </template>
                  <bk-option
                    v-for="(typeItem, typeIndex) in referenceTypeList"
                    :id="typeItem.id"
                    :key="typeIndex"
                    :name="typeItem.name" />
                </bk-select>
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
                <!-- <bk-input v-model="item.target_value" /> -->
                <!-- 不同前端类型 -->
                <form-item
                  ref="formItemRefs"
                  :data-config="toolsDetailData.config.input_variable.
                    find(i => i.raw_name === item.source_field) as SearchItem"
                  @change="(val:any) => handleFormItemChange(val, item)" />
              </div>
              <div style=" width: 75px;margin-left: 10px; color: #979ba5;">
                <span v-if="item.target_value_type==='field'"> {{ t('的值作为输入') }}</span>
              </div>
            </div>
          </div>
          <alternative-field
            :data="localOutputFields" />
        </div>
      </bk-form-item>
    </audit-form>
    <template #footer>
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
  </audit-sideslider>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolManageService from '@service/tool-manage';

  import ToolDetailModel from '@model/tool/tool-detail';

  import AlternativeField from './alternative-field.vue';
  import SelectMapValue from './select-map-value.vue';

  import useRequest from '@/hooks/use-request';
  import FormItem from '@/views/tools/tools-square/components/form-item.vue';

  interface SearchItem {
    // value: string;
    raw_name: string;
    required: boolean;
    description: string;
    display_name: string;
    field_category: string;
    choices:Array<{
      key: string,
      name: string
    }>;
  }

  interface LocalOutputFields {
    raw_name: string;
    display_name: string;
    description: string;
    [key: string]: string;
  }

  interface Emits {
    (e: 'submit', data: FormData): void;
    (e: 'openTool', value: ToolDetailModel): void;
  }

  interface Props {
    outputFields: Array<Record<string, any>>;
    newToolName: string;
    allToolsData: Array<ToolDetailModel>;
    tagData: Array<{
      tag_id: string
      tag_name: string;
      tool_count: number;
    }>;
  }

  interface ToolCascaderItem {
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
      target_field_type: string
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
  const currenToolType = ref('');

  const referenceTypeList = ref([{
    id: 'field',
    name: t('直接引用'),
  }, {
    id: 'fixed_value',
    name: t('固定值填充'),
  }]);

  const toolCascaderList = ref<Array<ToolCascaderItem>>([]);
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
      if (!formData.value.config) {
        formData.value.config = [];
      }

      // 获取当前配置中已存在的 source_field 集合
      const existingFields = new Set(formData.value.config.map(item => item.source_field));

      // 遍历工具详情数据中的输入变量
      toolsDetailData.value.config.input_variable.forEach((item) => {
        // 如果当前字段尚未存在于配置中，则添加新配置项
        if (!existingFields.has(item.raw_name)) {
          formData.value.config.push({
            source_field: item.raw_name,
            target_value_type: 'field',
            target_value: '',  // 初始化为空值
            target_field_type: '', // 初始化为空值
          });
        }
      });

      // 编辑时更新version
      if (toolsDetailData.value.version !== formData.value.tool.version) {
        formData.value.tool.version = toolsDetailData.value.version;
      }
    },
  });

  const resetFormData = () => {
    formData.value.tool.uid = '';
    formData.value.tool.version = 1;
    formData.value.config = [];
    toolsDetailData.value = new ToolDetailModel();
  };

  const handleSelectTool = (value: Array<string>) => {
    const tool = props.allToolsData.find(item => item.uid === value[1]);
    formData.value.config = [];
    if (tool) {
      currenToolType.value = tool.tool_type;
      formData.value.tool.uid = tool.uid;
      formData.value.tool.version = tool.version;
      fetchToolsDetail({
        uid: formData.value.tool.uid,
      });
      formRef.value.validate();
    } else {
      resetFormData();
      currenToolType.value = '';
    }
  };

  const handleRefresh = () => {
    // fetchAllTools();
  };

  const handleOpenTool = () => {
    const tool = props.allToolsData.find(item => item.uid ===  formData.value.tool.uid);
    if (tool) {
      emit('openTool', tool);
    }
  };

  const getDictName = (value: string) => {
    const selectItem = referenceTypeList.value.find(item => item.id === value);
    return selectItem ? selectItem.name : '';
  };

  const handleTypeChange = (index: number) => {
    formData.value.config[index].target_value = '';
  };

  const handleSelectMapValueChange = (index: number, value: Array<LocalOutputFields>) => {
    // 清空选择
    if (!value.length) {
      formData.value.config[index].target_value = '';
      if (formData.value.config[index].target_field_type) {
        formData.value.config[index].target_field_type = '';
      }
      return;
    }

    const [localOutputField]  = value;
    const configItem = formData.value.config[index];

    // 赋值结果字段
    configItem.target_value = localOutputField.raw_name || '';

    // 结果字段来源（策略配置中添加）
    if (localOutputField.target_field_type) {
      configItem.target_field_type = localOutputField.target_field_type;
    }
  };

  const handleFormItemChange = (val: any, item: FormData['config'][0]) => {
    // eslint-disable-next-line no-param-reassign
    item.target_value = val;
  };

  const handleSubmit = () => {
    const tastQueue = [formRef.value.validate()];

    Promise.all(tastQueue).then(() => {
      emit('submit', _.cloneDeep(formData.value));
      closeDialog();
    });
  };

  const closeDialog = () => {
    resetFormData();
    showEditSql.value = false;
    SelectTool.value = [];
  };

  const initLocalOutputFields = (val: Array<Record<string, any>>) => {
    localOutputFields.value = val.map(item => ({
      ...item,
      raw_name: item.raw_name,
      display_name: item.display_name,
      description: item.description,
    }));
  };

  const setFormData = (data: FormData) => {
    formData.value = _.cloneDeep(data);
    // 根据formData.value.uid.uid，在toolCascaderList中反查对应的级联数据id: [xxx, uid], xxx为父级id
    const tagItem = toolCascaderList.value.find(item => item.children.some(child => child.id === data.tool.uid));
    if (tagItem) {
      SelectTool.value = [tagItem.id, data.tool.uid];
    }
    // 编辑时重新获取详情
    if (formData.value.tool.uid) {
      fetchToolsDetail({
        uid: formData.value.tool.uid,
      });
    }
  };

  watch(() => props.outputFields, (val) => {
    initLocalOutputFields(val);
  }, {
    immediate: true,
  });

  // 监听formData.value.config中的target_value变化，相应更新localOutputFields
  watch(() => formData.value.config, (newConfig) => {
    if (!newConfig.length || !props.outputFields.length) return;

    // 重置localOutputFields
    initLocalOutputFields(props.outputFields);

    // 根据当前config中的target_value过滤localOutputFields
    newConfig.forEach((configItem) => {
      if (configItem.target_value_type === 'field' && configItem.target_value) {
        const outputField = props.outputFields.find(item => item.raw_name === configItem.target_value);
        if (outputField) {
          localOutputFields.value = localOutputFields.value.filter(item => item.raw_name !== outputField.raw_name);
        }
      }
    });
  }, {
    deep: true,
  });

  watch(() => props.allToolsData, (data) => {
    toolCascaderList.value  = props.tagData
      .map(item => ({
        id: item.tag_id,
        name: item.tag_name,
        children: item.tag_id === '-2'
          ? data
            .filter(tool => !tool.tags || tool.tags.length === 0)
            .map(({ uid, version, name }) => ({ id: uid, version, name }))
          : data
            .filter(tool => tool.tags && tool.tags.includes(item.tag_id))
            .map(({ uid, version, name }) => ({ id: uid, version, name })),
      }))
      .filter(item => item.children.length > 0);
  });

  defineExpose({
    setFormData: (data: FormData) => {
      setFormData(data);
    },
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

          &:hover {
            border-color: #979ba5;
          }
        }
      }
    }
  }
}
</style>
