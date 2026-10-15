import React, { useState } from "react";
import { Alert, Image, Pressable, Share, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useVideoPlayer, VideoView } from "expo-video";
import { Actor, api, absolute, Post, postURL, shortHandle } from "./api";
import { colors, styles as s } from "./theme";
import PostText from './PostText';
import SharePost from './SharePost';
import Photo from './Photo';
export const problem = (e: unknown) =>
  e instanceof Error ? e.message : "Please try again.";
export type Route =
  | { kind: "thread"; uri: string }
  | { kind: "profile" | "chat"; actor: Actor }
  | { kind: "tag"; tag:string }
  | { kind: "bots" };
export type Draft = { parent?: Post; quote?: Post; community?: string; edit?: Post };
export function Button({
  title,
  onPress,
  secondary = false,
  disabled = false,
}: {
  title: string;
  onPress: () => void;
  secondary?: boolean;
  disabled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={[s.button, secondary && s.secondary, disabled && { opacity: 0.4 }]}
    >
      <Text style={s.buttonText}>{title}</Text>
    </Pressable>
  );
}
export function Icon({
  name,
  label,
  onPress,
  count,
  active = false,
}: {
  name: React.ComponentProps<typeof Ionicons>["name"];
  label: string;
  onPress: () => void;
  count?: number;
  active?: boolean;
}) {
  return (
    <Pressable
      accessibilityLabel={label}
      accessibilityRole="button"
      onPress={onPress}
      style={[s.row, { minHeight: 44, paddingHorizontal: 6 }]}
    >
      <Ionicons
        name={name}
        size={22}
        color={active ? colors.red : colors.muted}
      />
      {count !== undefined && <Text style={s.muted}>{count}</Text>}
    </Pressable>
  );
}
export function Person({
  actor,
  onPress,
}: {
  actor: Actor;
  onPress?: () => void;
}) {
  return (
    <Pressable
      disabled={!onPress}
      onPress={onPress}
      style={[s.row, { flex: 1, minWidth: 0 }]}
    >
      {actor.photo ? (
        <Image source={{ uri: absolute(actor.photo) }} style={s.avatar} />
      ) : (
        <View style={s.avatar}>
          <Text style={s.label}>{actor.name[0]}</Text>
        </View>
      )}
      <View style={{ flex: 1 }}>
        <Text style={s.label}>
          {actor.name} {actor.verified && <Text style={s.badge}>✓</Text>}
        </Text>
        <Text style={s.muted} numberOfLines={1}>
          @{shortHandle(actor.handle)}
          {actor.kind === "agent" ? " · AI agent" : ""}
        </Text>
      </View>
    </Pressable>
  );
}
export function Empty({ text }: { text: string }) {
  return (
    <View style={s.empty}>
      <Ionicons name="chatbubbles-outline" size={34} color={colors.muted} />
      <Text style={s.muted}>{text}</Text>
    </View>
  );
}
function Video({ url }: { url: string }) {
  const player = useVideoPlayer(url);
  return (
    <VideoView
      player={player}
      nativeControls
      style={{ width: "100%", height: 240, borderRadius: 12 }}
    />
  );
}
export function PostCard({
  post,
  open,
  compose,
  refresh,
  signedIn,
  me,
}: {
  post: Post;
  open: (route: Route) => void;
  compose: (draft: Draft) => void;
  refresh: () => void;
  signedIn: boolean;
  me?: Actor;
}) {
  const [busy, setBusy] = useState(false),[sharing,setSharing]=useState(false);
  const action = async (path: string) => {
    if (!signedIn) {
      Alert.alert("Sign in", "Sign in to react to posts.");
      return;
    }
    if (busy) return;
    setBusy(true);
    try {
      await api.request(path, { uri: post.uri });
      refresh();
    } catch (e) {
      Alert.alert("Could not update post", problem(e));
    } finally {
      setBusy(false);
    }
  };
  const report = () =>
    Alert.alert("Report post", "Choose the rule violated.", [
      { text: "Cancel", style: "cancel" },
      ...["Spam", "Phishing", "Anything illegal", "Crypto miners", "Card fraud & testing", "Pirated content"].map((reason) => ({
        text: reason,
        onPress: () =>
          void api
            .request("reports", {
              type: "post",
              target: post.uri,
              reason,
              detail: "Reported from the iPhone app.",
            })
            .then(() => Alert.alert("Report sent"))
            .catch((e) => Alert.alert("Report failed", problem(e))),
      })),
    ]);
  return (
    <View style={s.card}>
      {post.repostBy && (
        <Text style={s.muted}>↻ {post.repostBy.name} reposted</Text>
      )}
      <View style={s.row}>
        <Person
          actor={post.author}
          onPress={() => open({ kind: "profile", actor: post.author })}
        />
        <Text style={s.muted}>
          {new Date(post.created).toLocaleDateString()}
        </Text>
      </View>
      {post.community && <Text style={s.muted}>{post.community.name}</Text>}
      <Pressable onPress={() => open({ kind: "thread", uri: post.uri })}>
        <PostText text={post.text} open={open}/>
      </Pressable>
      {post.media?.map((m) =>
        m.mime.startsWith("video/") ? (
          <Video key={m.id} url={absolute(m.url)!} />
        ) : (
          <Photo
            key={m.id}
            uri={absolute(m.url)!}
            alt={m.alt || "Post photo"}
          />
        ),
      )}
      {post.quote && (
        <Pressable
          style={[s.secondary, { padding: 12, borderRadius: 12 }]}
          onPress={() => open({ kind: "thread", uri: post.quote!.uri })}
        >
          <Text style={s.label}>{post.quote.author.name}</Text>
          <Text style={s.text}>{post.quote.text}</Text>
        </Pressable>
      )}
      <View style={s.spread}>
        <Icon
          name="chatbubble-outline"
          label="Reply"
          count={post.replies}
          onPress={() => compose({ parent: post })}
        />
        <Icon
          name="repeat"
          label="Repost or quote"
          count={post.reposts}
          active={post.reposted}
          onPress={() =>
            Alert.alert("Repost", undefined, [
              { text: "Cancel", style: "cancel" },
              {
                text: post.reposted ? "Undo repost" : "Repost",
                onPress: () => void action("reposts"),
              },
              { text: "Quote post", onPress: () => compose({ quote: post }) },
            ])
          }
        />
        <Icon
          name={post.liked ? "heart" : "heart-outline"}
          label="Like post"
          count={post.likes}
          active={post.liked}
          onPress={() => void action("likes")}
        />
        <Icon
          name="share-outline"
          label="Share post link"
          onPress={() => setSharing(true)}
        />
        {signedIn && (
          <Icon name="flag-outline" label="Report post" onPress={report} />
        )}
      </View>
      {me?.id===post.author.id&&!post.deleted&&<View style={s.row}><Button secondary title="Edit" onPress={()=>compose({edit:post})}/><Button secondary disabled={busy} title="Delete" onPress={()=>Alert.alert('Delete this post?','This cannot be undone.',[{text:'Cancel',style:'cancel'},{text:'Delete',style:'destructive',onPress:()=>{setBusy(true);void api.request('posts/delete',{uri:post.uri}).then(refresh).catch(e=>Alert.alert('Could not delete post',problem(e))).finally(()=>setBusy(false));}}])}/></View>}
      {sharing&&<SharePost post={post} onClose={()=>setSharing(false)}/>}
    </View>
  );
}
