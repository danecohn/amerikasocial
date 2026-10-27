import * as SecureStore from "expo-secure-store";

export const ORIGIN = process.env.EXPO_PUBLIC_API_ORIGIN || "https://altstack.io";
if (!/^https:\/\//.test(ORIGIN) || new URL(ORIGIN).origin !== ORIGIN) throw new Error("Use an HTTPS API origin without a path.");
const KEY = "amerika.session";
export type Actor = {
  id: string;
  handle: string;
  name: string;
  kind: "human" | "agent";
  bio: string;
  photo?: string;
  plus?: boolean;
  verified?: boolean;
  verificationType?: string;
  americanStatus?: string;
  followers?: number;
  following?: boolean;
  followsYou?: boolean;
  friendship?: string;
  friendsPrivate?: boolean;
  blocked?: boolean; blocking?: boolean;
  admin?: boolean;
  moderator?: boolean;
  followingCount?: number;
  mutualCount?: number;
};
export type Media = { id: string; mime: string; url: string; alt: string };
export type Post = {
  uri: string;
  text: string;
  created: string;
  author: Actor;
  likes: number;
  replies: number;
  reposts: number;
  liked: boolean;
  reposted: boolean;
  deleted: number;
  media: Media[];
  quote?: Post;
  parent?: string;
  repostBy?: Actor;
  community?: { id:string; name: string; slug?:string };
};
export type Notice = {
  id: number;
  type: string;
  sender: Actor;
  post?: string;
  postDetails?: Post;
  seen: number;
  created: string;
  message?: number;
};
export type Message = {
  id: number;
  sender: string;
  recipient: string;
  text: string;
  created: string;
  seen: number;
};
export type Config = {
  captcha: { enabled: boolean; siteKey?: string };
  handleDomain: string;
  rules: { version: string; prohibited: string[] };
};
export class APIError extends Error {
  constructor(
    message: string,
    public status: number,
    public retryAfter?: number,
  ) {
    super(message);
  }
}
export const absolute = (url?: string) =>
  url ? (url.startsWith("/") ? ORIGIN + url : url) : undefined;
export function shortHandle(handle: string) {
  return handle.replace(/\.pds\.amerika\.social$/, "");
}
export const postURL = (uri: string) =>
  ORIGIN + "/post/" + encodeURIComponent(uri);
export class API {
  token: string | null = null;
  onExpired?: () => void;
  async restore() {
    this.token = await SecureStore.getItemAsync(KEY);
  }
  async save(token: string) {
    await SecureStore.setItemAsync(KEY, token, {
      keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
    });
    this.token = token;
  }
  async clear() {
    this.token = null;
    await SecureStore.deleteItemAsync(KEY);
  }
  async request<T>(path: string, body?: unknown): Promise<T> {
    const identity = this.token;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 25000);
    try {
      const response = await fetch(ORIGIN + "/api/" + path, {
        method: body === undefined ? "GET" : "POST",
        credentials: "include",
        headers: {
          Accept: "application/json",
          ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
          ...(this.token ? { Authorization: "Bearer " + this.token } : {}),
        },
        ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
        signal: controller.signal,
      });
      const data = await response.json();
      if (identity !== this.token)
        throw new APIError("Account changed. Please retry.", 409);
      if (!response.ok) {
        if (
          response.status === 401 &&
          this.token &&
          !["login", "register", "account/delete", "recovery/codes", "agents/link"].includes(path)
        )
          this.onExpired?.();
        throw new APIError(
          data.error || "The request could not be completed.",
          response.status,
          data.retryAfter,
        );
      }
      return data;
    } finally {
      clearTimeout(timeout);
    }
  }
}
export const api = new API();
