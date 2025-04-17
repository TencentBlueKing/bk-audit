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
    class="add-field-btn"
    @click="handleShowPop">
    <audit-icon
      type="add" />
  </div>
  <bk-popover
    ref="popoverRef"
    ext-cls="field-custom-popover"
    height="500"
    :is-show="isShow"
    theme="light"
    trigger="click"
    width="980"
    @after-hidden="handleAfterHidden">
    <template #content>
      <div class="add-field-pop-content">
        <div
          class="flex"
          style="flex: 1; min-height: 0;">
          <div class="field-pop-select">
            <!-- 搜索框 -->
            <div class="field-pop-select-search">
              <bk-input
                v-model="searchKey"
                behavior="simplicity"
                class="mb8">
                <template #prefix>
                  <span class="input-icon">
                    <audit-icon type="search1" />
                  </span>
                </template>
              </bk-input>
            </div>
            <div class="field-pop-select-list">
              <scroll-faker v-if="renderFieldList.length">
                <div
                  v-for="(item, index) in renderFieldList"
                  :key="index"
                  class="field-pop-select-item">
                  <div style="display: flex; align-items: center;">
                    <bk-checkbox-group>
                      <bk-checkbox
                        :checked="isEdit"
                        :disabled="isEdit"
                        @change="(value: boolean) => handleChange(value, item)">
                        <div style="display: flex; align-items: center">
                          <audit-icon
                            style="margin-right: 4px;font-size: 14px;"
                            svg
                            :type="item.spec_field_type" />
                          <span
                            v-if="configType === 'LinkTable'"
                            style=" color: #3a84ff;">{{ item.table }}.</span>
                          <span>{{ item.display_name.replace(/\(.*?\)/g, '').trim() }}</span>
                        </div>
                      </bk-checkbox>
                    </bk-checkbox-group>
                  </div>
                  <div>{{ item.raw_name }}</div>
                </div>
              </scroll-faker>
              <bk-exception
                v-else-if="isSearching"
                scene="part"
                style="height: 200px;padding-top: 40px;"
                type="search-empty">
                <div>
                  <div style="color: #63656e;">
                    {{ t('搜索结果为空') }}
                  </div>
                  <div style="margin-top: 8px; color: #979ba5;">
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
              <bk-exception
                v-else
                class="exception-part"
                scene="part"
                type="empty">
                {{ t('暂无数据') }}
              </bk-exception>
            </div>
          </div>
          <div class="field-pop-radio">
            <div style=" margin-bottom: 12px;font-weight: 700">
              {{ t('预期结果') }}
            </div>
            <table class="field-pop-radio-table">
              <thead>
                <tr>
                  <th>
                    <span>{{ t('字段名') }}</span>
                  </th>
                  <th>
                    <span
                      v-bk-tooltips="{
                        content: t('sql示例：`字段名` AS `显示名`')
                      }"
                      style="border-bottom: 1px dashed #979ba5;">
                      {{ t('显示名') }}
                    </span>
                  </th>
                  <th>
                    <span
                      v-bk-tooltips="{
                        content: t('指合并同类数据，计算总和、平均等统计值；同时选择多个字段时，可用聚合算法是最小公集。')
                      }"
                      style="border-bottom: 1px dashed #979ba5;">
                      {{ t('聚合算法') }}
                    </span>
                    <bk-popover
                      ref="commAggRef"
                      allow-html
                      boundary="parent"
                      content="#hidden_pop_content"
                      ext-cls="comm-agg-pop"
                      placement="bottom"
                      theme="light"
                      trigger="click"
                      width="150">
                      <audit-icon
                        v-bk-tooltips="{
                          content: t('批量设置聚合算法')
                        }"
                        style="margin-left: 4px;color: #3a84ff;"
                        type="edit-fill" />
                    </bk-popover>
                    <div style="display: none">
                      <div id="hidden_pop_content">
                        <div
                          v-for="(item, index) in commonAggs"
                          :key="index"
                          class="common-agg-item"
                          :class="[item.disabled ? 'is-disabled' : '']"
                          @click="handleCommonAggClick(item)">
                          {{ item.label }}
                        </div>
                      </div>
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody class="field-pop-radio-table-body">
                <tr
                  v-for="(item, index) in tableData"
                  :key="index">
                  <td style=" width: 150px;background-color: #fafbfd;">
                    <div style="padding-left: 8px;">
                      {{ item.raw_name }}
                    </div>
                  </td>
                  <td style=" width: 280px;background-color: #fff;">
                    <bk-input
                      v-model="item.display_name"
                      behavior="simplicity" />
                  </td>
                  <td style="background-color: #fff;">
                    <bk-select
                      v-model="item.aggregate"
                      :popover-options="{ boundary: 'parent'}">
                      <bk-option
                        v-for="aggItem in item.aggregateList"
                        :key="aggItem.value"
                        :label="aggItem.label"
                        :value="aggItem.value" />
                    </bk-select>
                  </td>
                </tr>
              </tbody>
            </table>
            <div
              v-if="!tableData.length"
              style="border: 1px solid #ddd; border-top: 0;">
              <bk-exception
                class="exception-part"
                scene="part"
                type="empty">
                {{ t('暂无数据') }}
              </bk-exception>
            </div>
          </div>
        </div>
        <div class="field-pop-bth">
          <bk-button
            class="mr8"
            :disabled="!tableData.length"
            size="small"
            theme="primary"
            @click="handleAddField">
            {{ t('确定') }}
          </bk-button>
          <bk-button
            size="small"
            @click="handleCancel">
            {{ t('取消') }}
          </bk-button>
        </div>
      </div>
    </template>
  </bk-popover>
