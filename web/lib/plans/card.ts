// Demo card rules. Pure functions only: nothing here reads, stores or sends a card value.
// There is no Luhn check on purpose, so any made-up number works in the demo.

export const CARD_DIGITS = 16;
export const DECLINED_CARD = "4000000000000002";
export const NAME_MAX = 60;

const digitsOf = (value: string) => value.replace(/\D/g, "");

// Digits only, at most 16, shown in groups of 4.
export function formatCardNumber(value: string): string {
  return (digitsOf(value).slice(0, CARD_DIGITS).match(/.{1,4}/g) ?? []).join(" ");
}

// MM/YY. The slash is added after the month while typing forward, never forced back while deleting.
// A first digit of 2 to 9 gets a leading 0; a month outside 01 to 12 keeps only its first digit.
export function formatExpiry(value: string, deleting: boolean): string {
  let digits = digitsOf(value).slice(0, 4);
  if (digits.length > 0 && digits[0] > "1") digits = `0${digits}`.slice(0, 4);
  if (digits.length >= 2) {
    const month = Number(digits.slice(0, 2));
    if (month < 1 || month > 12) digits = digits.slice(0, 1);
  }
  if (digits.length > 2) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return digits.length === 2 && !deleting ? `${digits}/` : digits;
}

export function formatCvc(value: string): string {
  return digitsOf(value).slice(0, 4);
}

// Only this one number is declined. Every other complete number succeeds.
export function isDeclinedCard(cardNumber: string): boolean {
  return digitsOf(cardNumber) === DECLINED_CARD;
}

export type CardErrors = {
  number?: "numberIncomplete";
  expiry?: "expiryInvalid" | "expiryPast";
  cvc?: "cvcShort";
};

export function validateCard(fields: { number: string; expiry: string; cvc: string }, now: Date): CardErrors {
  const errors: CardErrors = {};
  if (digitsOf(fields.number).length < CARD_DIGITS) errors.number = "numberIncomplete";

  const expiry = digitsOf(fields.expiry);
  const month = Number(expiry.slice(0, 2));
  if (expiry.length < 4 || month < 1 || month > 12) {
    errors.expiry = "expiryInvalid";
  } else {
    const year = 2000 + Number(expiry.slice(2));
    const thisMonth = now.getFullYear() * 12 + now.getMonth();
    if (year * 12 + (month - 1) < thisMonth) errors.expiry = "expiryPast";
  }

  const cvc = digitsOf(fields.cvc).length;
  if (cvc < 3 || cvc > 4) errors.cvc = "cvcShort";
  return errors;
}
