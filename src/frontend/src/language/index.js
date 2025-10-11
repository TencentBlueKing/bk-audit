/*
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
*/
import Cookie from 'js-cookie';
import { createI18n } from 'vue-i18n';

import analysisEn from '@views/analysis-manage/language/en.js';
import analysisZh from '@views/analysis-manage/language/zh.js';
import eventEn from '@views/event-manage/language/en.js';
import eventZh from '@views/event-manage/language/zh.js';
import linkEn from '@views/link-data-manage/language/en.js';
import linkZh from '@views/link-data-manage/language/zh.js';
import noticeEn from '@views/notice-group/language/en.js';
import noticeZh from '@views/notice-group/language/zh.js';
import applicationEn from '@views/process-application-manage/language/en.js';
import applicationZh from '@views/process-application-manage/language/zh.js';
import riskEn from '@views/risk-manage/language/en.js';
import riskZh from '@views/risk-manage/language/zh.js';
import ruleEn from '@views/rule-manage/language/en.js';
import ruleZh from '@views/rule-manage/language/zh.js';
import storageEn from '@views/storage-manage/language/en.js';
import storageZh from '@views/storage-manage/language/zh.js';
import strategyEn from '@views/strategy-manage/language/en.js';
import strategyZh from '@views/strategy-manage/language/zh.js';
import systemEn from '@views/system-manage/language/en.js';
import systemZh from '@views/system-manage/language/zh.js';
import toolsEn from '@views/tools/language/en.js';
import toolsZh from '@views/tools/language/zh.js';

import allEn from '../../src/language/lang/en.js';
import allZh from '../../src/language/lang/zh.js';

let localeLanguage = 'zh-CN';
const bluekingLanguage = Cookie.get('blueking_language');
if (bluekingLanguage && bluekingLanguage.toLowerCase() === 'en') {
  localeLanguage = 'en-US';
}

const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: localeLanguage, // 初始化配置语言
  messages: {
    'zh-CN': {
      ...analysisZh.analysisManage,
      ...eventZh.eventManage,
      ...noticeZh.noticeManage,
      ...storageZh.storageManage,
      ...strategyZh.strategyManage,
      ...systemZh.systemManage,
      ...riskZh.riskManage,
      ...ruleZh.ruleManage,
      ...applicationZh.applicationManage,
      ...linkZh.linkDataManage,
      ...allZh,
      ...toolsZh.tools,
    },
    'en-US': {
      ...analysisEn.analysisManage,
      ...eventEn.eventManage,
      ...noticeEn.noticeManage,
      ...storageEn.storageManage,
      ...strategyEn.strategyManage,
      ...systemEn.systemManage,
      ...riskEn.riskManage,
      ...ruleEn.ruleManage,
      ...applicationEn.applicationManage,
      ...linkEn.linkDataManage,
      ...allEn,
      ...toolsEn.tools,
    },
  },
});

export default i18n;