</template>
<script setup lang="tsx">
  import _ from 'lodash';
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';

  import useDebouncedRef from '@hooks/use-debounced-ref';

  import { encodeRegexp } from '@utils/assist';

  // 扩展DatabaseTableFieldModel类型，添加aggregateList属性
  interface ExDatabaseTableFieldModel extends DatabaseTableFieldModel {
    aggregateList: Record<string, any>[];
  }


  interface Emits {
    (e: 'addExpectedResult', item: DatabaseTableFieldModel, index?: number): void;
  }
  interface Props {
    aggregateList: Array<Record<string, any>>
    expectedResultList: Array<DatabaseTableFieldModel>
    tableFields: Array<DatabaseTableFieldModel>
    configType: string,
  }
  interface Expose {
    handleEditShowPop: (index: number) => void,
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const isEdit = defineModel<boolean>({
    required: true,
  });
  const { t } = useI18n();

  const isShow = ref(false);
  const editIndex = ref(-1);
  const commAggRef = ref<{
    hide:() => void;
  } | null>(null);
  const localTableFields = ref<Array<ExDatabaseTableFieldModel>>([]);
  const formData = ref<DatabaseTableFieldModel>(new DatabaseTableFieldModel());
  const isSearching = ref(false);
  const tableData = ref<Array<ExDatabaseTableFieldModel>>([]);

  const searchKey = useDebouncedRef('');

  const renderFieldList = computed(() => localTableFields.value.reduce((result, item) => {
    const reg = new RegExp(encodeRegexp(searchKey.value), 'i');
    if (reg.test(item.raw_name) || reg.test(item.display_name)) {
      result.push(item);
    }
    isSearching.value = true;
    return result;
  }, [] as Array<ExDatabaseTableFieldModel>));

  const fieldAggregateMap = {
    string: ['COUNT', 'DISCOUNT'],
    text: ['COUNT', 'DISCOUNT'],
    double: ['SUM', 'AVG', 'MIN', 'MAX', 'COUNT'],
    float: ['SUM', 'AVG', 'MIN', 'MAX', 'COUNT'],
    int: ['SUM', 'AVG', 'MIN', 'MAX', 'COUNT'],
    long: ['SUM', 'AVG', 'MIN', 'MAX', 'COUNT'],
    timestamp: ['COUNT', 'MIX', 'MAX'],
  };

  // 计算公共聚合算法
  const commonAggs = computed(() => props.aggregateList
    .filter(agg => tableData.value
      .every(field => field.aggregateList
        .some(item => item.value === agg.value)))
    .map(agg => ({
      ...agg,
      disabled: tableData.value
        .some(field => field.aggregateList
          .find(item => item.value === agg.value)?.disabled),
    })) as Array<{
      label: string,
      value: string,
      disabled: boolean,
    }>);

  // 处理公共聚合算法点击
  const handleCommonAggClick = (item: Record<string, any>) => {
    if (!item.disabled) {
      tableData.value = tableData.value.map(field => ({
        ...field,
        aggregate: item.value,
      }));
    }
    commAggRef.value?.hide();
  };

  const handleClearSearch = () => {
    searchKey.value = '';
    isSearching.value = false;
  };

  const handleShowPop = () => {
    isEdit.value = false;
    isShow.value = !isShow.value;
  };

  const handleChange = (value: boolean, field: ExDatabaseTableFieldModel) => {
    const createAggregateList = () => {
      // 生成初始聚合列表
      const baseList = props.aggregateList.filter(item => (fieldAggregateMap[field.field_type as keyof typeof fieldAggregateMap].includes(item.value) || item.label === '不聚和'));

      // 检测重复聚合算法
      const existingAggregates = new Set(props.expectedResultList
        .filter(item => `${item.table}${item.raw_name}` === `${field.table}${field.raw_name}`)
        .map(item => item.aggregate));

      // 禁用已存在的选项
      return baseList.map<Record<string, any>>(item => ({
        ...item,
        disabled: existingAggregates.has(item.value),
      }));
    };

    if (value) {
      // 创建新对象避免参数修改
      const processedField = {
        ...field,
        aggregateList: createAggregateList(),
        aggregate: null,
      };

      // 设置初始选中值
      processedField.aggregate = processedField.aggregateList.find(item => !item.disabled)?.value;

      // 更新数据
      tableData.value.push({
        ...processedField,
        aggregateList: processedField.aggregateList,
      });
      formData.value = new DatabaseTableFieldModel();
    } else {
      tableData.value = tableData.value.filter(({ raw_name: rawName }) => rawName !== field.raw_name);
    }
  };

  const reset = () => {
    searchKey.value = '';
    isSearching.value = false;
    isEdit.value = false;
    editIndex.value = -1;
    formData.value = new DatabaseTableFieldModel();
    // 重置tableData
    tableData.value = [];
  };

  const handleAfterHidden = (value: { isShow: boolean}) => {
    isShow.value = value.isShow;
    reset();
  };

  const handleCancel = () => {
    isShow.value = false;
    reset();
  };

  const handleAddField = () => {
    const processItem = (item: ExDatabaseTableFieldModel) => {
      // 处理显示名称
      const withAggregate = `${item.display_name}${item.aggregate ? `_${item.aggregate}` : ''}`;

      // 统计重复显示名
      const displayNameCount = props.expectedResultList.reduce<Record<string, number>>(
        (acc, cur) => ({ ...acc, [cur.display_name]: (acc[cur.display_name] || 0) + 1 }),
        {},
      );

      // 生成最终显示名
      const finalDisplayName = displayNameCount[withAggregate] >= 1
        ? `${item.table}.${withAggregate}`
        : withAggregate;

      // 过滤不需要的属性
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { aggregateList, ...pureItem } = item;
      return { ...pureItem, display_name: finalDisplayName };
    };

    if (!isEdit.value) {
      // 处理新增模式
      const processedItems = tableData.value.map(processItem);
      processedItems.forEach(item => emits('addExpectedResult', item));
    } else {
      // 处理编辑模式
      const [currentItem] = tableData.value;
      if (currentItem) {
        const processedItem = processItem(currentItem);
        emits('addExpectedResult', processedItem, editIndex.value);
      }
    }

    handleCancel();
  };

  watch(() => props.tableFields, (data) => {
    localTableFields.value = data.map(item => ({
      ...item,
      aggregateList: _.cloneDeep(props.aggregateList),
    }));
    if (isEdit.value) {
      handleChange(true, localTableFields.value[0]);
    }
  }, {
    immediate: true,
  });

  defineExpose<Expose>({
    handleEditShowPop: (index: number) => {
      isShow.value = true;
      editIndex.value = index;
    },
  });
</script>
<style scoped lang="postcss">
  .add-field-btn {
    display: flex;
    width: 26px;
    height: 26px;
    margin: 3px 0;
    font-size: 16px;
    color: #3a84ff;
    cursor: pointer;
    background: #e1ecff;
    border-radius: 2px;
    justify-content: center;
    align-items: center;

    &:hover {
      color: #fff;
      background: #3a84ff;
    }
  }

  .add-field-pop-content {
    display: flex;
    height: 100%;
    box-shadow: 0 2px 6px #0000001a !important;
    flex-direction: column;

    .field-pop-select {
      display: flex;
      width: 350px;
      height: 100%;
      flex-direction: column;

      .input-icon {
        display: flex;
        padding-left: 8px;
        font-size: 16px;
        color: #c4c6cc;
        align-items: center;
        justify-content: center;
      }

      .field-pop-select-list {
        height: 100%;
        overflow: auto;

        .field-pop-select-item {
          display: flex;
          padding: 0 12px;
          line-height: 32px;
          justify-content: space-between;
          cursor: pointer;

          &:hover {
            background-color: #f5f7fa;
          }
        }

        .select-item-active {
          color: #3a84ff;
          background: #e1ecff;
        }

        .select-item-disabled {
          color: #c4c6cc;
          cursor: not-allowed;
        }
      }
    }

    .field-pop-radio {
      flex: 1;
      padding: 16px;
      background: #f5f7fa;

      :deep(.field-pop-radio-table) {
        width: 100%;
        border-collapse: collapse;

        th,
        td {
          padding: 8px;
          border: 1px solid #ddd;
        }

        th {
          text-align: left;
          background-color: #f0f1f5;
        }

        .field-pop-radio-table-body {
          th,
          td {
            padding: 0;
          }

          .bk-input--default {
            height: 42px;
            border: none;

            .bk-input--text {
              &:hover {
                border: 1px solid #a3c5fd;
              }

              &:focus {
                border: 1px solid #3a84ff;
              }
            }
          }
        }
      }
    }

    .field-pop-bth {
      display: flex;
      height: 42px;
      padding: 0 16px;
      background: #fafbfd;
      box-shadow: inset 0 1px #0000001f;
      align-items: center;
      justify-content: flex-end;
    }
  }
</style>
<style>
  .field-custom-popover {
    padding: 0 !important;
  }

  .comm-agg-pop {
    padding: 5px 0 !important;

    .common-agg-item {
      position: relative;
      display: flex;
      min-height: 32px;
      padding: 0 12px;
      overflow: hidden;
      color: #63656e;
      text-align: left;
      text-overflow: ellipsis;
      white-space: nowrap;
      cursor: pointer;
      user-select: none;
      align-items: center;

      &:hover {
        background-color: #f5f7fa;
      }
    }

    .is-disabled {
      color: #c4c6cc;
      cursor: not-allowed;
      background-color: transparent;
    }
  }

</style>
