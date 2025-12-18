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

import type {
  AxiosError,
  AxiosInterceptorManager,
  AxiosResponse,
} from 'axios';

import IamApplyDataModel from '@model/iam/apply-data';

import useEventBus from '@hooks/use-event-bus';
import useMessage from '@hooks/use-message';

import { showLoginModal } from '@blueking/login-modal';

import {
  parseURL,
  permissionDialog,
} from '@utils/assist';

import RequestError from '../lib/request-error';

const { messageError } = useMessage();


// 标记已经登录过状态
// 第一次登录跳转登录页面，之后弹框登录
let hasLogined = false;

const redirectLogin = (loginUrl:string) => {
  const { protocol, host, pathname } = parseURL(loginUrl);
  let pathnameWithoutPlain = pathname.replace('/plain/', '');
  pathnameWithoutPlain = pathnameWithoutPlain.endsWith('/') ? pathnameWithoutPlain : `${pathnameWithoutPlain}/`;
  if (hasLogined) {
    const loginUrl = `${protocol}://${host}${pathnameWithoutPlain}plain/?c_url=${decodeURIComponent(`${window.location.origin}/login-success.html`)}`;
    showLoginModal({
      loginUrl,
      width: 400,
      height: 400,
    });
  } else {
    window.location.href = `${protocol}://${host}${pathnameWithoutPlain}?c_url=${decodeURIComponent(window.location.href)}`;
  }
};

const downloadFile = (blob: Blob, fileName: string) => {
  // 如果 fileName 未定义或为空，使用默认文件名
  const defaultFileName = 'file.xlsx';
  let finalFileName = fileName || defaultFileName;

  // 解析 content-disposition 中的文件名
  if (fileName.includes('filename')) {
    const matches = fileName.match(/filename\*?=([^;]+)/i);
    if (matches && matches[1]) {
      const encodedFileName = matches[1];
      // 处理 filename*=utf-8'' 格式
      if (encodedFileName.startsWith('utf-8\'\'')) {
        finalFileName = decodeURIComponent(encodedFileName.substring(7));
      } else {
        // 处理普通 filename="..." 格式
        const quotedMatches = encodedFileName.match(/"([^"]+)"/i);
        if (quotedMatches && quotedMatches[1]) {
          // eslint-disable-next-line prefer-destructuring
          finalFileName = quotedMatches[1];
        }
      }
    }
  }

  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = finalFileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
};

export default (interceptors: AxiosInterceptorManager<AxiosResponse>) => {
  interceptors.use((response: AxiosResponse) => {
    if (response.data instanceof Blob) {
      downloadFile(response.data, response?.headers['content-disposition']);
      return response;
    }
    // 处理http响应成功，后端返回逻辑
    switch (response.data.code) {
      // 后端业务逻辑处理成功
      case 0:
        hasLogined = true;
        return response.data;
      // 后端业务逻辑处理成功
      case 200:
        hasLogined = true;
        return response.data;
      default: {
        // 后端逻辑处理报错
        const { code, message = '系统错误' } = response.data;
        throw new RequestError(code, message, response);
      }
    }
  }, (error: AxiosError<{message: string}> & {__CANCEL__: any}) => {
    // 超时取消
    if (error.__CANCEL__) { // eslint-disable-line no-underscore-dangle
      return Promise.reject(new RequestError('CANCEL', '请求已取消'));
    }
    // 处理 http 错误响应逻辑
    if (error.response) {
      // 登录状态失效
      if (error.response.status === 401) {
        return Promise.reject(new RequestError(401, '登录状态失效', error.response));
      }
      // 默认使用 http 错误描述，
      // 如果 response body 里面有自定义错误描述优先使用
      let errorMessage = error.response.statusText;
      if (error.response.data && error.response.data.message) {
        errorMessage = error.response.data.message as string;
      }
      return Promise.reject(new RequestError(
        error.response.status || -1,
        errorMessage,
        error.response,
      ));
    }
    return Promise.reject(new RequestError(-1, `${window.PROJECT_CONFIG.AJAX_URL_PREFIX} 无法访问`));
  });

  // 统一错误处理逻辑
  interceptors.use(undefined, (error: RequestError) => {
    switch (error.code) {
      // 未登陆
      case 401:
        redirectLogin(error.response.data.login_url);
        break;
      case 403:
        handlePermission(error);
        break;
      case 409:
        messageError(error.response.data.message);
        break;
      case 'CANCEL':
        break;
        // 网络超时
      case 'ECONNABORTED':
        messageError('请求超时');
        break;
      default:
        if (error.response.data.code === '9900403') {
          handlePermission(error);
        } else if (error.response.data.code === '2905003') {
          console.log('error', error);
        } else {
          messageError(`${error.message} (${error.response.data.trace_id})`);
        }
    }
    return Promise.reject(error);
  });
};

const handlePermission = (error:RequestError) => {
  const {  emit } = useEventBus();
  // eslint-disable-next-line no-case-declarations
  const requestPayload = error.response.config.payload;
  // eslint-disable-next-line no-case-declarations
  const iamResult = new IamApplyDataModel(error.response.data.data || {});
  if (requestPayload.permission === 'page') {
    // 配合 jb-router-view（@components/audit-router-view）全局展示没权限提示
    emit('permission-page', iamResult);
  } else if (requestPayload.permission === 'catch') {
    // 配合 apply-section （@components/apply-permission/catch）使用，局部展示没权限提示
    emit('permission-catch', iamResult);
  } else {
    // 弹框展示没权限提示
    permissionDialog(iamResult);
  }
};
