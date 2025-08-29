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
  <bk-dialog
    v-model:is-show="isShow"
    :quick-close="false"
    theme="primary"
    :title="t('SQL 变量占位符使用指引')"
    width="80%">
    <div
      class="content"
      @click="contentClick">
      <div class="content-left">
        <div class="item">
          <div class="title">
            {{ t('使用场景') }}
          </div>
          <div class="desc">
            {{ t('SQL 变量占位符用于工具的数据查询条件筛选，允许用户自定义输入或选择查询条件。') }}
          </div>
          <bk-divider style="width: 98%;" />
        </div>

        <div class="item">
          <div class="title">
            {{ t('核心规则') }}
          </div>
          <div class="item-child">
            <div class="item-child-tile">
              {{ t('1. 声明格式') }}
            </div>
            <div class="item-child-content">
              <span class="dot" />
              <span class="desc">{{ t('统一使用') }}<span class="desc-tag">:key</span> {{ t('形式声明变量') }}({{
                t('如') }}<span class="desc-tag">:user</span>)。</span>
            </div>
          </div>

          <div class="item-child">
            <div class="item-child-tile">
              {{ t('2. 变量复用') }}
            </div>
            <div class="item-child-content">
              <span class="dot" />
              <span class="desc">{{ t('同一变量名可在多处复用（如') }}
                <span class="desc-tag ">WHERE user = :id AND dept = :id</span>
                )。</span>
            </div>
          </div>


          <div class="item-child">
            <div class="item-child-tile">
              {{ t('3. 使用限制') }}
            </div>
            <div class="item-child-content">
              <span class="dot" />
              <span class="desc">
                {{ t('仅用于查询条件的值传递，禁止用于表名、列名、函数等结构（防SQL 注入）。') }}
              </span>
            </div>
          </div>

          <bk-divider style="width: 98%;" />
        </div>

        <div class="item">
          <div class="title">
            {{ t('前端组件适配写法') }}
          </div>
          <div class="component-table">
            <div class="table-header">
              <div class="header-cell">
                {{ t('前端组件类型') }}
              </div>
              <div class="header-cell cell-middle">
                {{ t('SQL写法示例') }}
              </div>
              <div class="header-cell">
                {{ t('说明') }}
              </div>
            </div>

            <div class="table-row">
              <div class="table-cell">
                {{ t('输入框/数字框') }}
              </div>
              <div class="table-cell cell-middle">
                <span class="desc-tag"> WHERE username = :name AND age = :age </span>
              </div>
              <div class="table-cell">
                {{ t('直接传递标量值') }}
              </div>
            </div>

            <div class="table-row">
              <div class="table-cell">
                {{ t('下拉列表/人员选择器') }}
              </div>
              <div class="table-cell cell-middle">
                <span class="desc-tag"> WHERE username IN :userlist </span>
              </div>
              <div class="table-cell">
                {{ t('变量自动转换为数组格式（如') }}<span class="desc-tag">{{ t("'张三'，'李四'") }}</span>)
              </div>
            </div>

            <div class="table-row">
              <div class="table-cell">
                {{ t('时间范围选择器') }}
              </div>
              <div class="table-cell cell-middle">
                <span class="desc-tag"> TIME_RANGE(dtField, :time_var, format) </span>
              </div>
              <div class="table-cell">
                {{ t('需使用') }} <span class="desc-tag span-color">TIME_RANGE</span>{{ t('函数') }} <span
                  class="function-link"
                  @click.stop="toFunLink('TIME_RANGE')">{{ t('查看详情') }}</span>
              </div>
            </div>

            <div class="table-row">
              <div class="table-cell">
                {{ t('非必填条件') }}
              </div>
              <div class="table-cell cell-middle">
                <span class="desc-tag"> SKIP_NULL_CLAUSE(field, operator, :var) </span>
              </div>
              <div class="table-cell">
                {{ t('需使用') }}<span class="desc-tag span-color"> SKIP_NULL_CLAUSE</span>{{ t('函数') }}
                <span
                  class="function-link"
                  @click.stop="toFunLink('SKIP_NULL_CLAUSE')">{{ t('查看详情') }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>


      <div class="content-right">
        <bk-divider
          direction="vertical"
          style="height: 100%;" />
        <div style=" width: 100%;margin-left: 2%;">
          <div class="title">
            {{ t('支持的函数') }}
          </div>
          <div
            ref="timeRangeRef"
            class="item"
            :style="style.TIME_RANGE">
            <div class="title">
              {{ t('一、') }}
              <span
                class="desc-tag span-color"
                :style="styleTag.TIME_RANGE">TIME_RANGE</span>
              {{ t('函数') }}
            </div>
            <div class="sql">
              <span class="sql-where"> WHERE </span>
              <p />
              <span class="sql-desc"><span class="span-color">TIME_RANGE</span> ( dtEventTime , <span
                class="span-color"> :time_range_var </span> , <span class="span-color2">'%Y-%m-%d
                %H:%M:%S'</span>) </span>
            </div>

            <div class="item-child-tile div-margin">
              {{ t('参数说明：') }}
            </div>
            <div class="item-child-content">
              <span class="dot" />
              <span class="desc">
                <span class="desc-tag">dtEventTime</span>
                {{ t('：时间字段名') }}
              </span>
              <p />
              <span class="dot" />
              <span class="desc">
                <span class="desc-tag">:time_range_var</span>
                {{ t('：前端传入的时间范围变量') }}
              </span>
              <p />
              <span class="dot" />
              <span class="desc">
                {{ t('时间格式，根据当前时间字段的内容设置与之匹配的时间格式，目前支持自定义格式与时间戳：') }}
              </span>
              <p />
              <span class="dot-samll" />
              <span class="desc">{{ t('自定义格式：') }}</span> <span class="desc-tag">'%Y-%m-%d %H:%M:%S'</span>
              <p />
              <span>
                <audit-icon
                  style="margin-left: 55px;font-size: 13px;color: #c4c6cc;"
                  type="right" />
                <span class="desc">{{ t('转换结果：') }}</span>
                <span class="desc-tag div-margin"> {{ t(`dtEventTime >='2025-07-30 00:00:00'AND dtEventTime
                  <'2025-07-30 23:59:59'`) }} </span>
              </span>
              <p />
              <span style="display: inline-block;margin-top: 10px;">
                <span class="dot-samll " />
                <span class="desc  div-margin">{{ t('时间戳当前支持三种精度的时间戳，') }}</span>
                <span class="desc-tag">'Timestamp(s)'/'Timestamp(ms)'/'Timestamp(us)'</span>
                <span class="desc">{{ t('请根据当前时间字段的精度选用') }}</span>
                <p />
                <span>
                  <audit-icon
                    style="margin-left: 55px;font-size: 13px;color: #c4c6cc;"
                    type="right" />
                  <span class="desc">{{ t('转换结果：') }}</span>
                  <span class="desc-tag div-margin"> {{ t(`dtEventTimestamp >= 1672502400008 AND
                      dtEventTimeStamp < 1672588800000`) }} </span>
                </span>
              </span>
              <p />
            </div>
            <bk-divider style="width: 98%;" />
          </div>

          <div
            ref="skipNullClauseRef"
            class="item"
            :style="style.SKIP_NULL_CLAUSE">
            <div class="title">
              {{ t('二、') }}
              <span
                class="desc-tag span-color"
                :style="styleTag.SKIP_NULL_CLAUSE">SKIP_NULL_CLAUSE</span>
              {{ t('函数') }}
            </div>
            <div class="sql">
              <span class="sql-where"> WHERE </span>
              <p />
              <span class="sql-desc"><span class="span-color">SKIP_NULL_CLAUSE</span> ( username , <span
                class="span-color2"> 'eq' </span> , <span>:username</span>) </span>
              <p />
              <span class="sql-desc">AND<span class="span-color"> SKIP_NULL_CLAUSE</span> ( age , <span
                class="span-color2"> 'eq' </span> , <span>:age</span>) </span>
            </div>
            <div class="item-child-tile div-margin">
              {{ t('参数说明：') }}
            </div>
            <div class="item-child-content">
              <span class="dot" />
              <span class="desc">
                <span class="desc-tag">username</span>
                {{ t('：条件字段') }}
              </span>
              <p />

              <span class="dot" />
              <span class="desc">
                <span class="desc-tag">'eq'</span>
                {{ t('：操作符（支持') }}<span class="desc-tag">eq/gt/gte/lt/lte/like/in</span>）
              </span>
              <p />
              <span class="dot" />
              <span class="desc">
                <span class="desc-tag">:username</span>
                {{ t('：变量名') }}
              </span>
              <p />
            </div>

            <div class="item-child-tile div-margin">
              {{ t('行为：') }}
            </div>
            <div class="item-child-content">
              <span class="desc">{{ t('若') }}
                <span class="desc-tag">:age</span>
                {{ t('未赋值') }}<audit-icon
                  style="margin-left: 5px;font-size: 13px;color: #c4c6cc;"
                  type="right" />
                {{ t('自动忽略') }}
                <span class="desc-tag">age</span>{{ t('条件，生成： ') }}
                <span class="desc-tag">WHERE username ='张三'</span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
    <template #footer />
  </bk-dialog>
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Exposes {
    openDialog: () => void,
  }

  const isShow = ref(false);
  const { t } = useI18n();
  const style = ref({
    TIME_RANGE: { backgroundColor: '' },
    SKIP_NULL_CLAUSE: { backgroundColor: '' },
  });
  const styleTag = ref({
    TIME_RANGE: { backgroundColor: '', color: '' },
    SKIP_NULL_CLAUSE: { backgroundColor: '', color: '' },
  });

  const timeRangeRef = ref<HTMLElement | null>(null);
  const skipNullClauseRef = ref<HTMLElement | null>(null);

  const contentClick = () => {
    styleTag.value.TIME_RANGE.backgroundColor = '';
    styleTag.value.TIME_RANGE.color = '';
    styleTag.value.SKIP_NULL_CLAUSE.backgroundColor = '';
    styleTag.value.SKIP_NULL_CLAUSE.color = '';
  };

  const toFunLink = (funName: string) => {
    contentClick();
    if (funName === 'TIME_RANGE') {
      style.value.TIME_RANGE.backgroundColor = 'rgba(245, 230, 200, 0.3)';
      styleTag.value.TIME_RANGE.backgroundColor = '#3A84FF';
      styleTag.value.TIME_RANGE.color = '#fff';
      timeRangeRef.value?.scrollIntoView({ behavior: 'smooth' });
    }
    if (funName === 'SKIP_NULL_CLAUSE') {
      style.value.SKIP_NULL_CLAUSE.backgroundColor = 'rgba(245, 230, 200, 0.3)';
      styleTag.value.SKIP_NULL_CLAUSE.backgroundColor = '#3A84FF';
      styleTag.value.SKIP_NULL_CLAUSE.color = '#fff';
      skipNullClauseRef.value?.scrollIntoView({ behavior: 'smooth' });
    }
    setTimeout(() => {
      style.value.TIME_RANGE.backgroundColor = '';
      style.value.SKIP_NULL_CLAUSE.backgroundColor = '';
    }, 500);
  };
  defineExpose<Exposes>({
    openDialog() {
      isShow.value = true;
    },
  });
</script>
<style scoped lang="postcss">
.content {
  display: flex;
  height: auto;
  max-height: 80vh;
  overflow: auto;
  justify-content: space-between;

  .content-left {
    width: 48%;
  }

  .content-right {
    display: flex;
    width: 52%;
    max-height: 80vh;
    overflow: auto;
  }
}

.title {
  padding-bottom: 10px;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0;
  color: #313238;
}

.item {
  .item-child {
    margin-left: 24px;
  }
}

.item-child-tile {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  color: #4d4f56;
}

.item-child-content {
  margin-left: 24px;

}

.div-margin {
  margin-top: 10px;
}

.dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  margin-top: 10px;
  margin-right: 10px;
  background-color: #3a84ff;
  border-radius: 50%
}

.dot-samll {
  display: inline-block;
  width: 5px;
  height: 5px;
  margin-top: 10px;
  margin-right: 10px;
  margin-left: 40px;
  background-color: #c4c6cc;
  border-radius: 50%
}

.desc {
  font-size: 12px;
  letter-spacing: 0;
  color: #4d4f56;
}

.desc-tag {
  display: inline-block;
  padding: 2px 4px;
  margin-right: 5px;
  margin-left: 5px;
  font-size: 12px;
  font-weight: 400;
  letter-spacing: 0;
  color: #7f879b;
  background: #f5f7fa;
  border-radius: 4px;

}

.span-color {
  color: #3a84ff;
}

.span-color2 {
  color: #a1e3ba;
}

.component-table {
  width: 98%;
  font-family: Arial, sans-serif;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.table-header {
  display: flex;
  font-weight: bold;
  background-color: #f5f5f5;
  border-bottom: 1px solid #dcdee5;
}

.table-row {
  display: flex;
  border-bottom: 1px solid #dcdee5;
}

.table-row:last-child {
  border-bottom: none;
}

.header-cell,
.table-cell {
  padding: 12px 15px;
  font-size: 12px;
  line-height: 20px;
  letter-spacing: 0;
  color: #4d4f56;
  word-break: break-word;
  flex: 1;
}

.cell-middle {
  border-right: 1px solid #dcdee5;
  border-left: 1px solid #dcdee5;

}

.function-link {
  color: #3a84ff;
  cursor: pointer;
}

.sql {
  width: 100%;
  padding: 10px 5px;
  font-size: 16px;
  line-height: 25px;
  letter-spacing: 0;
  color: #c4c6cc;
  background: #0f0503;
  border-radius: 8px;
}

.sql-where {
  margin-left: 16px;
}

.sql-desc {
  margin-left: 34px;
}
</style>
