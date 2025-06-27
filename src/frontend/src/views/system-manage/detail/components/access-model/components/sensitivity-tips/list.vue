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
  <template v-if="[1, 2].includes(item.value)">
    <div
      style="display: flex; align-items: center;">
      <h4>{{ sensitivityTipsMap[item.value].title }}</h4>
      <span>{{ sensitivityTipsMap[item.value].content }}</span>
    </div>
  </template>
  <template v-else-if="[3, 4].includes(item.value)">
    <div>
      <h4>{{ t(sensitivityTipsMap[item.value].title) }}</h4>
      <ul>
        <li
          v-for="(tip, index) in sensitivityTipsMap[item.value].content"
          :key="index"
          class="tips-li">
          <div>
            <span class="outside" />
          </div>
          <span>{{ tip }}</span>
        </li>
      </ul>
    </div>
  </template>
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Props {
    item: {
      value: number;
      label: string;
    };
  }

  defineProps<Props>();
  const { t } = useI18n();

  const sensitivityTipsMap = ref<Record<number, {
    title: string;
    content: string[] | string;
  }>>({
    1: {
      title: t('一级：'),
      content: t('不敏感的信息，可完全开放查看'),
    },
    2: {
      title: t('二级：'),
      content: t('查询非敏感类数据，如日志记录查询'),
    },
    3: {
      title: t('三级：非核心操作功能'),
      content: [
        t('相对没那么敏感的操作功能，或者不会马上造成严重影响的，如修改脚本计划排期、修改文件名、修改白名单等'),
        t('查询/修改 L2 级别数据的功能'),
      ],
    },
    4: {
      title: t('四级：核心操作功能与官方认定的敏感功能'),
      content: [
        t('比较敏感的操作，会直接影响用户或外网正式环境的，如现网 DB 增删改、服务器关停等'),
        t('查询/修改 L4、L3 级别数据的功能'),
        t('各类收入及运营活动配置、经营分析、业务受理、封号解封、游戏生命周期、内容筛选投放等可直接或间接对游戏正式环境的用户数据进行修改的功能'),
        t('可直接或间接对用户资料进行修改的功能（包括但不限于通过应用系统、GM 工具/指令、接口、脚本、DB 等方式进行修改）'),
        t('能直接/间接（拿到配置后）登录到服务器的功能'),
        t('能对直接/间接管理、变更、影响现网服务的系统功能，或包含命令执行、SQL 执行等功能的系统功能'),
        t('涉及运维/安全类告警、处置、闭环的系统功能'),
        t('如业务收入数据查询、个人实名信息数据查询和处理等'),
      ],
    },
  });
</script>
<style lang="postcss">
.sensitivity-tips-pop {
  .tips-li {
    display: flex;
    margin: 10px 0;

    .outside {
      display: inline-block;
      width: 5px;
      height: 5px;
      margin: 0 10px;
      background: #979ba5;
      border-radius: 50%;
    }
  }
}
</style>
