import React, { useState } from "react";
import {
  KeyboardAvoidingView,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  Share,
  Text,
  TextInput,
  View,
} from "react-native";
import { WebView } from "react-native-webview";
import { Ionicons } from "@expo/vector-icons";
import { Actor, api, Config, ORIGIN } from "./api";
import { Button, Icon, problem } from "./components";
import { colors, styles as s } from "./theme";
import Recovery from './Recovery';
export default function Auth({
  config,
  onDone,
  onClose,
}: {
  config: Config;
  onDone: (actor: Actor) => void;
  onClose: () => void;
}) {
  const [register, setRegister] = useState(false),[recover,setRecover]=useState(false),
    [handle, setHandle] = useState(""),
    [name, setName] = useState(""),
    [password, setPassword] = useState(""),
    [confirmed, setConfirmed] = useState(false),
    [rules, setRules] = useState(false),
    [token, setToken] = useState(""),
    [attempt, setAttempt] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [codes, setCodes] = useState<string[]>([]),
    [created, setCreated] = useState<Actor>();
  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      const data = await api.request<{
        token: string;
        actor: Actor;
        recoveryCodes?: string[];
      }>(register ? "register" : "login", {
        handle,
        password,
        ...(register ? { name, kind: "human" } : {}),
        americanConfirmed: confirmed,
        rulesAccepted: rules,
        captchaToken: token,
      });
      await api.save(data.token);
      setPassword("");
      if (data.recoveryCodes?.length) {
        setCreated(data.actor);
        setCodes(data.recoveryCodes);
      } else onDone(data.actor);
    } catch (e) {
      setError(problem(e));
      setToken("");
      setAttempt((v) => v + 1);
    } finally {
      setBusy(false);
    }
  };
  if(recover)return <Recovery onBack={()=>{setRecover(false);setToken('');setAttempt(v=>v+1);}}/>;
  if (codes.length)
    return (
      <ScrollView contentContainerStyle={s.content}>
        <Text style={s.title}>Save your recovery codes</Text>
        <Text style={s.text}>
          Each code can reset your password once. We do not use email recovery.
          Store these privately.
        </Text>
        <Text selectable style={s.text}>
          {codes.join("\n")}
        </Text>
        <Button
          title="Save codes privately"
          onPress={() =>
            void Share.share({
              message: "PRIVATE AltStack recovery codes\n" + codes.join("\n"),
            })
          }
        />
        <Button title="I saved my codes" onPress={() => onDone(created!)} />
      </ScrollView>
    );
  const input = (
    label: string,
    value: string,
    change: (value: string) => void,
    secure = false,
  ) => (
    <TextInput
      accessibilityLabel={label}
      placeholder={label}
      placeholderTextColor={colors.muted}
      value={value}
      onChangeText={change}
      style={s.input}
      autoCapitalize="none"
      autoCorrect={false}
      secureTextEntry={secure}
      textContentType={
        secure ? (register ? "newPassword" : "password") : "username"
      }
    />
  );
  const check = (label: string, value: boolean, toggle: () => void) => (
    <Pressable
      style={s.row}
      accessibilityRole="checkbox"
      accessibilityState={{ checked: value }}
      onPress={toggle}
    >
      <Ionicons
        name={value ? "checkbox" : "square-outline"}
        color={colors.red}
        size={26}
      />
      <Text style={[s.text, { flex: 1 }]}>{label}</Text>
    </Pressable>
  );
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
          <Text style={s.title}>
            {register ? "Join AltStack" : "Welcome back"}
          </Text>
          <Icon name="close" label="Close sign in" onPress={onClose} />
        </View>
        <Text style={s.muted}>Why Can’t We Be Friends?</Text>
        {register && input("Display name", name, setName)}
        {input("Username", handle, setHandle)}
        {input(
          "Password (at least 10 characters)",
          password,
          setPassword,
          true,
        )}
        {check("I confirm I am American.", confirmed, () =>
          setConfirmed(!confirmed),
        )}
        {check("I agree to the Terms and Community Rules.", rules, () =>
          setRules(!rules),
        )}
        <Text style={s.muted}>
          Strictly banned: {config.rules.prohibited.join(", ")}.
        </Text>
        <View style={s.row}>
          <Button
            secondary
            title="Terms"
            onPress={() => void Linking.openURL(ORIGIN + "/terms")}
          />
          <Button
            secondary
            title="Privacy"
            onPress={() => void Linking.openURL(ORIGIN + "/privacy")}
          />
        </View>
        {config.captcha.enabled && (
          <View style={{ height: 150, borderRadius: 12, overflow: "hidden" }}>
            <WebView
              key={String(register) + attempt}
              source={{
                uri:
                  ORIGIN +
                  "/mobile-verification?action=" +
                  (register ? "human-register" : "human-login"),
              }}
              sharedCookiesEnabled
              thirdPartyCookiesEnabled
              originWhitelist={[ORIGIN, "https://challenges.cloudflare.com"]}
              onShouldStartLoadWithRequest={(request) => {
                try {
                  return [
                    new URL(ORIGIN).hostname,
                    "challenges.cloudflare.com",
                  ].includes(new URL(request.url).hostname);
                } catch {
                  return request.url === "about:blank";
                }
              }}
              onMessage={(event) => {
                try {
                  const value = JSON.parse(event.nativeEvent.data);
                  if (
                    typeof value.token === "string" &&
                    value.token.length <= 2048
                  )
                    setToken(value.token);
                  else if (value.expired) setToken("");
                  else if (value.error) setError(value.error);
                } catch {
                  setError("Verification returned an invalid response.");
                }
              }}
              onError={() =>
                setError("Human verification could not load. Please retry.")
              }
              style={{ backgroundColor: colors.card }}
            />
          </View>
        )}
        {!!error && (
          <>
            <Text style={s.error}>{error}</Text>
            <Button
              secondary
              title="Retry verification"
              onPress={() => {
                setError("");
                setToken("");
                setAttempt((v) => v + 1);
              }}
            />
          </>
        )}
        <Button
          disabled={
            busy ||
            !confirmed ||
            !rules ||
            !handle ||
            password.length < 10 ||
            (register && !name) ||
            (config.captcha.enabled && !token)
          }
          title={
            busy ? "Please wait…" : register ? "Create account" : "Sign in"
          }
          onPress={() => void submit()}
        />
        <Button
          secondary
          disabled={busy}
          title={register ? "Already a member? Sign in" : "Create an account"}
          onPress={() => {
            setRegister(!register);
            setToken("");
            setError("");
          }}
        />
        <Button
          secondary
          title="Recover with a saved code"
          onPress={() => {setToken('');setRecover(true);}}
        />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
