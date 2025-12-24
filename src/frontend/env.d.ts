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
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_AJAX_URL_PREFIX: string
  readonly DEV_DOMAIN: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module '*.js' {
  const css: string;
  export default js;
}

declare interface Window {
  PROJECT_CONFIG: {
    AJAX_URL_PREFIX: string,
    NAMESPACE: string
  };
  changeConfirm: boolean | 'popover';
  testmessage: any;
  BkVisionSDK: any;
  timezone: string;
}

declare module 'js-cookie';

declare module 'dompurify';

declare module '@blueking/notice-component';

declare module '@blueking/login-modal';

declare module '@blueking/date-picker';

declare module '@blueking/platform-config' {
  export function getPlatformConfig(url: string, options: Recrod<string, any>): Promise<any>;
  export function setDocumentTitle(params: Recrod<string, any>): void;
  export function setShortcutIcon(params: string): void;
}

interface URLSearchParams {
  keys(): string[];
}

type ValueOf<T> = T[keyof T];

declare module '@blueking/bk-trace-core' {
  interface BkTraceOptions {
    url: string
    appCode: string
    appVersion: string
    spaceID?: string
    spaceType?: string
  }

  const BkTrace: {
    install: (app: any, options: BkTraceOptions) => void
  };

  export default BkTrace;
}
declare module 'vue-json-viewer' {
  import { Plugin } from 'vue';

  interface JsonViewerOptions {
    // 可以根据实际使用情况添加更多选项
    value?: any;
    expanded?: boolean;
    expandDepth?: number;
    copyable?: boolean;
    sort?: boolean;
    boxed?: boolean;
    theme?: string;
    previewMode?: boolean;
    timeformat?: string;
  }

  const JsonViewer: Plugin & {
    install: (app: any, options?: JsonViewerOptions) => void;
  };

  export default JsonViewer;
}
