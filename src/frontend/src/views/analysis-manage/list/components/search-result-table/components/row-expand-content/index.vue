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
    ref="rootRef"
    class="expand-content"
    :style="styles">
    <div class="flex">
      <render-info-block>
        <render-info-item :label="t('事件 ID')">
          {{ data.event_id || '--' }}
        </render-info-item>
        <render-info-item :label="t('请求 ID')">
          {{ data.request_id || '--' }}
          <router-link
            v-if="data.request_id"
            class="ml5"
            target="_blank"
            :to="{
              name: 'analysisManage',
              query: {
                request_id: data.request_id,
                start_time: datetime[0],
                end_time: datetime[1],
                searchType: 'value'
              }
            }">
            <audit-icon
              class="mr-18"
              type="jump-link" />
            {{ t('关联事件') }}
          </router-link>
        </render-info-item>
        <render-info-item :label="t('操作人')">
          {{ data.username || '--' }}
        </render-info-item>
        <render-info-item :label="t('资源类型')">
          {{ data.resource_type_id || '--' }}
        </render-info-item>
        <render-info-item :label="t('操作途径')">
          {{ data.access_type || '--' }}
        </render-info-item>
        <render-info-item :label="t('来源 IP')">
          {{ data.access_source_ip || '--' }}
        </render-info-item>
        <render-info-item :label="t('管理空间类型')">
          {{ data.scope_type || '--' }}
        </render-info-item>
        <render-info-item :label="t('开始时间')">
          {{ data.start_time || '--' }}
        </render-info-item>
      </render-info-block>
      <render-info-block>
        <render-info-item
          class="flex"
          :label="t('事件描述')">
          <span
            class="base-info-value flex">
            <span style="margin-right: auto;">
              {{ data.event_content || '--' }}
            </span>
          </span>
        </render-info-item>
        <render-info-item :label="t('来源系统')">
          <!-- {{ data.system_info.name || '--' }} ({{ data.system_id || '--' }}) -->
          {{ data.system_id || '--' }}
        </render-info-item>
        <render-info-item :label="t('操作事件名')">
          {{ data.action_id || '--' }}
        </render-info-item>
        <render-info-item :label="t('资源实例')">
          {{ data.instance_id || '--' }}
        </render-info-item>
        <render-info-item :label="t('操作结果')">
          {{ data.result_code || '--' }}
        </render-info-item>
        <render-info-item :label="t('客户端类型')">
          {{ data.access_user_agent || '--' }}
        </render-info-item>
        <render-info-item :label="t('管理空间ID')">
          {{ data.scope_id || '--' }}
        </render-info-item>
        <render-info-item :label="t('结束时间')">
          {{ data.end_time || '--' }}
        </render-info-item>
      </render-info-block>
      <div class="whole-log-btn">
        <log-box :data="data" />
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import dayjs from 'dayjs';
  import _ from 'lodash';
  import {
    onBeforeUnmount,
    onMounted,
    ref,
    shallowRef,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import {
    getParentByClass,
  } from '@utils/assist';

  import LogBox from './components/log-box/index.vue';
  import RenderInfoBlock from './components/render-info-block.vue';
  import RenderInfoItem from './components/render-info-item.vue';

  interface Props {
    data: Record<string, any>,
  }

  defineProps<Props>();

  const { t } = useI18n();

  const rootRef = ref();
  const styles = shallowRef({});
  const datetime = [
    dayjs(Date.now() - (86400000 * 30)).format('YYYY-MM-DD HH:mm:ss'),
    dayjs().format('YYYY-MM-DD HH:mm:ss'),
  ];
  const handlerPosition = _.throttle(() => {
    const parentEl = getParentByClass(rootRef.value, 'bk-table');
    if (parentEl) {
      const boxWidth = parentEl.getBoundingClientRect().width;
      styles.value = {
        position: 'sticky',
        left: 0,
        width: `${boxWidth - 10}px`,
      };
    }
  }, 30);

  onMounted(() => {
    handlerPosition();

    const observer = new MutationObserver(() => {
      handlerPosition();
    });
    observer.observe(document.querySelector('body') as Node, {
      subtree: true,
      childList: true,
      attributes: true,
      characterData: true,
    });

    window.addEventListener('resize', handlerPosition);
    onBeforeUnmount(() => {
      observer.takeRecords();
      observer.disconnect();
      window.removeEventListener('resize', handlerPosition);
    });
  });
</script>
<style lang="postcss" scoped>
  .expand-content {
    position: relative;
    padding: 10px 0;
    background-color: #fafbfd;

    .flex {
      display: flex;
    }

    .content-block {
      padding: 5px;
    }

    .whole-log-btn {
      position: absolute;
      top: 10px;
      right: 20px;
    }
  }
</style>
