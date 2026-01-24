// export function saveToken(token: string) {
//   if (typeof window !== "undefined") {
//     localStorage.setItem("access_token", token);
//   }
// }

export async function logout() {
  try {
    await fetch("http://localhost:8000/auth/logout", {
      method: "POST",
      credentials: "include",   // 🔑 send cookies
    });
  } catch (err) {
    console.error("Logout failed", err);
  } finally {
    window.location.href = "/login";
  }
}

// Auth check: ask backend if cookie is valid
export async function isAuthenticated(): Promise<boolean> {
  try {
    const res = await fetch("http://localhost:8000/auth/is_authenticated", {
      method: "GET",
      credentials: "include",   // send cookies
    });
    return res.ok;
  } catch (err) {
    console.error("Auth check failed", err);
    return false;
  }
}
