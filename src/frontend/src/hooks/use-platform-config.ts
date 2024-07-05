import { ref } from 'vue';

import RootManageService from '@service/root-manage';

import ConfigModel from '@model/root/config';

import useRequest from '@hooks/use-request';

import {
  getPlatformConfig,
  setDocumentTitle,
  setShortcutIcon,
} from '@blueking/platform-config';

import PlatformConfigModel from '@/domain/model/root/platform-config';

const platformConfig = ref({
  version: '',
  bkAppCode: '', // appcode
  name: '', // 站点的名称，通常显示在页面左上角，也会出现在网页title中
  nameEn: '', // 站点的名称-英文
  appLogo: '', // 站点logo
  helperText: '',
  helperTextEn: '',
  helperLink: '',
  brandImg: '',
  brandImgEn: '',
  brandName: '', // 品牌名，会用于拼接在站点名称后面显示在网页title中
  favIcon: '',
  brandNameEn: '', // 品牌名-英文
  footerInfo: '', // 页脚的内容，仅支持 a 的 markdown 内容格式
  footerInfoEn: '', // 页脚的内容-英文
  footerCopyright: '', // 版本信息，包含 version 变量，展示在页脚内容下方

  footerInfoHTML: '',
  footerInfoHTMLEn: '',
  footerCopyrightContent: '',

  // 需要国际化的字段，根据当前语言cookie自动匹配，页面中应该优先使用这里的字段
  i18n: {
    name: '',
    helperText: '...',
    brandImg: '...',
    brandName: '...',
    footerInfoHTML: '...',
  },
});

let isInit = false;

export default () => {
  const { run } = useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: false,
    onSuccess: (config) => {
      getPlatformConfig(`${config.shared_res_url}/bk_audit/base.js`, {
        version: config.version,
        appLogo: '/static/images/logo.png',
        favIcon: '/static/images/favicon.ico',
        name: '蓝鲸审计中心',
        nameEn: 'BK Audit',
        brandName: '腾讯蓝鲸智云',
        brandNameEn: 'BlueKing',
      }).then((data: PlatformConfigModel) => {
        isInit = true;
        platformConfig.value = data;
        setShortcutIcon(data.favIcon);
        setDocumentTitle(data.i18n);
      });
    },
  });

  if (!isInit) {
    run();
  }

  return platformConfig;
};
