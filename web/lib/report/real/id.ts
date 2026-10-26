// Real report ids are UUIDs (api/app/schemas/common.py Id). Mock ids look like "rep_01".
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const isRealReportId = (id: string): boolean => uuid.test(id);
