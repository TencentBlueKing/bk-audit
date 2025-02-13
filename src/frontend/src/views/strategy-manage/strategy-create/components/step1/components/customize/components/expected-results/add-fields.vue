<template>
  <div class="add-field-btn">
    <audit-icon
      type="add"
      @click="handleShowPop" />
  </div>
  <bk-popover
    ext-cls="field-custom-popover"
    height="310"
    :is-show="isShow"
    theme="light"
    trigger="click"
    width="446"
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
                  :key="item.raw_name"
                  class="field-pop-select-item"
                  :class="[selectIndex === index ? 'select-item-active' : '']"
                  @click="() => handleSelectField(index, item)">
                  <div style="display: flex; align-items: center;">
                    <audit-icon
                      style="margin-right: 4px;font-size: 14px;"
                      svg
                      :type="item.field_type" />
                    <span
                      v-if="configType === 'LinkTable'"
                      style=" color: #3a84ff;">{{ item.table }}.</span>
                    <span>{{ item.display_name.replace(/\(.*?\)/g, '').trim() }}</span>
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
            <div style=" margin-bottom: 8px;color: #313238;">
              {{ t('聚合算法') }}
            </div>
            <bk-radio-group v-model="formData.aggregate">
              <div class="aggregate-list">
                <bk-radio
                  v-for="item in localAggregateList"
                  :key="item.value"
                  v-bk-tooltips="{
                    disabled: !item.disabled,
                    content: t('已添加')
                  }"
                  :disabled="item.disabled"
                  :label="item.value">
                  {{ item.label }}
                </bk-radio>
              </div>
            </bk-radio-group>
          </div>
        </div>
        <div class="field-pop-bth">
          <bk-button
            class="mr8"
            :disabled="!formData.raw_name"
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
<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';

  import useDebouncedRef from '@hooks/use-debounced-ref';

  import { encodeRegexp } from '@utils/assist';


  interface Emits {
    (e: 'addExpectedResult', item: DatabaseTableFieldModel): void;
  }
  interface Props {
    aggregateList: Array<Record<string, any>>
    expectedResultList: Array<DatabaseTableFieldModel>
    tableFields: Array<DatabaseTableFieldModel>
    configType: string,
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const isShow = ref(false);
  const selectIndex = ref(-1);
  const localAggregateList = ref<Array<Record<string, any>>>([]);
  const formData = ref<DatabaseTableFieldModel>(new DatabaseTableFieldModel());
  const isSearching = ref(false);

  const searchKey = useDebouncedRef('');

  const renderFieldList = computed(() => props.tableFields.reduce((result, item) => {
    const reg = new RegExp(encodeRegexp(searchKey.value), 'i');
    if (reg.test(item.raw_name) || reg.test(item.display_name)) {
      result.push(item);
    }
    isSearching.value = true;
    return result;
  }, [] as Array<DatabaseTableFieldModel>));

  const fieldAggregateMap = {
    string: ['COUNT', 'DISCOUNT'],
    text: ['COUNT', 'DISCOUNT'],
    double: ['SUM', 'AVG', 'MIN', 'MAX', 'COUNT'],
    float: ['SUM', 'AVG', 'MIN', 'MAX', 'COUNT'],
    int: ['SUM', 'AVG', 'MIN', 'MAX', 'COUNT'],
    long: ['SUM', 'AVG', 'MIN', 'MAX', 'COUNT'],
    timestamp: ['COUNT', 'MIX', 'MAX'],
  };

  const handleClearSearch = () => {
    searchKey.value = '';
    isSearching.value = false;
  };

  const handleShowPop = () => {
    isShow.value = true;
    // 重置可选
    localAggregateList.value = props.aggregateList.map(item => ({
      ...item,
      disabled: false,
    }));
  };

  const handleSelectField = (index: number, field: DatabaseTableFieldModel) => {
    selectIndex.value = index;
    // 每种类型字段拥有不同的聚合算法
    // eslint-disable-next-line max-len
    localAggregateList.value =  props.aggregateList.filter(item => fieldAggregateMap[field.field_type as keyof typeof fieldAggregateMap].includes(item.value) || item.label === '不聚和');
    // 同一字段不能重复添加同一聚合算法
    // eslint-disable-next-line max-len
    const hasAggregate = props.expectedResultList.filter(item => (item.table + item.raw_name) === (field.table +  field.raw_name));
    if (hasAggregate.length) {
      localAggregateList.value = localAggregateList.value.map((item) => {
        if (hasAggregate.some(element => element.aggregate === item.value)) {
          return {
            ...item,
            disabled: true,
          };
        }
        return item;
      });
    }
    formData.value = {
      ...field,
      aggregate: localAggregateList.value.find(item => !item.disabled)?.value, // 选择第一个可选项
    };
  };

  const handleAfterHidden = (value: { isShow: boolean}) => {
    isShow.value = value.isShow;
  };

  const handleCancel = () => {
    isShow.value = false;
    selectIndex.value = -1;
  };

  const handleAddField = () => {
    handleCancel();
    // 添加聚合算法后缀
    formData.value.display_name = `${formData.value.display_name}${formData.value.aggregate ? `_${formData.value.aggregate}` : ''}`;
    // 统计每个 display_name 的出现次数
    const displayNameCount = props.expectedResultList.reduce<Record<string, number>>((acc, item) => {
      acc[item.display_name] = (acc[item.display_name] || 0) + 1;
      return acc;
    }, {});
    // 重复字段添加table前缀
    formData.value.display_name = displayNameCount[formData.value.display_name] >= 1 ?  `${formData.value.table}.${formData.value.display_name}` :  formData.value.display_name,
    emits('addExpectedResult', formData.value);
    formData.value = new DatabaseTableFieldModel();
  };

  watch(() => props.aggregateList, (data) => {
    localAggregateList.value = data.map(item => ({
      ...item,
      disabled: false,
    }));
  }, {
    immediate: true,
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
      flex: 1;
      display: flex;
      flex-direction: column;
      height: 100%;

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
      width: 136px;
      padding: 8px 16px;
      background: #f5f7fa;

      .aggregate-list {
        flex: 1;
        display: flex;
        flex-direction: column;

        :deep(.bk-radio) {
          padding-bottom: 12px;
          margin-left: 0;
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
</style>
