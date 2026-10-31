// Test-only: the raw bodies GET /api/reports/{id} would send (see __fixtures__/*.json, invented numbers). Only tests
// import this file, so none of it is part of a page.
import answered from "./__fixtures__/answered.json";
import empty from "./__fixtures__/empty.json";
import html from "./__fixtures__/html.json";
import korean from "./__fixtures__/korean.json";
import pdf from "./__fixtures__/pdf.json";
import partial from "./__fixtures__/partial.json";
import unknown from "./__fixtures__/unknown.json";
import zero from "./__fixtures__/zero.json";

export const fixtures = { answered, pdf, partial, zero, unknown, korean, empty, html } as const;
export type FixtureName = keyof typeof fixtures;

export const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
