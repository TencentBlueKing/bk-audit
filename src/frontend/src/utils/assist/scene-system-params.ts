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

/**
 * @desc 获取场景系统参数
 *
 */
export const getSceneSystemParams = ()  => {
  const scopeInfo = JSON.parse(sessionStorage.getItem('scene-system-selector:selected') || '{}');

  // 空值 返回空
  if (!scopeInfo.id) {
    return {
      scope_id: '',
      scope_type: '',
    };
  }
  if (scopeInfo.id === 'allSecen') { // 所有场景
    return {
      scope_id: '',
      scope_type: 'cross_scene',
    };
  } if (scopeInfo.id === 'allSystem') { // 所有系统
    return {
      scope_id: '',
      scope_type: 'cross_system',
    };
  } // 指定场景 指定系统

  return {
    scope_id: scopeInfo.id,
    scope_type: scopeInfo.type === 'scene' ? 'scene' : 'system',
  };
};
