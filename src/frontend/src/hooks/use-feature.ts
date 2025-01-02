import MetaManageService from '@service/meta-manage';

import useRequest from '@hooks/use-request';

export default function (featureId: string) {
  const {
    data,
  } = useRequest(MetaManageService.fetchFeature, {
    defaultValue: {
      enabled: false,
    },
    defaultParams: {
      feature_id: featureId,
    },
    manual: true,
  });

  return {
    feature: data,
  };
}
