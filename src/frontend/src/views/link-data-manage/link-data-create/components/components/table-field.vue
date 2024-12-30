<template>
  <div
    v-for="(field, index) in linkFields"
    :key="index"
    class="table-fields">
    <div class="left-fields">
      <bk-form-item
        class="no-label"
        label-width="0"
        property="left_field"
        style="margin-bottom: 8px;">
        <bk-select
          v-model="field.left_field"
          filterable
          :placeholder="t('请选择匹配字段')">
          <template #prefix>
            <span style="padding: 0 14px; color: #63656e; border-right: 1px solid #c4c6cc;">{{ t('字段') }}</span>
          </template>
          <bk-option
            v-for="item in leftFieldsList"
            :key="item.value"
            :label="item.label"
            :value="item.value" />
        </bk-select>
      </bk-form-item>
    </div>
    <div style="width: 46px; margin-bottom: 8px; text-align: center;">
      =
    </div>
    <div class="right-fields">
      <bk-form-item
        class="no-label"
        label-width="0"
        property="right_field"
        style="margin-bottom: 8px;">
        <bk-select
          v-model="field.right_field"
          filterable
          :placeholder="t('请选择匹配字段')">
          <template #prefix>
            <span style="padding: 0 14px; color: #63656e; border-right: 1px solid #c4c6cc;">{{ t('字段') }}</span>
          </template>
          <bk-option
            v-for="item in rightFieldsList"
            :key="item.value"
            :label="item.label"
            :value="item.value" />
        </bk-select>
      </bk-form-item>
    </div>
    <div class="icon-group">
      <audit-icon
        style="margin-right: 10px;"
        type="add-fill"
        @click="handleAdd" />
      <audit-icon
        v-if="index !== 0"
        type="reduce-fill"
        @click="() => handleDelete(index)" />
    </div>
  </div>
</template>
<script setup lang="ts">
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  interface FieldItem {
    field_type: string;
    label: string;
    value: string;
  }

  interface Props {
    leftTableRtId: string | Array<string>
    rightTableRtId: string | Array<string>
  }

  const props = defineProps<Props>();

  const { t } = useI18n();

  const linkFields = defineModel<Array<{
    left_field: string;
    right_field: string;
  }>>('linkFields');

  const leftFieldsList = ref<Array<FieldItem>>([]);
  const rightFieldsList = ref<Array<FieldItem>>([]);

  const getLeftTableFields = (id: string) => {
    StrategyManageService.fetchTableRtFields({
      table_id: id,
    }).then(data => leftFieldsList.value = data);
  };

  const getRightTableFields = (id: string) => {
    StrategyManageService.fetchTableRtFields({
      table_id: id,
    }).then(data => rightFieldsList.value = data);
  };

  // 新增
  const handleAdd = () => {
    linkFields.value?.push({
      left_field: '',
      right_field: '',
    });
  };

  // 删除
  const handleDelete = (index: number) => {
    linkFields.value?.splice(index, 1);
  };

  // 获取左边表字段
  watch(() => props.leftTableRtId, (data) => {
    if (data && data.length) {
      const id = Array.isArray(data) ? data[data.length - 1] : data;
      getLeftTableFields(id);
    } else {
      leftFieldsList.value = [];
    }
  });

  // 获取右边表字段
  watch(() => props.rightTableRtId, (data) => {
    if (data && data.length) {
      const id = Array.isArray(data) ? data[data.length - 1] : data;
      getRightTableFields(id);
    } else {
      rightFieldsList.value = [];
    }
  });
</script>
<style scoped lang="postcss">
.table-fields {
  display: grid;
  grid-template-columns: 1fr auto 1fr auto;
  gap: 8px;
  align-items: center;

  .icon-group {
    width: 36px;
    margin-bottom: 8px;
    color: #c4c6cc;
    cursor: pointer;
  }
}
</style>
