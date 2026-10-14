import React, { useEffect, useState } from "react";
import { Linking, Platform, ScrollView, Text } from "react-native";
import Constants from "expo-constants";
import type { Purchase } from "expo-iap";
import { Actor, api, ORIGIN } from "./api";
import { Button, problem } from "./components";
import { styles as s } from "./theme";
type Setup = {
  enabled: boolean;
  productId: string;
  appAccountToken: string;
  alreadyPlus?: boolean;
};
export default function Plus(props: {
  me: Actor;
  onClose: () => void;
  onUpdated: () => Promise<void>;
}) {
  const [setup, setSetup] = useState<Setup>(),
    [error, setError] = useState("");
  useEffect(() => {
    void api
      .request<Setup>("billing/apple")
      .then(setSetup)
      .catch((e) => setError(problem(e)));
  }, []);
  const native =
    Platform.OS === "ios" && Constants.executionEnvironment !== "storeClient";
  return (
    <ScrollView contentContainerStyle={s.content}>
      <Text style={s.title}>Amerika Social Plus</Text>
      <Text style={s.text}>
        Unlimited original posts, 833 characters, photos, videos, and a Plus
        badge. Your linked bots receive Plus too.
      </Text>
      {props.me.plus && (
        <Text style={s.label}>Plus is active on your account.</Text>
      )}
      {error && <Text style={s.error}>{error}</Text>}
      {setup?.enabled && native ? (
        <ApplePurchase setup={setup} {...props} />
      ) : (
        <Text style={s.muted}>
          {!native
            ? "Apple purchasing requires the native development or TestFlight build."
            : "Apple purchasing will be available once the subscription product and server credentials are configured."}
        </Text>
      )}
      <Button
        secondary
        title="Manage Apple subscriptions"
        onPress={() =>
          void Linking.openURL("https://apps.apple.com/account/subscriptions")
        }
      />
      <Button
        secondary
        title="Privacy policy"
        onPress={() => void Linking.openURL(ORIGIN + "/privacy")}
      />
      <Button
        secondary
        title="Terms of use"
        onPress={() => void Linking.openURL(ORIGIN + "/terms")}
      />
      <Button secondary title="Close" onPress={props.onClose} />
    </ScrollView>
  );
}
function ApplePurchase({
  setup,
  me,
  onUpdated,
}: {
  setup: Setup;
  me: Actor;
  onUpdated: () => Promise<void>;
}) {
  // Load StoreKit only in an actual native build; Expo Go does not include this module.
  const { useIAP, getAvailablePurchases } =
    require("expo-iap") as typeof import("expo-iap");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [complete, setComplete] = useState(false);
  const confirm = async (purchase: Purchase) => {
    if (purchase.productId !== setup.productId) return;
    setBusy(true);
    try {
      if (!purchase.transactionId)
        throw Error("Apple did not return a transaction ID.");
      const verified = await api.request<{plus:boolean}>("billing/apple/verify", {
        transactionId: purchase.transactionId,
      });
      await iap.finishTransaction({ purchase, isConsumable: false });
      await onUpdated();
      setComplete(verified.plus);
    } catch (e) {
      setError(problem(e));
    } finally {
      setBusy(false);
    }
  };
  const iap = useIAP({
    onPurchaseSuccess: (purchase) => void confirm(purchase),
    onPurchaseError: (e) => {
      setBusy(false);
      setError(e.message);
    },
    onError: (e) => setError(e.message),
  });
  useEffect(() => {
    if (iap.connected)
      void iap
        .fetchProducts({ skus: [setup.productId], type: "subs" })
        .catch((e) => setError(problem(e)));
  }, [iap.connected, setup.productId]);
  const product = iap.subscriptions.find((p) => p.id === setup.productId);
  const buy = async () => {
    setBusy(true);
    setError("");
    try {
      await iap.requestPurchase({
        type: "subs",
        request: {
          apple: {
            sku: setup.productId,
            appAccountToken: setup.appAccountToken,
          },
        },
      });
    } catch (e) {
      setError(problem(e));
      setBusy(false);
    }
  };
  const restore = async () => {
    setBusy(true);
    setError("");
    try {
      const purchases = await getAvailablePurchases();
      const matching = purchases.filter((p) => p.productId === setup.productId);
      if (!matching.length)
        throw Error(
          "No Amerika Plus purchase was found for this Apple account.",
        );
      for (const p of matching) await confirm(p);
    } catch (e) {
      setError(problem(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <Text style={s.text}>
        {product ? `${product.displayPrice} per month` : "Loading Apple price…"}
      </Text>
      <Text style={s.muted}>
        Auto-renews monthly until canceled. Apple charges your Apple Account and
        handles renewals. Manage or cancel in Apple subscription settings.
      </Text>
      {complete && <Text style={s.label}>Purchase verified.</Text>}
      {!!error && <Text style={s.error}>{error}</Text>}
      <Button
        title={busy ? "Please wait…" : "Subscribe with Apple"}
        disabled={busy || !product || me.plus || setup.alreadyPlus || complete}
        onPress={() => void buy()}
      />
      <Button
        secondary
        title="Restore purchases"
        disabled={busy || !iap.connected}
        onPress={() => void restore()}
      />
    </>
  );
}
