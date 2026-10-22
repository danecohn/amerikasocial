import React, { useEffect, useRef, useState } from 'react';
import { Alert, Image, Text, View } from 'react-native';
import { useVideoPlayer, VideoView } from 'expo-video';
import { Actor, api, absolute } from './api';
import { Button, problem } from './components';
import { Action, ApiForm, Disclosure, Field, FormField, Select, Status, Toggle, useResource } from './ui';
import Paged from './Paged';
import Photo from './Photo';
import { deviceLocation, upload } from './device';
import { styles as s } from './theme';
function PrivateVideo({
  media
}: {
  media: any;
}) {
  const player = useVideoPlayer(absolute(media.url)!);
  const last = useRef(0);
  useEffect(() => {
    const listener = player.addListener('statusChange', value => {
      if (value.status === 'error' && Date.now() - last.current > 60000) {
        last.current = Date.now();
        void api.request<{
          url: string;
        }>('dating/media-link?id=' + encodeURIComponent(media.id)).then(d => player.replaceAsync(absolute(d.url)!)).catch(() => {});
      }
    });
    return () => listener.remove();
  }, [player, media.id]);
  return <VideoView player={player} nativeControls style={{
    width: '100%',
    height: 240
  }} />;
}
function PrivateImage({
  photo,
  height = 220
}: {
  photo: any;
  height?: number;
}) {
  const [url, setURL] = useState(absolute(photo.url)),
    [failed, setFailed] = useState(false);
  const last = useRef(0);
  useEffect(() => {
    setURL(absolute(photo.url));
    setFailed(false);
  }, [photo.url]);
  return <>{failed && <Text style={s.muted}>Photo unavailable</Text>}<Photo uri={url!} alt="Dating photo" height={height} onError={() => {
      if (Date.now() - last.current < 60000) {
        setFailed(true);
        return;
      }
      last.current = Date.now();
      void api.request<{
        url: string;
      }>('dating/media-link?id=' + encodeURIComponent(photo.id)).then(d => setURL(absolute(d.url))).catch(() => setFailed(true));
    }} /></>;
}
export function Attachments({
  media
}: {
  media: any[];
}) {
  return <>{media.map(m => <View key={m.id}>{m.mime?.startsWith('video/') ? <PrivateVideo media={m} /> : <PrivateImage photo={m} />}</View>)}</>;
}
function Safety({
  subject,
  thread,
  after
}: {
  subject: string;
  thread?: number;
  after: () => void;
}) {
  return <Disclosure title="Safety · block and report"><Action title="Block Dating account" path="dating/block" body={{
      subject,
      blocked: true
    }} confirm="They will no longer appear in Dating or message you." after={after} /><ApiForm title="Private report" path="dating/report" extra={{
      subject,
      ...(thread ? {
        thread
      } : {})
    }} fields={[{
      key: 'reason',
      label: 'Reason',
      type: 'select',
      options: ['Harassment', 'Spam or scam', 'Non-consensual content', 'Underage account', 'Illegal content', 'Other'],
      default: 'Harassment'
    }, {
      key: 'detail',
      label: 'Report details',
      type: 'textarea',
      max: 2000,
      required: false
    }]} submit="Send private report" /></Disclosure>;
}
function Editor({
  p,
  options,
  blocked,
  reload
}: {
  p: any;
  options: Record<string, string[]>;
  blocked: any[];
  reload: () => void;
}) {
  const [photos, setPhotos] = useState<any[]>(p?.photos || []),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  const add = async () => {
    setBusy(true);
    setError('');
    controller.current = new AbortController();
    try {
      const saved = await upload('dating/upload?purpose=profile', false, controller.current.signal);
      if (saved) setPhotos(old => [...old, {
        id: saved.id,
        url: saved.preview
      }]);
    } catch (e) {
      setError(problem(e));
    } finally {
      setBusy(false);
      controller.current = null;
    }
  };
  const locate = async () => {
    setBusy(true);
    try {
      const position = await deviceLocation();
      await api.request('dating/location', position);
      reload();
    } catch (e) {
      setError(problem(e));
    } finally {
      setBusy(false);
    }
  };
  const fields: FormField[] = [{
    key: 'age',
    label: 'Age (18+)',
    type: 'number'
  }, {
    key: 'adultConfirmed',
    label: 'I am 18 or older and respect consent',
    type: 'boolean',
    default: !!p
  }, ...Object.entries(options).map(([key, values]) => ({
    key,
    label: ({
      intent: 'Here for',
      gender: 'Gender',
      sexuality: 'Sexuality',
      role: 'Dynamic / preference'
    } as any)[key],
    type: 'select' as const,
    options: values,
    default: key === 'intent' ? 'Both' : 'Prefer not to say'
  })), {
    key: 'genderDetail',
    label: 'Gender in your own words',
    max: 80,
    required: false
  }, {
    key: 'sexualityDetail',
    label: 'Sexuality in your own words',
    max: 80,
    required: false
  }, {
    key: 'bio',
    label: 'About you',
    type: 'textarea',
    max: 1500,
    required: false
  }, {
    key: 'favoriteSong',
    label: 'Favorite song',
    max: 200,
    required: false
  }, {
    key: 'perfectDay',
    label: 'My perfect day',
    type: 'textarea',
    max: 400,
    required: false
  }, {
    key: 'lookingFor',
    label: 'What I am looking for',
    type: 'textarea',
    max: 400,
    required: false
  }, {
    key: 'enabled',
    label: 'Show my profile in the Dating grid',
    type: 'boolean'
  }];
  return <><Text style={s.text}>Dating is optional, separate from your social profile, and only for humans aged 18+.</Text>{!p && <Text style={s.muted}>Save your private draft with age confirmation first, then add up to six photos and turn on grid visibility.</Text>}<Status error={error} loading={busy} />{photos.map((photo, i) => <View key={photo.id} style={{
      gap: 8
    }}><PrivateImage photo={photo} /><View style={s.row}><Button secondary disabled={busy} title="Remove photo" onPress={() => setPhotos(old => old.filter(x => x.id !== photo.id))} />{i > 0 && <Button secondary title="Move earlier" onPress={() => setPhotos(old => {
          const next = [...old];
          [next[i - 1], next[i]] = [next[i], next[i - 1]];
          return next;
        })} />}</View></View>)}<Button secondary disabled={!p || busy || photos.length >= 6} title={p ? 'Add profile photo' : 'Save draft below to add photos'} onPress={() => void add()} />{busy && <Button secondary title="Cancel upload" onPress={() => controller.current?.abort()} />}<ApiForm key={p?.updated || 'draft'} path="dating/profile" initial={p || {}} extra={{
      photos: photos.map(x => x.id)
    }} fields={fields} submit={p ? 'Save Dating profile' : 'Save private draft'} after={reload} />{p && <Disclosure title="Distance and Dating privacy"><Text style={s.muted}>Exact coordinates are never displayed. Optional distance uses approximate ranges, expires after seven days and is separate from US verification.</Text><Button secondary disabled={busy} title={p.locationEnabled ? 'Update distance location' : 'Share location for distance'} onPress={() => Alert.alert('Share approximate distance?', 'Dating members will see distance ranges, not exact coordinates.', [{
        text: 'Cancel',
        style: 'cancel'
      }, {
        text: 'Share location',
        onPress: () => void locate()
      }])} /><Action title="Turn off distance" path="dating/location" body={{
        enabled: false
      }} after={reload} /><Action title="Pause Dating profile" path="dating/pause" body={{}} after={reload} /><Action title="Delete Dating profile" path="dating/delete" body={{}} after={reload} confirm="Delete your Dating profile, uploaded media and conversations? Your social account remains." />{blocked.map(a => <Action key={a.id} title={'Unblock ' + a.name} path="dating/block" body={{
        subject: a.id,
        blocked: false
      }} after={reload} />)}</Disclosure>}</>;
}
function Chat({
  id,
  me,
  back
}: {
  id: number;
  me: Actor;
  back: () => void;
}) {
  const resource = useResource<any>('dating/thread?id=' + id),
    [text, setText] = useState(''),
    [media, setMedia] = useState<any[]>([]),
    [messages, setMessages] = useState<any[]>([]),
    [cursor, setCursor] = useState<number | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null);
  const d = resource.data,
    t = d?.conversation;
  const historyLoaded = useRef(false);
  useEffect(() => {
    if (d) {
      setMessages(old => historyLoaded.current ? [...old.filter(m => !d.messages.some((n: any) => n.id === m.id)), ...d.messages] : d.messages);
      if (!historyLoaded.current) setCursor(d.cursor);
      void api.request('dating/read', {
        id
      }).catch(() => {});
    }
  }, [d]);
  useEffect(() => {
    if (t?.status !== 'accepted') return;
    const timer = setInterval(() => resource.reload(), 10000);
    return () => clearInterval(timer);
  }, [t?.status]);
  useEffect(() => () => controller.current?.abort(), []);
  const add = async (video: boolean) => {
    setBusy(true);
    setError('');
    controller.current = new AbortController();
    try {
      const saved = await upload('dating/upload?purpose=chat&thread=' + id, video, controller.current.signal);
      if (saved) setMedia(old => [...old, saved]);
    } catch (e) {
      setError(problem(e));
    } finally {
      setBusy(false);
      controller.current = null;
    }
  };
  const send = async () => {
    setBusy(true);
    setError('');
    try {
      await api.request('dating/message', {
        id,
        text,
        media: media.map(m => m.id)
      });
      setText('');
      setMedia([]);
      resource.reload();
    } catch (e) {
      setError(problem(e));
    } finally {
      setBusy(false);
    }
  };
  const earlier = async () => {
    setBusy(true);
    try {
      const data = await api.request<any>('dating/thread?id=' + id + '&before=' + cursor);
      historyLoaded.current = true;
      setMessages(old => [...data.messages, ...old.filter(m => !data.messages.some((n: any) => n.id === m.id))]);
      setCursor(data.cursor);
    } catch (e) {
      setError(problem(e));
    } finally {
      setBusy(false);
    }
  };
  return <><Button secondary title="Back to requests and matches" onPress={back} /><Status error={resource.error || error} loading={resource.loading || busy} />{d && <><Text style={s.title}>{d.peer.name}</Text><Text style={s.muted}>{t.status === 'accepted' ? 'Matched' : 'Pending message request'} · Chat is not end-to-end encrypted</Text>{cursor !== null && <Button secondary disabled={busy} title="Earlier messages" onPress={() => void earlier()} />}{messages.map(m => <View key={m.id} style={[s.card, {
        backgroundColor: m.sender === me.id ? '#33171A' : '#161617'
      }]}><Text style={s.text}>{m.text}</Text><Attachments media={m.media || []} /><Text style={s.muted}>{new Date(m.created).toLocaleString()}{m.sender === me.id && m.seen ? ' · Seen' : ''}</Text></View>)}{t.status === 'pending' && t.sender !== me.id && <><Action title="Accept and match" path="dating/respond" body={{
          id,
          action: 'accept'
        }} after={resource.reload} /><Action title="Decline request" path="dating/respond" body={{
          id,
          action: 'decline'
        }} after={back} /></>}{t.status === 'accepted' && <><Field label="Message" value={text} onChange={setText} multiline max={4000} /><Text style={s.muted}>Up to four photos/videos, 250 MB each. iPhone HEIC/MOV supported; Dating videos up to ten minutes.</Text><View style={s.row}><Button secondary title="Add photo" disabled={busy || media.length >= 4} onPress={() => void add(false)} /><Button secondary title="Add video" disabled={busy || media.length >= 4} onPress={() => void add(true)} /></View>{busy && <Button secondary title="Cancel upload" onPress={() => controller.current?.abort()} />}{media.map(m => <View key={m.id} style={{
          gap: 8
        }}>{m.preview && <Image source={{
            uri: m.preview
          }} style={{
            width: '100%',
            height: 180
          }} />}<Text style={s.muted}>{m.mime} ready</Text><Button secondary title="Remove attachment" onPress={() => setMedia(old => old.filter(x => x.id !== m.id))} /></View>)}<Button disabled={busy || !text.trim() && !media.length} title="Send" onPress={() => void send()} /><Action title="Unmatch" path="dating/unmatch" body={{
          id
        }} after={back} confirm="End this match and prevent further Dating messages?" /></>}<Safety subject={d.peer.id} thread={id} after={back} /></>}</>;
}
const profileLabels:Record<string,string>={intent:'Here for',gender:'Gender',genderDetail:'Gender in their words',sexuality:'Sexuality',sexualityDetail:'Sexuality in their words',role:'Dynamic / preference',favoriteSong:'Favorite song',perfectDay:'My perfect day',lookingFor:'Looking for'};
export default function Dating({
  me,
  initialThread
}: {
  me: Actor;
  initialThread?: number;
}) {
  const owner = useResource<any>(me.kind === 'human' ? 'dating/me' : null),
    [view, setView] = useState(initialThread ? 'chat' : 'explore'),
    [selected, setSelected] = useState(''),
    [thread, setThread] = useState(initialThread || 0),
    [minAge, setMinAge] = useState('18'),
    [maxAge, setMaxAge] = useState('120'),
    [filters, setFilters] = useState<Record<string, string>>({}),
    [nearby, setNearby] = useState(false),
    [query, setQuery] = useState('minAge=18&maxAge=120');
  const p = owner.data?.profile,
    options = owner.data?.options;
  const detail = useResource<any>(view === 'profile' ? 'dating/profile?id=' + encodeURIComponent(selected) : null),
    inbox = useResource<any>(p && view === 'inbox' ? 'dating/inbox' : null);
  const refresh = () => {
    owner.reload();
    detail.reload();
    inbox.reload();
  };
  const toInbox = () => {
    setView('inbox');
    inbox.reload();
  };
  if (me.kind !== 'human') return <Text style={s.error}>Dating is for adult human accounts. Bots and MCP cannot use it.</Text>;
  return <><Text style={s.title}>Makk Dating</Text><Text style={s.muted}>18+ · Find a date. Make a friend. Be yourself.</Text><View style={[s.row, {
      flexWrap: 'wrap'
    }]}>{[['explore', 'Explore'], ['inbox', 'Requests & matches'], ['edit', 'My profile']].map(([key, label]) => <Button key={key} secondary={view !== key} title={label} onPress={() => {
        setView(key);
        inbox.reload();
      }} />)}</View><Status error={owner.error} loading={owner.loading} />{owner.data?.restricted ? <Text style={s.error}>Your Dating profile was removed. Contact the administrator to appeal.</Text> : owner.data && (!p || view === 'edit') ? <Editor key={p?.updated || 'new'} p={p} options={options} blocked={owner.data.blocked} reload={owner.reload} /> : p && view === 'chat' ? <Chat key={thread} id={thread} me={me} back={toInbox} /> : p && view === 'inbox' ? <><Status error={inbox.error} loading={inbox.loading} />{['pending', 'accepted'].map(status => <Disclosure key={status} initial title={status === 'accepted' ? 'Your matches' : 'Message requests'}>{inbox.data?.conversations.filter((t: any) => t.status === status).map((t: any) => <View key={t.id} style={s.card}><Text style={s.label}>{t.peer.name}</Text><Text style={s.text}>{t.last?.text || 'Attachment'}</Text><Text style={s.muted}>{t.status === 'accepted' ? 'Matched' : t.sender === me.id ? 'Sent · awaiting acceptance' : 'Received · accept to match'} · {t.unread} unread</Text><Button title="Open conversation" onPress={() => {
            setThread(t.id);
            setView('chat');
          }} /></View>)}</Disclosure>)}</> : p && view === 'profile' ? <><Button secondary title="Back to Dating grid" onPress={() => setView('explore')} /><Status error={detail.error} loading={detail.loading} />{detail.data && <><Text style={s.title}>{detail.data.profile.name}, {detail.data.profile.age}</Text>{detail.data.profile.photos.map((photo: any) => <PrivateImage key={photo.id} photo={photo} />)}<Text style={s.text}>{detail.data.profile.bio}</Text>{['intent', 'gender', 'genderDetail', 'sexuality', 'sexualityDetail', 'role', 'favoriteSong', 'perfectDay', 'lookingFor'].map(key => <Text key={key} style={s.muted}>{profileLabels[key]}: {detail.data.profile[key] || '—'}</Text>)}<Text style={s.muted}>{detail.data.profile.distance || 'Distance private'}</Text>{detail.data.conversation ? <Button title="Open request or match" onPress={() => {
          setThread(detail.data.conversation.id);
          setView('chat');
        }} /> : <ApiForm path="dating/request" extra={{
          recipient: selected
        }} fields={[{
          key: 'text',
          label: 'Your introduction',
          type: 'textarea',
          max: 2000
        }]} submit="Send message request" after={d => {
          setThread(d.id);
          setView('chat');
        }} />}<Safety subject={selected} after={toInbox} /></>}</> : p && <><Disclosure title="Filters · age, preferences and distance"><Field label="Minimum age" numeric value={minAge} onChange={setMinAge} /><Field label="Maximum age" numeric value={maxAge} onChange={setMaxAge} />{Object.entries(options as Record<string, string[]>).map(([key, values]) => <Select key={key} label={key} value={filters[key] || ''} options={['', ...values].map(value => ({
          value,
          label: value || 'Any'
        }))} onChange={value => setFilters(old => ({
          ...old,
          [key]: value
        }))} />)}<Toggle label="Sort by approximate distance" value={nearby} onChange={setNearby} /><Button title="Apply filters" onPress={() => setQuery(new URLSearchParams({
          minAge,
          maxAge,
          ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)),
          ...(nearby ? {
            nearby: '1'
          } : {})
        }).toString())} /></Disclosure>{!p.enabled && <Text style={s.muted}>Your profile is paused; turn on visibility in My profile to appear in the grid.</Text>}<Paged columns={2} path={'dating/profiles?' + query} field="profiles" render={(person: any) => <View style={[s.secondary, {
        borderRadius: 12,
        overflow: 'hidden'
      }]}><PrivateImage photo={person.photos[0]} height={180} /><View style={{
          padding: 12,
          gap: 8
        }}><Text style={s.label}>{person.name}, {person.age}</Text><Text style={s.muted}>{person.intent} · {person.distance || 'Distance private'}</Text><Button title="View profile" onPress={() => {
            setSelected(person.id);
            setView('profile');
          }} /></View></View>} /></>}</>;
}
