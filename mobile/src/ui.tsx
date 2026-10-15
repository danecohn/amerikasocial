import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Alert, Modal, Pressable, RefreshControl, ScrollView, Switch, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Clipboard from 'expo-clipboard';
import { api } from './api';
import { Button, Icon, problem } from './components';
import { colors, styles as s } from './theme';
import { PageRefreshContext, usePageRefresh } from './refresh';
export function Field({
  label,
  value,
  onChange,
  max = 2000,
  secure = false,
  multiline = false,
  numeric = false
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  max?: number;
  secure?: boolean;
  multiline?: boolean;
  numeric?: boolean;
}) {
  return <View style={{
    gap: 6
  }}><Text style={s.label}>{label}</Text><TextInput accessibilityLabel={label} value={value} onChangeText={onChange} maxLength={max} secureTextEntry={secure} multiline={multiline} autoCapitalize="none" autoCorrect={!secure} keyboardType={numeric ? 'numeric' : 'default'} placeholderTextColor={colors.muted} style={[s.input, multiline && {
      minHeight: 90,
      textAlignVertical: 'top'
    }]} /></View>;
}
export function Toggle({
  label,
  value,
  onChange
}: {
  label: string;
  value: boolean;
  onChange: (value: boolean) => void;
}) {
  return <View style={s.spread}><Text style={[s.text, {
      flex: 1
    }]}>{label}</Text><Switch accessibilityLabel={label} value={value} onValueChange={onChange} trackColor={{
      true: colors.red,
      false: colors.border
    }} /></View>;
}
export function Select({
  label,
  value,
  options,
  onChange
}: {
  label: string;
  value: string;
  options: {
    value: string;
    label: string;
  }[];
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  return <><Text style={s.label}>{label}</Text><Button secondary title={options.find(o => o.value === value)?.label || 'Choose…'} onPress={() => setOpen(true)} /><Modal visible={open} animationType="slide" onRequestClose={() => setOpen(false)}><SafeAreaView style={s.screen}><ScrollView contentContainerStyle={s.content}><Text style={s.title}>{label}</Text><Button secondary title="Close" onPress={() => setOpen(false)} />{options.map(o => <Button key={o.value} secondary={o.value !== value} title={o.label} onPress={() => {
            onChange(o.value);
            setOpen(false);
          }} />)}</ScrollView></SafeAreaView></Modal></>;
}
export function Disclosure({
  title,
  children,
  initial = false
}: {
  title: string;
  children: React.ReactNode;
  initial?: boolean;
}) {
  const [open, setOpen] = useState(initial);
  return <View style={[s.secondary, {
    padding: 14,
    borderRadius: 12,
    gap: 12
  }]}><Pressable accessibilityRole="button" accessibilityState={{
      expanded: open
    }} onPress={() => setOpen(!open)} style={s.spread}><Text style={[s.label, {
        flex: 1
      }]}>{title}</Text><Text style={s.text}>{open ? '−' : '+'}</Text></Pressable>{open && children}</View>;
}
export function Secret({
  value,
  title = 'Copy value',
  privateValue = false
}: {
  value: string;
  title?: string;
  privateValue?: boolean;
}) {
  return <View style={{
    gap: 8
  }}>{privateValue && <Text style={s.error}>Private. Save securely; this value may be shown only once.</Text>}<Text selectable style={s.muted}>{value}</Text><Button secondary title={title} onPress={() => void Clipboard.setStringAsync(value).then(() => Alert.alert('Copied'))} /></View>;
}
export function useResource<T>(path: string | null) {
  const [data, setData] = useState<T>(),
    [error, setError] = useState(''),
    [loading, setLoading] = useState(false);
  const generation = useRef(0),
    previous = useRef<string | null | undefined>(undefined);
  const reload = useCallback(async () => {
    const g = ++generation.current;
    if (previous.current !== path) setData(undefined);
    previous.current = path;
    setError('');
    if (!path) { setLoading(false); return; }
    setLoading(true);
    await api.request<T>(path).then(result => {
      if (g === generation.current) setData(result);
    }).catch(e => {
      if (g === generation.current) setError(problem(e));
    }).finally(() => {
      if (g === generation.current) setLoading(false);
    });
  }, [path]);
  usePageRefresh(reload);
  useEffect(() => {
    void reload();
    return () => { generation.current++; };
  }, [reload]);
  return {
    data,
    error,
    loading,
    reload
  };
}
export function Status({
  error,
  loading
}: {
  error?: string;
  loading?: boolean;
}) {
  return <>{loading && <ActivityIndicator color={colors.red} />}{!!error && <Text style={s.error}>{error}</Text>}</>;
}
export type FormField = {
  key: string;
  label: string;
  type?: 'text' | 'password' | 'number' | 'textarea' | 'boolean' | 'select' | 'scopes';
  options?: string[];
  choices?: {
    value: string;
    label: string;
  }[];
  default?: any;
  max?: number;
  required?: boolean;
};
export function ApiForm({
  title,
  path,
  fields,
  extra = {},
  initial = {},
  after,
  submit = 'Save'
}: {
  title?: string;
  path: string;
  fields: FormField[];
  extra?: Record<string, any>;
  initial?: Record<string, any>;
  after?: (result: any) => void;
  submit?: string;
}) {
  const [values, setValues] = useState<Record<string, any>>(() => Object.fromEntries(fields.map(f => [f.key, initial[f.key] ?? f.default ?? (f.type === 'boolean' ? false : f.type === 'scopes' ? [] : '')]))),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [result, setResult] = useState<any>();
  const set = (key: string, value: any) => setValues(old => ({
    ...old,
    [key]: value
  }));
  const send = async () => {
    setBusy(true);
    setError('');
    try {
      const body = {
        ...extra,
        ...Object.fromEntries(fields.map(f => [f.key, f.type === 'number' ? Number(values[f.key]) : values[f.key]]))
      };
      for (const f of fields) if (f.required !== false && f.type !== 'boolean' && f.type !== 'scopes' && String(body[f.key]).trim() === '') throw Error('Complete ' + f.label + '.');
      const d = await api.request<any>(path, body);
      setResult(d);
      setValues(old => Object.fromEntries(Object.entries(old).map(([k, v]) => [k, fields.find(f => f.key === k)?.type === 'password' ? '' : v])));
      after?.(d);
    } catch (e) {
      setError(problem(e));
    } finally {
      setBusy(false);
    }
  };
  return <View style={{
    gap: 12
  }}>{title && <Text style={s.label}>{title}</Text>}{fields.map(f => f.type === 'boolean' ? <Toggle key={f.key} label={f.label} value={!!values[f.key]} onChange={v => set(f.key, v)} /> : f.type === 'select' ? <Select key={f.key} label={f.label} value={values[f.key]} options={f.choices || f.options!.map(value => ({
      value,
      label: value
    }))} onChange={v => set(f.key, v)} /> : f.type === 'scopes' ? <View key={f.key} style={{
      gap: 8
    }}><Text style={s.label}>{f.label}</Text>{f.options!.map(v => <Toggle key={v} label={v} value={values[f.key].includes(v)} onChange={yes => set(f.key, yes ? [...values[f.key], v] : values[f.key].filter((x: string) => x !== v))} />)}</View> : <Field key={f.key} label={f.label} value={String(values[f.key])} onChange={v => set(f.key, v)} max={f.max} secure={f.type === 'password'} numeric={f.type === 'number'} multiline={f.type === 'textarea'} />)}<Status error={error} /><Button disabled={busy} title={busy ? 'Please wait…' : submit} onPress={() => void send()} />{result && <View style={{
      gap: 10
    }}><Text style={s.muted}>Saved successfully.</Text>{result.token && <Secret privateValue value={result.token} />}{result.signingSecret && <Secret privateValue value={result.signingSecret} />}{result.secret && <Secret privateValue value={result.secret} />}{result.mcpUrl && <Secret title="Copy MCP link" value={result.mcpUrl} />}{result.instructions && <Secret title="Copy bot instructions" value={result.instructions} />}{result.recoveryCodes && <Secret privateValue title="Copy recovery codes" value={result.recoveryCodes.join('\n')} />}</View>}</View>;
}
export function Action({
  title,
  path,
  body,
  after,
  confirm
}: {
  title: string;
  path: string;
  body: Record<string, any>;
  after?: () => void;
  confirm?: string;
}) {
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true);
    try {
      await api.request(path, body);
      after?.();
    } catch (e) {
      Alert.alert('Could not complete action', problem(e));
    } finally {
      setBusy(false);
    }
  };
  return <Button secondary disabled={busy} title={busy ? 'Please wait…' : title} onPress={() => confirm ? Alert.alert(title, confirm, [{
    text: 'Cancel',
    style: 'cancel'
  }, {
    text: 'Confirm',
    style: 'destructive',
    onPress: () => void send()
  }]) : void send()} />;
}
export function Page({
  title,
  onClose,
  onRefresh,
  children
}: {
  title: string;
  onClose: () => void;
  onRefresh?: () => Promise<unknown>;
  children: React.ReactNode;
}) {
  const tasks = useRef(new Set<() => Promise<unknown> | unknown>()).current;
  const running = useRef(false);
  const [refreshing, setRefreshing] = useState(false);
  const refresh = async () => {
    if (running.current) return;
    running.current = true;
    setRefreshing(true);
    try { await Promise.allSettled([...tasks, ...(onRefresh ? [onRefresh] : [])].map(task => Promise.resolve().then(task))); }
    finally { running.current = false; setRefreshing(false); }
  };
  return <PageRefreshContext.Provider value={tasks}><SafeAreaView style={s.screen}><View style={[s.header, s.spread]}><Text style={[s.title, {
        fontSize: 22,
        flex: 1
      }]}>{title}</Text><Icon name="refresh" label="Refresh page" onPress={() => void refresh()} /><Icon name="close" label="Close" onPress={onClose} /></View><ScrollView testID="feature-page-scroll" alwaysBounceVertical refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={colors.red} />} keyboardShouldPersistTaps="handled" contentContainerStyle={s.content}>{children}</ScrollView></SafeAreaView></PageRefreshContext.Provider>;
}
