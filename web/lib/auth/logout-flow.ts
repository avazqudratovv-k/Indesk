// The one logout sequence the navbar and My page share: end the session on the server first, and only then go to Home.
// If the server cannot be reached the session is still active, so nobody is sent away; the caller says so.
export async function runLogout(endSession: () => Promise<void>, goHome: () => void): Promise<"done" | "failed"> {
  try {
    await endSession();
  } catch {
    return "failed";
  }
  goHome();
  return "done";
}
