import React,{useState} from 'react';
import {Text} from 'react-native';
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import * as SecureStore from 'expo-secure-store';
import Constants from 'expo-constants';
import {api} from './api';
import {Button,problem} from './components';
import {Action,Status,Toggle,useResource} from './ui';
import {styles as s} from './theme';
const DEVICE_KEY='amerika.push-device';
export const storedPushDeviceId=()=>SecureStore.getItemAsync(DEVICE_KEY);
export async function unregisterThisDevice(){const id=await SecureStore.getItemAsync(DEVICE_KEY);if(id){await api.request('push/disable',{id});await SecureStore.deleteItemAsync(DEVICE_KEY);}}
export default function PushSettings(){const resource=useResource<any>('push'),[bots,setBots]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');const enable=async()=>{setBusy(true);setError('');try{if(!Device.isDevice||Constants.executionEnvironment==='storeClient')throw Error('Native push needs a real iPhone development or TestFlight build.');const projectId=Constants.easConfig?.projectId||Constants.expoConfig?.extra?.eas?.projectId;if(!projectId)throw Error('Connect this app to its Expo EAS project before enabling push.');let permission=await Notifications.getPermissionsAsync();if(permission.status!=='granted')permission=await Notifications.requestPermissionsAsync();if(permission.status!=='granted')throw Error('Allow notifications in iPhone Settings to enable push.');const token=(await Notifications.getExpoPushTokenAsync({projectId})).data;const result=await api.request<{id:string}>('push/register',{token,includeBots:bots});await SecureStore.setItemAsync(DEVICE_KEY,result.id);resource.reload();}catch(e){setError(problem(e));}finally{setBusy(false);}};return <><Status error={resource.error||error} loading={resource.loading||busy}/><Text style={s.muted}>Only generic activity alerts are sent through Expo and Apple. Private text, photo/video data, Dating details and locations are not included. Tap an alert to read it after authentication.</Text><Toggle label="Also alert me about my owned bots" value={bots} onChange={setBots}/><Button secondary title="Enable or update this iPhone" disabled={busy||!resource.data?.configured} onPress={()=>void enable()}/>{!resource.data?.configured&&<Text style={s.muted}>The server’s push service needs activation after Apple/Expo credentials are ready.</Text>}{resource.data?.devices.map((d:any)=><><Text key={d.id} style={s.muted}>{new Date(d.created).toLocaleString()} · {d.enabled?'Enabled':'Disabled'}{d.includeBots?' · Includes bots':''}</Text>{d.enabled&&<Action title="Disable device" path="push/disable" body={{id:d.id}} after={resource.reload}/>}</>)}</>;}
