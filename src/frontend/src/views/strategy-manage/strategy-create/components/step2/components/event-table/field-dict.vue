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
    v-model:isShow="showFieldDict"
    show-footer
    show-footer-slot
    :title="t('字段值映射配置')"
    :width="640">
    <audit-form
      ref="tableFormRef"
      class="field-dict-sideslider"
      form-type="vertical"
      :model="formData">
      <bk-form-item
        error-display-type="tooltips"
        :label="t('映射来源')"
        label-width="0"
        property="source">
        <bk-radio-group
          v-model="formData.source"
          class="upload-source-radio">
          <bk-radio
            label="manual_entry">
            {{ t('手动录入') }}
          </bk-radio>
          <bk-radio
            v-bk-tooltips="t('功能开发中')"
            disabled
            label="http">
            {{ t('HTTP(S)接口') }}
          </bk-radio>
          <bk-radio
            v-bk-tooltips="t('功能开发中')"
            disabled
            label="data_sheet">
            {{ t('使用数据表') }}
          </bk-radio>
        </bk-radio-group>
      </bk-form-item>
      <div class="action-header">
        <div
          style="
            margin-bottom: 6px;
            font-size: 14px;
            color: #63656e;
          ">
          {{ t('导入数据') }}
          <span
            style="
              padding-left: 8px;
              margin-left: 8px;
              font-size: 12px;
              color: #979ba5;
              border-left: 1px solid #979ba5;
            ">{{ t('支持手动输入导入以及Excel导入，Excel表头必须包含“存储值”，“展示文本”') }}</span>
        </div>
        <div class="button-group">
          <div>
            <input
              ref="uploadRef"
              accept=".xlsx, .xls, .csv"
              class="file-input"
              style="display: none;"
              type="file"
              @change="handleFileChange">
            <template v-if="renderList.length <= 1 && renderList[0]?.key === '' && renderList[0]?.name === ''">
              <bk-button
                :loading="loading"
                style="width: 88px; margin-right: 8px;"
                @click="handleUpload">
                <audit-icon
                  style="margin-right: 4px;"
                  type="upload" />
                {{ t('导入数据') }}
              </bk-button>
            </template>
            <audit-popconfirm
              v-else
              :confirm-handler="() => handleUpload()"
              :content="t('已有配置数据，导入数据前将清空配置数据，请确认！')"
              :title="t('确认导入数据？')">
              <bk-button
                :loading="loading"
                style="width: 88px; margin-right: 8px;">
                <audit-icon
                  style="margin-right: 4px;"
                  type="upload" />
                {{ t('导入数据') }}
              </bk-button>
            </audit-popconfirm>
            <audit-popconfirm
              :confirm-handler="() => handleClear()"
              :content="t('清空操作无法撤回，请谨慎操作！')"
              :title="t('确认清空数据？')">
              <bk-button
                :disabled="renderList.length <= 1 && renderList[0]?.key === '' && renderList[0]?.name === ''"
                style="width: 88px;">
                <audit-icon
                  style="margin-right: 4px;"
                  type="delete" />
                {{ t('清空数据') }}
              </bk-button>
            </audit-popconfirm>
          </div>
          <bk-input
            v-model="searchKey"
            style="width: 240px;"
            type="search" />
        </div>
      </div>
      <div class="render-field">
        <div class="field-header-row">
          <div class="field-value is-required">
            {{ t('存储值') }}
          </div>
          <div class="field-value is-required">
            {{ t('展示文本') }}
          </div>
          <div class="field-operation" />
        </div>
        <template v-if="renderList.length">
          <template
            v-for="(item, index) in renderList"
            :key="`row_${index}`">
            <div class="field-row">
              <div class="field-value">
                <bk-form-item
                  error-display-type="tooltips"
                  label=""
                  label-width="0"
                  :property="`renderData[${index}].key`"
                  required
                  :rules="[
                    { message: '不能为空', trigger: 'change', validator: (value: string) => !!value},
                    { message: 'ID重复，请修改', trigger: 'change', validator: (value: string) => {
                      // 检查当前表单中是否有重复
                      const duplicatesInForm = formData.renderData.filter(
                        (item, idx) => item.key === value && idx !== index
                      );
                      if (duplicatesInForm.length > 0) {
                        return false;
                      }
                      return true;
                    }}
                  ]">
                  <bk-input
                    ref="fieldItemRef"
                    v-model="item.key" />
                </bk-form-item>
              </div>
              <div class="field-value">
                <bk-form-item
                  error-display-type="tooltips"
                  label=""
                  label-width="0"
                  :property="`renderData[${index}].name`"
                  required
                  :rules="[
                    { message: t('不能为空'), trigger: 'change', validator: (value: string) => !!value },
                  ]">
                  <bk-input
                    ref="fieldItemRef"
                    v-model="item.name" />
                </bk-form-item>
              </div>
              <div class="field-operation">
                <div class="icon-group">
                  <audit-icon
                    v-bk-tooltips="{
                      content: t('新增'),
                    }"
                    class="icon-item"
                    type="add-fill"
                    @click="handleAdd(index)" />
                  <audit-icon
                    v-bk-tooltips="{
                      content: formData.renderData.length > 1 ? t('删除') : t('至少保留一个'),
                    }"
                    class="icon-item"
                    :class="[formData.renderData.length <= 1 ? 'delete-icon-disabled' : '']"
                    type="reduce-fill"
                    @click="handleDelete(index)" />
                </div>
              </div>
            </div>
          </template>
        </template>
        <template v-else>
          <bk-exception
            scene="part"
            style="height: 280px;padding-top: 40px;"
            type="search-empty">
            <div>
              <div style="color: #63656e;">
                {{ t('搜索结果为空') }}
              </div>
              <div
                style="margin-top: 8px; color: #979ba5;">
                {{ t('可以尝试调整关键词') }} {{ t('或') }}
                <bk-button
                  text
                  theme="primary"
                  @click="handleClearSearch">
                  {{ t('清空搜索条件') }}
                </bk-button>
              </div>
            </div>
          </bk-exception>
        </template>
      </div>
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
  import { computed, nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import * as XLSX from 'xlsx';

  import useDebouncedRef from '@/hooks/use-debounced-ref';
  import useMessage from '@/hooks/use-message';
  import { encodeRegexp } from '@/utils/assist';

  interface Emits {
    (e: 'submit', data: Array<{
      key: string,
      name: string,
    }>): void;
  }

  interface Props {
    editData:  Array<{
      key: string,
      name: string,
    }>;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const { messageSuccess, messageError } = useMessage();

  const showFieldDict = defineModel<boolean>('showFieldDict', {
    required: true,
  });

  const searchKey = useDebouncedRef('');
  const isSearching = ref(false);
  const loading = ref(false);
  const uploadRef = ref();
  const tableFormRef = ref();

  const formData  = ref<{
    source: string,
    renderData: Array<{
      key: string,
      name: string,
    }>,
  }>({
    source: 'manual_entry',
    renderData: [{
      key: '',
      name: '',
    }],
  });

  const renderList = computed(() => formData.value.renderData.reduce((result, item) => {
    const reg = new RegExp(encodeRegexp(searchKey.value), 'i');
    if (reg.test(item.key) || reg.test(item.name) || (item.key === '' && item.name === '')) {
      result.push(item);
    }
    isSearching.value = true;
    return result;
  }, [] as Array<{
    key: string,
    name: string,
  }>));

  const handleClearSearch = () => {
    searchKey.value = '';
  };

  const handleAdd = (index: number) => {
    // 在对应index后添加新字段
    formData.value.renderData.splice(index + 1, 0, {
      key: '',
      name: '',
    });
    nextTick(() => {
      tableFormRef.value.clearValidate();
    });
  };

  const handleDelete = (index: number) => {
    // 只有一个不能再删除
    if (formData.value.renderData.length === 1) {
      return;
    }
    // 在对应index后删除字段
    formData.value.renderData.splice(index, 1);
  };

  const convertExcelData = (data: any[][]): { key: any; name: string }[] => {
    // 1. 获取表头行
    const headers = data[0];

    // 2. 确定"存储值"和"展示文本"的列索引
    const valueIndex = headers.indexOf('存储值');
    const textIndex = headers.indexOf('展示文本');

    // 3. 验证索引是否有效
    if (valueIndex === -1 || textIndex === -1) {
      const missingHeaders = [];
      if (valueIndex === -1) missingHeaders.push(t('存储值'));
      if (textIndex === -1) missingHeaders.push(t('展示文本'));
      throw new Error(`${t('缺少必要的表头')}: ${missingHeaders.join(', ')}`);
    }

    // 4. 处理数据行（跳过表头）
    return data.slice(1)
      .map(row => ({
        key: String(row[valueIndex]),
        name: String(row[textIndex]),
      }))
      .filter(item => !(item.key === '' && item.name === ''));
  };

  // 解析Excel文件
  const parseExcel = (file: File): Promise<Array<{
    key: string;
    name: string;
  }>> => new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = (e) => {
      try {
        const arrayBuffer = e.target?.result as ArrayBuffer | null;
        if (!arrayBuffer) {
          throw new Error(t('文件读取失败'));
        }
        const data = new Uint8Array(arrayBuffer);
        const workbook = XLSX.read(data, { type: 'array' });

        // 获取第一个工作表
        const firstSheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[firstSheetName];

        // 转换为二维数组 (保留空值)
        const jsonData = XLSX.utils.sheet_to_json(worksheet, {
          header: 1,       // 生成二维数组
          defval: '',       // 空单元格默认值
          blankrows: true,  // 保留空行
        });

        if (jsonData.length === 0) {
          throw new Error(t('Excel文件中没有数据'));
        }

        const result = convertExcelData(jsonData as any[][]);
        resolve(result);
      } catch (error) {
        reject(error);
      }
    };

    reader.onerror = error => reject(error);
    reader.readAsArrayBuffer(file);
  });

  const handleFileChange = async (e: any) => {
    const file = e.target.files[0];
    if (!file) return;

    try {
      loading.value = true;
      // 解析Excel数据
      formData.value.renderData = await parseExcel(file);
      messageSuccess(t('导入成功'));
    } catch (error) {
      messageError(`${t('Excel解析失败')}: ${error}`);
    } finally {
      loading.value = false;
      if (e.target) {
        e.target.value = '';
      }
    }
  };

  const handleUpload = async () => {
    uploadRef.value.click();
  };

  const handleClear = async () => {
    formData.value.renderData = [{
      key: '',
      name: '',
    }];
    await nextTick();
    tableFormRef.value.clearValidate();
  };

  const handleSubmit = () => {
    const tastQueue = [tableFormRef.value.validate()];

    Promise.all(tastQueue).then(() => {
      emit('submit', _.cloneDeep(formData.value.renderData));
      closeDialog();
    });
  };

  const closeDialog = () => {
    showFieldDict.value = false;
    formData.value.renderData = [{
      key: '',
      name: '',
    }];
  };

  watch(() => showFieldDict.value, (value) => {
    if (value && props.editData.length) {
      formData.value.renderData = _.cloneDeep(props.editData);
    } else {
      formData.value.renderData = [{
        key: '',
        name: '',
      }];
    }
  });
