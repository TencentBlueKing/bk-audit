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
        property="selectTool"
        required>
        <div style="display: flex;">
          <bk-loading
            :loading="isToolLoading"
            style="width: 100%;">
            <bk-select
              v-model="formData.selectTool"
              class="bk-select"
              display-key="name"
              filterable
              id-key="id"
              multiple
              multiple-mode="tag"
              style="flex: 1;"
              @change="handleSelectTool">
              <template
                v-for="(item, index) in toolCascaderList"
                :key="index">
                <bk-option-group
                  collapsible
                  :label="item.name">
                  <bk-option
                    v-for="(child, childIndex) in item.children"
                    :id="child.id"
                    :key="childIndex"
                    :name="child.name" />
                </bk-option-group>
              </template>
              <template #extension>
                <div class="create-tool-group">
                  <router-link
                    class="create_tool-group"
                    target="_blank"
                    :to="{
                      name: 'toolsAdd',
                    }">
                    <audit-icon
                      style="font-size: 14px;color: #3a84ff;"
                      type="plus-circle" />
                    {{ t('新建工具') }}
                  </router-link>
                </div>
                <div
                  class="refresh"
                  @click="refreshToolList">
                  <audit-icon
                    v-if="isToolLoading"
                    class="rotate-loading"
                    svg
                    type="loading" />
                  <template v-else>
                    <audit-icon
                      type="refresh" />
                    {{ t('刷新') }}
                  </template>
                </div>
              </template>
            </bk-select>
          </bk-loading>
          <bk-button
            class="ml16"
            :disabled="formData.selectTool.length === 0"
            text
            theme="primary"
            @click="handleOpenTool">
            {{ t('去使用') }}
          </bk-button>
        </div>
      </bk-form-item>

      <!-- 多工具配置 -->
      <vuedraggable
        v-if="formData.tools.length > 0"
        item-key="tool.uid"
        :list="formData.tools">
        <template #item="{ element: toolConfig, index: toolIndex }">
          <div class="filed-wrapper">
            <bk-form-item
              error-display-type="tooltips"
              label=""
              label-width="0"
              :property="`tools.${toolIndex}.tool`"
              required>
              <audit-collapse-panel
                is-active>
                <template #label="{ isCollapseActive, handleClick }">
                  <div
                    class="field-title"
                    @click="handleClick">
                    <div style="margin-right: 10px;">
                      <audit-icon :type="isCollapseActive ? 'angle-fill-down' : 'angle-fill-rignt'" />
                    </div>
                    <div style="flex: 1">
                      <span style="font-weight: 700;">{{ getToolName(toolConfig.tool.uid) }}</span>
                      <span>{{ t('的输入字段') }}</span>
                    </div>
                    <div style="width: 38px;" />
                    <div style="flex: 1">
                      <span style="font-weight: 700;">{{ newToolName }}</span>
                      <span>{{ t('的结果字段') }}</span>
                    </div>
                  </div>
                  <div class="field-title-icon">
                    <audit-icon
                      v-bk-tooltips="{
                        content: t('拖动调整顺序'),
                      }"
                      class="field-title-icon-item"
                      style="margin: 0 10px;"
                      type="move" />
                    <audit-icon
                      class="field-title-icon-item"
                      type="delete"
                      @click="handleDeleteTool(toolConfig)" />
                  </div>
                </template>
                <div class="field-list">
                  <div
                    v-for="(item, index) in toolConfig.config"
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
                        @change="() => handleTypeChange(toolIndex, index)">
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
                      <bk-select
                        v-model="item.target_value"
                        class="bk-select"
                        filterable>
                        <bk-option
                          v-for="(outputField, OutputFieldIndex) in localOutputFields"
                          :id="outputField.raw_name"
                          :key="OutputFieldIndex"
                          :disabled="getUsedFields(toolIndex, index).has(outputField.raw_name)"
                          :name="outputField.display_name"
                          @change="(value: string) => handleSelectMapValueChange(toolIndex, index, value)">
                          {{ outputField.raw_name }}({{ outputField.display_name }})
                        </bk-option>
                      </bk-select>
                    </div>
                    <div
                      v-else
                      class="field-value"
                      style="border: none;">
                      <!-- 不同前端类型 -->
                      <form-item
                        v-if="toolInputVariableMap.get(toolConfig.tool.uid)?.has(item.source_field)"
                        :data-config="toolInputVariableMap
                          .get(toolConfig.tool.uid)?.get(item.source_field) as SearchItem"
                        origin-model
                        :target-value="item.target_value"
                        @change="(val:any) => handleFormItemChange(val, toolIndex, index)" />
                    </div>
                    <div style=" width: 75px;margin-left: 10px; color: #979ba5;">
                      <span v-if="item.target_value_type==='field'"> {{ t('的值作为输入') }}</span>
                    </div>
                  </div>
                </div>
              </audit-collapse-panel>
            </bk-form-item>
            <bk-form-item
              :label="t('下钻按钮名称')"
              label-width="160"
              property="tools.${toolIndex}.drill_name"
              style="padding-left: 20px;">
              <bk-input
                v-model="formData.tools[toolIndex].drill_name" />
            </bk-form-item>
          </div>
        </template>
      </vuedraggable>
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
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import Vuedraggable from 'vuedraggable';

  import ToolManageService from '@service/tool-manage';

  import ToolDetailModel from '@model/tool/tool-detail';

  // import AlternativeField from './alternative-field.vue';
  // import SelectMapValue from './select-map-value.vue';
  import AuditCollapsePanel from '@/components/audit-collapse-panel/index.vue';
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
    target_field_type?: string;
  }

  interface Emits {
    (e: 'submit', data: FormData['tools']): void;
    (e: 'openTool', value: string): void;
    (e: 'refreshToolList'): void;
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

  interface ToolConfig {
    tool: {
      uid: string;
      version: number;
    };
    config: Array<{
      source_field: string;
      target_value_type: string;
      target_value: string;
      target_field_type: string;
      description: string;
    }>;
    drill_name: string;
  }

  interface FormData {
    tools: Array<ToolConfig>;
    selectTool: Array<string>;
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
    name: t('固定值填充'),
  }]);

  const toolCascaderList = ref<Array<ToolCascaderItem>>([]);

  const isToolLoading = ref(true);

  const formData = ref<FormData>({
    tools: [],
    selectTool: [],
  });

  const toolsDetailData = ref<Map<string, ToolDetailModel>>(new Map());

  // 创建工具输入变量的映射，避免在模板中重复查找
  const toolInputVariableMap = computed(() => {
    const map = new Map<string, Map<string, SearchItem>>();
    toolsDetailData.value.forEach((toolDetail, uid) => {
      if (toolDetail.config?.input_variable) {
        const fieldMap = new Map<string, SearchItem>();
        toolDetail.config.input_variable.forEach((item) => {
          fieldMap.set(item.raw_name, item);
        });
        map.set(uid, fieldMap);
      }
    });
    return map;
  });

  // 计算已被其他配置项选中的字段（只在同一个工具配置中互斥）
  const getUsedFields = (currentToolIndex: number, currentConfigIndex: number) => {
    const usedFields = new Set<string>();
    // 只检查当前工具配置中的其他配置项
    const currentToolConfig = formData.value.tools[currentToolIndex];
    if (currentToolConfig) {
      currentToolConfig.config.forEach((configItem, configIdx) => {
        // 排除当前正在编辑的配置项
        if (configIdx === currentConfigIndex) {
          return;
        }
        // 如果配置项类型是 field 且有选中的值，则标记为已使用
        if (configItem.target_value_type === 'field' && configItem.target_value) {
          usedFields.add(configItem.target_value);
        }
      });
    }
    return usedFields;
  };

  const fetchToolsDetail = async (uid: string) => {
    try {
      const result = await ToolManageService.fetchToolsDetail({ uid });
      toolsDetailData.value.set(uid, result);
      return result;
    } catch (error) {
      return new ToolDetailModel();
    }
  };

  // 处理单个工具详情的对比逻辑
  const processToolDetailComparison = (toolConfig: ToolConfig, toolDetail: ToolDetailModel): ToolConfig => {
    if (!toolDetail.config?.input_variable) return toolConfig;

    // 获取当前配置中已存在的字段映射
    const existingConfigMap = new Map(toolConfig.config.map(item => [item.source_field, item]));

    // 按照工具详情中的 input_variable 顺序重新构建配置
    const orderedConfig: Array<{
      source_field: string;
      target_value_type: string;
      target_value: string;
      target_field_type: string;
      description: string;
    }> = [];

    toolDetail.config.input_variable.forEach((item) => {
      // 如果当前字段已存在于配置中，保留原有配置
      if (existingConfigMap.has(item.raw_name)) {
        orderedConfig.push(existingConfigMap.get(item.raw_name)!);
      } else {
        // 如果当前字段尚未存在于配置中，则添加新配置项
        orderedConfig.push({
          source_field: item.raw_name,
          target_value_type: 'field',
          target_value: '',  // 初始化为空值
          target_field_type: '', // 初始化为空值
          description: item.description,
        });
      }
    });

    // 返回更新后的配置，按照 detail 的顺序排列
    return {
      ...toolConfig,
      config: orderedConfig,
      tool: {
        ...toolConfig.tool,
        version: toolDetail.version !== toolConfig.tool.version ? toolDetail.version : toolConfig.tool.version,
      },
    };
  };

  const resetFormData = () => {
    formData.value.tools = [];
    formData.value.selectTool = [];
    toolsDetailData.value.clear();
  };

  const handleSelectTool = async (value: string[]) => {
    // 批量处理多个工具选择
    if (value.length > 0) {
      // 获取当前选择的工具 UID 列表
      const selectedToolUids = value;

      const currentToolUids = formData.value.tools.length > 0
        ? formData.value.tools.map(toolConfig => toolConfig.tool.uid)
        : [];

      // 找出需要添加的工具（新选择的工具）
      const toolsToAdd = selectedToolUids.filter(uid => !currentToolUids.includes(uid));

      // 找出需要移除的工具（取消选择的工具）
      const toolsToRemove = currentToolUids.filter(uid => !selectedToolUids.includes(uid));

      // 移除取消选择的工具
      if (toolsToRemove.length > 0) {
        formData.value.tools = formData.value.tools.filter(toolConfig => !toolsToRemove.includes(toolConfig.tool.uid));
        // 清理对应的工具详情数据
        toolsToRemove.forEach((uid) => {
          toolsDetailData.value.delete(uid);
        });
      }

      // 添加新选择的工具
      if (toolsToAdd.length > 0) {
        for (const toolUid of toolsToAdd) {
          const tool = props.allToolsData.find(item => item.uid === toolUid);
          if (tool) {
            const toolDetail = await fetchToolsDetail(tool.uid);

            // 创建工具配置
            const toolConfig: ToolConfig = {
              tool: {
                uid: tool.uid,
                version: tool.version,
              },
              config: [],
              drill_name: '',
            };

            // 为每个输入变量创建配置项
            if (toolDetail.config?.input_variable) {
              toolDetail.config.input_variable.forEach((item) => {
                toolConfig.config.push({
                  source_field: item.raw_name,
                  target_value_type: 'field',
                  target_value: '',
                  target_field_type: '',
                  description: item.description,
                });
              });
            }

            formData.value.tools.push(toolConfig);
          }
        }
      }

      formRef.value?.validate();
    } else {
      resetFormData();
    }
  };

  const refreshToolList = () => {
    isToolLoading.value = true;
    emit('refreshToolList');
  };

  // 获取工具名称
  const getToolName = (uid: string) => {
    const tool = props.allToolsData.find(item => item.uid === uid);
    return tool?.name || uid;
  };

  const handleOpenTool = () => {
    const uids = formData.value.tools.map(tool => tool.tool.uid).join('&');
    emit('openTool', uids);
  };

  const getDictName = (value: string) => {
    const selectItem = referenceTypeList.value.find(item => item.id === value);
    return selectItem ? selectItem.name : '';
  };

  const handleTypeChange = (toolIndex: number, configIndex: number) => {
    formData.value.tools[toolIndex].config[configIndex].target_value = '';
    if (formData.value.tools[toolIndex].config[configIndex].target_field_type) {
      formData.value.tools[toolIndex].config[configIndex].target_field_type = '';
    }
  };

  const handleSelectMapValueChange = (toolIndex: number, configIndex: number, value: string) => {
    const localOutputField = localOutputFields.value.find(item => item.raw_name === value);
    const configItem = formData.value.tools[toolIndex].config[configIndex];

    // 结果字段来源（策略配置中添加）
    if (localOutputField?.target_field_type) {
      configItem.target_field_type = localOutputField.target_field_type;
    }
  };

  const handleFormItemChange = (val: any, toolIndex: number, configIndex: number) => {
    formData.value.tools[toolIndex].config[configIndex].target_value = val;
  };

  // 删除工具配置
  const handleDeleteTool = (element: ToolConfig) => {
    const deleteTool = element.tool.uid;
    formData.value.tools = formData.value.tools.filter(tool => tool.tool.uid !== deleteTool);
    formData.value.selectTool = formData.value.tools.map(tool => tool.tool.uid);
    toolsDetailData.value.delete(deleteTool);
  };

  const handleSubmit = () => {
    const tastQueue = [formRef.value.validate()];

    Promise.all(tastQueue).then(() => {
      emit('submit', _.cloneDeep(formData.value.tools));
      closeDialog();
    });
  };

  const closeDialog = () => {
    resetFormData();
    showEditSql.value = false;
  };

  const setFormData = async (data: FormData['tools']) => {
    formData.value.tools = _.cloneDeep(data);

    if (formData.value.tools.length > 0) {
      formData.value.selectTool = formData.value.tools.map(tool => tool.tool.uid);

      // 使用 Promise.all 并发获取所有工具详情
      const toolDetailPromises = formData.value.tools
        .filter(toolConfig => toolConfig.tool.uid)
        .map(async (toolConfig, index) => {
          const toolDetail = await fetchToolsDetail(toolConfig.tool.uid);
          // 对每个工具详情执行对比逻辑，返回更新后的配置
          const updatedToolConfig = processToolDetailComparison(toolConfig, toolDetail);
          return { index, updatedToolConfig, toolDetail };
        });

      try {
        const results = await Promise.all(toolDetailPromises);
        // 更新 formData 中的工具配置
        results.forEach(({ index, updatedToolConfig }) => {
          formData.value.tools[index] = updatedToolConfig;
        });
      } catch (error) {
        console.error('获取工具详情时发生错误:', error);
      }
    }
  };

  watch(() => props.outputFields, (val: Array<Record<string, any>>) => {
    localOutputFields.value = val?.map(item => ({
      ...item,
      raw_name: item.raw_name,
      display_name: item.display_name,
      description: item.description,
    }));
  }, {
    immediate: true,
  });

  watch(() => props.allToolsData, (data) => {
    isToolLoading.value = false;
    // 先过滤出有权限数据
    const filteredData = data.filter(tool => tool.permission.use_tool || tool.permission.manage_tool);
    toolCascaderList.value  = props.tagData
      .map(item => ({
        id: item.tag_id,
        name: item.tag_name,
        children: item.tag_id === '-2'
          ? filteredData
            .filter(tool => !tool.tags || tool.tags.length === 0)
            .map(({ uid, version, name }) => ({ id: uid, version, name }))
          : filteredData
            .filter(tool => tool.tags && tool.tags.includes(item.tag_id))
            .map(({ uid, version, name }) => ({ id: uid, version, name })),
      }))
      .filter(item => item.children.length > 0);
  });

  defineExpose({
    setFormData: async (data: FormData['tools']) => {
      await setFormData(data);
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

    .filed-wrapper {
      position: relative;
      padding: 10px;
      margin-bottom: 16px;
      background-color: #f5f7fa;

      .field-list {
        display: flex;
        padding-left: 20px;
        background: #f5f7fa;
        flex-direction: column;
      }

      .field-title-icon {
        position: absolute;
        top: 0;
        right: 0;

        .field-title-icon-item {
          font-size: 13px;
          color: #c4c6cc;
          cursor: pointer;
        }
      }

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

          /* border: 1px solid #c4c6cc; */

          &:hover {
            border-color: #979ba5;
          }
        }
      }
    }
  }
}

.create-tool-group {
  padding: 0 12px;
  text-align: center;
  flex: 1;
}

.refresh {
  padding: 0 12px;
  color: #3a84ff;
  text-align: center;
  cursor: pointer;
  border-left: 1px solid #dcdee5;
  flex: 1;
}
</style>
