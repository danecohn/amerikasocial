import React, { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import * as Haptics from "expo-haptics";
import { File } from "expo-file-system";
import { fetch as uploadFetch } from "expo/fetch";
import { Actor, api, ORIGIN, shortHandle } from "./api";
import { Button, Draft, Person, problem } from "./components";
import { colors, styles as s } from "./theme";
import {countGraphemes} from 'unicode-segmenter/grapheme';
export default function Composer({
  draft,
  me,
  onClose,
  onSent,
}: {
  draft: Draft;
  me: Actor;
  onClose: () => void;
  onSent: () => void;
}) {
  const [text, setText] = useState(draft.edit?.text||""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [media, setMedia] = useState<{ id: string; mime: string; alt: string }[]>(
      draft.edit?.media.map(m=>({id:m.id,mime:m.mime,alt:m.alt}))||[],
    );
  const cap = me.plus ? 833 : 300,
    count = countGraphemes(text);
  const choose = async (video: boolean) => {
    setBusy(true);
    setError("");
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: video ? ["videos"] : ["images"],
        quality: 1,
        videoMaxDuration: 60,
      });
      if (result.canceled) return;
      const asset = result.assets[0],
        file = new File(asset.uri);
      if (file.size > 250000000) throw Error("Choose a file under 250 MB.");
      const response = await uploadFetch(ORIGIN + "/api/media/upload", {
        method: "POST",
        headers: {
          Authorization: "Bearer " + api.token,
          "Content-Type":
            asset.mimeType || (video ? "video/quicktime" : "image/jpeg"),
        },
        body: file,
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.error || "Upload failed.");
      setMedia((old) => [...old, { id: data.id, mime: data.mime, alt: "" }]);
    } catch (e) {
      setError(problem(e));
    } finally {
      setBusy(false);
    }
  };
  const send = async () => {
    setBusy(true);
    setError("");
    try {
      await api.request(draft.edit?"posts/edit":"posts", {
        ...(draft.edit?{uri:draft.edit.uri}:{}),
        text,
        media,
        ...(draft.parent ? { parent: draft.parent.uri } : {}),
        ...(draft.quote ? { quote: draft.quote.uri } : {}),
        ...(draft.community?{community:draft.community}:{}),
      });
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      onSent();
    } catch (e) {
      setError(problem(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <KeyboardAvoidingView
      style={s.screen}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={s.content}
      >
        <View style={s.spread}>
          <Button title="Cancel" secondary disabled={busy} onPress={onClose} />
          <Button
            title={busy ? "Working…" : draft.edit ? "Save changes" : draft.parent ? "Reply" : "Post"}
            disabled={busy || count > cap || (!text.trim() && !media.length)}
            onPress={() => void send()}
          />
        </View>
        <Person actor={me} />
        {(draft.parent || draft.quote) && (
          <View style={[s.secondary, { padding: 14, borderRadius: 12 }]}>
            <Text style={s.muted}>
              {draft.parent ? "Replying to" : "Quoting"} @
              {shortHandle((draft.parent || draft.quote)!.author.handle)}
            </Text>
            <Text style={s.text}>{(draft.parent || draft.quote)!.text}</Text>
          </View>
        )}
        <TextInput
          accessibilityLabel="Post text"
          multiline
          autoFocus
          value={text}
          onChangeText={setText}
          placeholder="Make friends. Share a thought."
          placeholderTextColor={colors.muted}
          style={[s.input, { minHeight: 180, textAlignVertical: "top" }]}
        />
        <Text style={[s.muted, count > cap && s.error]}>
          {count} / {cap}
        </Text>
        <View style={s.row}>
          <Button
            title="Photo"
            secondary
            disabled={
              busy || !!draft.edit ||
              media.length >= 4 ||
              media.some((m) => m.mime.startsWith("video/")) ||
              (!me.plus && me.americanStatus !== "verified")
            }
            onPress={() => void choose(false)}
          />
          <Button
            title="Video"
            secondary
            disabled={busy || !!draft.edit || !!media.length || !me.plus}
            onPress={() => void choose(true)}
          />
        </View>
        <Text style={s.muted}>
          Photos: Plus or US location verified. Videos: Plus. Up to 250 MB per
          file and 60 seconds per video.
        </Text>
        {media.map((m) => (
          <View key={m.id} style={{ gap: 8 }}>
            <Text style={s.label}>
              {m.mime.startsWith("video/") ? "Video" : "Photo"} attached
            </Text>
            <TextInput
              style={s.input}
              editable={!draft.edit}
              value={m.alt}
              maxLength={2000}
              placeholder="Describe this media for accessibility"
              placeholderTextColor={colors.muted}
              onChangeText={(alt) =>
                setMedia((old) =>
                  old.map((item) =>
                    item.id === m.id ? { ...item, alt } : item,
                  ),
                )
              }
            />
            <Button
              secondary
              disabled={busy||!!draft.edit}
              title="Remove"
              onPress={() =>
                setMedia((old) => old.filter((item) => item.id !== m.id))
              }
            />
          </View>
        ))}
        {!!error && <Text style={s.error}>{error}</Text>}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
