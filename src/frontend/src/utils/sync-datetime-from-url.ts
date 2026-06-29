import { DateRange } from '@blueking/date-picker';

const DATETIME_FORMAT = 'YYYY-MM-DD HH:mm:ss';

export const isRelativeDatetimeOrigin = (datetimeOrigin: string[]) => (
  datetimeOrigin.some(item => typeof item === 'string' && /^now(-|$)/.test(item))
);

export const syncDatetimeFromOrigin = (
  datetimeOrigin: string[],
  format = DATETIME_FORMAT,
): [string, string] => {
  const date = new DateRange(datetimeOrigin, format, (window as any).timezone);
  return [date.startDisplayText, date.endDisplayText];
};

type DatetimeSearchModel = {
  datetime: string[];
  datetime_origin: string[];
};

const asDatetimeSearchModel = (searchModel: Record<string, any>): DatetimeSearchModel => (
  searchModel as DatetimeSearchModel
);

export const applyDatetimeUrlParams = (
  searchModel: Record<string, any>,
  urlParams: Record<string, any>,
  normalizeParamArray: (value: unknown) => Array<string | number>,
) => {
  const model = asDatetimeSearchModel(searchModel);
  if (urlParams.datetime_origin) {
    model.datetime_origin = normalizeParamArray(urlParams.datetime_origin).map(String);
  }

  if (model.datetime_origin?.length >= 2) {
    model.datetime = syncDatetimeFromOrigin(model.datetime_origin);
    return;
  }

  if (urlParams.start_time && urlParams.end_time) {
    model.datetime = [
      String(urlParams.start_time),
      String(urlParams.end_time),
    ];
  }
};

export const ensureDatetimeSynced = (searchModel: Record<string, any>) => {
  const model = asDatetimeSearchModel(searchModel);
  if (model.datetime_origin?.length >= 2) {
    model.datetime = syncDatetimeFromOrigin(model.datetime_origin);
  }
};
