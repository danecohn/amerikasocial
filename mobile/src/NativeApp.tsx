import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  AppState,
  FlatList,
  KeyboardAvoidingView,
  Linking,
  Modal,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  SafeAreaProvider,
  SafeAreaView,
  useSafeAreaInsets,
} from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { Ionicons } from "@expo/vector-icons";
import { Actor, api, Config, Message, Notice, ORIGIN, Post } from "./api";
import {
  Button,
  Draft,
  Empty,
  Icon,
  Person,
  PostCard,
  problem,
  Route,
} from "./components";
import Auth from "./Auth";
import Composer from "./Composer";
import Plus from "./Plus";
import { colors, styles as s } from "./theme";
function AppContent() {
  const insets = useSafeAreaInsets();
  const [me, setMe] = useState<Actor | null>(null),
    [config, setConfig] = useState<Config>(),
    [ready, setReady] = useState(false),
    [error, setError] = useState(""),
    [tab, setTab] = useState("home"),
    [filter, setFilter] = useState("everyone"),
    [stack, setStack] = useState<Route[]>([]),
    [list, setList] = useState(""),
    [auth, setAuth] = useState(false),
    [draft, setDraft] = useState<Draft>(),
    [plus, setPlus] = useState(false),
    [busy, setBusy] = useState(false),
    [sending, setSending] = useState(false),
    [posts, setPosts] = useState<Post[]>([]),
    [cursor, setCursor] = useState<string | null>(null),
    [people, setPeople] = useState<Actor[]>([]),
    [profile, setProfile] = useState<Actor>(),
    [notices, setNotices] = useState<Notice[]>([]),
    [unread, setUnread] = useState(0),
    [messages, setMessages] = useState<Message[]>([]),
    [inbox, setInbox] = useState<(Message & { peer: Actor; unread: number })[]>(
      [],
    ),
    [text, setText] = useState("");
  const requestEpoch = useRef(0);
  const route = stack.at(-1);
  const clear = () => {
    requestEpoch.current++;
    setPosts([]);
    setPeople([]);
    setNotices([]);
    setMessages([]);
    setInbox([]);
    setProfile(undefined);
  };
  const open = (r: Route) => {
    clear();
    setList("");
    setStack((old) => [...old, r]);
  };
  const logged = () => {
    if (me) return true;
    setAuth(true);
    return false;
  };
  const compose = (d: Draft) => {
    if (logged()) setDraft(d);
  };
  const feedPath = () =>
    filter === "friends"
      ? "feed?following=1"
      : filter === "agents"
        ? "feed?kind=agent"
        : "feed?";
  async function bootstrap() {
    setError("");
    try {
      await api.restore();
      setConfig(await api.request<Config>("config"));
      const restored = (await api.request<{ actor: Actor | null }>("me")).actor;
      if (!restored) await api.clear();
      setMe(restored);
      setReady(true);
    } catch (e) {
      setError(problem(e));
    }
  }
  useEffect(() => {
    api.onExpired = () => {
      void api.clear();
      setMe(null);
      clear();
      setStack([]);
      setDraft(undefined);
      setUnread(0);
      setError("Your session expired. Please sign in again.");
    };
    void bootstrap();
    return () => {
      api.onExpired = undefined;
    };
  }, []);
  async function load() {
    if (!ready) return;
    const epoch = ++requestEpoch.current;
    const scoped = async <T,>(path: string) => {
      const data = await api.request<T>(path);
      if (epoch !== requestEpoch.current) throw Error("STALE_REQUEST");
      return data;
    };
    setBusy(true);
    setError("");
    try {
      if (route?.kind === "thread") {
        const d = await scoped<{
          post: Post;
          root: Post | null;
          conversation: Post[];
        }>("thread?uri=" + encodeURIComponent(route.uri));
        const root = d.root || d.post;
        setPosts([root, ...d.conversation.filter((p) => p.uri !== root.uri)]);
      } else if (route?.kind === "profile") {
        setProfile(
          (
            await scoped<{ actor: Actor }>(
              "profile?id=" + encodeURIComponent(route.actor.id),
            )
          ).actor,
        );
        if (list)
          setPeople(
            (
              await scoped<{ actors: Actor[] }>(
                "profile/friends?id=" +
                  encodeURIComponent(route.actor.id) +
                  "&list=" +
                  list,
              )
            ).actors,
          );
        else
          setPosts(
            (
              await scoped<{ posts: Post[] }>(
                "feed?author=" + encodeURIComponent(route.actor.id),
              )
            ).posts,
          );
      } else if (route?.kind === "chat") {
        const d = await scoped<{ messages: Message[] }>(
          "messages?peer=" + encodeURIComponent(route.actor.id),
        );
        setMessages(d.messages);
        if (d.messages.length)
          await api.request("messages/read", {
            peer: route.actor.id,
            through: d.messages.at(-1)!.id,
          });
      } else if (route?.kind === "bots")
        setPeople((await scoped<{ agents: Actor[] }>("agents")).agents);
      else if (tab === "home") {
        const d = await scoped<{ posts: Post[]; cursor: string | null }>(
          feedPath(),
        );
        setPosts(d.posts);
        setCursor(d.cursor);
      } else if (me && tab === "friends")
        setPeople((await scoped<{ friends: Actor[] }>("friends")).friends);
      else if (me && tab === "alerts") {
        const d = await scoped<{ notifications: Notice[]; unread: number }>(
          "notifications",
        );
        setNotices(d.notifications);
        setUnread(d.unread);
      } else if (me && tab === "inbox")
        setInbox(
          (
            await scoped<{
              conversations: (Message & { peer: Actor; unread: number })[];
            }>("messages")
          ).conversations,
        );
    } catch (e) {
      if (epoch === requestEpoch.current) setError(problem(e));
    } finally {
      if (epoch === requestEpoch.current) setBusy(false);
    }
  }
  useEffect(() => {
    void load();
  }, [ready, tab, filter, route, list, me?.id]);
  useEffect(() => {
    if (!me) return;
    const poll = async () => {
      if (AppState.currentState !== "active") return;
      try {
        setUnread(
          (await api.request<{ unread: number }>("notifications")).unread,
        );
      } catch {}
    };
    void poll();
    const timer = setInterval(poll, 30000);
    const l = AppState.addEventListener("change", (value) => {
      if (value === "active") void poll();
    });
    return () => {
      clearInterval(timer);
      l.remove();
    };
  }, [me?.id]);
  const more = async () => {
    if (!cursor || busy || route || tab !== "home") return;
    setBusy(true);
    try {
      const d = await api.request<{ posts: Post[]; cursor: string | null }>(
        feedPath() + "&cursor=" + encodeURIComponent(cursor),
      );
      setPosts((old) => [
        ...old,
        ...d.posts.filter((p) => !old.some((o) => o.uri === p.uri)),
      ]);
      setCursor(d.cursor);
    } catch (e) {
      setError(problem(e));
    } finally {
      setBusy(false);
    }
  };
  const friend = async (a: Actor) => {
    if (!logged()) return;
    try {
      await api.request("follows", { subject: a.id });
      void load();
    } catch (e) {
      Alert.alert("Friendship update failed", problem(e));
    }
  };
  const send = async () => {
    if (route?.kind !== "chat" || sending || !text.trim()) return;
    setSending(true);
    try {
      await api.request("messages", { recipient: route.actor.id, text });
      setText("");
      void load();
    } catch (e) {
      Alert.alert("Message not sent", problem(e));
    } finally {
      setSending(false);
    }
  };
  const signOut = async () => {
    try {
      await api.request("logout", {});
    } catch {
    } finally {
      await api.clear();
      setMe(null);
      clear();
      setStack([]);
      setUnread(0);
      setFilter("everyone");
      setTab("home");
    }
  };
  const rc = (
    <RefreshControl
      refreshing={busy}
      onRefresh={() => void load()}
      tintColor={colors.red}
    />
  );
  const peopleView = (
    <FlatList
      data={people}
      keyExtractor={(a) => a.id}
      refreshControl={rc}
      ListEmptyComponent={<Empty text="No accounts in this list yet." />}
      renderItem={({ item }) => (
        <View style={s.card}>
          <Person
            actor={item}
            onPress={() => open({ kind: "profile", actor: item })}
          />
          <Text style={s.muted}>
            {item.friendship === "mutual"
              ? "Mutual friends"
              : item.following
                ? "You added them"
                : item.followsYou
                  ? "They added you"
                  : item.kind === "agent"
                    ? "Your linked bot"
                    : "Not connected yet"}
          </Text>
          {item.id !== me?.id && (
            <Button
              secondary
              title={item.following ? "Remove friend" : "Add friend"}
              onPress={() => void friend(item)}
            />
          )}
        </View>
      )}
    />
  );
  let header: React.ReactElement | undefined;
  if (!route && tab === "home")
    header = (
      <>
        <View style={s.hero}>
          <Text style={s.title}>Why Can’t We{"\n"}Be Friends?</Text>
          <Text style={s.text}>Make friends. Grow stronger together.</Text>
          <Text style={[s.muted, { color: colors.white }]}>
            Free speech. Newest first. No paid boosts.
          </Text>
        </View>
        <View style={s.tabs}>
          {["everyone", "friends", "agents"].map((f) => (
            <Button
              key={f}
              secondary={filter !== f}
              title={f[0].toUpperCase() + f.slice(1)}
              onPress={() => {
                if (f === "friends" && !logged()) return;
                setFilter(f);
              }}
            />
          ))}
        </View>
      </>
    );
  if (route?.kind === "profile" && profile)
    header = (
      <View style={s.content}>
        <Person actor={profile} />
        <Text style={s.text}>{profile.bio || "Say hello."}</Text>
        <Text style={s.muted}>
          American ·{" "}
          {profile.americanStatus === "verified"
            ? "Location verified"
            : "Self-declared"}
        </Text>
        <View style={[s.row, { flexWrap: "wrap" }]}>
          {["friends", "added", "mutual"].map((value) => (
            <Button
              key={value}
              secondary
              title={value[0].toUpperCase() + value.slice(1)}
              onPress={() => setList(value)}
            />
          ))}
        </View>
        {profile.id !== me?.id && (
          <>
            <Button
              title={profile.following ? "Remove friend" : "Add friend"}
              onPress={() => void friend(profile)}
            />
            <Button
              secondary
              title="Message"
              onPress={() => logged() && open({ kind: "chat", actor: profile })}
            />
          </>
        )}
      </View>
    );
  const feed = (
    <FlatList
      data={posts}
      keyExtractor={(p) => p.uri}
      refreshControl={rc}
      ListHeaderComponent={header}
      ListEmptyComponent={
        <Empty text={busy ? "Loading…" : "The conversation starts with you."} />
      }
      onEndReached={() => void more()}
      onEndReachedThreshold={0.5}
      contentContainerStyle={{ paddingBottom: 90 }}
      renderItem={({ item }) => (
        <PostCard
          post={item}
          open={open}
          compose={compose}
          refresh={() => void load()}
          signedIn={!!me}
        />
      )}
    />
  );
  let content: React.ReactElement = feed;
  if (route?.kind === "profile" && list)
    content = (
      <>
        {header}
        {peopleView}
      </>
    );
  else if (route?.kind === "bots")
    content = (
      <>
        {peopleView}
        <View style={s.content}>
          <Text selectable style={s.text}>
            {ORIGIN}/mcp/service
          </Text>
          <Button
            secondary
            title="Read bot API guide"
            onPress={() => void Linking.openURL(ORIGIN + "/agent.md")}
          />
        </View>
      </>
    );
  else if (route?.kind === "chat")
    content = (
      <KeyboardAvoidingView
        style={s.screen}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <FlatList
          data={messages}
          keyExtractor={(m) => String(m.id)}
          refreshControl={rc}
          ListEmptyComponent={<Empty text="Say hello." />}
          renderItem={({ item }) => (
            <View
              style={{
                padding: 12,
                alignItems: item.sender === me?.id ? "flex-end" : "flex-start",
              }}
            >
              <View
                style={{
                  backgroundColor:
                    item.sender === me?.id ? colors.red : colors.card,
                  padding: 14,
                  borderRadius: 14,
                  maxWidth: "85%",
                }}
              >
                <Text style={s.text}>{item.text}</Text>
              </View>
            </View>
          )}
        />
        <View
          style={[
            s.row,
            { padding: 12, paddingBottom: Math.max(insets.bottom, 12) },
          ]}
        >
          <TextInput
            accessibilityLabel="Message"
            value={text}
            onChangeText={setText}
            maxLength={2000}
            placeholder="Message…"
            placeholderTextColor={colors.muted}
            style={[s.input, { flex: 1 }]}
          />
          <Button
            disabled={sending || !text.trim()}
            title={sending ? "Sending…" : "Send"}
            onPress={() => void send()}
          />
        </View>
      </KeyboardAvoidingView>
    );
  else if (!route && tab !== "home" && !me)
    content = (
      <View style={s.empty}>
        <Text style={s.text}>Sign in to see your account.</Text>
        <Button title="Sign in" onPress={() => setAuth(true)} />
      </View>
    );
  else if (!route && tab === "friends") content = peopleView;
  else if (!route && tab === "alerts")
    content = (
      <FlatList
        data={notices}
        keyExtractor={(n) => String(n.id)}
        refreshControl={rc}
        ListEmptyComponent={<Empty text="You’re all caught up." />}
        renderItem={({ item }) => (
          <Pressable
            style={[s.card, !item.seen && { backgroundColor: colors.card }]}
            onPress={() =>
              void api
                .request("notifications/read", { id: item.id })
                .then(() => {
                  if (item.type === "message")
                    open({ kind: "chat", actor: item.sender });
                  else if (item.post) open({ kind: "thread", uri: item.post });
                  else open({ kind: "profile", actor: item.sender });
                })
                .catch((e) =>
                  Alert.alert("Could not open notification", problem(e)),
                )
            }
          >
            <Person actor={item.sender} />
            <Text style={s.text}>{item.type.replaceAll("_", " ")}</Text>
            {item.postDetails && (
              <>
                <Text style={s.muted} numberOfLines={3}>
                  {item.postDetails.text}
                </Text>
                <Button
                  title="Reply"
                  onPress={() => compose({ parent: item.postDetails })}
                />
              </>
            )}
          </Pressable>
        )}
      />
    );
  else if (!route && tab === "inbox")
    content = (
      <FlatList
        data={inbox}
        keyExtractor={(c) => c.peer.id}
        refreshControl={rc}
        ListEmptyComponent={<Empty text="Open a profile to start a message." />}
        renderItem={({ item }) => (
          <Pressable
            style={s.card}
            onPress={() => open({ kind: "chat", actor: item.peer })}
          >
            <Person actor={item.peer} />
            <Text style={s.text} numberOfLines={2}>
              {item.text}
            </Text>
            {!!item.unread && <Text style={s.badge}>{item.unread} unread</Text>}
          </Pressable>
        )}
      />
    );
  else if (!route && tab === "me" && me)
    content = (
      <ScrollView contentContainerStyle={s.content}>
        <Person actor={me} />
        <Text style={s.text}>{me.bio}</Text>
        <Text style={s.muted}>
          {me.plus
            ? "Plus · 833 characters"
            : "Standard · 300 characters, 3 original posts per hour"}
        </Text>
        <Button title="Amerika Social Plus" onPress={() => setPlus(true)} />
        <Button
          secondary
          title="My profile"
          onPress={() => open({ kind: "profile", actor: me })}
        />
        <Button
          secondary
          title="My bots"
          onPress={() => open({ kind: "bots" })}
        />
        {[
          ["Privacy policy", "/privacy"],
          ["Terms and rules", "/terms"],
          ["Support", "/support"],
        ].map(([title, path]) => (
          <Button
            key={path}
            secondary
            title={title}
            onPress={() => void Linking.openURL(ORIGIN + path)}
          />
        ))}
        <Button
          secondary
          title="Sign out"
          onPress={() =>
            Alert.alert("Sign out?", undefined, [
              { text: "Cancel", style: "cancel" },
              {
                text: "Sign out",
                style: "destructive",
                onPress: () => void signOut(),
              },
            ])
          }
        />
      </ScrollView>
    );
  if (!ready)
    return (
      <SafeAreaView style={s.screen}>
        <View style={s.empty}>
          <Text style={s.title}>Amerika Social</Text>
          {error ? (
            <>
              <Text style={s.error}>{error}</Text>
              <Button title="Retry" onPress={() => void bootstrap()} />
            </>
          ) : (
            <ActivityIndicator color={colors.red} />
          )}
        </View>
      </SafeAreaView>
    );
  const title =
    route?.kind === "thread"
      ? "Conversation"
      : route?.kind === "profile" || route?.kind === "chat"
        ? route.actor.name
        : route?.kind === "bots"
          ? "Your bots"
          : {
              home: "Amerika",
              friends: "Friends",
              alerts: "Notifications",
              inbox: "Messages",
              me: "Your account",
            }[tab];
  return (
    <SafeAreaView style={s.screen} edges={["top", "left", "right"]}>
      <StatusBar style="light" />
      <View style={[s.header, s.row]}>
        {route ? (
          <Icon
            name="arrow-back"
            label="Back"
            onPress={() => {
              if (list) { setList(""); return; }
              clear();
              setStack((old) => old.slice(0, -1));
            }}
          />
        ) : (
          <View style={[s.logo, { width: 32, height: 32 }]}>
            <Text style={[s.label, { fontSize: 25 }]}>A</Text>
          </View>
        )}
        <Text numberOfLines={1} style={[s.title, { fontSize: 22, flex: 1 }]}>
          {title}
        </Text>
        {!me && <Button title="Sign in" onPress={() => setAuth(true)} />}
      </View>
      {!!error && (
        <View style={{ padding: 12 }}>
          <Text style={s.error}>{error}</Text>
          <Button secondary title="Retry" onPress={() => void load()} />
        </View>
      )}
      {content}
      {!route && (
        <>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Write a post"
            style={[s.fab, { bottom: 76 + insets.bottom }]}
            onPress={() => compose({})}
          >
            <Ionicons name="add" size={32} color="white" />
          </Pressable>
          <View style={[s.bar, { paddingBottom: Math.max(insets.bottom, 8) }]}>
            {(["home", "friends", "alerts", "inbox", "me"] as const).map(
              (name, i) => (
                <Pressable
                  key={name}
                  style={s.tab}
                  accessibilityRole="tab"
                  accessibilityState={{ selected: tab === name }}
                  onPress={() => {
                    if (name === tab) {
                      void load();
                      return;
                    }
                    clear();
                    setTab(name);
                  }}
                >
                  <Ionicons
                    name={
                      (
                        [
                          "home-outline",
                          "people-outline",
                          "notifications-outline",
                          "mail-outline",
                          "person-circle-outline",
                        ] as const
                      )[i]
                    }
                    size={23}
                    color={tab === name ? colors.red : colors.muted}
                  />
                  <Text
                    style={{
                      color: tab === name ? colors.white : colors.muted,
                      fontSize: 11,
                    }}
                  >
                    {
                      [
                        "Home",
                        "Friends",
                        unread ? `Alerts (${unread})` : "Alerts",
                        "Inbox",
                        "Me",
                      ][i]
                    }
                  </Text>
                </Pressable>
              ),
            )}
          </View>
        </>
      )}
      <Modal
        visible={auth}
        animationType="slide"
        presentationStyle="fullScreen"
        onRequestClose={() => setAuth(false)}
      >
        <SafeAreaView style={s.screen}>
          {config && (
            <Auth
              config={config}
              onClose={() => setAuth(false)}
              onDone={(actor) => {
                setMe(actor);
                setAuth(false);
              }}
            />
          )}
        </SafeAreaView>
      </Modal>
      <Modal
        visible={!!draft}
        animationType="slide"
        presentationStyle="fullScreen"
        onRequestClose={() => setDraft(undefined)}
      >
        <SafeAreaView style={s.screen}>
          {draft && me && (
            <Composer
              draft={draft}
              me={me}
              onClose={() => setDraft(undefined)}
              onSent={() => {
                setDraft(undefined);
                void load();
              }}
            />
          )}
        </SafeAreaView>
      </Modal>
      <Modal
        visible={plus}
        animationType="slide"
        presentationStyle="fullScreen"
        onRequestClose={() => setPlus(false)}
      >
        <SafeAreaView style={s.screen}>
          {me && (
            <Plus
              me={me}
              onClose={() => setPlus(false)}
              onUpdated={async () =>
                setMe((await api.request<{ actor: Actor }>("me")).actor)
              }
            />
          )}
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}
export default function App() {
  return (
    <SafeAreaProvider>
      <AppContent />
    </SafeAreaProvider>
  );
}
