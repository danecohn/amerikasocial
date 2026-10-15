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
import FeatureHost, {Feature} from "./FeatureHost";
import {unregisterThisDevice,storedPushDeviceId} from "./PushSettings";
import * as Notifications from "expo-notifications";
import {nativePushAvailable,notificationActivity} from "./activity";
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
    [feature,setFeature]=useState<Feature|null>(null),
    [datingThread,setDatingThread]=useState<number|undefined>(),
    [busy, setBusy] = useState(false),
    [sending, setSending] = useState(false),
    [posts, setPosts] = useState<Post[]>([]),
    [cursor, setCursor] = useState<string | null>(null),
    [listCursor,setListCursor]=useState<number|null>(null),
    [messageCursor,setMessageCursor]=useState<number|null>(null),
    [noticeCursor,setNoticeCursor]=useState<number|null>(null),
    [threadCursor,setThreadCursor]=useState<number|null>(null),
    [profileTab,setProfileTab]=useState("posts"),
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
  const updated=async()=>setMe((await api.request<{actor:Actor}>("me")).actor);
  const showFeature=(name:Feature)=>{if(!me){setAuth(true);return;}setDatingThread(undefined);setFeature(name);};
  const clear = () => {
    requestEpoch.current++;
    setPosts([]);setCursor(null);setListCursor(null);setMessageCursor(null);setNoticeCursor(null);setThreadCursor(null);
    setPeople([]);
    setNotices([]);
    setMessages([]);
    setInbox([]);
    setProfile(undefined);
  };
  const open = (r: Route) => {
    clear();
    setList("");setProfileTab("posts");
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
      setFeature(null);setPlus(false);
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
  useEffect(()=>{
    if(!me||!nativePushAvailable)return;
    const receive=async(response:Notifications.NotificationResponse)=>{try{const value=await notificationActivity(me,response.notification.request.content.data||{});if(!value)return;if(value.bot){setFeature('developers');return;}const n=value.notice;if(!n){setFeature(null);setTab('alerts');return;}await api.request('notifications/read',{id:n.id});if(n.type.startsWith('dating_')&&n.message){setDatingThread(n.message);setFeature('dating');}else{setFeature(null);if(n.type==='message')open({kind:'chat',actor:n.sender});else if(n.post)open({kind:'thread',uri:n.post});else open({kind:'profile',actor:n.sender});}await Notifications.clearLastNotificationResponseAsync();}catch{setError('Sign in to open this notification.');}};
    const listener=Notifications.addNotificationResponseReceivedListener(response=>void receive(response));
    void Notifications.getLastNotificationResponseAsync().then(response=>{if(response)void receive(response);});
    return()=>listener.remove();
  },[me?.id]);
  useEffect(()=>{
    const receive=(value:string)=>{try{const url=new URL(value);let uri='';if(url.protocol==='https:'&&url.origin===ORIGIN&&url.pathname.startsWith('/post/'))uri=decodeURIComponent(url.pathname.slice(6));else if(url.protocol==='amerikasocial:'&&url.hostname==='post')uri=decodeURIComponent(url.pathname.slice(1));if(uri&&uri.length<=2048){setFeature(null);open({kind:'thread',uri});}}catch{}};
    const listener=Linking.addEventListener('url',event=>receive(event.url));void Linking.getInitialURL().then(url=>{if(url)receive(url);});return()=>listener.remove();
  },[]);
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
          conversation: Post[];conversationCursor:number|null;
        }>("thread?uri=" + encodeURIComponent(route.uri));
        const root = d.root || d.post;
        const thread=[root,...d.conversation.filter(p=>p.uri!==root.uri)];if(!thread.some(p=>p.uri===d.post.uri))thread.push(d.post);setPosts(thread);setThreadCursor(d.conversationCursor);
      } else if (route?.kind === "profile") {
        setProfile(
          (
            await scoped<{ actor: Actor }>(
              "profile?id=" + encodeURIComponent(route.actor.id),
            )
          ).actor,
        );
        if(list){const d=await scoped<{actors:Actor[];cursor:number|null}>('profile/friends?id='+encodeURIComponent(route.actor.id)+'&list='+list);setPeople(d.actors);setListCursor(d.cursor);}
        else {const d=await scoped<{posts:Post[];cursor:string|null}>('feed?author='+encodeURIComponent(route.actor.id)+'&tab='+profileTab);setPosts(d.posts);setCursor(d.cursor);}
      } else if (route?.kind === "chat") {
        const d = await scoped<{ messages: Message[];cursor:number|null }>(
          "messages?peer=" + encodeURIComponent(route.actor.id),
        );
        setMessages(d.messages);setMessageCursor(d.cursor);
        if (d.messages.length)
          await api.request("messages/read", {
            peer: route.actor.id,
            through: d.messages.at(-1)!.id,
          });
      } else if (route?.kind === "bots")
        setFeature("developers");
      else if (route?.kind==="tag"||tab === "home") {
        const d = await scoped<{ posts: Post[]; cursor: string | null }>(
          route?.kind==="tag"?"feed?tag="+encodeURIComponent(route.tag):feedPath(),
        );
        setPosts(d.posts);
        setCursor(d.cursor);
      } else if (me && tab === "friends")
        setPeople((await scoped<{ friends: Actor[] }>("friends")).friends);
      else if (me && tab === "alerts") {
        const d = await scoped<{ notifications: Notice[]; unread: number;cursor:number|null }>(
          "notifications",
        );
        setNotices(d.notifications);setNoticeCursor(d.cursor);
        setUnread(d.unread);
      } else if (me && tab === "inbox")
        setInbox(
          (
            await scoped<{
              conversations: (Message & { peer: Actor; unread: number })[];
            }>("messages")
          ).conversations,
        );
      else if (me && tab === "me")
        setMe((await scoped<{ actor: Actor }>("me")).actor);
    } catch (e) {
      if (epoch === requestEpoch.current) setError(problem(e));
    } finally {
      if (epoch === requestEpoch.current) setBusy(false);
    }
  }
  useEffect(() => {
    void load();
  }, [ready, tab, filter, route, list, profileTab, me?.id]);
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
  const more=async()=>{const canMore=route?.kind==='thread'?threadCursor!==null:route?.kind==='profile'&&list?listCursor!==null:route?.kind==='chat'?messageCursor!==null:!route&&tab==='alerts'?noticeCursor!==null:!!cursor;if(busy||!canMore)return;const epoch=requestEpoch.current;setBusy(true);try{
    if(route?.kind==='thread'&&threadCursor!==null){const d=await api.request<{conversation:Post[];conversationCursor:number|null}>('thread?uri='+encodeURIComponent(route.uri)+'&cursor='+threadCursor);if(epoch!==requestEpoch.current)return;setPosts(old=>[...old,...d.conversation.filter(p=>!old.some(o=>o.uri===p.uri))]);setThreadCursor(d.conversationCursor);}
    else if(route?.kind==='profile'&&list&&listCursor!==null){const d=await api.request<{actors:Actor[];cursor:number|null}>('profile/friends?id='+encodeURIComponent(route.actor.id)+'&list='+list+'&cursor='+listCursor);if(epoch!==requestEpoch.current)return;setPeople(old=>[...old,...d.actors.filter(a=>!old.some(o=>o.id===a.id))]);setListCursor(d.cursor);}
    else if(route?.kind==='chat'&&messageCursor!==null){const d=await api.request<{messages:Message[];cursor:number|null}>('messages?peer='+encodeURIComponent(route.actor.id)+'&before='+messageCursor);if(epoch!==requestEpoch.current)return;setMessages(old=>[...d.messages,...old.filter(m=>!d.messages.some(n=>n.id===m.id))]);setMessageCursor(d.cursor);}
    else if(!route&&tab==='alerts'&&noticeCursor!==null){const d=await api.request<{notifications:Notice[];cursor:number|null}>('notifications?before='+noticeCursor);if(epoch!==requestEpoch.current)return;setNotices(old=>[...old,...d.notifications.filter(n=>!old.some(o=>o.id===n.id))]);setNoticeCursor(d.cursor);}
    else if(cursor&&(!route&&tab==='home'||route?.kind==='profile'&&!list||route?.kind==='tag')){const path=route?.kind==='profile'?'feed?author='+encodeURIComponent(route.actor.id)+'&tab='+profileTab:route?.kind==='tag'?'feed?tag='+encodeURIComponent(route.tag):feedPath();const d=await api.request<{posts:Post[];cursor:string|null}>(path+'&cursor='+encodeURIComponent(cursor));if(epoch!==requestEpoch.current)return;setPosts(old=>[...old,...d.posts.filter(p=>!old.some(o=>o.uri===p.uri))]);setCursor(d.cursor);}
  }catch(e){if(epoch===requestEpoch.current)setError(problem(e));}finally{if(epoch===requestEpoch.current)setBusy(false);}};
  useEffect(()=>{
    if(!me||route?.kind!=='chat')return;
    const peer=route.actor.id,epoch=requestEpoch.current;
    const poll=async()=>{if(AppState.currentState!=='active')return;try{const d=await api.request<{messages:Message[]}>('messages?peer='+encodeURIComponent(peer));if(requestEpoch.current!==epoch)return;setMessages(old=>[...old.filter(m=>!d.messages.some(n=>n.id===m.id)),...d.messages]);if(d.messages.length)await api.request('messages/read',{peer,through:d.messages.at(-1)!.id});}catch{}};
    const timer=setInterval(()=>void poll(),10000);return()=>clearInterval(timer);
  },[me?.id,route]);
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
      const pushDeviceId=await storedPushDeviceId();
      try{await unregisterThisDevice();}catch{}
      await api.request("logout", {pushDeviceId});
    } catch {
    } finally {
      await api.clear();
      setMe(null);
      setFeature(null);setPlus(false);
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
      ListFooterComponent={route?.kind==="profile"&&list&&listCursor!==null?<Button secondary title="More accounts" disabled={busy} onPress={()=>void more()}/>:null}
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
              title={(value==="friends"?profile.followers:value==="added"?profile.followingCount:profile.mutualCount)+" "+value[0].toUpperCase()+value.slice(1)}
              onPress={() => setList(value)}
            />
          ))}
        </View>
        {profile.id !== me?.id&&!profile.blocked && (
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
        {me&&profile.id!==me.id&&<View style={[s.row,{flexWrap:'wrap'}]}><Button secondary title={profile.blocking?'Unblock account':'Block account'} onPress={()=>Alert.alert(profile.blocking?'Unblock account?':'Block account and linked bots?', 'Blocking hides activity and prevents direct interaction.',[{text:'Cancel',style:'cancel'},{text:'Confirm',onPress:()=>void api.request('account/block',{subject:profile.id,blocked:!profile.blocking}).then(()=>load()).catch(e=>Alert.alert('Update failed',problem(e)))}])}/><Button secondary title="Report account" onPress={()=>Alert.alert('Report account','Choose the prohibited conduct. Profanity and viewpoints are allowed.',[{text:'Cancel',style:'cancel'},...['Spam','Phishing','Card fraud & testing','Anything illegal','Crypto miners','Pirated content'].map(reason=>({text:reason,onPress:()=>void api.request('reports',{target:profile.id,type:'account',reason,detail:'Reported from the native account profile.'}).then(()=>Alert.alert('Report received')).catch(e=>Alert.alert('Report failed',problem(e)))}))])}/></View>}
      </View>
    );
  if(route?.kind==="tag")header=<View style={s.content}><Text style={s.title}>#{route.tag}</Text>{me&&<Button secondary title="Follow hashtag" onPress={()=>void api.request("hashtags/follow",{tag:route.tag,following:true}).then(()=>Alert.alert("Hashtag followed")).catch(e=>Alert.alert("Could not follow hashtag",problem(e)))}/>}</View>;
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
          signedIn={!!me} me={me||undefined}
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
          ListHeaderComponent={messageCursor!==null?<Button secondary title="Earlier messages" disabled={busy} onPress={()=>void more()}/>:null}
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
        ListFooterComponent={noticeCursor!==null?<Button secondary title="Earlier notifications" disabled={busy} onPress={()=>void more()}/>:null}
        ListEmptyComponent={<Empty text="You’re all caught up." />}
        renderItem={({ item }) => (
          <Pressable
            style={[s.card, !item.seen && { backgroundColor: colors.card }]}
            onPress={() =>
              void api
                .request("notifications/read", { id: item.id })
                .then(() => {
                  if(item.type.startsWith("dating_")&&item.message){setDatingThread(item.message);setFeature("dating");} else if (item.type === "message")
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
        <ScrollView alwaysBounceVertical refreshControl={rc} contentContainerStyle={s.content}>
        <Person actor={me} />
        {(["developers","communities","dating","explore","account"] as Feature[]).map(name=><Button key={name} secondary title={{developers:"Developer hub",communities:"Amerika Communities",dating:"Amerika Dating",explore:"Discover & hashtags",account:"Account settings",moderation:"Moderation"}[name]} onPress={()=>showFeature(name)}/>)}
        {(me.admin||me.moderator)&&<Button secondary title="Moderation & administration" onPress={()=>showFeature("moderation")}/>}
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
          onPress={() => showFeature("developers")}
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
  if(feature&&me)return <FeatureHost feature={feature} me={me} initialThread={datingThread} onClose={()=>setFeature(null)} open={route=>{setFeature(null);open(route);}} compose={draft=>{setFeature(null);compose(draft);}} onUpdated={updated} onDeleted={()=>{setMe(null);clear();setStack([]);setFeature(null);setPlus(false);setTab('home');setFilter('everyone');}}/>;
  const title =
    route?.kind==="tag"?"#"+route.tag:route?.kind === "thread"
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