</script>
<style lang="postcss" scoped>
:deep(.field-dict-sideslider) {
  padding: 24px;

  .bk-form-item {
    .bk-form-label {
      font-size: 14px;
    }

    .upload-source-radio {
      .bk-radio-label {
        font-size: 12px;
      }
    }
  }

  .action-header {
    margin-bottom: 8px;

    .button-group {
      display: flex;
      margin-top: 14px;
      justify-content: space-between;
    }
  }
}

.render-field {
  display: flex;
  overflow: hidden;
  border: 1px solid #dcdee5;
  border-radius: 2px;
  user-select: none;
  flex-direction: column;
  flex: 1;

  .field-select {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    background: #fafbfd;
  }

  .field-operation {
    width: 170px;
    padding-left: 16px;
    background: #fafbfd;
    border-left: 1px solid #dcdee5;

    .icon-group {
      font-size: 16px;
      color: #979ba5;

      .icon-item {
        margin-right: 10px;
        cursor: pointer;

        &:hover:not(.delete-icon-disabled) {
          color: #4d4f56;
        }
      }

      .delete-icon-disabled {
        color: #dcdee5;
        cursor: not-allowed;
      }
    }
  }

  :deep(.field-value) {
    display: flex;
    flex: 1;
    overflow: hidden;
    border-left: 1px solid #dcdee5;
    align-items: center;

    .tips {
      line-height: 16px;
      cursor: pointer;
      border-bottom: 1px dashed #979ba5;
    }

    .bk-form-item.is-error {
      .bk-input--text {
        background-color: #ffebeb;
      }
    }

    .bk-form-item {
      width: 100%;
      margin-bottom: 0;

      .bk-input {
        height: 42px;
        border: none;
      }

      .bk-input.is-focused:not(.is-readonly) {
        border: 1px solid #3a84ff;
        outline: 0;
        box-shadow: 0 0 3px #a3c5fd;
      }

      .bk-form-error-tips {
        top: 12px
      }
    }
  }

  .field-header-row {
    display: flex;
    height: 42px;
    font-size: 12px;
    line-height: 40px;
    color: #313238;
    background: #f0f1f5;

    .field-value {
      padding-left: 8px;
    }

    .field-value.is-required {
      &::after {
        margin-left: 4px;
        color: red;
        content: '*';
      }
    }

    .field-select,
    .field-operation {
      background: #f0f1f5;
    }
  }

  .field-row {
    display: flex;
    overflow: hidden;
    font-size: 12px;
    line-height: 42px;
    color: #63656e;
    border-top: 1px solid #dcdee5;
  }
}
</style>
