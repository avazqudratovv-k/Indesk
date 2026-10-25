// Client-side checks for the fake log in / sign up forms. The server re-checks everything at ROADMAP 3.5.
export type AuthMode = "login" | "signup";

export type AuthValues = { name: string; email: string; password: string };
export type AuthField = keyof AuthValues;

// Keys under `auth.errors` in the message files.
export type AuthErrorKey =
  | "nameRequired"
  | "nameTooLong"
  | "emailRequired"
  | "emailInvalid"
  | "emailTooLong"
  | "passwordRequired"
  | "passwordTooShort"
  | "passwordTooLong";

export type AuthErrors = Partial<Record<AuthField, AuthErrorKey>>;

// Limits: email and display name from DATA.md (users); password minimum from the sign-up board.
export const limits = { emailMax: 254, nameMax: 60, passwordMin: 10, passwordMax: 128 } as const;

const emailShape = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateAuth(mode: AuthMode, values: AuthValues): AuthErrors {
  const errors: AuthErrors = {};
  const email = values.email.trim();

  if (mode === "signup") {
    const name = values.name.trim();
    if (name.length === 0) errors.name = "nameRequired";
    else if (name.length > limits.nameMax) errors.name = "nameTooLong";
  }

  if (email.length === 0) errors.email = "emailRequired";
  else if (email.length > limits.emailMax) errors.email = "emailTooLong";
  else if (!emailShape.test(email)) errors.email = "emailInvalid";

  if (values.password.length === 0) errors.password = "passwordRequired";
  else if (values.password.length > limits.passwordMax) errors.password = "passwordTooLong";
  else if (mode === "signup" && values.password.length < limits.passwordMin) errors.password = "passwordTooShort";

  return errors;
}
